"""
Configuration management for NEXLINK backend.

Uses Pydantic Settings for environment-based configuration.
All sensitive values must come from environment variables.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = Field(default="NEXLINK Backend", description="Application name")
    app_env: str = Field(default="development", description="Environment (development/production/testing)")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://nexlink:nexlink_dev@127.0.0.1:5432/nexlink",
        description="PostgreSQL connection URL"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL"
    )
    
    # JWT Authentication
    jwt_secret_key: str = Field(
        default="",
        description="JWT secret key for signing tokens"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=1440,  # 24 hours
        description="Access token expiration in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration in days"
    )
    
    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Security
    bcrypt_rounds: int = Field(default=12, description="bcrypt hashing rounds")
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = Settings()
    return _settings
