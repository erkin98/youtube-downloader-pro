"""
File management API endpoints
"""

import mimetypes
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging_config import LoggerMixin
from app.models.downloads import Download, DownloadFile

router = APIRouter()


class FileAPI(LoggerMixin):
    """File API handlers"""

    pass


file_api = FileAPI()


@router.get("/download/{download_id}")
async def download_file(
    download_id: int,
    file_type: str = Query("video", description="Type of file to download"),
    db: AsyncSession = Depends(get_db),
):
    """Download a file from a completed download"""

    # Get download record
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status != "completed":
        raise HTTPException(status_code=400, detail="Download not completed")

    # Get file based on type
    if file_type == "video" and download.file_path:
        file_path = Path(download.file_path)
    else:
        # Look for specific file type in download files
        file_result = await db.execute(
            select(DownloadFile)
            .where(DownloadFile.download_id == download_id)
            .where(DownloadFile.file_type == file_type)
        )
        file_record = file_result.scalar_one_or_none()

        if not file_record:
            raise HTTPException(
                status_code=404, detail=f"File type '{file_type}' not found"
            )

        file_path = Path(file_record.file_path)

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Determine media type
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    file_api.log_info(
        f"Serving file for download {download_id}",
        file_path=str(file_path),
        file_size=file_path.stat().st_size,
    )

    return FileResponse(
        path=str(file_path), media_type=media_type, filename=file_path.name
    )


@router.get("/stream/{download_id}")
async def stream_file(download_id: int, db: AsyncSession = Depends(get_db)):
    """Stream a video file for in-browser playback"""

    # Get download record
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.status != "completed" or not download.file_path:
        raise HTTPException(status_code=400, detail="No streamable file available")

    file_path = Path(download.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Check if it's a video file
    if not download.format or download.format.lower() not in ["mp4", "webm", "mkv"]:
        raise HTTPException(status_code=400, detail="File is not streamable")

    def file_streamer():
        with open(file_path, "rb") as file:
            while chunk := file.read(8192):
                yield chunk

    file_size = file_path.stat().st_size
    media_type = f"video/{download.format}"

    return StreamingResponse(
        file_streamer(),
        media_type=media_type,
        headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
    )


@router.get("/list/{download_id}")
async def list_download_files(
    download_id: int, db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """List all files associated with a download"""

    # Get download record
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    # Get all files
    files_result = await db.execute(
        select(DownloadFile).where(DownloadFile.download_id == download_id)
    )
    files = files_result.scalars().all()

    file_list = []

    # Add main file if exists
    if download.file_path:
        file_path = Path(download.file_path)
        if file_path.exists():
            file_list.append(
                {
                    "type": "main",
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "format": download.format,
                    "path": str(file_path),
                    "download_url": f"/api/files/download/{download_id}?file_type=video",
                }
            )

    # Add associated files
    for file_record in files:
        file_path = Path(file_record.file_path)
        if file_path.exists():
            file_list.append(
                {
                    "type": file_record.file_type,
                    "name": file_record.file_name,
                    "size": file_record.file_size or file_path.stat().st_size,
                    "format": file_record.file_format,
                    "quality": file_record.quality,
                    "resolution": file_record.resolution,
                    "language": file_record.language,
                    "path": str(file_path),
                    "download_url": f"/api/files/download/{download_id}?file_type={file_record.file_type}",
                }
            )

    return file_list


@router.delete("/{download_id}")
async def delete_download_files(
    download_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete all files associated with a download"""

    # Get download record
    result = await db.execute(select(Download).where(Download.id == download_id))
    download = result.scalar_one_or_none()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    deleted_files = []
    errors = []

    # Delete main file
    if download.file_path:
        file_path = Path(download.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
                deleted_files.append(str(file_path))
            except Exception as e:
                errors.append(f"Failed to delete {file_path}: {e}")

    # Delete associated files
    files_result = await db.execute(
        select(DownloadFile).where(DownloadFile.download_id == download_id)
    )
    files = files_result.scalars().all()

    for file_record in files:
        file_path = Path(file_record.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
                deleted_files.append(str(file_path))
            except Exception as e:
                errors.append(f"Failed to delete {file_path}: {e}")

    file_api.log_info(
        f"Deleted files for download {download_id}",
        deleted_count=len(deleted_files),
        error_count=len(errors),
    )

    return {
        "deleted_files": deleted_files,
        "errors": errors,
        "total_deleted": len(deleted_files),
        "total_errors": len(errors),
    }


@router.get("/storage/stats")
async def get_storage_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Get storage statistics"""

    # Calculate total size from database
    result = await db.execute(select(Download).where(Download.file_size.isnot(None)))
    downloads = result.scalars().all()

    total_size = sum(d.file_size for d in downloads if d.file_size)

    # Get download directory size
    download_dir = Path(settings.DOWNLOAD_DIR)
    actual_size = 0
    file_count = 0

    if download_dir.exists():
        for file_path in download_dir.rglob("*"):
            if file_path.is_file():
                try:
                    actual_size += file_path.stat().st_size
                    file_count += 1
                except (OSError, FileNotFoundError):
                    pass

    # Get disk usage
    import shutil

    disk_usage = shutil.disk_usage(
        download_dir.parent if download_dir.exists() else "/"
    )

    return {
        "database_size": total_size,
        "actual_size": actual_size,
        "file_count": file_count,
        "download_directory": str(download_dir),
        "disk_usage": {
            "total": disk_usage.total,
            "used": disk_usage.used,
            "free": disk_usage.free,
            "percent_used": round((disk_usage.used / disk_usage.total) * 100, 2),
        },
    }


@router.post("/cleanup")
async def cleanup_orphaned_files(db: AsyncSession = Depends(get_db)) -> dict:
    """Clean up orphaned files that have no database record"""

    download_dir = Path(settings.DOWNLOAD_DIR)

    if not download_dir.exists():
        return {"message": "Download directory does not exist", "cleaned_files": []}

    # Get all file paths from database
    result = await db.execute(
        select(Download.file_path).where(Download.file_path.isnot(None))
    )
    db_file_paths = {Path(fp) for fp, in result.fetchall()}

    files_result = await db.execute(select(DownloadFile.file_path))
    db_file_paths.update(Path(fp) for fp, in files_result.fetchall())

    # Find orphaned files
    orphaned_files = []

    for file_path in download_dir.rglob("*"):
        if file_path.is_file() and file_path not in db_file_paths:
            orphaned_files.append(file_path)

    # Delete orphaned files
    cleaned_files = []
    errors = []

    for file_path in orphaned_files:
        try:
            file_path.unlink()
            cleaned_files.append(str(file_path))
        except Exception as e:
            errors.append(f"Failed to delete {file_path}: {e}")

    file_api.log_info(
        f"Cleanup completed",
        orphaned_count=len(orphaned_files),
        cleaned_count=len(cleaned_files),
        error_count=len(errors),
    )

    return {
        "message": f"Cleanup completed: {len(cleaned_files)} files deleted",
        "cleaned_files": cleaned_files,
        "errors": errors,
        "total_cleaned": len(cleaned_files),
        "total_errors": len(errors),
    }
