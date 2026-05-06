"""Multi-tenant isolation middleware for FastAPI"""

from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt


class TenantContext:
    """Holds tenant context for the current request"""
    def __init__(self, tenant_id: str, user_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant_id from JWT and attaches it to request.state.
    Skips public endpoints (health check, docs, openapi).
    """

    PUBLIC_PATHS = {"/", "/health", "/api/docs", "/api/redoc", "/api/openapi.json"}

    def __init__(self, app, secret_key: str, algorithm: str = "HS256"):
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
            )

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        tenant_id: Optional[str] = payload.get("tenant_id")
        user_id: Optional[str] = payload.get("sub")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token missing tenant_id claim",
            )

        request.state.tenant = TenantContext(tenant_id=tenant_id, user_id=user_id)
        return await call_next(request)


def get_tenant_namespace(tenant_id: str, visibility: str = "private") -> str:
    """Return Qdrant namespace for a tenant: tenant:<id>:private|public"""
    return f"tenant:{tenant_id}:{visibility}"
