"""
Download service for managing download operations and job queue
"""

import asyncio
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging_config import LoggerMixin
from app.core.redis_client import redis_manager


class DownloadService(LoggerMixin):
    """Service for managing downloads"""

    def __init__(self):
        self.yt_dlp_path = "yt-dlp"
        self.active_downloads: Dict[int, asyncio.Task] = {}
        self.download_queue = "download_queue"

    async def queue_download(self, download_id: int) -> bool:
        """Add download to queue"""

        try:
            # Add to Redis queue
            await redis_manager.push_to_queue(
                self.download_queue,
                {"download_id": download_id, "queued_at": time.time()},
            )

            self.log_info(f"Download {download_id} added to queue")
            return True

        except Exception as e:
            self.log_error(f"Failed to queue download {download_id}: {e}")
            return False

    async def process_download(
        self, download_id: int, download_config: Dict[str, Any]
    ) -> bool:
        """Process a single download"""

        try:
            self.log_info(f"Starting download {download_id}")

            # Build yt-dlp command
            cmd = self._build_download_command(download_config)

            # Execute download with progress tracking
            success = await self._execute_download(download_id, cmd)

            if success:
                self.log_info(f"Download {download_id} completed successfully")
            else:
                self.log_error(f"Download {download_id} failed")

            return success

        except Exception as e:
            self.log_error(f"Error processing download {download_id}: {e}")
            return False

        finally:
            # Remove from active downloads
            if download_id in self.active_downloads:
                del self.active_downloads[download_id]

    async def cancel_download(self, download_id: int) -> bool:
        """Cancel an active download"""

        try:
            if download_id in self.active_downloads:
                task = self.active_downloads[download_id]
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

                del self.active_downloads[download_id]
                self.log_info(f"Download {download_id} cancelled")
                return True

            return False

        except Exception as e:
            self.log_error(f"Failed to cancel download {download_id}: {e}")
            return False

    def _build_download_command(self, config: Dict[str, Any]) -> List[str]:
        """Build yt-dlp command from download configuration"""

        cmd = [self.yt_dlp_path]

        # Output template and directory
        output_dir = Path(config.get("output_directory", "downloads"))
        output_dir.mkdir(parents=True, exist_ok=True)

        output_template = str(output_dir / "%(title)s.%(ext)s")
        cmd.extend(["-o", output_template])

        # Format selection
        if config.get("audio_only"):
            cmd.extend(["-f", "bestaudio"])
        else:
            quality = config.get("quality", "1080")
            fps = config.get("fps")

            fps_filter = f"[fps<={fps}]" if fps else ""
            format_str = f"bestvideo[height<={quality}]{fps_filter}+bestaudio/best[height<={quality}]"
            cmd.extend(["-f", format_str])

        # Audio extraction
        if config.get("extract_audio"):
            cmd.extend(
                ["--extract-audio", "--audio-format", config.get("audio_format", "mp3")]
            )

        # Video format
        if not config.get("audio_only") and not config.get("extract_audio"):
            cmd.extend(["--remux-video", config.get("format", "mp4")])

        # Subtitles
        if config.get("include_subtitles"):
            cmd.append("--write-subs")
            subtitle_langs = config.get("subtitle_languages", ["en"])
            if subtitle_langs:
                cmd.extend(["--sub-langs", ",".join(subtitle_langs)])

        if config.get("auto_subtitles"):
            cmd.append("--write-auto-subs")

        # Thumbnail
        if config.get("include_thumbnail"):
            cmd.append("--write-thumbnail")

        # Metadata
        if config.get("include_metadata", True):
            cmd.extend(["--write-info-json", "--write-description"])

        # Time range
        if config.get("start_time") or config.get("end_time"):
            cmd.extend(["--external-downloader", "ffmpeg"])

            if config.get("start_time"):
                cmd.extend(
                    ["--external-downloader-args", f"-ss {config['start_time']}"]
                )

            if config.get("end_time"):
                if config.get("start_time"):
                    cmd.extend(
                        ["--external-downloader-args", f"-to {config['end_time']}"]
                    )
                else:
                    cmd.extend(
                        ["--external-downloader-args", f"-to {config['end_time']}"]
                    )

        # Playlist range
        if config.get("playlist_start"):
            cmd.extend(["--playlist-start", str(config["playlist_start"])])

        if config.get("playlist_end"):
            cmd.extend(["--playlist-end", str(config["playlist_end"])])

        # Additional options
        cmd.extend(
            [
                "--embed-chapters",
                "--ignore-errors",
                "--no-warnings",
                "--progress",
                "--newline",
            ]
        )

        # Add the URL
        cmd.append(config["url"])

        return cmd

    async def _execute_download(self, download_id: int, cmd: List[str]) -> bool:
        """Execute download command with progress tracking"""
        process = None
        try:
            self.log_info(f"Executing command: {' '.join(cmd)}")

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )

            # Store process in active downloads for cancellation
            task = asyncio.current_task()
            if task:
                self.active_downloads[download_id] = task

            # Read output line by line
            async for line in process.stdout:
                line_str = line.decode().strip()

                if line_str:
                    # Parse progress from yt-dlp output
                    await self._parse_progress(download_id, line_str)
                    self.log_debug(f"Download {download_id}: {line_str}")

            # Wait for process to complete
            await process.wait()

            success = process.returncode == 0

            if success:
                # Update download status to completed
                await self._update_download_status(download_id, "completed", 100.0)
            else:
                # Update download status to failed
                await self._update_download_status(download_id, "failed", 0.0)

            return success

        except asyncio.CancelledError:
            # Handle cancellation
            if process and process.returncode is None:
                process.terminate()
                await process.wait()

            await self._update_download_status(download_id, "cancelled", 0.0)
            raise

        except Exception as e:
            self.log_error(f"Download execution failed: {e}")
            await self._update_download_status(download_id, "failed", 0.0, str(e))
            return False

    async def _parse_progress(self, download_id: int, line: str) -> None:
        """Parse progress information from yt-dlp output"""

        try:
            # Look for download progress lines
            if "[download]" in line and "%" in line:
                # Extract percentage
                parts = line.split()
                for part in parts:
                    if part.endswith("%"):
                        try:
                            percentage = float(part.replace("%", ""))
                            await self._update_download_progress(
                                download_id, percentage
                            )
                            break
                        except ValueError:
                            pass

            # Look for speed information
            if "[download]" in line and ("/s" in line or "iB/s" in line):
                # Extract speed information
                speed_info = self._extract_speed(line)
                if speed_info:
                    await self._update_download_speed(download_id, speed_info)

        except Exception as e:
            self.log_debug(f"Failed to parse progress: {e}")

    def _extract_speed(self, line: str) -> Optional[float]:
        """Extract download speed from yt-dlp output"""

        try:
            # Look for speed patterns like "1.2MiB/s" or "500KiB/s"
            import re

            speed_pattern = r"(\d+\.?\d*)(K|M|G)iB/s"
            match = re.search(speed_pattern, line)

            if match:
                value = float(match.group(1))
                unit = match.group(2)

                # Convert to bytes per second
                multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
                return value * multipliers.get(unit, 1)

            return None

        except Exception:
            return None

    async def _update_download_status(
        self,
        download_id: int,
        status: str,
        progress: float = None,
        error_message: str = None,
    ) -> None:
        """Update download status in database"""

        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if progress is not None:
                update_data["progress"] = progress

            if error_message:
                update_data["error_message"] = error_message

            if status == "completed":
                update_data["completed_at"] = datetime.utcnow().isoformat()
            elif status == "downloading" and "started_at" not in update_data:
                update_data["started_at"] = datetime.utcnow().isoformat()

            # Store in Redis for real-time updates
            await redis_manager.set(
                f"download_status:{download_id}", update_data, expire=3600
            )

        except Exception as e:
            self.log_error(f"Failed to update download status: {e}")

    async def _update_download_progress(
        self, download_id: int, progress: float
    ) -> None:
        """Update download progress"""

        await self._update_download_status(download_id, "downloading", progress)

    async def _update_download_speed(self, download_id: int, speed: float) -> None:
        """Update download speed"""

        try:
            await redis_manager.set(
                f"download_speed:{download_id}",
                {"speed": speed, "timestamp": time.time()},
                expire=300,
            )
        except Exception as e:
            self.log_debug(f"Failed to update download speed: {e}")

    async def get_download_progress(self, download_id: int) -> Optional[Dict[str, Any]]:
        """Get current download progress"""

        try:
            status_data = await redis_manager.get(f"download_status:{download_id}")
            speed_data = await redis_manager.get(f"download_speed:{download_id}")

            if status_data:
                if speed_data:
                    status_data["current_speed"] = speed_data.get("speed")

                return status_data

            return None

        except Exception as e:
            self.log_error(f"Failed to get download progress: {e}")
            return None

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""

        try:
            queue_length = await redis_manager.get_queue_length(self.download_queue)
            active_count = len(self.active_downloads)

            return {
                "queue_length": queue_length,
                "active_downloads": active_count,
                "total_capacity": settings.MAX_CONCURRENT_DOWNLOADS,
                "available_slots": max(
                    0, settings.MAX_CONCURRENT_DOWNLOADS - active_count
                ),
            }

        except Exception as e:
            self.log_error(f"Failed to get queue status: {e}")
            return {
                "queue_length": 0,
                "active_downloads": 0,
                "total_capacity": settings.MAX_CONCURRENT_DOWNLOADS,
                "available_slots": settings.MAX_CONCURRENT_DOWNLOADS,
            }
