"""
Database models for YouTube Downloader Pro
"""

from .analytics import (
    AnalyticsEvent,
    ErrorLog,
    EventType,
    PerformanceMetrics,
    UsageStatistics,
)

# Import all models to ensure they're registered with SQLAlchemy
from .downloads import (
    Download,
    DownloadFile,
    DownloadStatus,
    DownloadType,
    VideoMetadata,
    VideoQuality,
)
from .users import User, UserRole, UserSession

__all__ = [
    # Download models
    "Download",
    "VideoMetadata",
    "DownloadFile",
    "DownloadStatus",
    "DownloadType",
    "VideoQuality",
    # User models
    "User",
    "UserSession",
    "UserRole",
    # Analytics models
    "AnalyticsEvent",
    "PerformanceMetrics",
    "ErrorLog",
    "UsageStatistics",
    "EventType",
]
