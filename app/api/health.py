"""
Health check endpoints
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis

router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
    }


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Detailed health check with system metrics"""

    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "checks": {},
    }

    # Database check
    try:
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        health_data["checks"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0,  # Could add timing here
        }
    except Exception as e:
        health_data["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_data["status"] = "degraded"

    # Redis check
    redis_client = await get_redis()
    if redis_client:
        try:
            await redis_client.ping()
            health_data["checks"]["redis"] = {"status": "healthy"}
        except Exception as e:
            health_data["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
            health_data["status"] = "degraded"
    else:
        health_data["checks"]["redis"] = {"status": "not_configured"}

    # Disk space check
    try:
        disk_usage = psutil.disk_usage("/")
        free_gb = disk_usage.free / (1024**3)
        health_data["checks"]["disk_space"] = {
            "status": "healthy" if free_gb > 1 else "warning",
            "free_gb": round(free_gb, 2),
            "total_gb": round(disk_usage.total / (1024**3), 2),
            "used_percent": round((disk_usage.used / disk_usage.total) * 100, 2),
        }
    except Exception as e:
        health_data["checks"]["disk_space"] = {"status": "unknown", "error": str(e)}

    # Memory check
    try:
        memory = psutil.virtual_memory()
        health_data["checks"]["memory"] = {
            "status": "healthy" if memory.percent < 90 else "warning",
            "used_percent": memory.percent,
            "available_gb": round(memory.available / (1024**3), 2),
            "total_gb": round(memory.total / (1024**3), 2),
        }
    except Exception as e:
        health_data["checks"]["memory"] = {"status": "unknown", "error": str(e)}

    # Directory checks
    directories = [settings.DOWNLOAD_DIR, settings.UPLOAD_DIR, settings.TEMP_DIR]

    health_data["checks"]["directories"] = {}
    for directory in directories:
        path = Path(directory)
        health_data["checks"]["directories"][directory] = {
            "exists": path.exists(),
            "writable": path.exists() and path.is_dir() and os.access(path, os.W_OK),
        }

    return health_data


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get system metrics"""

    # CPU metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()

    # Memory metrics
    memory = psutil.virtual_memory()

    # Disk metrics
    disk = psutil.disk_usage("/")

    # Network metrics (basic)
    network = psutil.net_io_counters()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu": {"percent": cpu_percent, "cores": cpu_count},
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100,
        },
        "network": {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv,
        },
    }
