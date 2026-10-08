"""Monitoring API routes."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models import Device, DeviceMetric, User
from app.schemas import (
    DeviceMetricsFullResponse,
    DeviceStatusResponse,
    MonitoringSummaryResponse,
    DeviceMetricsResponse,
    MemoryMetrics,
    DiskMetrics,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])


@router.get("/devices/{device_id}/metrics", response_model=DeviceMetricsFullResponse)
async def get_device_metrics(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get latest metrics for a device."""
    # Verify device ownership
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    # Get latest metrics
    result = await db.execute(
        select(DeviceMetric)
        .where(DeviceMetric.device_id == device_id)
        .order_by(desc(DeviceMetric.recorded_at))
        .limit(1)
    )
    metric = result.scalar_one_or_none()
    
    metrics_response = None
    if metric:
        metrics_response = DeviceMetricsResponse(
            cpu=metric.cpu_percent,
            cpu_cores=metric.cpu_cores,
            memory=MemoryMetrics(
                total=metric.memory_total_bytes,
                used=metric.memory_used_bytes,
                percent=metric.memory_percent,
            ),
            disk=DiskMetrics(
                total=metric.disk_total_bytes,
                used=metric.disk_used_bytes,
                percent=metric.disk_percent,
            ),
            uptime=metric.uptime_seconds,
            hostname=metric.hostname,
            os_name=metric.os_name,
            os_version=metric.os_version,
            architecture=metric.architecture,
            recorded_at=metric.recorded_at,
        )
    
    return DeviceMetricsFullResponse(
        device_id=device.id,
        device_identity=device.device_id,
        name=device.name,
        status=device.status,
        last_seen_at=device.last_seen_at,
        last_metrics_at=device.last_metrics_at,
        metrics=metrics_response,
    )


@router.get("/devices/{device_id}/status", response_model=DeviceStatusResponse)
async def get_device_status(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get real-time device status."""
    result = await db.execute(
        select(Device).where(
            Device.id == device_id,
            Device.owner_id == current_user.id
        )
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "DEVICE_NOT_FOUND"}
        )
    
    # Calculate if device is actually online (seen within last 60 seconds)
    is_online = False
    if device.status == "online" and device.last_seen_at:
        time_diff = datetime.utcnow() - device.last_seen_at
        is_online = time_diff.total_seconds() < 60
    
    return DeviceStatusResponse(
        device_id=device.id,
        device_identity=device.device_id,
        name=device.name,
        status=device.status,
        approved=device.approved,
        is_online=is_online,
        last_seen_at=device.last_seen_at,
        os_type=device.os_type,
        os_version=device.os_version,
        agent_version=device.agent_version,
    )


@router.get("/summary", response_model=MonitoringSummaryResponse)
async def get_monitoring_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get monitoring summary for all user devices."""
    result = await db.execute(
        select(Device).where(Device.owner_id == current_user.id)
    )
    devices = result.scalars().all()
    
    now = datetime.utcnow()
    online_count = 0
    offline_count = 0
    pending_count = 0
    revoked_count = 0
    
    for device in devices:
        if device.status == "revoked":
            revoked_count += 1
        elif not device.approved:
            pending_count += 1
        elif device.status == "online" and device.last_seen_at:
            time_diff = now - device.last_seen_at
            if time_diff.total_seconds() < 60:
                online_count += 1
            else:
                offline_count += 1
        else:
            offline_count += 1
    
    return MonitoringSummaryResponse(
        total_devices=len(devices),
        online_devices=online_count,
        offline_devices=offline_count,
        pending_devices=pending_count,
        revoked_devices=revoked_count,
    )
