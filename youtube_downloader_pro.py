#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# GUI imports (optional)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


@dataclass
class DownloadJob:
    """Represents a download job with all its parameters"""

    url: str
    output_dir: str = "downloads"
    resolution: str = "1080"
    fps: Optional[int] = None
    format: str = "mp4"
    audio_only: bool = False
    extract_audio: bool = False
    audio_format: str = "mp3"
    subtitles: bool = False
    auto_subtitles: bool = False
    subtitle_langs: List[str] = None
    thumbnail: bool = False
    metadata: bool = True
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    speed: Optional[float] = None
    playlist_start: Optional[int] = None
    playlist_end: Optional[int] = None
    status: str = "pending"  # pending, downloading, completed, failed
    progress: float = 0.0
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.subtitle_langs is None:
            self.subtitle_langs = ["en"]
        if self.created_at is None:
            self.created_at = datetime.now()


class DatabaseManager:
    """Manages SQLite database for download history and queue"""

    def __init__(self, db_path: str = "downloads.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            output_dir TEXT,
            resolution TEXT,
            fps INTEGER,
            format TEXT,
            audio_only BOOLEAN,
            extract_audio BOOLEAN,
            audio_format TEXT,
            subtitles BOOLEAN,
            auto_subtitles BOOLEAN,
            subtitle_langs TEXT,
            thumbnail BOOLEAN,
            metadata BOOLEAN,
            start_time TEXT,
            end_time TEXT,
            speed REAL,
            playlist_start INTEGER,
            playlist_end INTEGER,
            status TEXT,
            progress REAL,
            file_path TEXT,
            error_message TEXT,
            created_at TIMESTAMP,
            completed_at TIMESTAMP
        )
        """
        )

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS video_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            download_id INTEGER,
            title TEXT,
            uploader TEXT,
            duration INTEGER,
            view_count INTEGER,
            like_count INTEGER,
            upload_date TEXT,
            description TEXT,
            tags TEXT,
            FOREIGN KEY (download_id) REFERENCES downloads (id)
        )
        """
        )

        conn.commit()
        conn.close()

    def save_job(self, job: DownloadJob) -> int:
        """Save a download job to database and return its ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
        INSERT INTO downloads (
            url, output_dir, resolution, fps, format, audio_only, extract_audio,
            audio_format, subtitles, auto_subtitles, subtitle_langs, thumbnail,
            metadata, start_time, end_time, speed, playlist_start, playlist_end,
            status, progress, file_path, error_message, created_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                job.url,
                job.output_dir,
                job.resolution,
                job.fps,
                job.format,
                job.audio_only,
                job.extract_audio,
                job.audio_format,
                job.subtitles,
                job.auto_subtitles,
                json.dumps(job.subtitle_langs),
                job.thumbnail,
                job.metadata,
                job.start_time,
                job.end_time,
                job.speed,
                job.playlist_start,
                job.playlist_end,
                job.status,
                job.progress,
                job.file_path,
                job.error_message,
                job.created_at,
                job.completed_at,
            ),
        )

        job_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return job_id

    def update_job(self, job_id: int, **kwargs):
        """Update a download job in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [job_id]

        cursor.execute(f"UPDATE downloads SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def get_job_history(self, limit: int = 100) -> List[Dict]:
        """Get download history from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
        SELECT * FROM downloads 
        ORDER BY created_at DESC 
        LIMIT ?
        """,
            (limit,),
        )

        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return results


