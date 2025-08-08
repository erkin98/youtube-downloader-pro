"""
Download management API endpoints
"""

import asyncio
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.logging_config import LoggerMixin
from app.core.redis_client import redis_manager
from app.models.downloads import (
    Download,
    DownloadFile,
    DownloadStatus,
    DownloadType,
    VideoMetadata,
)
from app.schemas.downloads import (
    BatchDownloadCreate,
    BatchDownloadResponse,
    DownloadCreate,
    DownloadListResponse,
    DownloadResponse,
    DownloadStats,
    DownloadUpdate,
    VideoInfoRequest,
    VideoInfoResponse,
)
from app.services.download_service import DownloadService
from app.services.youtube_service import YouTubeService

router = APIRouter()


class DownloadAPI(LoggerMixin):
    """Download API handlers"""

    def __init__(self):
        self.youtube_service = YouTubeService()
        self.download_service = DownloadService()


download_api = DownloadAPI()


@router.post("/", response_model=DownloadResponse, status_code=201)
async def create_download(
    download_data: DownloadCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DownloadResponse:
    """Create a new download job"""

    try:
        # Validate URL and get basic info
        video_info = await download_api.youtube_service.get_video_info(
            str(download_data.url)
        )

        # Create download record
        download = Download(
            url=str(download_data.url),
            download_type=(
                DownloadType.PLAYLIST
                if video_info.get("is_playlist")
                else DownloadType.VIDEO
            ),
            quality=download_data.quality.value,
            format=download_data.format.value,
            audio_format=download_data.audio_format.value,
            fps=download_data.fps,
            audio_only=download_data.audio_only,
            extract_audio=download_data.extract_audio,
            include_subtitles=download_data.include_subtitles,
            auto_subtitles=download_data.auto_subtitles,
            subtitle_languages=download_data.subtitle_languages,
            include_thumbnail=download_data.include_thumbnail,
            include_metadata=download_data.include_metadata,
            start_time=download_data.start_time,
            end_time=download_data.end_time,
            playlist_start=download_data.playlist_start,
            playlist_end=download_data.playlist_end,
            output_directory=download_data.output_directory,
            priority=download_data.priority,
            status=DownloadStatus.PENDING,
        )

        # Add metadata if available
        if video_info:
            metadata = VideoMetadata(
                video_id=video_info.get("id"),
                title=video_info.get("title"),
                uploader=video_info.get("uploader"),
                uploader_id=video_info.get("uploader_id"),
                channel=video_info.get("channel"),
                channel_id=video_info.get("channel_id"),
                duration=video_info.get("duration"),
                view_count=video_info.get("view_count"),
                like_count=video_info.get("like_count"),
                upload_date=video_info.get("upload_date"),
                categories=video_info.get("categories"),
                tags=video_info.get("tags"),
                thumbnail_url=video_info.get("thumbnail"),
                webpage_url=video_info.get("webpage_url"),
            )
            download.video_metadata = metadata
            download.title = video_info.get("title")
            download.description = video_info.get("description")

        db.add(download)
        await db.commit()
        await db.refresh(download)

        # Queue download job
        background_tasks.add_task(
            download_api.download_service.queue_download, download.id
        )

        download_api.log_info(
            "Download created successfully",
            download_id=download.id,
            url=str(download_data.url),
        )

        return await _get_download_with_relations(db, download.id)

    except Exception as e:
        download_api.log_error(
            f"Failed to create download: {e}", url=str(download_data.url)
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=DownloadListResponse)
async def list_downloads(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[DownloadStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title or URL"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
) -> DownloadListResponse:
    """List downloads with pagination and filtering"""

    # Build query
    query = select(Download).options(
        selectinload(Download.metadata), selectinload(Download.files)
    )

    # Apply filters
    if status:
        query = query.where(Download.status == status)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Download.title.ilike(search_term),
                Download.url.ilike(search_term),
                Download.description.ilike(search_term),
            )
        )

    # Apply sorting
    sort_column = getattr(Download, sort_by, Download.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Count total items
    count_query = select(func.count(Download.id))
    if status:
        count_query = count_query.where(Download.status == status)
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                Download.title.ilike(search_term),
                Download.url.ilike(search_term),
                Download.description.ilike(search_term),
            )
        )

    total = await db.scalar(count_query)

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    downloads = result.scalars().all()

    pages = math.ceil(total / per_page)

    return DownloadListResponse(
        items=[DownloadResponse.model_validate(download, from_attributes=True) for download in downloads],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        has_prev=page > 1,
        has_next=page < pages,
    )


@router.get("/{download_id}", response_model=DownloadResponse)
async def get_download(
    download_id: int, db: AsyncSession = Depends(get_db)
) -> DownloadResponse:
    """Get a specific download by ID"""

    download = await _get_download_with_relations(db, download_id)
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    return download


@router.patch("/{download_id}", response_model=DownloadResponse)
async def update_download(
    download_id: int, update_data: DownloadUpdate, db: AsyncSession = Depends(get_db)
) -> DownloadResponse:
    """Update a download"""

    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(download, field, value)

    download.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(download)

    return await _get_download_with_relations(db, download_id)


