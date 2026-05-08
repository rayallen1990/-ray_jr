"""CowAgent user-to-tenant mapping for Ray_jr knowledge base.

Extracts user information from CowAgent context and maps it to a tenant_id
and Qdrant namespace for multi-tenant isolation.

Supported channels: weixin, feishu, dingtalk, web, and custom.
Handles group chats (uses group_id) and anonymous users (assigns fallback).
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_CHANNELS = frozenset({"weixin", "feishu", "dingtalk", "web"})
ANONYMOUS_USER_ID = "anonymous"
DEFAULT_CHANNEL = "unknown"
NAMESPACE_PRIVATE = "private"
NAMESPACE_PUBLIC = "public"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantInfo:
    """Resolved tenant information for a CowAgent user."""

    tenant_id: str
    channel_type: str
    user_id: str
    namespace: str
    is_group: bool = False
    is_anonymous: bool = False
    display_name: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_SAFE_ID_RE = re.compile(r"^[\w@.\-:]+$")


def _sanitize_id(raw: str) -> str:
    """Sanitize an ID value for safe namespace construction.

    Only allows alphanumeric chars, underscores, dots, hyphens, colons, and @.
    Other characters are replaced with underscores.

    Args:
        raw: Raw identifier string.

    Returns:
        Sanitized identifier string.
    """
    if not raw:
        return ""
    if _SAFE_ID_RE.match(raw):
        return raw
    return re.sub(r"[^\w@.\-:]", "_", raw)


def _normalize_channel(channel: Optional[str]) -> str:
    """Normalize channel type to a known value.

    Args:
        channel: Raw channel type string from CowAgent context.

    Returns:
        Normalized channel string (lowercase, trimmed).
    """
    if not channel or not channel.strip():
        return DEFAULT_CHANNEL
    normalized = channel.strip().lower()
    if normalized not in SUPPORTED_CHANNELS:
        logger.warning("Unrecognized channel type: %s (using as-is)", normalized)
    return normalized


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


def extract_user_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract user information from a CowAgent context dict.

    CowAgent delivers context with the following structure (simplified)::

        {
            "channel_type": "dingtalk",
            "msg": {
                "from_user_id": "user123",
                "from_user_nickname": "张三",
                "is_group": False,
                "other_user_id": "group_abc",       # present for group chats
                "actual_user_id": "real_user_xyz",   # sometimes set in groups
                ...
            },
            ...
        }

    This function normalizes the extraction so downstream code does not need
    to know the raw CowAgent shape.

    Args:
        context: CowAgent context dictionary.

    Returns:
        Dict with keys: channel_type, user_id, display_name, is_group,
        group_id (optional).

    Raises:
        ValueError: If context is None or missing required fields.
    """
    if not context:
        raise ValueError("CowAgent context cannot be None or empty")

    channel_type = _normalize_channel(context.get("channel_type"))

    msg: Any = context.get("msg")
    if msg is None:
        raise ValueError("CowAgent context missing 'msg' field")

    # Support both dict-like access and attribute access (dataclass/object)
    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    from_user_id: Optional[str] = _get(msg, "from_user_id")
    display_name: str = _get(msg, "from_user_nickname", "") or ""
    is_group: bool = bool(_get(msg, "is_group", False))
    group_id: Optional[str] = _get(msg, "other_user_id") if is_group else None
    actual_user_id: Optional[str] = _get(msg, "actual_user_id")

    # In group chats, prefer actual_user_id if available
    user_id = actual_user_id or from_user_id

    result: Dict[str, Any] = {
        "channel_type": channel_type,
        "user_id": user_id,
        "display_name": display_name,
        "is_group": is_group,
    }
    if group_id:
        result["group_id"] = group_id

    logger.debug(
        "Extracted user info: channel=%s user=%s group=%s",
        channel_type,
        user_id,
        is_group,
    )
    return result


# ---------------------------------------------------------------------------
# Tenant mapping
# ---------------------------------------------------------------------------


def generate_tenant_id(channel_type: str, user_id: str) -> str:
    """Generate a deterministic tenant_id from channel + user identity.

    The tenant_id is a stable identifier used for data isolation.  It
    combines channel and user so the same user on different channels gets
    separate tenants (by design – this avoids cross-channel data leaks).

    Args:
        channel_type: Normalized channel string (e.g. "dingtalk").
        user_id: User identifier within the channel.

    Returns:
        Tenant ID string in the format ``{channel}:{user_id}``.

    Raises:
        ValueError: If user_id is empty after sanitization.
    """
    safe_channel = _sanitize_id(channel_type) or DEFAULT_CHANNEL
    safe_user = _sanitize_id(user_id)

    if not safe_user:
        raise ValueError("Cannot generate tenant_id: user_id is empty")

    tenant_id = f"{safe_channel}:{safe_user}"
    logger.debug("Generated tenant_id: %s", tenant_id)
    return tenant_id


