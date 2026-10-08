-- Add enrollment_tokens table for persistent enrollment state
CREATE TABLE enrollment_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR(64) NOT NULL UNIQUE,
    device_id VARCHAR(64) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_name VARCHAR(100) NOT NULL,
    used BOOLEAN NOT NULL DEFAULT false,
    cancelled BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ,
    ip_address VARCHAR(45)
);

CREATE INDEX idx_enrollment_tokens_token ON enrollment_tokens(token);
CREATE INDEX idx_enrollment_tokens_user ON enrollment_tokens(user_id);
CREATE INDEX idx_enrollment_tokens_expires ON enrollment_tokens(expires_at);
CREATE INDEX idx_enrollment_tokens_used ON enrollment_tokens(used) WHERE used = false;

-- Add device_metrics table for storing metrics history
CREATE TABLE device_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    cpu_percent REAL,
    cpu_cores INTEGER,
    memory_total_bytes BIGINT,
    memory_used_bytes BIGINT,
    memory_percent REAL,
    disk_total_bytes BIGINT,
    disk_used_bytes BIGINT,
    disk_percent REAL,
    uptime_seconds BIGINT,
    hostname VARCHAR(255),
    os_name VARCHAR(100),
    os_version VARCHAR(100),
    architecture VARCHAR(50),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_device_metrics_device ON device_metrics(device_id);
CREATE INDEX idx_device_metrics_recorded ON device_metrics(recorded_at DESC);

-- Add connection tracking table
CREATE TABLE device_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    connection_id VARCHAR(64) NOT NULL UNIQUE,
    session_token VARCHAR(255),
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disconnected_at TIMESTAMPTZ,
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
);

CREATE INDEX idx_device_connections_device ON device_connections(device_id);
CREATE INDEX idx_device_connections_status ON device_connections(status) WHERE status = 'active';
CREATE INDEX idx_device_connections_connection_id ON device_connections(connection_id);
