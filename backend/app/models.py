"""SQLAlchemy models for NEXLINK database."""

from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class User(Base):
    """User accounts."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="owner")  # owner, admin, member, viewer
    email_verified = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret = Column(Text, nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Organization(Base):
    """Organizations/tenants."""
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    plan = Column(String(50), nullable=False, default="personal")
    settings = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    members = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="organization")


class Membership(Base):
    """User-organization memberships."""
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint('user_id', 'organization_id', name='uq_memberships_user_org'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="member")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="members")


class Device(Base):
    """Managed devices."""
    __tablename__ = "devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(64), nullable=False, unique=True, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id'), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    public_key = Column(Text, nullable=False)
    os_type = Column(String(20), nullable=False)
    os_version = Column(String(50), nullable=False, default="")
    agent_version = Column(String(20), nullable=False, default="0.1.0")
    status = Column(String(20), nullable=False, default="offline", index=True)  # online, offline, revoked, pending
    approved = Column(Boolean, nullable=False, default=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_metrics_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="devices")
    organization = relationship("Organization", back_populates="devices")
    identities = relationship("DeviceIdentity", back_populates="device", cascade="all, delete-orphan")
    metrics = relationship("DeviceMetric", back_populates="device", cascade="all, delete-orphan")
    connections = relationship("DeviceConnection", back_populates="device", cascade="all, delete-orphan")


class DeviceIdentity(Base):
    """Device cryptographic identities."""
    __tablename__ = "device_identities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id', ondelete='CASCADE'), nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    key_type = Column(String(20), nullable=False, default="ed25519")
    active = Column(Boolean, nullable=False, default=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="identities")


class DeviceGroup(Base):
    """Logical device groupings."""
    __tablename__ = "device_groups"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Session(Base):
    """User authentication sessions."""
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = Column(Text, nullable=False)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class ConnectionSession(Base):
    """Remote connection sessions."""
    __tablename__ = "connection_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id'), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # remote_desktop, terminal, file_transfer, ai_assistant
    status = Column(String(20), nullable=False, default="active")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)


class AuditEvent(Base):
    """Security audit trail."""
    __tablename__ = "audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_type = Column(String(20), nullable=False)  # user, device, system
    target_type = Column(String(50), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    action = Column(String(50), nullable=False)
    result = Column(String(20), nullable=False)  # success, failure
    details = Column(JSONB, nullable=False, default=dict)
    ip_address = Column(String(45), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class Automation(Base):
    """Automation workflow definitions."""
    __tablename__ = "automations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    trigger_config = Column(JSONB, nullable=False)
    actions = Column(JSONB, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AutomationRun(Base):
    """Automation execution history."""
    __tablename__ = "automation_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    automation_id = Column(UUID(as_uuid=True), ForeignKey('automations.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSONB, nullable=False, default=dict)
    error = Column(Text, nullable=True)


class EnrollmentToken(Base):
    """Device enrollment tokens."""
    __tablename__ = "enrollment_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(64), nullable=False, unique=True, index=True)
    device_id = Column(String(64), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    device_name = Column(String(100), nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    cancelled = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)


class DeviceMetric(Base):
    """Device metrics history."""
    __tablename__ = "device_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id', ondelete='CASCADE'), nullable=False, index=True)
    cpu_percent = Column(Float, nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    memory_total_bytes = Column(Integer, nullable=True)
    memory_used_bytes = Column(Integer, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_total_bytes = Column(Integer, nullable=True)
    disk_used_bytes = Column(Integer, nullable=True)
    disk_percent = Column(Float, nullable=True)
    uptime_seconds = Column(Integer, nullable=True)
    hostname = Column(String(255), nullable=True)
    os_name = Column(String(100), nullable=True)
    os_version = Column(String(100), nullable=True)
    architecture = Column(String(50), nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    
    # Relationships
    device = relationship("Device", back_populates="metrics")


class DeviceConnection(Base):
    """Active device WebSocket connections."""
    __tablename__ = "device_connections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey('devices.id', ondelete='CASCADE'), nullable=False, index=True)
    connection_id = Column(String(64), nullable=False, unique=True, index=True)
    session_token = Column(String(255), nullable=True)
    connected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    
    # Relationships
    device = relationship("Device", back_populates="connections")

class DeviceGroupMember(Base):
    """Many-to-many membership between devices and logical groups."""
    __tablename__ = "device_group_members"
    __table_args__ = (UniqueConstraint("group_id", "device_id", name="uq_device_group_member"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("device_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DeviceAlert(Base):
    """RMM health/security alert generated from real device telemetry."""
    __tablename__ = "device_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="warning", index=True)
    category = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    state = Column(String(20), nullable=False, default="open", index=True)
    details = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class DeviceSoftware(Base):
    """Software inventory reported by a managed endpoint."""
    __tablename__ = "device_software"
    __table_args__ = (UniqueConstraint("device_id", "name", "version", name="uq_device_software"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    version = Column(String(100), nullable=False, default="")
    publisher = Column(String(255), nullable=False, default="")
    install_date = Column(String(32), nullable=True)
    source = Column(String(30), nullable=False, default="agent")
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AccessPolicy(Base):
    """Conditional-access policy for remote operations."""
    __tablename__ = "access_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    rules = Column(JSONB, nullable=False, default=dict)
    capabilities = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AIActionRequest(Base):
    """AI plan/action requiring policy evaluation and optional human approval."""
    __tablename__ = "ai_action_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    parameters = Column(JSONB, nullable=False, default=dict)
    risk_level = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="pending", index=True)
    decision_reason = Column(Text, nullable=False, default="")
    result = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)


class SupportRequest(Base):
    """User/endpoint support ticket that can be converted into a remote session."""
    __tablename__ = "support_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    priority = Column(String(20), nullable=False, default="normal")
    status = Column(String(20), nullable=False, default="open", index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RelayNode(Base):
    """Registered NEXLINK relay/signaling node metadata."""
    __tablename__ = "relay_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    endpoint = Column(String(500), nullable=False)
    region = Column(String(100), nullable=False, default="local")
    mode = Column(String(30), nullable=False, default="relay")
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    capacity = Column(Integer, nullable=False, default=100)
    active_sessions = Column(Integer, nullable=False, default=0)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
