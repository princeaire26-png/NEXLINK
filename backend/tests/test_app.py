"""
Tests for the FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "nexlink-backend"
        assert "version" in data
    
    def test_health_check_no_sensitive_info(self, client):
        """Test health endpoint doesn't expose sensitive information."""
        response = client.get("/health")
        data = response.json()
        
        # Should not contain database URLs, secrets, etc.
        assert "database" not in data
        assert "secret" not in data
        assert "password" not in data


class TestRootEndpoint:
    """Test root endpoint."""
    
    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "NEXLINK Backend"
        assert data["status"] == "running"


class TestApplicationStartup:
    """Test application startup."""
    
    def test_app_creates_successfully(self):
        """Test that the FastAPI app creates without errors."""
        assert app is not None
        assert app.title == "NEXLINK Backend"
    
    def test_cors_configured(self):
        """Test that CORS middleware is configured."""
        # Check that CORS middleware is present
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes
