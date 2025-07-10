"""
Analytics API endpoints for monitoring and insights
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.logging_config import LoggerMixin
from app.models.analytics import (
    AnalyticsEvent,
    EventType,
    PerformanceMetrics,
    UsageStatistics,
)
from app.models.downloads import Download, DownloadStatus, DownloadType
from app.models.users import User

router = APIRouter()


class AnalyticsAPI(LoggerMixin):
    """Analytics API handlers"""

    pass


analytics_api = AnalyticsAPI()


@router.get("/dashboard")
async def get_dashboard_stats(
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive dashboard statistics"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Download statistics
    total_downloads = await db.scalar(select(func.count(Download.id)))

    recent_downloads = await db.scalar(
        select(func.count(Download.id)).where(Download.created_at >= start_date)
    )

    completed_downloads = await db.scalar(
        select(func.count(Download.id)).where(
            and_(
                Download.status == DownloadStatus.COMPLETED,
                Download.created_at >= start_date,
            )
        )
    )

    failed_downloads = await db.scalar(
        select(func.count(Download.id)).where(
            and_(
                Download.status == DownloadStatus.FAILED,
                Download.created_at >= start_date,
            )
        )
    )

    active_downloads = await db.scalar(
        select(func.count(Download.id)).where(
            Download.status.in_(
                [
                    DownloadStatus.DOWNLOADING,
                    DownloadStatus.QUEUED,
                    DownloadStatus.PENDING,
                ]
            )
        )
    )

    # Success rate
    total_finished = (completed_downloads or 0) + (failed_downloads or 0)
    success_rate = (
        (completed_downloads / total_finished * 100) if total_finished > 0 else 0
    )

    # Data volume
    total_size = (
        await db.scalar(
            select(func.sum(Download.file_size)).where(
                and_(Download.file_size.isnot(None), Download.created_at >= start_date)
            )
        )
        or 0
    )

    # Average download speed
    avg_speed = await db.scalar(
        select(func.avg(Download.download_speed)).where(
            and_(
                Download.download_speed.isnot(None),
                Download.status == DownloadStatus.COMPLETED,
                Download.created_at >= start_date,
            )
        )
    )

    # Most popular formats and qualities
    format_stats = await db.execute(
        select(Download.format, func.count(Download.id).label("count"))
        .where(Download.created_at >= start_date)
        .group_by(Download.format)
        .order_by(desc("count"))
        .limit(5)
    )

    quality_stats = await db.execute(
        select(Download.quality, func.count(Download.id).label("count"))
        .where(Download.created_at >= start_date)
        .group_by(Download.quality)
        .order_by(desc("count"))
        .limit(5)
    )

    # User statistics (if users are tracked)
    total_users = await db.scalar(select(func.count(User.id))) or 0

    active_users = (
        await db.scalar(
            select(func.count(func.distinct(Download.user_id))).where(
                and_(Download.user_id.isnot(None), Download.created_at >= start_date)
            )
        )
        or 0
    )

    return {
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "downloads": {
            "total": total_downloads or 0,
            "recent": recent_downloads or 0,
            "completed": completed_downloads or 0,
            "failed": failed_downloads or 0,
            "active": active_downloads or 0,
            "success_rate": round(success_rate, 2),
        },
        "data": {
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2) if total_size else 0,
            "avg_speed_mbps": round(avg_speed / (1024**2), 2) if avg_speed else None,
        },
        "popular": {
            "formats": [{"format": fmt, "count": count} for fmt, count in format_stats],
            "qualities": [
                {"quality": qual, "count": count} for qual, count in quality_stats
            ],
        },
        "users": {"total": total_users, "active": active_users},
    }


@router.get("/downloads/timeline")
async def get_downloads_timeline(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    interval: str = Query(
        "day", regex="^(hour|day|week)$", description="Time interval"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get download timeline data"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Determine date truncation based on interval
    if interval == "hour":
        date_trunc = func.date_trunc("hour", Download.created_at)
        delta = timedelta(hours=1)
    elif interval == "day":
        date_trunc = func.date_trunc("day", Download.created_at)
        delta = timedelta(days=1)
    else:  # week
        date_trunc = func.date_trunc("week", Download.created_at)
        delta = timedelta(weeks=1)

    # Get download counts by time period and status
    result = await db.execute(
        select(
            date_trunc.label("period"),
            Download.status,
            func.count(Download.id).label("count"),
        )
        .where(Download.created_at >= start_date)
        .group_by(date_trunc, Download.status)
        .order_by(date_trunc)
    )

    # Process results
    timeline_data = {}
    for period, status, count in result:
        period_str = period.isoformat()
        if period_str not in timeline_data:
            timeline_data[period_str] = {
                "period": period_str,
                "completed": 0,
                "failed": 0,
                "downloading": 0,
                "pending": 0,
                "total": 0,
            }

        status_key = (
            status.value.lower() if hasattr(status, "value") else str(status).lower()
        )
        if status_key in timeline_data[period_str]:
            timeline_data[period_str][status_key] = count
        timeline_data[period_str]["total"] += count

    return list(timeline_data.values())


@router.get("/performance/metrics")
async def get_performance_metrics(
    hours: int = Query(24, ge=1, le=168, description="Number of hours"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get system performance metrics"""

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    # Get performance metrics from database
    result = await db.execute(
        select(PerformanceMetrics)
        .where(PerformanceMetrics.created_at >= start_time)
        .order_by(PerformanceMetrics.created_at)
    )

    metrics = result.scalars().all()

    # Group metrics by name
    grouped_metrics = {}
    for metric in metrics:
        name = metric.metric_name
        if name not in grouped_metrics:
            grouped_metrics[name] = []

        grouped_metrics[name].append(
            {
                "timestamp": metric.created_at.isoformat(),
                "value": metric.metric_value,
                "unit": metric.metric_unit,
                "component": metric.component,
            }
        )

    # Calculate averages
    averages = {}
    for name, values in grouped_metrics.items():
        if values:
            avg_value = sum(v["value"] for v in values) / len(values)
            averages[name] = {
                "average": round(avg_value, 2),
                "unit": values[0]["unit"],
                "samples": len(values),
            }

    return {
        "period": {
            "hours": hours,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        "metrics": grouped_metrics,
        "averages": averages,
    }


@router.get("/errors/summary")
async def get_error_summary(
    days: int = Query(7, ge=1, le=30, description="Number of days"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get error summary and analysis"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get failed downloads with error messages
    result = await db.execute(
        select(Download.error_message, func.count(Download.id).label("count"))
        .where(
            and_(
                Download.status == DownloadStatus.FAILED,
                Download.created_at >= start_date,
                Download.error_message.isnot(None),
            )
        )
        .group_by(Download.error_message)
        .order_by(desc("count"))
        .limit(10)
    )

    error_types = [{"error": error, "count": count} for error, count in result]

    # Get error trends over time
    daily_errors = await db.execute(
        select(
            func.date_trunc("day", Download.created_at).label("date"),
            func.count(Download.id).label("count"),
        )
        .where(
            and_(
                Download.status == DownloadStatus.FAILED,
                Download.created_at >= start_date,
            )
        )
        .group_by(func.date_trunc("day", Download.created_at))
        .order_by(func.date_trunc("day", Download.created_at))
    )

    error_timeline = [
        {"date": date.isoformat(), "errors": count} for date, count in daily_errors
    ]

    # Total error count
    total_errors = (
        await db.scalar(
            select(func.count(Download.id)).where(
                and_(
                    Download.status == DownloadStatus.FAILED,
                    Download.created_at >= start_date,
                )
            )
        )
        or 0
    )

    return {
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "summary": {
            "total_errors": total_errors,
            "unique_error_types": len(error_types),
        },
        "top_errors": error_types,
        "timeline": error_timeline,
    }


@router.get("/usage/patterns")
async def get_usage_patterns(
    days: int = Query(30, ge=1, le=90, description="Number of days"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get usage patterns and insights"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Downloads by hour of day
    hourly_pattern = await db.execute(
        select(
            func.extract("hour", Download.created_at).label("hour"),
            func.count(Download.id).label("count"),
        )
        .where(Download.created_at >= start_date)
        .group_by(func.extract("hour", Download.created_at))
        .order_by(func.extract("hour", Download.created_at))
    )

    hourly_data = [
        {"hour": int(hour), "downloads": count} for hour, count in hourly_pattern
    ]

    # Downloads by day of week
    daily_pattern = await db.execute(
        select(
            func.extract("dow", Download.created_at).label("dow"),
            func.count(Download.id).label("count"),
        )
        .where(Download.created_at >= start_date)
        .group_by(func.extract("dow", Download.created_at))
        .order_by(func.extract("dow", Download.created_at))
    )

    day_names = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    weekly_data = [
        {"day": day_names[int(dow)], "day_number": int(dow), "downloads": count}
        for dow, count in daily_pattern
    ]

    # Download type distribution
    type_distribution = await db.execute(
        select(Download.download_type, func.count(Download.id).label("count"))
        .where(Download.created_at >= start_date)
        .group_by(Download.download_type)
    )

    type_data = [
        {"type": dtype.value, "count": count} for dtype, count in type_distribution
    ]

    # Average processing time
    avg_processing_time = await db.scalar(
        select(
            func.avg(
                func.extract("epoch", Download.completed_at)
                - func.extract("epoch", Download.started_at)
            )
        ).where(
            and_(
                Download.status == DownloadStatus.COMPLETED,
                Download.started_at.isnot(None),
                Download.completed_at.isnot(None),
                Download.created_at >= start_date,
            )
        )
    )

    return {
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "patterns": {
            "hourly": hourly_data,
            "weekly": weekly_data,
            "download_types": type_data,
        },
        "performance": {
            "avg_processing_time_seconds": (
                round(avg_processing_time, 2) if avg_processing_time else None
            )
        },
    }


@router.post("/events")
async def track_event(
    event_data: Dict[str, Any], db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Track an analytics event"""

    try:
        event = AnalyticsEvent(
            event_type=EventType(event_data.get("event_type", "feature_used")),
            event_name=event_data.get("event_name", "unknown"),
            event_data=event_data.get("data"),
            user_id=event_data.get("user_id"),
            session_id=event_data.get("session_id"),
            ip_address=event_data.get("ip_address"),
            user_agent=event_data.get("user_agent"),
            duration_ms=event_data.get("duration_ms"),
        )

        db.add(event)
        await db.commit()

        analytics_api.log_info(
            f"Analytics event tracked: {event.event_name}",
            event_type=event.event_type.value,
        )

        return {"message": "Event tracked successfully"}

    except Exception as e:
        analytics_api.log_error(f"Failed to track event: {e}")
        return {"message": "Failed to track event"}


@router.get("/export")
async def export_analytics_data(
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    format: str = Query("json", regex="^(json|csv)$", description="Export format"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Export analytics data"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get download data
    result = await db.execute(
        select(Download)
        .where(Download.created_at >= start_date)
        .order_by(Download.created_at)
    )

    downloads = result.scalars().all()

    export_data = []
    for download in downloads:
        export_data.append(
            {
                "id": download.id,
                "url": download.url,
                "title": download.title,
                "status": download.status.value if download.status else None,
                "quality": download.quality,
                "format": download.format,
                "file_size": download.file_size,
                "download_speed": download.download_speed,
                "created_at": download.created_at.isoformat(),
                "completed_at": (
                    download.completed_at.isoformat() if download.completed_at else None
                ),
                "progress": download.progress,
                "error_message": download.error_message,
            }
        )

    return {
        "period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "format": format,
        "total_records": len(export_data),
        "data": export_data,
    }
