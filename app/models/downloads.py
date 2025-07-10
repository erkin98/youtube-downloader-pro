"""
Download models for YouTube Downloader Pro
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DownloadStatus(str, Enum):
    """Download status enumeration"""

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class DownloadType(str, Enum):
    """Download type enumeration"""

    VIDEO = "video"
    AUDIO = "audio"
    PLAYLIST = "playlist"
    CHANNEL = "channel"


class VideoQuality(str, Enum):
    """Video quality enumeration"""

    Q144P = "144"
    Q240P = "240"
    Q360P = "360"
    Q480P = "480"
    Q720P = "720"
    Q1080P = "1080"
    Q1440P = "1440"
    Q2160P = "2160"
    Q4320P = "4320"
    BEST = "best"


class Download(Base):
    """Main download record"""

    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Basic info
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Download configuration
    download_type: Mapped[DownloadType] = mapped_column(
        SQLEnum(DownloadType), default=DownloadType.VIDEO
    )
    quality: Mapped[str] = mapped_column(String(10), default="1080")
    format: Mapped[str] = mapped_column(String(10), default="mp4")
    audio_format: Mapped[str] = mapped_column(String(10), default="mp3")
    fps: Mapped[Optional[int]] = mapped_column(Integer)

    # Options
    audio_only: Mapped[bool] = mapped_column(Boolean, default=False)
    extract_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    include_subtitles: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_subtitles: Mapped[bool] = mapped_column(Boolean, default=False)
    subtitle_languages: Mapped[Optional[str]] = mapped_column(JSON)
    include_thumbnail: Mapped[bool] = mapped_column(Boolean, default=False)
    include_metadata: Mapped[bool] = mapped_column(Boolean, default=True)

    # Time range
    start_time: Mapped[Optional[str]] = mapped_column(String(20))
    end_time: Mapped[Optional[str]] = mapped_column(String(20))

    # Playlist options
    playlist_start: Mapped[Optional[int]] = mapped_column(Integer)
    playlist_end: Mapped[Optional[int]] = mapped_column(Integer)

    # Status and progress
    status: Mapped[DownloadStatus] = mapped_column(
        SQLEnum(DownloadStatus), default=DownloadStatus.PENDING, index=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # File info
    output_directory: Mapped[str] = mapped_column(String(500), default="downloads")
    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)

    # Performance metrics
    download_speed: Mapped[Optional[float]] = mapped_column(Float)
    eta: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # Estimated time remaining in seconds

    # User and session
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    session_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Priority and retry
    priority: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    metadata: Mapped[Optional["VideoMetadata"]] = relationship(
        "VideoMetadata",
        back_populates="download",
        uselist=False,
        cascade="all, delete-orphan",
    )
    files: Mapped[List["DownloadFile"]] = relationship(
        "DownloadFile", back_populates="download", cascade="all, delete-orphan"
    )
    user: Mapped[Optional["User"]] = relationship("User", back_populates="downloads")


class VideoMetadata(Base):
    """Video metadata information"""

    __tablename__ = "video_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    download_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("downloads.id"), unique=True
    )

    # Basic video info
    video_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    uploader: Mapped[Optional[str]] = mapped_column(String(100))
    uploader_id: Mapped[Optional[str]] = mapped_column(String(100))
    channel: Mapped[Optional[str]] = mapped_column(String(100))
    channel_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Video metrics
    duration: Mapped[Optional[int]] = mapped_column(Integer)  # Duration in seconds
    view_count: Mapped[Optional[int]] = mapped_column(Integer)
    like_count: Mapped[Optional[int]] = mapped_column(Integer)
    dislike_count: Mapped[Optional[int]] = mapped_column(Integer)
    comment_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Video details
    upload_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    release_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    categories: Mapped[Optional[str]] = mapped_column(JSON)  # List of categories
    tags: Mapped[Optional[str]] = mapped_column(JSON)  # List of tags

    # Technical details
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    fps: Mapped[Optional[int]] = mapped_column(Integer)
    vcodec: Mapped[Optional[str]] = mapped_column(String(50))
    acodec: Mapped[Optional[str]] = mapped_column(String(50))

    # Thumbnails
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500))
    thumbnails: Mapped[Optional[str]] = mapped_column(JSON)  # List of thumbnail info

    # Additional metadata
    webpage_url: Mapped[Optional[str]] = mapped_column(String(500))
    original_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    download: Mapped["Download"] = relationship("Download", back_populates="metadata")


class DownloadFile(Base):
    """Files associated with a download"""

    __tablename__ = "download_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    download_id: Mapped[int] = mapped_column(Integer, ForeignKey("downloads.id"))

    # File info
    file_type: Mapped[str] = mapped_column(
        String(20)
    )  # video, audio, subtitle, thumbnail, etc.
    file_path: Mapped[str] = mapped_column(String(1000))
    file_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    file_format: Mapped[str] = mapped_column(String(10))

    # Quality info
    quality: Mapped[Optional[str]] = mapped_column(String(20))
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    fps: Mapped[Optional[int]] = mapped_column(Integer)
    bitrate: Mapped[Optional[int]] = mapped_column(Integer)

    # Language (for subtitles)
    language: Mapped[Optional[str]] = mapped_column(String(10))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    download: Mapped["Download"] = relationship("Download", back_populates="files")
