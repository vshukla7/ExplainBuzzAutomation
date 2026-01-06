import whisper
import os
from google import genai
from dotenv import load_dotenv
import json

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

def Transcriber(audio_path):
    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio file not found")

    # ---------------- WHISPER ---------------- #
    model = whisper.load_model("small")  # medium if GPU

    result = model.transcribe(
        audio_path,
        language="hi",          # None if Hinglish
        fp16=False,
        verbose=False,
        no_speech_threshold=0.1,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,
    )

    raw_segments = [
        {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip()
        }
        for seg in result["segments"]
    ]

    # ---------------- AI AUDIO FORMATTER ---------------- #
    SYSTEM_PROMPT = """
You are an **Audio Intent Formatter and Action Segmenter** for AI short-form video editing.

You will receive **raw Hindi/Hinglish audio segments with timestamps**.

TASK:

1. If a segment contains multiple actions or events, **split it into separate units**.
2. Each output unit must represent **ONE clear visual action**, fully self-contained.
3. Clean the text for narration: **remove fillers, stutters, and irrelevant words**.
4. Extract a **short, clear intent in simple English** summarizing the action.
5. Generate **3–5 relevant visual tags** for each unit, describing the action.
6. Preserve and **adjust timestamps logically**:  
   - No overlaps between units.  
   - Keep chronological order.  
   - Merge tiny segments (<0.5s) with adjacent ones if needed for coherence.

STRICT RULES:

- Return **JSON only**. No explanations, no notes.  
- Maintain **chronological order**.  
- Output must be **ready for TTS narration and automated video generation pipelines**.  
- Make each unit **perfectly indexable** for video editing.

OUTPUT FORMAT:

{
  "audio_units": [
    {
      "audio_index": 0,
      "start": 0.0,
      "end": 3.2,
      "text": "Bachcha pedon ke beech se daudta hai aur chhoti lakdi par se jump karta hai.",
      "intent": "Boy running and jumping over log",
      "tags": ["boy", "running", "jump", "trees", "outdoor"]
    },
    {
      "audio_index": 1,
      "start": 3.2,
      "end": 6.0,
      "text": "Ladki paudhon ko paani deti hai aur kutta titar-bitar karta hua guzar jaata hai.",
      "intent": "Girl watering plants, dog passing by",
      "tags": ["girl", "watering", "dog", "plants", "garden"]
    }
  ]
}
"""


    user_prompt = f"""
Raw Audio Segments:
{json.dumps(raw_segments, ensure_ascii=False, indent=2)}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[SYSTEM_PROMPT, user_prompt]
    )

    # ---------------- SAFE JSON EXTRACTION ---------------- #
    text = response.text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == -1:
        raise ValueError("AI did not return valid JSON")

    formatted_audio = json.loads(text[start:end])

    # ---------------- FINAL RETURN ---------------- #
    return {
        "original_text": result["text"].strip(),
        "raw_segments": raw_segments,
        "audio_units": formatted_audio["audio_units"]
    }
