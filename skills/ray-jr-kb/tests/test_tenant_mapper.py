"""Unit tests for tenant_mapper tool.

Covers:
- Context extraction from CowAgent context (dict and object msg)
- Tenant ID generation
- Namespace generation (private, public, group)
- Group chat scenarios
- Anonymous user handling
- Edge cases: missing fields, special characters, empty values
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from tenant_mapper import (
    TenantInfo,
    extract_user_from_context,
    generate_group_namespace,
    generate_namespace,
    generate_tenant_id,
    resolve_tenant,
    _normalize_channel,
    _sanitize_id,
    _generate_anonymous_id,
    ANONYMOUS_USER_ID,
    DEFAULT_CHANNEL,
    NAMESPACE_PRIVATE,
    NAMESPACE_PUBLIC,
)


# -----------------------------------------------------------------------
# Helpers: build CowAgent-style context dicts
# -----------------------------------------------------------------------


def _ctx(
    channel: str = "dingtalk",
    user_id: str = "user123",
    nickname: str = "张三",
    is_group: bool = False,
    group_id: str = None,
    actual_user_id: str = None,
    session_id: str = None,
):
    """Build a minimal CowAgent context dict."""
    msg = {
        "from_user_id": user_id,
        "from_user_nickname": nickname,
        "is_group": is_group,
    }
    if group_id is not None:
        msg["other_user_id"] = group_id
    if actual_user_id is not None:
        msg["actual_user_id"] = actual_user_id
    ctx = {"channel_type": channel, "msg": msg}
    if session_id is not None:
        ctx["session_id"] = session_id
    return ctx


class _MsgObject:
    """Simulates an object-style CowAgent message (attribute access)."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# -----------------------------------------------------------------------
# _sanitize_id
# -----------------------------------------------------------------------


class TestSanitizeId:
    def test_safe_string(self):
        assert _sanitize_id("user_123") == "user_123"

    def test_with_at_sign(self):
        assert _sanitize_id("user@company.com") == "user@company.com"

    def test_with_special_chars(self):
        assert _sanitize_id("user<>!#id") == "user____id"

    def test_empty_string(self):
        assert _sanitize_id("") == ""

    def test_with_colon(self):
        assert _sanitize_id("ns:value") == "ns:value"


# -----------------------------------------------------------------------
# _normalize_channel
# -----------------------------------------------------------------------


class TestNormalizeChannel:
    def test_known_channel(self):
        assert _normalize_channel("dingtalk") == "dingtalk"
        assert _normalize_channel("weixin") == "weixin"
        assert _normalize_channel("feishu") == "feishu"
        assert _normalize_channel("web") == "web"

    def test_uppercase(self):
        assert _normalize_channel("DingTalk") == "dingtalk"
        assert _normalize_channel("WEIXIN") == "weixin"

    def test_with_whitespace(self):
        assert _normalize_channel("  dingtalk  ") == "dingtalk"

    def test_none_returns_default(self):
        assert _normalize_channel(None) == DEFAULT_CHANNEL

    def test_empty_returns_default(self):
        assert _normalize_channel("") == DEFAULT_CHANNEL
        assert _normalize_channel("   ") == DEFAULT_CHANNEL

    def test_unknown_channel(self):
        # Should still accept it (with a logged warning)
        assert _normalize_channel("telegram") == "telegram"


# -----------------------------------------------------------------------
# extract_user_from_context
# -----------------------------------------------------------------------