@router.delete("/{download_id}")
async def delete_download(
    download_id: int, db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Delete a download"""

    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    # Cancel if in progress
    if download.status in [DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED]:
        await download_api.download_service.cancel_download(download_id)

    # Delete files if they exist
    if download.file_path and Path(download.file_path).exists():
        try:
            Path(download.file_path).unlink()
        except Exception as e:
            download_api.log_warning(
                f"Failed to delete file: {e}", download_id=download_id
            )

    await db.delete(download)
    await db.commit()

    return {"message": "Download deleted successfully"}


@router.post("/{download_id}/retry", response_model=DownloadResponse)
async def retry_download(
    download_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DownloadResponse:
    """Retry a failed download"""

    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status not in [DownloadStatus.FAILED, DownloadStatus.CANCELLED]:
        raise HTTPException(
            status_code=400, detail="Can only retry failed or cancelled downloads"
        )

    # Reset download state
    download.status = DownloadStatus.PENDING
    download.progress = 0.0
    download.error_message = None
    download.retry_count += 1
    download.updated_at = datetime.utcnow()

    await db.commit()

    # Queue download job
    background_tasks.add_task(download_api.download_service.queue_download, download_id)

    return await _get_download_with_relations(db, download_id)


@router.post("/{download_id}/cancel", response_model=DownloadResponse)
async def cancel_download(
    download_id: int, db: AsyncSession = Depends(get_db)
) -> DownloadResponse:
    """Cancel a download"""

    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status not in [
        DownloadStatus.PENDING,
        DownloadStatus.QUEUED,
        DownloadStatus.DOWNLOADING,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Can only cancel pending, queued, or downloading items",
        )

    # Cancel the download
    await download_api.download_service.cancel_download(download_id)

    download.status = DownloadStatus.CANCELLED
    download.updated_at = datetime.utcnow()

    await db.commit()

    return await _get_download_with_relations(db, download_id)


@router.get("/stats/overview", response_model=DownloadStats)
async def get_download_stats(db: AsyncSession = Depends(get_db)) -> DownloadStats:
    """Get download statistics"""

    # Total downloads
    total_query = select(func.count(Download.id))
    total = await db.scalar(total_query) or 0

    # Status counts
    status_counts = {}
    for status in DownloadStatus:
        count_query = select(func.count(Download.id)).where(Download.status == status)
        status_counts[status] = await db.scalar(count_query) or 0

    # Total size
    size_query = select(func.sum(Download.file_size)).where(
        Download.file_size.isnot(None)
    )
    total_size = await db.scalar(size_query) or 0

    # Average speed
    speed_query = select(func.avg(Download.download_speed)).where(
        and_(
            Download.download_speed.isnot(None),
            Download.status == DownloadStatus.COMPLETED,
        )
    )
    avg_speed = await db.scalar(speed_query)

    # Success rate
    completed = status_counts.get(DownloadStatus.COMPLETED, 0)
    failed = status_counts.get(DownloadStatus.FAILED, 0)
    success_rate = (
        (completed / (completed + failed)) * 100 if (completed + failed) > 0 else 0
    )

    return DownloadStats(
        total_downloads=total,
        completed_downloads=completed,
        failed_downloads=failed,
        in_progress=status_counts.get(DownloadStatus.DOWNLOADING, 0),
        queued=status_counts.get(DownloadStatus.QUEUED, 0),
        total_size=total_size,
        avg_speed=avg_speed,
        success_rate=success_rate,
    )


@router.post("/video-info", response_model=VideoInfoResponse)
async def get_video_info(request: VideoInfoRequest) -> VideoInfoResponse:
    """Get video information without downloading"""

    try:
        info = await download_api.youtube_service.get_video_info(str(request.url))

        return VideoInfoResponse(
            url=str(request.url),
            title=info.get("title"),
            description=info.get("description"),
            uploader=info.get("uploader"),
            duration=info.get("duration"),
            view_count=info.get("view_count"),
            upload_date=info.get("upload_date"),
            thumbnail_url=info.get("thumbnail"),
            is_playlist=info.get("is_playlist", False),
            playlist_count=info.get("playlist_count"),
            available_formats=info.get("formats", []),
            available_qualities=info.get("qualities", []),
            has_subtitles=info.get("has_subtitles", False),
            available_subtitles=info.get("subtitles", []),
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get video info: {e}")


@router.post("/batch", response_model=BatchDownloadResponse)
async def create_batch_downloads(
    batch_data: BatchDownloadCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> BatchDownloadResponse:
    """Create multiple downloads at once"""

    created_downloads = []
    failed_urls = []

    for url in batch_data.urls:
        try:
            # Create individual download
            download_data = batch_data.settings.copy()
            download_data.url = url

            # Create download record (simplified version)
            download = Download(
                url=str(url),
                quality=download_data.quality.value,
                format=download_data.format.value,
                audio_format=download_data.audio_format.value,
                fps=download_data.fps,
                audio_only=download_data.audio_only,
                extract_audio=download_data.extract_audio,
                include_subtitles=download_data.include_subtitles,
                auto_subtitles=download_data.auto_subtitles,
                subtitle_languages=download_data.subtitle_languages,
                include_thumbnail=download_data.include_thumbnail,
                include_metadata=download_data.include_metadata,
                output_directory=download_data.output_directory,
                priority=download_data.priority,
                status=DownloadStatus.PENDING,
            )

            db.add(download)
            await db.flush()  # Get ID without committing

            created_downloads.append(download.id)

            # Queue download job
            background_tasks.add_task(
                download_api.download_service.queue_download, download.id
            )

        except Exception as e:
            failed_urls.append(str(url))
            download_api.log_error(
                f"Failed to create batch download: {e}", url=str(url)
            )

    await db.commit()

    return BatchDownloadResponse(
        created_downloads=created_downloads,
        failed_urls=failed_urls,
        total_created=len(created_downloads),
        total_failed=len(failed_urls),
    )


async def _get_download_with_relations(
    db: AsyncSession, download_id: int
) -> Optional[DownloadResponse]:
    """Helper to get download with all relations"""

    result = await db.execute(
        select(Download)
        .options(selectinload(Download.video_metadata), selectinload(Download.files))
        .where(Download.id == download_id)
    )
    download = result.scalar_one_or_none()

    if not download:
        return None

    return DownloadResponse.model_validate(download, from_attributes=True)
