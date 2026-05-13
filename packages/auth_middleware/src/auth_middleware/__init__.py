"""Authentication middleware for Ray_jr knowledge base.

Provides password hashing, JWT token management, and FastAPI dependencies
for authentication and authorization.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt


# Password hashing (using bcrypt directly for Python 3.11+ compatibility)
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# JWT defaults
_DEFAULT_SECRET = "your-secret-key-change-in-production"
_DEFAULT_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 30
_REFRESH_TOKEN_EXPIRE_DAYS = 7

# Module-level config (set via configure())
_secret_key: str = _DEFAULT_SECRET
_algorithm: str = _DEFAULT_ALGORITHM
_access_expire_minutes: int = _ACCESS_TOKEN_EXPIRE_MINUTES
_refresh_expire_days: int = _REFRESH_TOKEN_EXPIRE_DAYS


def configure(
    secret_key: str,
    algorithm: str = "HS256",
    access_expire_minutes: int = 30,
    refresh_expire_days: int = 7,
) -> None:
    """Configure JWT settings. Call once at app startup."""
    global _secret_key, _algorithm, _access_expire_minutes, _refresh_expire_days
    _secret_key = secret_key
    _algorithm = algorithm
    _access_expire_minutes = access_expire_minutes
    _refresh_expire_days = refresh_expire_days


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=_access_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    return jwt.encode(to_encode, _secret_key, algorithm=_algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=_refresh_expire_days)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    return jwt.encode(to_encode, _secret_key, algorithm=_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, _secret_key, algorithms=[_algorithm])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass
class UserPayload:
    user_id: str
    tenant_id: str
    role: str
    email: str


async def get_current_user(request: Request) -> UserPayload:
    """FastAPI dependency: extract and validate user from Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(auth_header[7:])

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "user")
    email = payload.get("email", "")

    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
        )

    return UserPayload(user_id=user_id, tenant_id=tenant_id, role=role, email=email)


def require_role(roles: List[str]) -> Callable:
    """FastAPI dependency factory: require user to have one of the specified roles."""
    async def _check(user: UserPayload = Depends(get_current_user)) -> UserPayload:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorized. Required: {roles}",
            )
        return user
    return _check
