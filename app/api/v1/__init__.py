"""API v1 router aggregation

This module aggregates all v1 API routers into a single router
that can be included in the main FastAPI application.
"""

from fastapi import APIRouter

# Create main API router for v1
api_router = APIRouter()

# Include sub-routers here as they are created
# Example:
# from app.api.v1.endpoints import auth, documents, search
# api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
# api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# api_router.include_router(search.router, prefix="/search", tags=["search"])
