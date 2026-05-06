"""Ray_jr Knowledge Base Platform - Main FastAPI Application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import engine, Base
from app.kb_sync import sync_knowledge_base
from app.api.v1 import api_router

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Industrial Control Knowledge Base Platform for HMI Systems",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    # Sync knowledge base from external repository
    if settings.knowledge_base_auto_sync:
        print("📚 Syncing knowledge base...")
        if sync_knowledge_base():
            print("✓ Knowledge base synced")
        else:
            print("⚠ Knowledge base sync failed (will use local data)")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    print(f"🚀 {settings.app_name} v{settings.app_version} started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    print(f"👋 {settings.app_name} shutting down")


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": settings.app_version
        }
    )


# Register API routers
app.include_router(api_router, prefix="/api/v1")

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# TODO: Register API routers
# from app.api.v1 import api_router
# app.include_router(api_router, prefix="/api/v1")
