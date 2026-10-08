"""
NEXLINK Backend - Main FastAPI Application

This is the entry point for the Python backend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database import close_db
from app.api import auth, devices, enrollment, monitoring, sessions, audit, health, network_guard, remote, platform
from app.websocket import router as websocket_router

# Configure logging
setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    settings = get_settings()
    logger.info(
        "Starting NEXLINK Backend",
        version="0.1.0",
        environment=settings.app_env,
        host=settings.host,
        port=settings.port
    )
    
    # Database schema is provisioned by the PostgreSQL migrations mounted by Docker.
    # The application does not mutate schema at startup.
    yield
    
    # Shutdown
    await close_db()
    logger.info("Shutting down NEXLINK Backend")


# Create FastAPI application
app = FastAPI(
    title="NEXLINK Backend",
    description="NEXLINK Backend API - Python/FastAPI Migration",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(enrollment.router)
app.include_router(monitoring.router)
app.include_router(sessions.router)
app.include_router(audit.router)
app.include_router(health.router)
app.include_router(network_guard.router)
app.include_router(remote.router)
app.include_router(platform.router)

# Include WebSocket router
app.include_router(websocket_router)


@app.get("/health", tags=["Health"])
async def root_health():
    """Container and load-balancer health endpoint."""
    return {"status": "healthy", "service": "nexlink-backend", "version": "0.1.0"}


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": "NEXLINK Backend",
        "version": "0.1.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