def generate_namespace(
    tenant_id: str, visibility: str = NAMESPACE_PRIVATE
) -> str:
    """Generate a Qdrant namespace string for tenant-isolated vector storage.

    Format: ``tenant:{channel}:{user_id}:private`` (or ``:public``).

    Args:
        tenant_id: Tenant identifier (from :func:`generate_tenant_id`).
        visibility: ``"private"`` or ``"public"``.

    Returns:
        Qdrant namespace string.

    Raises:
        ValueError: If tenant_id is empty or visibility is invalid.
    """
    if not tenant_id:
        raise ValueError("tenant_id cannot be empty")
    if visibility not in (NAMESPACE_PRIVATE, NAMESPACE_PUBLIC):
        raise ValueError(
            f"visibility must be '{NAMESPACE_PRIVATE}' or '{NAMESPACE_PUBLIC}', "
            f"got '{visibility}'"
        )

    namespace = f"tenant:{tenant_id}:{visibility}"
    logger.debug("Generated namespace: %s", namespace)
    return namespace


def generate_group_namespace(
    channel_type: str, group_id: str, visibility: str = NAMESPACE_PRIVATE
) -> str:
    """Generate a namespace for shared group knowledge.

    Group namespaces are used when a group chat has shared documents that
    all members can access.

    Format: ``tenant:{channel}:group:{group_id}:private``

    Args:
        channel_type: Normalized channel type.
        group_id: Group identifier.
        visibility: ``"private"`` or ``"public"``.

    Returns:
        Qdrant namespace string for the group.

    Raises:
        ValueError: If channel_type or group_id is empty, or visibility invalid.
    """
    if not channel_type:
        raise ValueError("channel_type cannot be empty")
    if not group_id:
        raise ValueError("group_id cannot be empty for group namespace")
    if visibility not in (NAMESPACE_PRIVATE, NAMESPACE_PUBLIC):
        raise ValueError(
            f"visibility must be '{NAMESPACE_PRIVATE}' or '{NAMESPACE_PUBLIC}', "
            f"got '{visibility}'"
        )

    safe_channel = _sanitize_id(channel_type)
    safe_group = _sanitize_id(group_id)
    namespace = f"tenant:{safe_channel}:group:{safe_group}:{visibility}"
    logger.debug("Generated group namespace: %s", namespace)
    return namespace


# ---------------------------------------------------------------------------
# Anonymous user handling
# ---------------------------------------------------------------------------


def _generate_anonymous_id(channel_type: str, session_hint: str = "") -> str:
    """Generate a stable anonymous user ID.

    Uses a hash of channel + session hint to create a repeatable ID for the
    same anonymous session, so short-lived context is still isolated.

    Args:
        channel_type: Channel the anonymous user comes from.
        session_hint: Optional session or request identifier for stability.

    Returns:
        Anonymous user ID string.
    """
    seed = f"{channel_type}:{session_hint}" if session_hint else channel_type
    short_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"{ANONYMOUS_USER_ID}_{short_hash}"


# ---------------------------------------------------------------------------
# High-level API: resolve tenant from CowAgent context
# ---------------------------------------------------------------------------


def resolve_tenant(context: Dict[str, Any]) -> TenantInfo:
    """Resolve full tenant information from a CowAgent context.

    This is the main entry point.  It extracts user info, maps to a tenant_id,
    and builds the Qdrant namespace — handling group chats, anonymous users,
    and edge cases.

    Args:
        context: CowAgent context dictionary.

    Returns:
        :class:`TenantInfo` with all resolved fields.

    Raises:
        ValueError: If context is invalid.
    """
    user_info = extract_user_from_context(context)

    channel_type: str = user_info["channel_type"]
    user_id: Optional[str] = user_info.get("user_id")
    display_name: str = user_info.get("display_name", "")
    is_group: bool = user_info.get("is_group", False)
    group_id: Optional[str] = user_info.get("group_id")

    is_anonymous = not user_id or not user_id.strip()

    if is_anonymous:
        session_hint = context.get("session_id", "")
        user_id = _generate_anonymous_id(channel_type, session_hint)
        logger.info(
            "Anonymous user detected on channel=%s, assigned id=%s",
            channel_type,
            user_id,
        )

    tenant_id = generate_tenant_id(channel_type, user_id)
    namespace = generate_namespace(tenant_id)

    extra: Dict[str, Any] = {}
    if is_group and group_id:
        extra["group_namespace"] = generate_group_namespace(
            channel_type, group_id
        )
        extra["group_id"] = group_id

    tenant_info = TenantInfo(
        tenant_id=tenant_id,
        channel_type=channel_type,
        user_id=user_id,
        namespace=namespace,
        is_group=is_group,
        is_anonymous=is_anonymous,
        display_name=display_name,
        extra=extra,
    )

    logger.info(
        "Resolved tenant: id=%s ns=%s group=%s anon=%s",
        tenant_info.tenant_id,
        tenant_info.namespace,
        tenant_info.is_group,
        tenant_info.is_anonymous,
    )
    return tenant_info