class AdvancedYouTubeDownloader:
    """Advanced YouTube downloader with queue management, GUI, and extensive features"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.download_queue = queue.Queue()
        self.active_downloads = {}
        self.db = DatabaseManager()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = True

        # Start queue processor
        self.queue_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.queue_thread.start()

    def check_dependencies(self):
        """Check and install required dependencies"""
        try:
            subprocess.run(
                ["yt-dlp", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            print("✅ yt-dlp is installed")
        except (subprocess.SubprocessError, FileNotFoundError):
            print("❌ yt-dlp not installed. Installing...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "yt-dlp"], check=True
                )
                print("✅ yt-dlp installed successfully")
            except subprocess.SubprocessError:
                print("❌ Failed to install yt-dlp")
                return False

        # Check for optional dependencies
        optional_deps = {
            "ffmpeg": ["ffmpeg", "-version"],
            "aria2c": ["aria2c", "--version"],
        }

        for dep, cmd in optional_deps.items():
            try:
                subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                )
                print(f"✅ {dep} is available")
            except (subprocess.SubprocessError, FileNotFoundError):
                print(f"⚠️  {dep} not available (optional but recommended)")

        return True

    def get_video_info(self, url: str) -> Dict:
        """Extract video information without downloading"""
        try:
            cmd = ["yt-dlp", "--dump-json", "--no-download", "--flat-playlist", url]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Handle both single videos and playlists
            lines = result.stdout.strip().split("\n")
            videos = []

            for line in lines:
                if line.strip():
                    try:
                        video_info = json.loads(line)
                        videos.append(video_info)
                    except json.JSONDecodeError:
                        continue

            return {"videos": videos, "count": len(videos)}

        except subprocess.SubprocessError as e:
            return {"error": str(e), "videos": [], "count": 0}

    def build_command(self, job: DownloadJob) -> List[str]:
        """Build yt-dlp command based on job parameters"""
        cmd = ["yt-dlp"]

        # Output template and directory
        os.makedirs(job.output_dir, exist_ok=True)
        output_template = os.path.join(job.output_dir, "%(title)s.%(ext)s")
        cmd.extend(["-o", output_template])

        # Format selection
        if job.audio_only:
            cmd.extend(["-f", "bestaudio"])
        else:
            fps_filter = f"[fps<={job.fps}]" if job.fps else ""
            format_str = f"bestvideo[height<={job.resolution}]{fps_filter}+bestaudio/best[height<={job.resolution}]"
            cmd.extend(["-f", format_str])

        # Audio extraction
        if job.extract_audio:
            cmd.extend(["--extract-audio", "--audio-format", job.audio_format])

        # Remux to specified format if not audio-only
        if not job.audio_only and not job.extract_audio:
            cmd.extend(["--remux-video", job.format])

        # Subtitles
        if job.subtitles:
            cmd.append("--write-subs")
            if job.subtitle_langs:
                cmd.extend(["--sub-langs", ",".join(job.subtitle_langs)])

        if job.auto_subtitles:
            cmd.append("--write-auto-subs")

        # Thumbnail
        if job.thumbnail:
            cmd.append("--write-thumbnail")

        # Metadata
        if job.metadata:
            cmd.extend(["--write-info-json", "--write-description"])

        # Time range
        if job.start_time:
            cmd.extend(
                [
                    "--external-downloader",
                    "ffmpeg",
                    "--external-downloader-args",
                    f"-ss {job.start_time}",
                ]
            )

        if job.end_time:
            if not job.start_time:
                cmd.extend(["--external-downloader", "ffmpeg"])
            cmd.extend(["--external-downloader-args", f"-to {job.end_time}"])

        # Playlist range
        if job.playlist_start:
            cmd.extend(["--playlist-start", str(job.playlist_start)])

        if job.playlist_end:
            cmd.extend(["--playlist-end", str(job.playlist_end)])

        # Speed limit
        if job.speed:
            cmd.extend(["--limit-rate", f"{job.speed}M"])

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
        cmd.append(job.url)

        return cmd

    def download_with_progress(self, job: DownloadJob, job_id: int) -> bool:
        """Download a video with progress tracking"""
        try:
            cmd = self.build_command(job)

            print(f"🚀 Starting download: {job.url}")
            print(f"📁 Output: {job.output_dir}")
            print(f"⚙️  Command: {' '.join(cmd)}")

            # Update status to downloading
            self.db.update_job(job_id, status="downloading", progress=0.0)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            output_lines = []
            for line in process.stdout:
                output_lines.append(line.strip())

                # Parse progress from yt-dlp output
                if "[download]" in line and "%" in line:
                    try:
                        # Extract percentage
                        parts = line.split()
                        for part in parts:
                            if part.endswith("%"):
                                percentage = float(part.replace("%", ""))
                                self.db.update_job(job_id, progress=percentage)
                                break
                    except (ValueError, IndexError):
                        pass

                print(line.strip())

            process.wait()

            if process.returncode == 0:
                self.db.update_job(
                    job_id,
                    status="completed",
                    progress=100.0,
                    completed_at=datetime.now(),
                )
                print(f"✅ Download completed: {job.url}")
                return True
            else:
                error_msg = "\n".join(output_lines[-10:])  # Last 10 lines
                self.db.update_job(
                    job_id,
                    status="failed",
                    error_message=error_msg,
                    completed_at=datetime.now(),
                )
                print(f"❌ Download failed: {job.url}")
                return False

        except Exception as e:
            self.db.update_job(
                job_id,
                status="failed",
                error_message=str(e),
                completed_at=datetime.now(),
            )
            print(f"❌ Error downloading {job.url}: {e}")
            return False

    def add_download(self, job: DownloadJob) -> int:
        """Add a download job to the queue"""
        job_id = self.db.save_job(job)
        self.download_queue.put((job, job_id))
        print(f"📋 Added to queue: {job.url} (ID: {job_id})")
        return job_id

    def _process_queue(self):
        """Process the download queue"""
        while self.running:
            try:
                job, job_id = self.download_queue.get(timeout=1)

                # Submit to thread pool
                future = self.executor.submit(self.download_with_progress, job, job_id)
                self.active_downloads[job_id] = future

                # Clean up completed downloads
                completed = [
                    jid for jid, fut in self.active_downloads.items() if fut.done()
                ]
                for jid in completed:
                    del self.active_downloads[jid]

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Queue processing error: {e}")

    def get_queue_status(self) -> Dict:
        """Get current queue and download status"""
        return {
            "queue_size": self.download_queue.qsize(),
            "active_downloads": len(self.active_downloads),
            "total_capacity": self.max_workers,
        }

    def shutdown(self):
        """Shutdown the downloader gracefully"""
        print("🛑 Shutting down downloader...")
        self.running = False
        self.executor.shutdown(wait=True)


def create_gui(downloader: AdvancedYouTubeDownloader):
    """Create a GUI interface for the downloader"""

    class DownloaderGUI:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Advanced YouTube Downloader Pro")
            self.root.geometry("800x600")
            self.downloader = downloader

            self.create_widgets()

        def create_widgets(self):
            # Create notebook for tabs
            notebook = ttk.Notebook(self.root)
            notebook.pack(fill="both", expand=True, padx=10, pady=10)

            # Download tab
            download_frame = ttk.Frame(notebook)
            notebook.add(download_frame, text="Download")

            # URL input
            ttk.Label(download_frame, text="URL(s):").pack(anchor="w")
            self.url_text = scrolledtext.ScrolledText(download_frame, height=3)
            self.url_text.pack(fill="x", pady=(0, 10))

            # Options frame
            options_frame = ttk.LabelFrame(download_frame, text="Options")
            options_frame.pack(fill="x", pady=(0, 10))

            # Resolution and format
            row1 = ttk.Frame(options_frame)
            row1.pack(fill="x", padx=5, pady=5)

            ttk.Label(row1, text="Resolution:").pack(side="left")
            self.resolution_var = tk.StringVar(value="1080")
            resolution_combo = ttk.Combobox(
                row1,
                textvariable=self.resolution_var,
                values=["720", "1080", "1440", "2160", "4320"],
                width=10,
            )
            resolution_combo.pack(side="left", padx=(5, 20))

            ttk.Label(row1, text="FPS:").pack(side="left")
            self.fps_var = tk.StringVar()
            fps_combo = ttk.Combobox(
                row1,
                textvariable=self.fps_var,
                values=["", "30", "60", "120"],
                width=10,
            )
            fps_combo.pack(side="left", padx=(5, 20))

            ttk.Label(row1, text="Format:").pack(side="left")
            self.format_var = tk.StringVar(value="mp4")
            format_combo = ttk.Combobox(
                row1,
                textvariable=self.format_var,
                values=["mp4", "mkv", "webm"],
                width=10,
            )
            format_combo.pack(side="left", padx=(5, 0))

            # Checkboxes
            check_frame = ttk.Frame(options_frame)
            check_frame.pack(fill="x", padx=5, pady=5)

            self.audio_only_var = tk.BooleanVar()
            ttk.Checkbutton(
                check_frame, text="Audio Only", variable=self.audio_only_var
            ).pack(side="left")

            self.extract_audio_var = tk.BooleanVar()
            ttk.Checkbutton(
                check_frame, text="Extract Audio", variable=self.extract_audio_var
            ).pack(side="left")

            self.subtitles_var = tk.BooleanVar()
            ttk.Checkbutton(
                check_frame, text="Subtitles", variable=self.subtitles_var
            ).pack(side="left")

            self.thumbnail_var = tk.BooleanVar()
            ttk.Checkbutton(
                check_frame, text="Thumbnail", variable=self.thumbnail_var
            ).pack(side="left")

            # Output directory
            dir_frame = ttk.Frame(options_frame)
            dir_frame.pack(fill="x", padx=5, pady=5)

            ttk.Label(dir_frame, text="Output Directory:").pack(side="left")
            self.output_dir_var = tk.StringVar(value="downloads")
            self.output_dir_entry = ttk.Entry(
                dir_frame, textvariable=self.output_dir_var
            )
            self.output_dir_entry.pack(side="left", fill="x", expand=True, padx=(5, 5))

            ttk.Button(dir_frame, text="Browse", command=self.browse_directory).pack(
                side="right"
            )

            # Download button
            ttk.Button(
                download_frame, text="Add to Queue", command=self.add_downloads
            ).pack(pady=10)

            # Progress tab
            progress_frame = ttk.Frame(notebook)
            notebook.add(progress_frame, text="Progress")

            # Progress tree
            columns = ("ID", "URL", "Status", "Progress", "Output")
            self.progress_tree = ttk.Treeview(
                progress_frame, columns=columns, show="headings"
            )

            for col in columns:
                self.progress_tree.heading(col, text=col)
                self.progress_tree.column(col, width=100)

            self.progress_tree.pack(fill="both", expand=True)

            # Refresh button
            ttk.Button(
                progress_frame, text="Refresh", command=self.refresh_progress
            ).pack(pady=5)

            # History tab
            history_frame = ttk.Frame(notebook)
            notebook.add(history_frame, text="History")

            # History tree
            self.history_tree = ttk.Treeview(
                history_frame, columns=columns, show="headings"
            )

            for col in columns:
                self.history_tree.heading(col, text=col)
                self.history_tree.column(col, width=100)

            self.history_tree.pack(fill="both", expand=True)

            # Load history
            self.load_history()

        def browse_directory(self):
            directory = filedialog.askdirectory()
            if directory:
                self.output_dir_var.set(directory)

        def add_downloads(self):
            urls = self.url_text.get("1.0", tk.END).strip().split("\n")
            urls = [url.strip() for url in urls if url.strip()]

            if not urls:
                messagebox.showwarning("Warning", "Please enter at least one URL")
                return

            for url in urls:
                try:
                    job = DownloadJob(
                        url=url,
                        output_dir=self.output_dir_var.get(),
                        resolution=self.resolution_var.get(),
                        fps=int(self.fps_var.get()) if self.fps_var.get() else None,
                        format=self.format_var.get(),
                        audio_only=self.audio_only_var.get(),
                        extract_audio=self.extract_audio_var.get(),
                        subtitles=self.subtitles_var.get(),
                        thumbnail=self.thumbnail_var.get(),
                    )

                    self.downloader.add_download(job)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add {url}: {e}")

            self.url_text.delete("1.0", tk.END)
            messagebox.showinfo("Success", f"Added {len(urls)} download(s) to queue")

        def refresh_progress(self):
            # Clear existing items
            for item in self.progress_tree.get_children():
                self.progress_tree.delete(item)

            # Load recent downloads
            recent = self.downloader.db.get_job_history(50)
            for job in recent:
                if job["status"] in ["pending", "downloading"]:
                    self.progress_tree.insert(
                        "",
                        "end",
                        values=(
                            job["id"],
                            (
                                job["url"][:50] + "..."
                                if len(job["url"]) > 50
                                else job["url"]
                            ),
                            job["status"],
                            f"{job['progress']:.1f}%",
                            job["output_dir"],
                        ),
                    )

        def load_history(self):
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            # Load all history
            history = self.downloader.db.get_job_history(100)
            for job in history:
                self.history_tree.insert(
                    "",
                    "end",
                    values=(
                        job["id"],
                        job["url"][:50] + "..." if len(job["url"]) > 50 else job["url"],
                        job["status"],
                        f"{job['progress']:.1f}%",
                        job["output_dir"],
                    ),
                )

        def run(self):
            self.root.mainloop()

    gui = DownloaderGUI()
    return gui


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Advanced YouTube Downloader Pro")

    # Basic options
    parser.add_argument("-u", "--url", help="Video/playlist URL(s)", nargs="+")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="downloads",
        help="Output directory (default: downloads)",
    )
    parser.add_argument(
        "-r", "--resolution", default="1080", help="Maximum resolution (default: 1080)"
    )
    parser.add_argument("--fps", type=int, help="Target FPS")
    parser.add_argument(
        "-f", "--format", default="mp4", help="Video format (default: mp4)"
    )

    # Audio options
    parser.add_argument("--audio-only", action="store_true", help="Download audio only")
    parser.add_argument(
        "--extract-audio", action="store_true", help="Extract audio from video"
    )
    parser.add_argument(
        "--audio-format",
        default="mp3",
        help="Audio format for extraction (default: mp3)",
    )

    # Subtitle options
    parser.add_argument("--subtitles", action="store_true", help="Download subtitles")
    parser.add_argument(
        "--auto-subtitles",
        action="store_true",
        help="Download auto-generated subtitles",
    )
    parser.add_argument(
        "--subtitle-langs",
        nargs="+",
        default=["en"],
        help="Subtitle languages (default: en)",
    )

    # Additional options
    parser.add_argument("--thumbnail", action="store_true", help="Download thumbnail")
    parser.add_argument(
        "--metadata",
        action="store_true",
        default=True,
        help="Save metadata (default: True)",
    )
    parser.add_argument("--start-time", help="Start time (HH:MM:SS)")
    parser.add_argument("--end-time", help="End time (HH:MM:SS)")
    parser.add_argument("--speed", type=float, help="Speed limit in MB/s")

    # Playlist options
    parser.add_argument("--playlist-start", type=int, help="Playlist start index")
    parser.add_argument("--playlist-end", type=int, help="Playlist end index")

    # System options
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Number of parallel downloads (default: 4)",
    )
    parser.add_argument("--gui", action="store_true", help="Launch GUI interface")
    parser.add_argument("--batch-file", help="File containing URLs to download")
    parser.add_argument(
        "--info-only", action="store_true", help="Show video info without downloading"
    )

    return parser.parse_args()


def main():
    """Main function"""
    args = parse_arguments()

    # Create downloader instance
    downloader = AdvancedYouTubeDownloader(max_workers=args.workers)

    # Check dependencies
    if not downloader.check_dependencies():
        sys.exit(1)

    try:
        # GUI mode
        if args.gui:
            if not GUI_AVAILABLE:
                print("❌ GUI not available. Install tkinter to use GUI mode.")
                sys.exit(1)

            print("🎨 Launching GUI...")
            gui = create_gui(downloader)
            gui.run()
            return

        # Collect URLs
        urls = []
        if args.url:
            urls.extend(args.url)

        if args.batch_file:
            try:
                with open(args.batch_file, "r") as f:
                    urls.extend([line.strip() for line in f if line.strip()])
            except FileNotFoundError:
                print(f"❌ Batch file not found: {args.batch_file}")
                sys.exit(1)

        if not urls:
            print("❌ No URLs provided. Use --url, --batch-file, or --gui")
            sys.exit(1)

        # Info only mode
        if args.info_only:
            for url in urls:
                print(f"\n📺 Getting info for: {url}")
                info = downloader.get_video_info(url)
                if "error" in info:
                    print(f"❌ Error: {info['error']}")
                else:
                    print(f"📊 Found {info['count']} video(s)")
                    for i, video in enumerate(info["videos"][:5], 1):
                        title = video.get("title", "Unknown")
                        duration = video.get("duration", "Unknown")
                        print(f"  {i}. {title} ({duration}s)")
            return

        # Create download jobs
        for url in urls:
            job = DownloadJob(
                url=url,
                output_dir=args.output_dir,
                resolution=args.resolution,
                fps=args.fps,
                format=args.format,
                audio_only=args.audio_only,
                extract_audio=args.extract_audio,
                audio_format=args.audio_format,
                subtitles=args.subtitles,
                auto_subtitles=args.auto_subtitles,
                subtitle_langs=args.subtitle_langs,
                thumbnail=args.thumbnail,
                metadata=args.metadata,
                start_time=args.start_time,
                end_time=args.end_time,
                speed=args.speed,
                playlist_start=args.playlist_start,
                playlist_end=args.playlist_end,
            )

            downloader.add_download(job)

        # Wait for all downloads to complete
        print(f"⏳ Waiting for {len(urls)} download(s) to complete...")

        while True:
            status = downloader.get_queue_status()
            if status["queue_size"] == 0 and status["active_downloads"] == 0:
                break

            print(
                f"📊 Queue: {status['queue_size']}, Active: {status['active_downloads']}"
            )
            time.sleep(2)

        print("🎉 All downloads completed!")

    except KeyboardInterrupt:
        print("\n🛑 Download interrupted by user")
    finally:
        downloader.shutdown()


if __name__ == "__main__":
    main()