class TestExtractUserFromContext:
    def test_basic_extraction(self):
        ctx = _ctx(channel="dingtalk", user_id="u1", nickname="Nick")
        result = extract_user_from_context(ctx)
        assert result["channel_type"] == "dingtalk"
        assert result["user_id"] == "u1"
        assert result["display_name"] == "Nick"
        assert result["is_group"] is False
        assert "group_id" not in result

    def test_group_chat(self):
        ctx = _ctx(
            channel="weixin",
            user_id="u1",
            is_group=True,
            group_id="grp_abc",
        )
        result = extract_user_from_context(ctx)
        assert result["is_group"] is True
        assert result["group_id"] == "grp_abc"

    def test_group_with_actual_user_id(self):
        ctx = _ctx(
            channel="feishu",
            user_id="bot_proxy",
            is_group=True,
            group_id="grp_xyz",
            actual_user_id="real_user_42",
        )
        result = extract_user_from_context(ctx)
        assert result["user_id"] == "real_user_42"

    def test_object_style_msg(self):
        msg = _MsgObject(
            from_user_id="obj_user",
            from_user_nickname="ObjNick",
            is_group=False,
        )
        ctx = {"channel_type": "web", "msg": msg}
        result = extract_user_from_context(ctx)
        assert result["channel_type"] == "web"
        assert result["user_id"] == "obj_user"
        assert result["display_name"] == "ObjNick"

    def test_none_context_raises(self):
        with pytest.raises(ValueError, match="cannot be None or empty"):
            extract_user_from_context(None)

    def test_empty_context_raises(self):
        with pytest.raises(ValueError, match="cannot be None or empty"):
            extract_user_from_context({})

    def test_missing_msg_raises(self):
        with pytest.raises(ValueError, match="missing 'msg'"):
            extract_user_from_context({"channel_type": "dingtalk"})

    def test_missing_channel_defaults(self):
        ctx = {"msg": {"from_user_id": "u1"}}
        result = extract_user_from_context(ctx)
        assert result["channel_type"] == DEFAULT_CHANNEL

    def test_missing_nickname_defaults_empty(self):
        ctx = _ctx(nickname=None)
        result = extract_user_from_context(ctx)
        assert result["display_name"] == ""


# -----------------------------------------------------------------------
# generate_tenant_id
# -----------------------------------------------------------------------


class TestGenerateTenantId:
    def test_basic(self):
        assert generate_tenant_id("dingtalk", "user123") == "dingtalk:user123"

    def test_different_channels_different_tenants(self):
        t1 = generate_tenant_id("dingtalk", "user123")
        t2 = generate_tenant_id("weixin", "user123")
        assert t1 != t2

    def test_sanitizes_special_chars(self):
        tid = generate_tenant_id("dingtalk", "user<bad>")
        assert "<" not in tid
        assert ">" not in tid

    def test_empty_user_raises(self):
        with pytest.raises(ValueError, match="user_id is empty"):
            generate_tenant_id("dingtalk", "")

    def test_empty_channel_uses_default(self):
        tid = generate_tenant_id("", "user123")
        assert tid == f"{DEFAULT_CHANNEL}:user123"


# -----------------------------------------------------------------------
# generate_namespace
# -----------------------------------------------------------------------


class TestGenerateNamespace:
    def test_private(self):
        ns = generate_namespace("dingtalk:user123")
        assert ns == "tenant:dingtalk:user123:private"

    def test_public(self):
        ns = generate_namespace("dingtalk:user123", visibility="public")
        assert ns == "tenant:dingtalk:user123:public"

    def test_invalid_visibility_raises(self):
        with pytest.raises(ValueError, match="visibility must be"):
            generate_namespace("dingtalk:user123", visibility="shared")

    def test_empty_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            generate_namespace("")


# -----------------------------------------------------------------------
# generate_group_namespace
# -----------------------------------------------------------------------


class TestGenerateGroupNamespace:
    def test_basic(self):
        ns = generate_group_namespace("weixin", "grp_001")
        assert ns == "tenant:weixin:group:grp_001:private"

    def test_public(self):
        ns = generate_group_namespace("weixin", "grp_001", visibility="public")
        assert ns == "tenant:weixin:group:grp_001:public"

    def test_empty_channel_raises(self):
        with pytest.raises(ValueError, match="channel_type cannot be empty"):
            generate_group_namespace("", "grp_001")

    def test_empty_group_id_raises(self):
        with pytest.raises(ValueError, match="group_id cannot be empty"):
            generate_group_namespace("weixin", "")

    def test_invalid_visibility_raises(self):
        with pytest.raises(ValueError, match="visibility must be"):
            generate_group_namespace("weixin", "grp_001", visibility="secret")


# -----------------------------------------------------------------------
# Anonymous user handling
# -----------------------------------------------------------------------


