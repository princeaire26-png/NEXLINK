"""Audit log API routes."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models import AuditEvent, User
from app.schemas import AuditEventResponse, AuditListResponse
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


@router.get("/", response_model=AuditListResponse)
async def list_audit_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List audit events for the user's organization."""
    query = select(AuditEvent)
    
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    
    query = query.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return AuditListResponse(
        events=[AuditEventResponse.model_validate(e) for e in events],
        total=len(events),
        limit=limit,
        offset=offset,
    )


@router.get("/{event_id}", response_model=AuditEventResponse)
async def get_audit_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific audit event."""
    result = await db.execute(
        select(AuditEvent).where(AuditEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND"}
        )
    
    return AuditEventResponse.model_validate(event)
