"""
YouTube service for video information extraction using yt-dlp
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging_config import LoggerMixin


class YouTubeService(LoggerMixin):
    """Service for YouTube video operations"""

    def __init__(self):
        self.yt_dlp_path = "yt-dlp"

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Extract video information without downloading"""

        try:
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-download",
                "--flat-playlist",
                "--no-warnings",
                url,
            ]

            # Run yt-dlp command
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.log_error(f"yt-dlp failed: {stderr.decode()}", url=url)
                raise Exception(f"Failed to extract video info: {stderr.decode()}")

            # Parse JSON output
            output_lines = stdout.decode().strip().split("\n")
            videos = []

            for line in output_lines:
                if line.strip():
                    try:
                        video_data = json.loads(line)
                        videos.append(video_data)
                    except json.JSONDecodeError:
                        continue

            if not videos:
                raise Exception("No video information found")

            # Process first video (or playlist info)
            main_video = videos[0]

            # Check if it's a playlist
            is_playlist = len(videos) > 1 or "entries" in main_video

            # Extract formats and qualities
            formats = self._extract_formats(main_video)
            qualities = self._extract_qualities(formats)

            # Extract subtitles
            subtitles = self._extract_subtitles(main_video)

            return {
                "id": main_video.get("id"),
                "title": main_video.get("title"),
                "description": main_video.get("description"),
                "uploader": main_video.get("uploader"),
                "uploader_id": main_video.get("uploader_id"),
                "channel": main_video.get("channel"),
                "channel_id": main_video.get("channel_id"),
                "duration": main_video.get("duration"),
                "view_count": main_video.get("view_count"),
                "like_count": main_video.get("like_count"),
                "upload_date": self._parse_date(main_video.get("upload_date")),
                "thumbnail": main_video.get("thumbnail"),
                "webpage_url": main_video.get("webpage_url"),
                "is_playlist": is_playlist,
                "playlist_count": len(videos) if is_playlist else None,
                "formats": formats,
                "qualities": qualities,
                "has_subtitles": len(subtitles) > 0,
                "subtitles": subtitles,
                "categories": main_video.get("categories", []),
                "tags": main_video.get("tags", []),
            }

        except Exception as e:
            self.log_error(f"Failed to get video info: {e}", url=url)
            raise

    async def get_playlist_videos(self, url: str) -> List[Dict[str, Any]]:
        """Get all videos in a playlist"""

        try:
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-download",
                "--flat-playlist",
                "--no-warnings",
                url,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"Failed to extract playlist: {stderr.decode()}")

            videos = []
            for line in stdout.decode().strip().split("\n"):
                if line.strip():
                    try:
                        video_data = json.loads(line)
                        videos.append(
                            {
                                "id": video_data.get("id"),
                                "title": video_data.get("title"),
                                "url": video_data.get("url"),
                                "duration": video_data.get("duration"),
                                "uploader": video_data.get("uploader"),
                            }
                        )
                    except json.JSONDecodeError:
                        continue

            return videos

        except Exception as e:
            self.log_error(f"Failed to get playlist videos: {e}", url=url)
            raise

    async def check_url_validity(self, url: str) -> bool:
        """Check if URL is valid YouTube URL"""

        try:
            cmd = [self.yt_dlp_path, "--simulate", "--no-warnings", url]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()
            return process.returncode == 0

        except Exception:
            return False

    def _extract_formats(self, video_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract available formats from video data"""

        formats = video_data.get("formats", [])
        processed_formats = []

        for fmt in formats:
            processed_formats.append(
                {
                    "format_id": fmt.get("format_id"),
                    "ext": fmt.get("ext"),
                    "resolution": fmt.get("resolution"),
                    "fps": fmt.get("fps"),
                    "vcodec": fmt.get("vcodec"),
                    "acodec": fmt.get("acodec"),
                    "filesize": fmt.get("filesize"),
                    "quality": fmt.get("quality"),
                    "format_note": fmt.get("format_note"),
                }
            )

        return processed_formats

    def _extract_qualities(self, formats: List[Dict[str, Any]]) -> List[str]:
        """Extract available qualities from formats"""

        qualities = set()

        for fmt in formats:
            resolution = fmt.get("resolution")
            if resolution and resolution != "audio only":
                # Extract height from resolution (e.g., "1920x1080" -> "1080")
                if "x" in resolution:
                    try:
                        height = resolution.split("x")[1]
                        qualities.add(height)
                    except (IndexError, ValueError):
                        pass

        # Sort qualities numerically
        try:
            sorted_qualities = sorted(qualities, key=int, reverse=True)
            return sorted_qualities
        except ValueError:
            return list(qualities)

    def _extract_subtitles(self, video_data: Dict[str, Any]) -> List[str]:
        """Extract available subtitle languages"""

        subtitles = video_data.get("subtitles", {})
        automatic_captions = video_data.get("automatic_captions", {})

        languages = set()
        languages.update(subtitles.keys())
        languages.update(automatic_captions.keys())

        return list(languages)

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse upload date string to datetime"""

        if not date_str:
            return None

        try:
            # yt-dlp usually returns dates in YYYYMMDD format
            if len(date_str) == 8 and date_str.isdigit():
                return datetime.strptime(date_str, "%Y%m%d")

            # Try other common formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            return None

        except Exception:
            return None