class TestAnonymousUser:
    def test_generate_anonymous_id(self):
        aid = _generate_anonymous_id("dingtalk")
        assert aid.startswith(f"{ANONYMOUS_USER_ID}_")
        assert len(aid) > len(ANONYMOUS_USER_ID) + 1

    def test_same_input_same_id(self):
        a1 = _generate_anonymous_id("dingtalk", "session_a")
        a2 = _generate_anonymous_id("dingtalk", "session_a")
        assert a1 == a2

    def test_different_session_different_id(self):
        a1 = _generate_anonymous_id("dingtalk", "session_a")
        a2 = _generate_anonymous_id("dingtalk", "session_b")
        assert a1 != a2

    def test_resolve_anonymous_user(self):
        ctx = _ctx(user_id=None)
        tenant = resolve_tenant(ctx)
        assert tenant.is_anonymous is True
        assert tenant.user_id.startswith(ANONYMOUS_USER_ID)
        assert tenant.tenant_id  # should not be empty

    def test_resolve_empty_string_user(self):
        ctx = _ctx(user_id="")
        tenant = resolve_tenant(ctx)
        assert tenant.is_anonymous is True

    def test_resolve_whitespace_user(self):
        ctx = _ctx(user_id="   ")
        tenant = resolve_tenant(ctx)
        assert tenant.is_anonymous is True


# -----------------------------------------------------------------------
# resolve_tenant (high-level integration)
# -----------------------------------------------------------------------


class TestResolveTenant:
    def test_basic_dingtalk_user(self):
        ctx = _ctx(channel="dingtalk", user_id="u_dt_001", nickname="测试用户")
        tenant = resolve_tenant(ctx)

        assert isinstance(tenant, TenantInfo)
        assert tenant.tenant_id == "dingtalk:u_dt_001"
        assert tenant.channel_type == "dingtalk"
        assert tenant.user_id == "u_dt_001"
        assert tenant.namespace == "tenant:dingtalk:u_dt_001:private"
        assert tenant.is_group is False
        assert tenant.is_anonymous is False
        assert tenant.display_name == "测试用户"

    def test_weixin_user(self):
        ctx = _ctx(channel="weixin", user_id="wx_user_42")
        tenant = resolve_tenant(ctx)
        assert tenant.tenant_id == "weixin:wx_user_42"
        assert tenant.namespace == "tenant:weixin:wx_user_42:private"

    def test_feishu_user(self):
        ctx = _ctx(channel="feishu", user_id="fs_u_99")
        tenant = resolve_tenant(ctx)
        assert tenant.tenant_id == "feishu:fs_u_99"

    def test_group_chat_includes_group_namespace(self):
        ctx = _ctx(
            channel="dingtalk",
            user_id="u_in_group",
            is_group=True,
            group_id="grp_dt_001",
        )
        tenant = resolve_tenant(ctx)
        assert tenant.is_group is True
        assert "group_namespace" in tenant.extra
        assert tenant.extra["group_namespace"] == "tenant:dingtalk:group:grp_dt_001:private"
        assert tenant.extra["group_id"] == "grp_dt_001"
        # The user's private namespace is still their own
        assert tenant.namespace == "tenant:dingtalk:u_in_group:private"

    def test_group_chat_without_group_id(self):
        ctx = _ctx(
            channel="dingtalk",
            user_id="u_lonely",
            is_group=True,
            group_id=None,
        )
        tenant = resolve_tenant(ctx)
        assert tenant.is_group is True
        assert "group_namespace" not in tenant.extra

    def test_anonymous_with_session_id(self):
        ctx = _ctx(user_id=None, session_id="sess_abc")
        ctx["session_id"] = "sess_abc"
        tenant = resolve_tenant(ctx)
        assert tenant.is_anonymous is True
        assert "sess_abc" not in tenant.user_id  # hashed, not raw

    def test_different_channels_are_isolated(self):
        ctx_dt = _ctx(channel="dingtalk", user_id="same_user")
        ctx_wx = _ctx(channel="weixin", user_id="same_user")
        t_dt = resolve_tenant(ctx_dt)
        t_wx = resolve_tenant(ctx_wx)
        assert t_dt.tenant_id != t_wx.tenant_id
        assert t_dt.namespace != t_wx.namespace

    def test_tenant_info_is_frozen(self):
        ctx = _ctx()
        tenant = resolve_tenant(ctx)
        with pytest.raises(AttributeError):
            tenant.tenant_id = "tampered"

    def test_web_channel(self):
        ctx = _ctx(channel="web", user_id="web_visitor_1")
        tenant = resolve_tenant(ctx)
        assert tenant.channel_type == "web"
        assert tenant.tenant_id == "web:web_visitor_1"

    def test_unknown_channel_still_works(self):
        ctx = _ctx(channel="telegram", user_id="tg_user")
        tenant = resolve_tenant(ctx)
        assert tenant.channel_type == "telegram"
        assert tenant.tenant_id == "telegram:tg_user"
