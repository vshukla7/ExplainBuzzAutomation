from google import genai
import json
import subprocess
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import ffmpeg

# ================= ENV ================= #
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# ================= OUTPUT ================= #
os.makedirs("Output", exist_ok=True)
output_path = f"Output/video_{int(time.time())}.mp4"

# ================= HELPERS ================= #
def get_media_duration(path: str) -> float:
    """Return media duration in seconds using ffprobe."""
    try:
        probe = ffmpeg.probe(path)
        return float(probe["format"]["duration"])
    except Exception:
        return 0.0

# ================= UTILS ================= #
def hhmmss_to_sec(t: str) -> float:
    try:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0  # fallback if format is invalid

def extract_json(text: str):
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == -1:
            return []
        return json.loads(text[start:end])
    except Exception as e:
        print("⚠️ Failed to parse JSON:", e)
        return []

# ================= INDEX → TIMELINE (SAFE) ================= #
def index_plan_to_timeline(index_plan, video_scenes, audio_units):
    timeline = []

    for pair in index_plan:
        # ✅ SUPPORT BOTH [a, v] and {"audio_index":a, "video_index":v}
        if isinstance(pair, list) and len(pair) == 2:
            ai, vi = pair
        elif isinstance(pair, dict):
            ai = pair.get("audio_index")
            vi = pair.get("video_index")
        else:
            print(f"⚠️ Invalid pair format: {pair}")
            continue

        if ai is None or vi is None:
            continue

        if not (0 <= ai < len(audio_units)) or not (0 <= vi < len(video_scenes)):
            print(f"⚠️ Skipping invalid index pair: {pair}")
            continue

        a = audio_units[ai]
        v = video_scenes[vi]

        timeline.append({
            "video_start": v.get("start", "00:00:00.000"),
            "video_end": v.get("end", "00:00:01.000"),
            "audio_start": a.get("start", 0.0),
            "audio_end": a.get("end", a.get("start", 0.0) + 1.0)
        })

    if not timeline:
        raise RuntimeError("Timeline empty after index mapping")

    return timeline

