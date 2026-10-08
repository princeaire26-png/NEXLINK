"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


# ============================================================================
# Authentication Schemas
# ============================================================================

class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)


class UserLogin(BaseModel):
    """User login request with optional TOTP MFA code."""
    email: EmailStr
    password: str
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=6)


class UserResponse(BaseModel):
    """User response."""
    id: UUID
    email: str
    name: str
    role: str
    email_verified: bool
    active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuthTokenResponse(BaseModel):
    """Authentication response containing user and both tokens."""
    user: UserResponse
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response returned when an access/refresh token pair is rotated."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ============================================================================
# Device Schemas
# ============================================================================

class DeviceRegister(BaseModel):
    """Device registration request."""
    name: str = Field(..., min_length=1, max_length=100)
    public_key: str = Field(..., min_length=64, max_length=64)  # Ed25519 public key hex
    os_type: str = Field(..., pattern="^(windows|linux|macos)$")
    os_version: Optional[str] = Field("", max_length=50)
    agent_version: Optional[str] = Field("0.1.0", max_length=20)


class DeviceResponse(BaseModel):
    """Device response."""
    id: UUID
    device_id: str
    name: str
    status: str
    os_type: str
    os_version: Optional[str]
    agent_version: Optional[str]
    public_key: str
    approved: bool
    last_seen_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """Device list response."""
    devices: list[DeviceResponse]
    total: int


# ============================================================================
# Enrollment Schemas
# ============================================================================

class CreateEnrollmentRequest(BaseModel):
    """Create enrollment token request."""
    device_name: str = Field(..., min_length=1, max_length=100)


class CreateEnrollmentResponse(BaseModel):
    """Create enrollment token response."""
    enrollment_token: str
    device_id: str
    expires_at: datetime


class EnrollDeviceRequest(BaseModel):
    """Enroll device request."""
    enrollment_token: str = Field(..., min_length=64, max_length=64)
    device_id: str = Field(..., min_length=32, max_length=64)
    public_key: str = Field(..., min_length=64, max_length=64)
    signature: str = Field(..., min_length=128, max_length=128)
    os_type: str = Field(..., pattern="^(windows|linux|macos)$")
    os_version: Optional[str] = Field("", max_length=50)
    agent_version: Optional[str] = Field("0.1.0", max_length=20)
    timestamp: int
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        """Validate timestamp is recent (within 5 minutes)."""
        import time
        current_time = int(time.time())
        if abs(current_time - v) > 300:  # 5 minutes
            raise ValueError('Timestamp must be within 5 minutes of current time')
        return v


class EnrollDeviceResponse(BaseModel):
    """Enroll device response."""
    device_id: UUID
    device_identity: str
    status: str
    message: str


class EnrollmentStatusResponse(BaseModel):
    """Enrollment status response."""
    valid: bool
    used: bool
    cancelled: bool
    expired: bool
    expires_at: datetime


# ============================================================================
# Monitoring Schemas
# ============================================================================

class MemoryMetrics(BaseModel):
    """Memory metrics."""
    total: Optional[int]
    used: Optional[int]
    percent: Optional[float]


class DiskMetrics(BaseModel):
    """Disk metrics."""
    total: Optional[int]
    used: Optional[int]
    percent: Optional[float]


class DeviceMetricsResponse(BaseModel):
    """Device metrics response."""
    cpu: Optional[float]
    cpu_cores: Optional[int]
    memory: MemoryMetrics
    disk: DiskMetrics
    uptime: Optional[int]
    hostname: Optional[str]
    os_name: Optional[str]
    os_version: Optional[str]
    architecture: Optional[str]
    recorded_at: Optional[datetime]


class DeviceMetricsFullResponse(BaseModel):
    """Full device metrics response."""
    device_id: UUID
    device_identity: str
    name: str
    status: str
    last_seen_at: Optional[datetime]
    last_metrics_at: Optional[datetime]
    metrics: Optional[DeviceMetricsResponse]


class DeviceStatusResponse(BaseModel):
    """Device status response."""
    device_id: UUID
    device_identity: str
    name: str
    status: str
    approved: bool
    is_online: bool
    last_seen_at: Optional[datetime]
    os_type: str
    os_version: Optional[str]
    agent_version: Optional[str]


class MonitoringSummaryResponse(BaseModel):
    """Monitoring summary response."""
    total_devices: int
    online_devices: int
    offline_devices: int
    pending_devices: int
    revoked_devices: int




# ============================================================================
# Network Guard Schemas
# ============================================================================

class NetworkGuardRequest(BaseModel):
    """Explicit, allow-listed network guard action for a managed Windows device."""
    action: str = Field(..., pattern=r"^(block_all|unblock_all|block_domains|status)$")
    domains: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, values):
        cleaned = []
        for value in values:
            domain = value.strip().lower().rstrip(".")
            if not domain or len(domain) > 253 or any(c in domain for c in "/\\: "):
                raise ValueError("Invalid domain")
            cleaned.append(domain)
        return list(dict.fromkeys(cleaned))


# ============================================================================
# Session Schemas
# ============================================================================

class StartSessionRequest(BaseModel):
    """Start session request."""
    device_id: UUID
    type: str = Field(..., pattern="^(remote_desktop|terminal|file_transfer|ai_assistant)$")


class SessionResponse(BaseModel):
    """Session response."""
    id: UUID
    type: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration: Optional[int]
    device_id: UUID
    device_name: Optional[str]
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Session list response."""
    sessions: list[SessionResponse]
    total: int


# ============================================================================
# Audit Schemas
# ============================================================================

class AuditEventResponse(BaseModel):
    """Audit event response."""
    id: UUID
    event_type: str
    actor_id: Optional[UUID]
    actor_type: str
    target_type: Optional[str]
    target_id: Optional[UUID]
    action: str
    result: str
    details: dict
    ip_address: Optional[str]
    session_id: Optional[UUID]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    """Audit list response."""
    events: list[AuditEventResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Health Schemas
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    ready: bool
    database: str
    timestamp: datetime


# ============================================================================
# Remote Desktop Schemas
# ============================================================================

class CreateRemoteSessionRequest(BaseModel):
    """Create remote session request."""
    device_id: UUID


class RemoteSessionResponse(BaseModel):
    """Remote session response."""
    session_id: UUID
    device_id: UUID
    state: str


class RemoteSessionMetrics(BaseModel):
    """Remote session metrics."""
    frames_sent: int
    bytes_sent: int
    dropped_frames: int


class RemoteSessionDetail(BaseModel):
    """Remote session detail response."""
    id: UUID
    device_id: UUID
    state: str
    created_at: datetime
    last_activity: datetime
    metrics: RemoteSessionMetrics
