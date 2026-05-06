"""Dependency injection functions for FastAPI routes"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.config import settings
from app.database import get_db

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Validate JWT token and return current user.

    This is a placeholder implementation. In production, you would:
    1. Decode the JWT token
    2. Query the user from the database
    3. Return the user object
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # TODO: Query user from database using user_id
        # For now, return a mock user object
        return {"id": user_id, "username": payload.get("username")}

    except JWTError:
        raise credentials_exception


async def get_current_tenant(
    current_user: dict = Depends(get_current_user)
) -> str:
    """
    Extract tenant ID from current user.

    This is used for multi-tenant isolation.
    """
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any tenant"
        )
    return tenant_id


async def require_admin(
    current_user: dict = Depends(get_current_user)
):
    """
    Require admin role for the current user.
    """
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
