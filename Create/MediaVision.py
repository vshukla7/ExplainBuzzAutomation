from google import genai
import ffmpeg
import os
import tempfile
from dotenv import load_dotenv
from PIL import Image
import json
import re

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)
SYSTEM_PROMPT = """
You are an **Expert Short-Form Video Editor and YouTube Shorts Creator**.

Each input image is a video frame with an exact timestamp, sampled at 2 FPS.
Frames are **temporally ordered** and may contain multiple actions.

Your job is to **analyze the video frames** and return a **JSON of all scenes**, including multiple actions per scene with detailed descriptions that capture everything clearly for video generation and script alignment.

STRICT RULES:

1. Detect **clear scene boundaries**. Do not split actions mid-motion.  
2. Each scene must be **visually continuous** and coherent.  
3. Scene duration should ideally be **3–6 seconds**, but adjust if necessary to include full actions.  
4. **Do not overlap scenes.** Each frame belongs to exactly one scene.  
5. **Include multiple actions** in the scene description if they happen together or sequentially.  
6. Scene descriptions must be **detailed, natural, and concise**, suitable for matching with commentary scripts and TTS-ready narration.  
7. Return **JSON only**, strictly following the format below. No extra notes, explanations, or formatting.

OUTPUT FORMAT:

[
  {
    "scene_index": 0,
    "start": "00:00:00.000",
    "end": "00:00:05.000",
    "score": 0.92,
    "scene_description": "A boy runs between trees, then jumps over a small log, laughing as he lands."
  },
  {
    "scene_index": 1,
    "start": "00:00:05.000",
    "end": "00:00:10.000",
    "score": 0.88,
    "scene_description": "A girl waters plants while a dog runs past her, chasing a butterfly."
  }
]

ADDITIONAL GUIDANCE:

- Include **all visible actions** per scene. Multiple actions per scene are allowed.  
- Scene descriptions should be **clear enough to align with Hindi commentary scripts** like in {VideoData} from your other prompt.  
- Assign **confidence score** (0–1) for how visually clear the scene is.  
- Maintain **temporal order** and exact timestamps from the video frames.  
- JSON should be **fully ready for automated video assembly pipelines**, ensuring continuity, script sync, and TTS narration alignment.
"""


# ---------------- Helpers ---------------- #

def sec_to_hhmmss(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    ms = (sec - int(sec)) * 1000
    return f"{h:02}:{m:02}:{s:02}.{int(ms):03}"

def extract_frames(video_path, fps=1):
    temp_dir = tempfile.mkdtemp()
    frames = []

    (
        ffmpeg
        .input(video_path)
        .filter('fps', fps=fps)
        .output(os.path.join(temp_dir, 'frame_%05d.png'))
        .run(overwrite_output=True, quiet=True)
    )

    files = sorted(os.listdir(temp_dir))
    for i, f in enumerate(files):
        ts = sec_to_hhmmss(i / fps)
        img = Image.open(os.path.join(temp_dir, f))
        frames.append((ts, img))

    return frames, temp_dir

def extract_json(text):
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        raise ValueError("No JSON found in Gemini response")
    return json.loads(match.group())

# ---------------- Analyzer ---------------- #

def analyze_video(video_path):
    frames, temp_dir = extract_frames(video_path)

    contents = []
    for i, (ts, img) in enumerate(frames):
        contents.append(f"Frame {i+1} timestamp {ts}")
        contents.append(img)

    contents.append(SYSTEM_PROMPT)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    scenes = extract_json(response.text)

    # 🔑 enforce clean index flow
    clean_scenes = []
    for idx, sc in enumerate(scenes):
        clean_scenes.append({
            "scene_index": idx,
            "start": sc["start"],
            "end": sc["end"],
            "score": sc.get("score", 0.85),
            "scene_description": sc["scene_description"]
        })

    # cleanup
    for f in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, f))
    os.rmdir(temp_dir)

    return {
        "scenes": clean_scenes
    }

# ---------------- Run ---------------- #

if __name__ == "__main__":
    data = analyze_video("Output/video.mp4")
    print(json.dumps(data, indent=2))
