"""Tests for device enrollment API."""

import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from nacl.signing import SigningKey
from app.main import app
from app.database import get_db, engine, Base
from app.models import User, EnrollmentToken
from app.security import get_password_hash, create_access_token
from datetime import datetime, timedelta
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


class TestEnrollmentCreation:
    """Test enrollment token creation."""
    
    @pytest.mark.asyncio
    async def test_create_enrollment_success(self, client, auth_headers):
        """Test successful enrollment token creation."""
        response = client.post(
            "/api/v1/enrollment/create",
            json={"device_name": "Test Device"},
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "enrollment_token" in data
        assert "device_id" in data
        assert "expires_at" in data
        assert len(data["enrollment_token"]) == 64  # 32 bytes hex
        assert len(data["device_id"]) == 32  # 16 bytes hex
    
    @pytest.mark.asyncio
    async def test_create_enrollment_unauthenticated(self, client):
        """Test enrollment creation without authentication."""
        response = client.post(
            "/api/v1/enrollment/create",
            json={"device_name": "Test Device"}
        )
        
        assert response.status_code == 401


class TestEnrollmentStatus:
    """Test enrollment status checking."""
    
    @pytest.mark.asyncio
    async def test_get_enrollment_status_valid(self, client, db_session, test_user):
        """Test getting status of valid enrollment token."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        response = client.get(f"/api/v1/enrollment/status/{token}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["used"] is False
        assert data["cancelled"] is False
        assert data["expired"] is False
    
    @pytest.mark.asyncio
    async def test_get_enrollment_status_expired(self, client, db_session, test_user):
        """Test getting status of expired enrollment token."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() - timedelta(minutes=1)  # Expired
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        response = client.get(f"/api/v1/enrollment/status/{token}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["expired"] is True
    
    @pytest.mark.asyncio
    async def test_get_enrollment_status_used(self, client, db_session, test_user):
        """Test getting status of used enrollment token."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=True,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        response = client.get(f"/api/v1/enrollment/status/{token}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["used"] is True
    
    @pytest.mark.asyncio
    async def test_get_enrollment_status_not_found(self, client):
        """Test getting status of non-existent enrollment token."""
        response = client.get("/api/v1/enrollment/status/nonexistent")
        
        assert response.status_code == 404


class TestDeviceEnrollment:
    """Test device enrollment with Ed25519 signatures."""
    
    @pytest.fixture
    def test_keypair(self):
        """Generate a test keypair for signing."""
        seed = b'\x00' * 32
        signing_key = SigningKey(seed)
        verify_key = signing_key.verify_key
        return {
            'signing_key': signing_key,
            'public_key_hex': verify_key.encode().hex(),
        }
    
    @pytest.mark.asyncio
    async def test_enroll_device_success(self, client, db_session, test_user, test_keypair):
        """Test successful device enrollment."""
        # Create enrollment token
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        # Sign enrollment proof
        timestamp = int(time.time())
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        # Enroll device
        response = client.post(
            "/api/v1/enrollment/enroll",
            json={
                "enrollment_token": token,
                "device_id": device_id,
                "public_key": test_keypair['public_key_hex'],
                "signature": signature_hex,
                "os_type": "windows",
                "os_version": "10.0.19041",
                "agent_version": "0.1.0",
                "timestamp": timestamp
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert "Device enrolled successfully" in data["message"]
    
    @pytest.mark.asyncio
    async def test_enroll_device_invalid_token(self, client, test_keypair):
        """Test enrollment with invalid token."""
        timestamp = int(time.time())
        device_id = "b" * 32
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        response = client.post(
            "/api/v1/enrollment/enroll",
            json={
                "enrollment_token": "invalid" * 8,
                "device_id": device_id,
                "public_key": test_keypair['public_key_hex'],
                "signature": signature_hex,
                "os_type": "windows",
                "timestamp": timestamp
            }
        )
        
        assert response.status_code == 400
        assert "Invalid enrollment token" in str(response.json())
    
    @pytest.mark.asyncio
    async def test_enroll_device_expired_token(self, client, db_session, test_user, test_keypair):
        """Test enrollment with expired token."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() - timedelta(minutes=1)  # Expired
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        timestamp = int(time.time())
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        response = client.post(
            "/api/v1/enrollment/enroll",
            json={
                "enrollment_token": token,
                "device_id": device_id,
                "public_key": test_keypair['public_key_hex'],
                "signature": signature_hex,
                "os_type": "windows",
                "timestamp": timestamp
            }
        )
        
        assert response.status_code == 400
        assert "expired" in str(response.json()).lower()
    
    @pytest.mark.asyncio
    async def test_enroll_device_invalid_signature(self, client, db_session, test_user):
        """Test enrollment with invalid signature."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        timestamp = int(time.time())
        
        response = client.post(
            "/api/v1/enrollment/enroll",
            json={
                "enrollment_token": token,
                "device_id": device_id,
                "public_key": "c" * 64,
                "signature": "d" * 128,  # Invalid signature
                "os_type": "windows",
                "timestamp": timestamp
            }
        )
        
        assert response.status_code == 400
        assert "Invalid cryptographic signature" in str(response.json())
    
    @pytest.mark.asyncio
    async def test_enroll_device_wrong_device_id(self, client, db_session, test_user, test_keypair):
        """Test enrollment with wrong device ID."""
        token = "a" * 64
        correct_device_id = "b" * 32
        wrong_device_id = "c" * 32
        
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=correct_device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        # Sign with wrong device ID
        timestamp = int(time.time())
        message = f"{wrong_device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        response = client.post(
            "/api/v1/enrollment/enroll",
            json={
                "enrollment_token": token,
                "device_id": wrong_device_id,  # Wrong device ID
                "public_key": test_keypair['public_key_hex'],
                "signature": signature_hex,
                "os_type": "windows",
                "timestamp": timestamp
            }
        )
        
        assert response.status_code == 400
        assert "Device ID mismatch" in str(response.json())
    
    @pytest.mark.asyncio
    async def test_enroll_device_old_timestamp(self, client, db_session, test_user, test_keypair):
        """Test enrollment with old timestamp (replay protection)."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        # Use old timestamp (10 minutes ago)
        timestamp = int(time.time()) - 600
        message = f"{device_id}:{timestamp}".encode('utf-8')
        signed = test_keypair['signing_key'].sign(message)
        signature_hex = signed.signature.hex()
        
        response = client.post(
            "/api/v1/enrollment/enroll",
            json={
                "enrollment_token": token,
                "device_id": device_id,
                "public_key": test_keypair['public_key_hex'],
                "signature": signature_hex,
                "os_type": "windows",
                "timestamp": timestamp
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestEnrollmentCancellation:
    """Test enrollment token cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancel_enrollment_success(self, client, auth_headers, db_session, test_user):
        """Test successful enrollment cancellation."""
        token = "a" * 64
        device_id = "b" * 32
        enrollment = EnrollmentToken(
            id=uuid.uuid4(),
            token=token,
            device_id=device_id,
            user_id=test_user.id,
            device_name="Test Device",
            used=False,
            cancelled=False,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db_session.add(enrollment)
        await db_session.commit()
        
        response = client.post(
            f"/api/v1/enrollment/cancel/{token}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["cancelled"] is True
    
    @pytest.mark.asyncio
    async def test_cancel_enrollment_not_found(self, client, auth_headers):
        """Test cancelling non-existent enrollment."""
        response = client.post(
            "/api/v1/enrollment/cancel/nonexistent",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_cancel_enrollment_unauthenticated(self, client):
        """Test cancellation without authentication."""
        response = client.post("/api/v1/enrollment/cancel/sometoken")
        
        assert response.status_code == 401
