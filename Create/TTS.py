import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

def text_to_speech(script: str) -> str:
    if not script.strip():
        raise ValueError("Script text is empty")

    os.makedirs("Audio", exist_ok=True)
    wav_filename = f"tts_{int(time.time())}.wav"
    wav_path = os.path.join("Audio", wav_filename)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/wav",
    }

    payload = {
    "text": script,
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
        "stability": 0.92,          # image me 92%
        "similarity_boost": 0.95,   # High (almost max)
        "speed": 1.1                # Faster side (approx max practical)
    }
}


    response = requests.post(url, json=payload, headers=headers, stream=True)
    if response.status_code != 200:
        raise RuntimeError(f"TTS failed: {response.status_code} - {response.text}")

    with open(wav_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return wav_path
