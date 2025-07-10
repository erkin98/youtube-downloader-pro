#!/usr/bin/env python3

import os
import subprocess
import sys
import argparse
import time
from concurrent.futures import ThreadPoolExecutor

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Download YouTube playlist videos or single videos.")
    parser.add_argument("-p", "--playlist", default="https://www.youtube.com/playlist?list=PLFAoLYoZ_IxY3mMaG0X9OrvJFyVHSOZRn",
                        help="YouTube playlist URL or single video URL (default: %(default)s)")
    parser.add_argument("-o", "--output-dir", default="downloads",
                        help="Directory to save downloaded videos (default: %(default)s)")
    parser.add_argument("-w", "--workers", type=int, default=4,
                        help="Number of parallel downloads (default: %(default)s)")
    parser.add_argument("-r", "--resolution", default="1080",
                        help="Maximum video resolution in pixels (e.g., 1080, 2160) (default: %(default)s)")
    parser.add_argument("--fps", type=int,
                        help="Desired video FPS (e.g., 30, 60). If not specified, best available FPS is chosen.")
    parser.add_argument("-f", "--format", dest="video_format", default="mp4",
                        help="Video format (default: %(default)s)")
    parser.add_argument("-s", "--start-index", type=int, default=1,
                        help="Start downloading from this position in playlist (default: %(default)s). Not used for single video URLs.")
    parser.add_argument("-e", "--end-index", type=int,
                        help="Stop downloading at this position in playlist (default: end of playlist). Not used for single video URLs.")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output from yt-dlp")
    parser.add_argument("--ignore-errors", action="store_true",
                        help="Continue on download errors (skip unavailable videos)")
    return parser.parse_args()

