"""
Main FastAPI application for YouTube Downloader Pro
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import analytics, downloads, files, health
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.redis_client import init_redis

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting YouTube Downloader Pro application...")

    # Initialize database
    await init_db()

    # Initialize Redis
    await init_redis()

    # Create necessary directories
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("Application startup complete")

    yield

    logger.info("Shutting down application...")


app = FastAPI(
    title="YouTube Downloader Pro",
    description="A world-class YouTube downloader with advanced features",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# API Routes
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(downloads.router, prefix="/api/downloads", tags=["downloads"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

# Static files for React frontend
if Path("frontend/dist").exists():
    app.mount("/static", StaticFiles(directory="frontend/dist/static"), name="static")

    @app.get("/{path:path}")
    async def serve_react_app(path: str):
        """Serve React app for all unmatched routes"""
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")

        file_path = Path(f"frontend/dist/{path}")
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Return index.html for SPA routing
        return FileResponse("frontend/dist/index.html")


@app.get("/")
async def root():
    """Root endpoint - serve React app or API info"""
    if Path("frontend/dist/index.html").exists():
        return FileResponse("frontend/dist/index.html")

    return {
        "message": "YouTube Downloader Pro API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "redoc": "/api/redoc",
    }
