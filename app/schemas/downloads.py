"""
Download-related Pydantic schemas for request/response validation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator

from app.models.downloads import DownloadStatus, DownloadType, VideoQuality


class DownloadQualityEnum(str, Enum):
    """Available download qualities"""

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


class DownloadFormatEnum(str, Enum):
    """Available download formats"""

    MP4 = "mp4"
    WEBM = "webm"
    MKV = "mkv"
    AVI = "avi"
    MOV = "mov"


class AudioFormatEnum(str, Enum):
    """Available audio formats"""

    MP3 = "mp3"
    AAC = "aac"
    M4A = "m4a"
    OPUS = "opus"
    FLAC = "flac"
    WAV = "wav"


class DownloadCreate(BaseModel):
    """Schema for creating a new download"""

    url: HttpUrl = Field(..., description="YouTube video, playlist, or channel URL")

    # Quality settings
    quality: DownloadQualityEnum = Field(
        default=DownloadQualityEnum.Q1080P, description="Video quality"
    )
    format: DownloadFormatEnum = Field(
        default=DownloadFormatEnum.MP4, description="Video format"
    )
    fps: Optional[int] = Field(None, ge=1, le=120, description="Frames per second")

    # Audio settings
    audio_only: bool = Field(default=False, description="Download audio only")
    extract_audio: bool = Field(default=False, description="Extract audio from video")
    audio_format: AudioFormatEnum = Field(
        default=AudioFormatEnum.MP3, description="Audio format"
    )

    # Subtitle settings
    include_subtitles: bool = Field(default=False, description="Download subtitles")
    auto_subtitles: bool = Field(
        default=False, description="Download auto-generated subtitles"
    )
    subtitle_languages: List[str] = Field(
        default=["en"], description="Subtitle languages"
    )

    # Additional options
    include_thumbnail: bool = Field(default=False, description="Download thumbnail")
    include_metadata: bool = Field(default=True, description="Save metadata")

    # Time range
    start_time: Optional[str] = Field(None, description="Start time (HH:MM:SS)")
    end_time: Optional[str] = Field(None, description="End time (HH:MM:SS)")

    # Playlist options
    playlist_start: Optional[int] = Field(
        None, ge=1, description="Playlist start index"
    )
    playlist_end: Optional[int] = Field(None, ge=1, description="Playlist end index")

    # Priority
    priority: int = Field(
        default=0, ge=-10, le=10, description="Download priority (-10 to 10)"
    )

    # Output directory
    output_directory: str = Field(default="downloads", description="Output directory")

    @validator("playlist_end")
    def validate_playlist_range(cls, v, values):
        if (
            v is not None
            and "playlist_start" in values
            and values["playlist_start"] is not None
        ):
            if v < values["playlist_start"]:
                raise ValueError(
                    "playlist_end must be greater than or equal to playlist_start"
                )
        return v

    @validator("subtitle_languages")
    def validate_subtitle_languages(cls, v):
        if len(v) == 0:
            return ["en"]
        return v


class DownloadUpdate(BaseModel):
    """Schema for updating a download"""

    status: Optional[DownloadStatus] = None
    priority: Optional[int] = Field(None, ge=-10, le=10)

    class Config:
        use_enum_values = True


class VideoMetadataResponse(BaseModel):
    """Schema for video metadata response"""

    video_id: Optional[str]
    uploader: Optional[str]
    uploader_id: Optional[str]
    channel: Optional[str]
    channel_id: Optional[str]
    duration: Optional[int]
    view_count: Optional[int]
    like_count: Optional[int]
    dislike_count: Optional[int]
    comment_count: Optional[int]
    upload_date: Optional[datetime]
    release_date: Optional[datetime]
    categories: Optional[List[str]]
    tags: Optional[List[str]]
    resolution: Optional[str]
    fps: Optional[int]
    vcodec: Optional[str]
    acodec: Optional[str]
    thumbnail_url: Optional[str]
    webpage_url: Optional[str]

    class Config:
        from_attributes = True


class DownloadFileResponse(BaseModel):
    """Schema for download file response"""

    id: int
    file_type: str
    file_path: str
    file_name: str
    file_size: Optional[int]
    file_format: str
    quality: Optional[str]
    resolution: Optional[str]
    fps: Optional[int]
    bitrate: Optional[int]
    language: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DownloadResponse(BaseModel):
    """Schema for download response"""

    id: int
    url: str
    title: Optional[str]
    description: Optional[str]
    download_type: DownloadType
    quality: str
    format: str
    audio_format: str
    fps: Optional[int]
    audio_only: bool
    extract_audio: bool
    include_subtitles: bool
    auto_subtitles: bool
    subtitle_languages: Optional[List[str]]
    include_thumbnail: bool
    include_metadata: bool
    start_time: Optional[str]
    end_time: Optional[str]
    playlist_start: Optional[int]
    playlist_end: Optional[int]
    status: DownloadStatus
    progress: float
    error_message: Optional[str]
    output_directory: str
    file_path: Optional[str]
    file_size: Optional[int]
    download_speed: Optional[float]
    eta: Optional[int]
    user_id: Optional[int]
    session_id: Optional[str]
    priority: int
    retry_count: int
    max_retries: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Related data
    metadata: Optional[VideoMetadataResponse]
    files: List[DownloadFileResponse]

    class Config:
        from_attributes = True
        use_enum_values = True


class DownloadListResponse(BaseModel):
    """Schema for paginated download list"""

    items: List[DownloadResponse]
    total: int
    page: int
    per_page: int
    pages: int
    has_prev: bool
    has_next: bool


class DownloadStats(BaseModel):
    """Schema for download statistics"""

    total_downloads: int
    completed_downloads: int
    failed_downloads: int
    in_progress: int
    queued: int
    total_size: int
    avg_speed: Optional[float]
    success_rate: float


class VideoInfoRequest(BaseModel):
    """Schema for video info request"""

    url: HttpUrl = Field(..., description="YouTube video, playlist, or channel URL")


class VideoInfoResponse(BaseModel):
    """Schema for video info response"""

    url: str
    title: Optional[str]
    description: Optional[str]
    uploader: Optional[str]
    duration: Optional[int]
    view_count: Optional[int]
    upload_date: Optional[datetime]
    thumbnail_url: Optional[str]
    is_playlist: bool
    playlist_count: Optional[int]
    available_formats: List[Dict[str, Any]]
    available_qualities: List[str]
    has_subtitles: bool
    available_subtitles: List[str]

    class Config:
        from_attributes = True


class BatchDownloadCreate(BaseModel):
    """Schema for batch download creation"""

    urls: List[HttpUrl] = Field(
        ..., min_items=1, max_items=100, description="List of URLs to download"
    )
    settings: DownloadCreate = Field(
        ..., description="Common settings for all downloads"
    )


class BatchDownloadResponse(BaseModel):
    """Schema for batch download response"""

    created_downloads: List[int] = Field(
        ..., description="List of created download IDs"
    )
    failed_urls: List[str] = Field(
        ..., description="URLs that failed to create downloads"
    )
    total_created: int
    total_failed: int
