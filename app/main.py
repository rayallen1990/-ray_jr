"""Ray_jr Knowledge Base Platform - Main FastAPI Application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base

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


# TODO: Register API routers
# from app.api.v1 import api_router
# app.include_router(api_router, prefix="/api/v1")
