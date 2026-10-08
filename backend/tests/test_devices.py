"""Tests for device management API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.database import get_db, engine, Base
from app.models import User, Device
from app.security import get_password_hash, create_access_token
import uuid


@pytest.fixture
async def db_session():
    """Create a fresh database session for testing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client(db_session):
    """Create test client with database override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        name="Test User",
        role="owner",
        active=True
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers."""
    token = create_access_token(data={"sub": str(test_user.id), "email": test_user.email, "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}


class TestDeviceRegistration:
    """Test device registration."""
    
    @pytest.mark.asyncio
    async def test_register_device_success(self, client, auth_headers):
        """Test successful device registration."""
        response = client.post(
            "/api/v1/devices",
            json={
                "name": "Test Device",
                "public_key": "a" * 64,
                "os_type": "windows",
                "os_version": "10.0.19041",
                "agent_version": "0.1.0"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Device"
        assert data["os_type"] == "windows"
        assert data["status"] == "offline"
        assert data["approved"] is False
    
    @pytest.mark.asyncio
    async def test_register_device_unauthenticated(self, client):
        """Test device registration without authentication."""
        response = client.post(
            "/api/v1/devices",
            json={
                "name": "Test Device",
                "public_key": "a" * 64,
                "os_type": "windows"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_register_device_invalid_os(self, client, auth_headers):
        """Test device registration with invalid OS type."""
        response = client.post(
            "/api/v1/devices",
            json={
                "name": "Test Device",
                "public_key": "a" * 64,
                "os_type": "invalid"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422


class TestDeviceListing:
    """Test device listing."""
    
    @pytest.mark.asyncio
    async def test_list_devices_empty(self, client, auth_headers):
        """Test listing devices when none exist."""
        response = client.get("/api/v1/devices", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["devices"] == []
        assert data["total"] == 0
    
    @pytest.mark.asyncio
    async def test_list_devices_with_devices(self, client, auth_headers, db_session, test_user):
        """Test listing devices when some exist."""
        # Create devices
        device1 = Device(
            id=uuid.uuid4(),
            device_id="device1",
            owner_id=test_user.id,
            name="Device 1",
            public_key="a" * 64,
            os_type="windows",
            status="online"
        )
        device2 = Device(
            id=uuid.uuid4(),
            device_id="device2",
            owner_id=test_user.id,
            name="Device 2",
            public_key="b" * 64,
            os_type="linux",
            status="offline"
        )
        db_session.add(device1)
        db_session.add(device2)
        await db_session.commit()
        
        response = client.get("/api/v1/devices", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 2
        assert data["total"] == 2


class TestDeviceApproval:
    """Test device approval."""
    
    @pytest.mark.asyncio
    async def test_approve_device_success(self, client, auth_headers, db_session, test_user):
        """Test successful device approval."""
        device = Device(
            id=uuid.uuid4(),
            device_id="device1",
            owner_id=test_user.id,
            name="Test Device",
            public_key="a" * 64,
            os_type="windows",
            approved=False
        )
        db_session.add(device)
        await db_session.commit()
        
        response = client.patch(
            f"/api/v1/devices/{device.id}/approve",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["approved"] is True
    
    @pytest.mark.asyncio
    async def test_approve_device_not_found(self, client, auth_headers):
        """Test approving non-existent device."""
        response = client.patch(
            f"/api/v1/devices/{uuid.uuid4()}/approve",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestDeviceRevocation:
    """Test device revocation."""
    
    @pytest.mark.asyncio
    async def test_revoke_device_success(self, client, auth_headers, db_session, test_user):
        """Test successful device revocation."""
        device = Device(
            id=uuid.uuid4(),
            device_id="device1",
            owner_id=test_user.id,
            name="Test Device",
            public_key="a" * 64,
            os_type="windows",
            approved=True,
            status="online"
        )
        db_session.add(device)
        await db_session.commit()
        
        response = client.patch(
            f"/api/v1/devices/{device.id}/revoke",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["revoked"] is True
    
    @pytest.mark.asyncio
    async def test_revoke_device_not_found(self, client, auth_headers):
        """Test revoking non-existent device."""
        response = client.patch(
            f"/api/v1/devices/{uuid.uuid4()}/revoke",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestDeviceDeletion:
    """Test device deletion."""
    
    @pytest.mark.asyncio
    async def test_delete_device_success(self, client, auth_headers, db_session, test_user):
        """Test successful device deletion."""
        device = Device(
            id=uuid.uuid4(),
            device_id="device1",
            owner_id=test_user.id,
            name="Test Device",
            public_key="a" * 64,
            os_type="windows"
        )
        db_session.add(device)
        await db_session.commit()
        
        response = client.delete(
            f"/api/v1/devices/{device.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
    
    @pytest.mark.asyncio
    async def test_delete_device_not_found(self, client, auth_headers):
        """Test deleting non-existent device."""
        response = client.delete(
            f"/api/v1/devices/{uuid.uuid4()}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
