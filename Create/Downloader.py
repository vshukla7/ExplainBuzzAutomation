import os
import time
from pathlib import Path
from yt_dlp import YoutubeDL

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "Input"


def download_video(url: str, output_dir: str | os.PathLike | None = None) -> str:
    """
    Download a single video and merge into mp4.
    Returns the full path to the downloaded file.
    """
    target_dir = Path(output_dir) if output_dir else DEFAULT_INPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"video_{int(time.time())}.mp4"
    output_path = target_dir / filename

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(output_path),
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return str(output_path)


if __name__ == "__main__":
    link = input("Video link daalo (YT / Kuaishou / etc): ")
    path = download_video(link)
    print(path)
