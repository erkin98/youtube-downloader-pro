"""
Analytics models for YouTube Downloader Pro
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EventType(str, Enum):
    """Event type enumeration"""

    DOWNLOAD_STARTED = "download_started"
    DOWNLOAD_COMPLETED = "download_completed"
    DOWNLOAD_FAILED = "download_failed"
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    API_REQUEST = "api_request"
    ERROR_OCCURRED = "error_occurred"
    FEATURE_USED = "feature_used"


class AnalyticsEvent(Base):
    """Analytics events tracking"""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Event details
    event_type: Mapped[EventType] = mapped_column(SQLEnum(EventType), index=True)
    event_name: Mapped[str] = mapped_column(String(100), index=True)
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # User context
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    session_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    referer: Mapped[Optional[str]] = mapped_column(String(500))

    # Performance metrics
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Event duration in milliseconds

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")


class PerformanceMetrics(Base):
    """System performance metrics"""

    __tablename__ = "performance_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Metric details
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    metric_unit: Mapped[str] = mapped_column(
        String(20)
    )  # e.g., 'seconds', 'bytes', 'percent'

    # Context
    component: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # e.g., 'database', 'redis', 'download'
    additional_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class ErrorLog(Base):
    """Error logging and tracking"""

    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Error details
    error_type: Mapped[str] = mapped_column(String(100), index=True)
    error_message: Mapped[str] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)

    # Context
    component: Mapped[Optional[str]] = mapped_column(String(50))
    function_name: Mapped[Optional[str]] = mapped_column(String(100))
    line_number: Mapped[Optional[int]] = mapped_column(Integer)

    # Request context
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    session_id: Mapped[Optional[str]] = mapped_column(String(100))
    request_path: Mapped[Optional[str]] = mapped_column(String(500))
    request_method: Mapped[Optional[str]] = mapped_column(String(10))

    # Additional data
    additional_data: Mapped[Optional[str]] = mapped_column(JSON)

    # Status
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")


class UsageStatistics(Base):
    """Daily usage statistics"""

    __tablename__ = "usage_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Date
    date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Download statistics
    total_downloads: Mapped[int] = mapped_column(Integer, default=0)
    successful_downloads: Mapped[int] = mapped_column(Integer, default=0)
    failed_downloads: Mapped[int] = mapped_column(Integer, default=0)
    total_data_downloaded: Mapped[int] = mapped_column(Integer, default=0)  # in bytes

    # User statistics
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)

    # Performance statistics
    avg_download_speed: Mapped[Optional[float]] = mapped_column(Float)
    avg_response_time: Mapped[Optional[float]] = mapped_column(Float)

    # System resources
    cpu_usage_avg: Mapped[Optional[float]] = mapped_column(Float)
    memory_usage_avg: Mapped[Optional[float]] = mapped_column(Float)
    disk_usage: Mapped[Optional[float]] = mapped_column(Float)

    # Quality metrics
    popular_formats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    popular_resolutions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
