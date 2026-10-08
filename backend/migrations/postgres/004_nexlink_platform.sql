-- NEXLINK Platform expansion: RMM, security center, AI approvals, support, relay.
CREATE TABLE IF NOT EXISTS device_group_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES device_groups(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(group_id, device_id)
);
CREATE INDEX IF NOT EXISTS idx_device_group_members_group ON device_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_device_group_members_device ON device_group_members(device_id);

CREATE TABLE IF NOT EXISTS device_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL DEFAULT 'warning',
    category VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    state VARCHAR(20) NOT NULL DEFAULT 'open',
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_device_alerts_device_state ON device_alerts(device_id, state);
CREATE INDEX IF NOT EXISTS idx_device_alerts_created ON device_alerts(created_at DESC);

CREATE TABLE IF NOT EXISTS device_software (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(100) NOT NULL DEFAULT '',
    publisher VARCHAR(255) NOT NULL DEFAULT '',
    install_date VARCHAR(32),
    source VARCHAR(30) NOT NULL DEFAULT 'agent',
    metadata JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(device_id, name, version)
);
CREATE INDEX IF NOT EXISTS idx_device_software_device ON device_software(device_id);

CREATE TABLE IF NOT EXISTS access_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    rules JSONB NOT NULL DEFAULT '{}',
    capabilities JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_access_policies_org ON access_policies(organization_id);

CREATE TABLE IF NOT EXISTS ai_action_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    tool_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    risk_level VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    decision_reason TEXT NOT NULL DEFAULT '',
    result JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ai_action_requests_status ON ai_action_requests(status);
CREATE INDEX IF NOT EXISTS idx_ai_action_requests_device ON ai_action_requests(device_id);

CREATE TABLE IF NOT EXISTS support_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    requester_id UUID REFERENCES users(id) ON DELETE SET NULL,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_support_requests_status ON support_requests(status);

CREATE TABLE IF NOT EXISTS relay_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    region VARCHAR(100) NOT NULL DEFAULT 'local',
    mode VARCHAR(30) NOT NULL DEFAULT 'relay',
    enabled BOOLEAN NOT NULL DEFAULT true,
    capacity INTEGER NOT NULL DEFAULT 100,
    active_sessions INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    last_heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
