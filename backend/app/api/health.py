"""Health check API routes."""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.schemas import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check."""
    return HealthResponse(
        status="healthy",
        service="nexlink-backend",
        version="0.1.0",
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check with database connectivity."""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        database_status = "connected"
        ready = True
    except Exception as e:
        database_status = "disconnected"
        ready = False
    
    if not ready:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ready": False,
                "database": database_status,
                "error": "Database connection failed",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    return ReadinessResponse(
        ready=ready,
        database=database_status,
        timestamp=datetime.utcnow(),
    )
