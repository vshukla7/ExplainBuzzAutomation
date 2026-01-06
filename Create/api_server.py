from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Optional

from Downloader import download_video
from TTS import text_to_speech
from VideoMaker import build_video_from_timeline


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "Input"
AUDIO_DIR = BASE_DIR / "Audio"
OUTPUT_DIR = BASE_DIR / "Output"


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Video URL (YouTube / Kuaishou / etc)")


class ScriptRequest(BaseModel):
    script: str = Field(..., description="Approved script text for TTS")


class Segment(BaseModel):
    video_start: float | str
    video_end: float | str


class AudioTrim(BaseModel):
    start: float = 0
    end: Optional[float] = None


class RenderRequest(BaseModel):
    video_path: str
    audio_path: str
    bgm_path: Optional[str] = None
    segments: List[Segment]
    audio_trim: Optional[AudioTrim] = None
    voice_volume: float = 5.0
    bg_volume: float = 0.3


app = FastAPI(title="Shorts Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _as_media_url(path: str, route: str) -> str:
    fname = Path(path).name
    return f"/media/{route}/{fname}"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/download")
def api_download(payload: DownloadRequest):
    try:
        video_path = download_video(payload.url, output_dir=INPUT_DIR)
        return {
            "video_path": video_path,
            "video_url": _as_media_url(video_path, "input"),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tts")
def api_tts(payload: ScriptRequest):
    script = payload.script.strip()
    if not script:
        raise HTTPException(status_code=400, detail="Script cannot be empty.")
    try:
        audio_path = text_to_speech(script)
        return {
            "audio_path": audio_path,
            "audio_url": _as_media_url(audio_path, "audio"),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/render")
def api_render(payload: RenderRequest):
    if not payload.segments:
        raise HTTPException(status_code=400, detail="At least one segment required.")

    try:
        output_path = build_video_from_timeline(
            video_path=payload.video_path,
            audio_path=payload.audio_path,
            segments=[s.dict() for s in payload.segments],
            output_path=str(OUTPUT_DIR / f"manual_{int(Path(payload.video_path).stat().st_mtime)}.mp4"),
            bg_music=payload.bgm_path,
            audio_trim=payload.audio_trim.dict() if payload.audio_trim else None,
            voice_volume=payload.voice_volume,
            bg_volume=payload.bg_volume,
        )
        return {
            "output_path": output_path,
            "output_url": _as_media_url(output_path, "output"),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/library")
def api_library():
    def list_files(directory: Path, exts: tuple[str, ...]):
        if not directory.exists():
            return []
        return [
            {
                "name": f.name,
                "path": str(f),
                "url": _as_media_url(f, directory.name.lower()),
            }
            for f in directory.iterdir()
            if f.suffix.lower() in exts
        ]

    return {
        "videos": list_files(INPUT_DIR, (".mp4", ".mov", ".mkv")),
        "audios": list_files(AUDIO_DIR, (".mp3", ".wav", ".m4a")),
        "outputs": list_files(OUTPUT_DIR, (".mp4", ".mov")),
    }


# ---------- Static mounts ----------
INPUT_DIR.mkdir(exist_ok=True, parents=True)
AUDIO_DIR.mkdir(exist_ok=True, parents=True)
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

app.mount("/media/input", StaticFiles(directory=INPUT_DIR), name="input-media")
app.mount("/media/audio", StaticFiles(directory=AUDIO_DIR), name="audio-media")
app.mount("/media/output", StaticFiles(directory=OUTPUT_DIR), name="output-media")