def check_dependencies():
    """Check if yt-dlp is installed"""
    try:
        subprocess.run(["yt-dlp", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("✅ yt-dlp is installed")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        print("❌ yt-dlp is not installed. Installing...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"], check=True)
            print("✅ yt-dlp installed successfully")
            return True
        except subprocess.SubprocessError:
            print("❌ Failed to install yt-dlp. Please install it manually:")
            print(f"{sys.executable} -m pip install yt-dlp")
            return False

def get_video_ids(target_url):
    """Get video IDs from the playlist or return the ID if it's a single video URL."""
    # Check if it's a playlist
    if "list=" in target_url:
        print(f"📋 Getting videos from playlist: {target_url}")
        command = [
            "yt-dlp", 
            "--flat-playlist", 
            "--print", "id", 
            target_url
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            video_ids = result.stdout.strip().split('\n')
            if not video_ids or not video_ids[0]: # Handle empty playlist or error
                 print(f"❌ No video IDs found for playlist: {target_url}. It might be empty or private.")
                 return [], True # Return empty list and is_playlist=True
            return video_ids, True # It's a playlist
        except subprocess.SubprocessError as e:
            print(f"❌ Failed to retrieve video IDs from playlist {target_url}: {e}")
            if e.stderr:
                 print(f"stderr: {e.stderr}")
            return [], True # Return empty list and is_playlist=True

    # Assume it's a single video URL, extract ID (yt-dlp can handle full URLs directly)
    print(f"📋 Target is a single video: {target_url}")
    # yt-dlp can take the full URL, no need to extract ID beforehand for downloading.
    # For consistency, we'll treat it as a list of one ID (the URL itself, yt-dlp handles it).
    return [target_url], False # It's a single video, not a playlist

def download_video(args_tuple):
    """Download a single video at specified resolution in specified format"""
    video_url_or_id, output_dir, resolution, video_format, fps, verbose, ignore_errors, index, total = args_tuple
    
    # If it's an ID (from playlist), construct URL. If it's a URL (single video), use as is.
    video_url = video_url_or_id if "://" in video_url_or_id else f"https://www.youtube.com/watch?v={video_url_or_id}"
    
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    
    fps_filter = f"[fps={fps}]" if fps else ""
    # Format string: try with specified FPS, then without, then best overall for resolution
    format_string = (
        f"bestvideo[height<={resolution}]{fps_filter}[ext={video_format}]+bestaudio[ext=m4a]/"  # With FPS, with ext
        f"bestvideo[height<={resolution}]{fps_filter}+bestaudio[ext=m4a]/"  # With FPS, any ext
        f"bestvideo[height<={resolution}][ext={video_format}]+bestaudio[ext=m4a]/"  # No FPS, with ext
        f"bestvideo[height<={resolution}]+bestaudio[ext=m4a]/"  # No FPS, any ext (general best for res)
        f"best[height<={resolution}]{fps_filter}/" # Fallback with FPS if specified
        f"best[height<={resolution}]" # Absolute fallback for resolution
    )
    
    command = [
        "yt-dlp",
        "-f", format_string,
        "-o", output_template,
        "--merge-output-format", video_format,
    ]
    # --no-playlist is important if we are passing a playlist URL but treating it as a single video context
    # However, since get_video_ids now returns the direct URL for single videos, 
    # and only IDs for playlist items, --no-playlist might cause issues if yt-dlp
    # tries to get playlist info from a single video URL that also happens to have a list param.
    # For playlist items (video_id), it's fine. For single video URLs, it's also fine.
    # Add --no-playlist to prevent downloading whole playlist if a video URL also contains playlist context
    command.append("--no-playlist")


    if not verbose:
        command.extend(["--quiet", "--progress"])
    
    command.append(video_url)
    
    start_time = time.time()
    process = None
    try:
        print(f"⏳ [{index}/{total}] Downloading: {video_url} (Res: {resolution}p{f', FPS: {fps}' if fps else ''})")
        process = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        if verbose and process.stdout:
            print(f"""yt-dlp output:
{process.stdout}""")
        duration = time.time() - start_time
        print(f"✅ [{index}/{total}] Downloaded: {video_url} ({duration:.1f}s)")
        return True
    except subprocess.CalledProcessError as e: # Explicitly catch CalledProcessError for stderr
        print(f"❌ [{index}/{total}] Failed to download {video_url}: {e}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        if ignore_errors:
            print(f"⚠️ Skipping video due to error (--ignore-errors is enabled)")
            return False
        else:
            raise e # Re-raise to be caught by the main loop
    except subprocess.SubprocessError as e: # Catch other subprocess errors
        print(f"❌ [{index}/{total}] Failed to download {video_url} (SubprocessError): {str(e)}")
        if ignore_errors:
            print(f"⚠️ Skipping video due to error (--ignore-errors is enabled)")
            return False
        else:
            raise e # Re-raise
    except Exception as e: # Catch any other unexpected errors
        print(f"❌ [{index}/{total}] An unexpected error occurred for {video_url}: {str(e)}")
        if ignore_errors:
            print(f"⚠️ Skipping video due to error (--ignore-errors is enabled)")
            return False
        else:
            raise e


def main():
    args = parse_arguments()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    if not check_dependencies():
        sys.exit(1)
    
    video_items, is_playlist = get_video_ids(args.playlist) # args.playlist is the URL from CLI

    if not video_items:
        print("ℹ️ No videos to download.")
        sys.exit(0)

    count_to_download = len(video_items)
    start_idx_user = args.start_index
    end_idx_user = args.end_index

    if is_playlist:
        print(f"📋 Found {len(video_items)} videos in playlist.")
        # Apply start and end indices only for playlists
        start_idx_0based = max(0, start_idx_user - 1)
        end_idx_0based = end_idx_user if end_idx_user else len(video_items)
        
        if start_idx_0based >= len(video_items):
            print(f"❌ Start index {start_idx_user} is greater than the number of videos ({len(video_items)}).")
            sys.exit(1)
        
        video_ids_to_download = video_items[start_idx_0based:end_idx_0based]
        count_to_download = len(video_ids_to_download)
        if count_to_download == 0 :
             print(f"ℹ️ No videos to download with current start/end indices for the playlist.")
             sys.exit(0)
        print(f"📋 Will download {count_to_download} videos (from playlist position {start_idx_0based + 1} to {start_idx_0based + count_to_download})")
    else: # Single video
        video_ids_to_download = video_items # This will be a list with one item (the URL itself)
        count_to_download = 1
        print(f"📋 Will download 1 video: {video_ids_to_download[0]}")


    download_tasks = []
    for i, video_id_or_url in enumerate(video_ids_to_download):
        download_tasks.append((
            video_id_or_url, 
            args.output_dir, 
            args.resolution, 
            args.video_format,
            args.fps, # New FPS argument
            args.verbose,
            args.ignore_errors,
            i + 1, 
            count_to_download
        ))
    
    successful_downloads = 0
    failed_downloads = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(download_video, task) for task in download_tasks]
        for future in futures:
            try:
                if future.result():
                    successful_downloads += 1
                else:
                    failed_downloads +=1 
            except Exception as e: 
                print(f"‼️ A critical error occurred for one of the downloads: {e}")
                failed_downloads += 1
                if not args.ignore_errors:
                    print("Halting further downloads as --ignore-errors is not set.")
                    for f in futures: # Attempt to cancel pending tasks
                        if not f.done():
                            f.cancel()
                    break 
    
    print(f"🎉 Download session complete!")
    print(f"Successfully downloaded: {successful_downloads}/{count_to_download} videos.")
    if failed_downloads > 0:
        print(f"Failed to download:    {failed_downloads}/{count_to_download} videos.")
    print(f"📁 Videos saved to: {os.path.abspath(args.output_dir)}")

if __name__ == "__main__":
    main() 