"""
Application configuration management
"""

import os
from typing import List, Optional

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "YouTube Downloader Pro"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./downloads.db"
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_EXPIRE: int = 3600  # 1 hour

    # File Storage
    UPLOAD_DIR: str = "uploads"
    DOWNLOAD_DIR: str = "downloads"
    TEMP_DIR: str = "temp"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB

    # Download Settings
    MAX_CONCURRENT_DOWNLOADS: int = 10
    DEFAULT_RESOLUTION: str = "1080"
    DEFAULT_FORMAT: str = "mp4"
    DEFAULT_AUDIO_FORMAT: str = "mp3"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 3600  # 1 hour

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # External Services
    YOUTUBE_API_KEY: Optional[str] = None

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # Feature Flags
    ENABLE_ANALYTICS: bool = True
    ENABLE_CLOUD_STORAGE: bool = False
    ENABLE_SCHEDULED_DOWNLOADS: bool = True
    ENABLE_USER_MANAGEMENT: bool = True

    # Cloud Storage (AWS S3)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: Optional[str] = None

    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        if v == "your-secret-key-change-in-production":
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError("Must set SECRET_KEY in production")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
