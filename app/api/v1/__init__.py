"""API v1 router aggregation

This module aggregates all v1 API routers into a single router
that can be included in the main FastAPI application.
"""

from fastapi import APIRouter
from app.api.v1 import chat
from app.api.v1 import documents
from app.api.v1 import skill_handler

# Create main API router for v1
api_router = APIRouter()

# Include chat router
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])

# Include documents router
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])

# Include knowledge-base skill handler (sync, status, documents)
api_router.include_router(skill_handler.router, prefix="/kb", tags=["knowledge-base"])
