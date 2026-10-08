"""Tests for authentication API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.database import get_db, engine, Base
from app.models import User
from app.security import get_password_hash
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


class TestRegistration:
    """Test user registration."""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "securepassword123",
            "name": "Test User"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, db_session):
        """Test registration with duplicate email."""
        # Create existing user
        user = User(
            id=uuid.uuid4(),
            email="existing@example.com",
            password_hash=get_password_hash("password123"),
            name="Existing User"
        )
        db_session.add(user)
        await db_session.commit()
        
        # Try to register with same email
        response = client.post("/api/v1/auth/register", json={
            "email": "existing@example.com",
            "password": "securepassword123",
            "name": "Test User"
        })
        
        assert response.status_code == 409
        assert "REGISTRATION_FAILED" in str(response.json())
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        """Test registration with invalid email."""
        response = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "securepassword123",
            "name": "Test User"
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_short_password(self, client):
        """Test registration with short password."""
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "short",
            "name": "Test User"
        })
        
        assert response.status_code == 422


class TestLogin:
    """Test user login."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, db_session):
        """Test successful login."""
        # Create user
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash("securepassword123"),
            name="Test User",
            active=True
        )
        db_session.add(user)
        await db_session.commit()
        
        # Login
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "securepassword123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, db_session):
        """Test login with wrong password."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash("correctpassword"),
            name="Test User",
            active=True
        )
        db_session.add(user)
        await db_session.commit()
        
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_disabled_user(self, client, db_session):
        """Test login with disabled user."""
        user = User(
            id=uuid.uuid4(),
            email="disabled@example.com",
            password_hash=get_password_hash("password123"),
            name="Disabled User",
            active=False
        )
        db_session.add(user)
        await db_session.commit()
        
        response = client.post("/api/v1/auth/login", json={
            "email": "disabled@example.com",
            "password": "password123"
        })
        
        assert response.status_code == 403


class TestTokenRefresh:
    """Test token refresh."""
    
    @pytest.mark.asyncio
    async def test_refresh_success(self, client):
        """Test successful token refresh."""
        # First register to get tokens
        register_response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "securepassword123",
            "name": "Test User"
        })
        
        refresh_token = register_response.json()["refresh_token"]
        
        # Refresh token
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token."""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-token"
        })
        
        assert response.status_code == 401


class TestProtectedEndpoints:
    """Test protected endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client):
        """Test getting current user when authenticated."""
        # Register and login
        register_response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "securepassword123",
            "name": "Test User"
        })
        
        access_token = register_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