# ================= FFMPEG BUILDER ================= #
def build_video(video_path, audio_path, timeline, output_path, audio_units, bg_music=None):

    total_audio_duration = audio_units[-1]["end"] if audio_units else 10

    v_filters = []
    v_inputs = []

    for i, seg in enumerate(timeline):
        start = hhmmss_to_sec(seg["video_start"]) if isinstance(seg["video_start"], str) else seg["video_start"]
        end   = hhmmss_to_sec(seg["video_end"]) if isinstance(seg["video_end"], str) else seg["video_end"]

        if end <= start:
            continue

        v_filters.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
        v_inputs.append(f"[v{i}]")

    if not v_inputs:
        raise RuntimeError("No valid video segments found")

    video_filter = ";".join(v_filters) + f";{''.join(v_inputs)}concat=n={len(v_inputs)}:v=1:a=0[v]"

    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]

    if bg_music:
        cmd += ["-i", bg_music]

    a_filters = ["[1:a]volume=5[voice]"]

    if bg_music:
        a_filters += ["[2:a]volume=0.3[a_bg]", "[voice][a_bg]amix=inputs=2[aout]"]
    else:
        a_filters.append("[voice]anull[aout]")

    # Adding -map_metadata -1 to remove all metadata
    cmd += [
        "-filter_complex", video_filter + ";" + ";".join(a_filters),
        "-map", "[v]",
        "-map", "[aout]",
        "-t", str(total_audio_duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-map_metadata", "-1",  # remove all metadata
        "-movflags", "+faststart",  # optimize for streaming
        output_path
    ]

    print("\n[FFMPEG CMD]\n", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("\n✅ FINAL VIDEO CREATED:", output_path)


# ================= MANUAL FFMPEG BUILDER ================= #
def build_video_from_timeline(
    video_path: str,
    audio_path: str,
    segments: list,
    output_path: str | None = None,
    bg_music: str | None = None,
    audio_trim: dict | None = None,
    voice_volume: float = 5.0,
    bg_volume: float = 0.3,
):
    """
    Build a video using manual cut segments from the GUI timeline.
    segments: [{"video_start": 0, "video_end": 5}, ...]
    audio_trim: {"start": 0, "end": 12.5} optional voiceover trimming
    """
    if not segments:
        raise RuntimeError("No segments provided for manual render")

    output_path = output_path or f"Output/manual_{int(time.time())}.mp4"

    trim_start = float(audio_trim.get("start", 0) if audio_trim else 0)
    trim_end = audio_trim.get("end") if audio_trim else None

    full_audio_duration = get_media_duration(audio_path)
    if trim_end is None or trim_end <= 0:
        trim_end = full_audio_duration

    target_audio_duration = max(0.5, float(trim_end) - float(trim_start))

    v_filters = []
    v_inputs = []

    for i, seg in enumerate(segments):
        start = hhmmss_to_sec(seg.get("video_start")) if isinstance(seg.get("video_start"), str) else float(seg.get("video_start", 0))
        end = hhmmss_to_sec(seg.get("video_end")) if isinstance(seg.get("video_end"), str) else float(seg.get("video_end", 0))
        if end <= start:
            continue
        v_filters.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")
        v_inputs.append(f"[v{i}]")

    if not v_inputs:
        raise RuntimeError("No valid video segments in manual render")

    video_filter = ";".join(v_filters) + f";{''.join(v_inputs)}concat=n={len(v_inputs)}:v=1:a=0[v]"

    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]
    if bg_music:
        cmd += ["-i", bg_music]

    a_filters = [
        f"[1:a]atrim=start={trim_start}:end={trim_end},asetpts=PTS-STARTPTS,volume={voice_volume}[voice]"
    ]

    if bg_music:
        a_filters += [
            f"[2:a]atrim=end={target_audio_duration},asetpts=PTS-STARTPTS,volume={bg_volume}[a_bg]",
            "[voice][a_bg]amix=inputs=2[aout]",
        ]
    else:
        a_filters.append("[voice]anull[aout]")

    cmd += [
        "-filter_complex",
        video_filter + ";" + ";".join(a_filters),
        "-map",
        "[v]",
        "-map",
        "[aout]",
        "-t",
        str(target_audio_duration),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        output_path,
    ]

    print("\n[FFMPEG CMD]\n", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("\n✅ MANUAL VIDEO CREATED:", output_path)
    return output_path

# ================= COMMAND BUILDER ================= #
def CommandBuilder(AudioPath, VideoPath, VideoData, AudioData):

    audio_units = AudioData.get("audio_units", [])

    SYSTEM_PROMPT = f"""
You are a professional video editor.

TASK:
Map each AUDIO UNIT to ONE VIDEO SCENE using INDEX only.

STRICT RULES:
- audio_index must be between 0 and {len(audio_units)-1}
- video_index must be between 0 and {len(VideoData.get("scenes", []))-1}
- Never invent indexes
- One-to-one mapping
- Prefer same index
- Output length MUST equal audio units count
- Return ONLY JSON array of [audio_index, video_index] pairs
- Example format: [[0,0],[1,1],[2,2],[3,3]]
- **IMPORTANT:** Do not use video_index >= number of video scenes
- **IMPORTANT:** Do not use audio_index >= number of audio units

Audio Units:
{audio_units}

Video Scenes:
{VideoData.get("scenes", [])}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[SYSTEM_PROMPT]
    )

    index_plan = extract_json(getattr(response, "output_text", getattr(response, "text", "")))
    print("\n[Index Plan]", json.dumps(index_plan, indent=2))

    timeline = index_plan_to_timeline(index_plan, VideoData.get("scenes", []), audio_units)

    build_video(
        video_path=VideoPath,
        audio_path=AudioPath,
        timeline=timeline,
        audio_units=audio_units,
        output_path=output_path,
        bg_music="Audio/Aai.mp3"
    )

# ================= TEST ================= #
if __name__ == "__main__":

    AudioData = {
        "audio_units": [
            {"audio_index":0,"start":0.0,"end":2.5,"text":"बच्चे जंगल में घूम रहे हैं"},
            {"audio_index":1,"start":2.6,"end":5.0,"text":"पेड़ों के बीच दौड़ते हैं"},
            {"audio_index":2,"start":5.1,"end":7.0,"text":"एक बच्चा फिसलता है"},
            {"audio_index":3,"start":7.1,"end":9.0,"text":"तालाब के पास खेलते हैं"}
        ]
    }

    VideoData = {
        "scenes": [
            {"start":"00:00:00.000","end":"00:00:02.500"},
            {"start":"00:00:02.500","end":"00:00:05.000"},
            {"start":"00:00:05.000","end":"00:00:07.000"},
            {"start":"00:00:07.000","end":"00:00:09.000"}
        ]
    }

    CommandBuilder(
        AudioPath="Audio/q.wav",
        VideoPath="Input/1.mp4",
        VideoData=VideoData,
        AudioData=AudioData
    )
