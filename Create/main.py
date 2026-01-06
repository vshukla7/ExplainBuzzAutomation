import time
import os
import shutil
import threading
import msvcrt  # For non-blocking input on Windows
from TTS import text_to_speech
from VideoMaker import CommandBuilder
from AudioListner import Transcriber
from MediaVision import analyze_video
from Downloader import download_video

# ===============================
# Gemini Rate Limiter
# ===============================
LAST_GEMINI_CALL = 0
GEMINI_GAP = 100  # seconds

def gemini_call(func, *args, **kwargs):
    global LAST_GEMINI_CALL
    now = time.time()
    elapsed = now - LAST_GEMINI_CALL
    if elapsed < GEMINI_GAP:
        wait_time = GEMINI_GAP - elapsed
        print(f"⏳ Waiting {wait_time:.1f}s to respect Gemini rate limit...")
        time.sleep(wait_time)
    result = func(*args, **kwargs)
    LAST_GEMINI_CALL = time.time()
    return result

# ===============================
# Generic retry wrapper
# ===============================
MAX_RETRIES = 3

def retry_step(step_name, func, *args, **kwargs):
    last_exception = None
    for attempt in range(1, MAX_RETRIES+1):
        try:
            print(f"\n🔹 Running step: {step_name} (Attempt {attempt})")
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            last_exception = e
            print(f"⚠️ Step '{step_name}' failed on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                print(f"⏳ Retrying '{step_name}'...")
                time.sleep(2)
            else:
                print(f"❌ Max retries reached for '{step_name}'")
                raise last_exception

# ===============================
# Script Management
# ===============================
SCRIPT_FILE = "script.txt"

def load_or_edit_script():
    if not os.path.exists(SCRIPT_FILE):
        with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
            f.write("")
        print(f"⚠️ Script file created: {SCRIPT_FILE}")

    while True:
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            script = f.read()

        print("\n📄 Current Script:\n")
        print(script or "⚠️ Script is empty.")

        print("\nOptions:")
        print("  y = approve script")
        print("  e = edit script manually")
        print("  (auto-approve in 10 seconds if no input)")

        choice = None
        start_time = time.time()

        # ---------- WAIT FOR INPUT OR TIMEOUT ----------
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getwch().lower()
                if ch in ("y", "e"):
                    choice = ch
                    break

            if time.time() - start_time > 10:
                choice = "y"
                print("\n⏱️ No input detected. Auto-approving script...")
                break

            time.sleep(0.1)

        # ---------- HANDLE CHOICE ----------
        if choice == "y":
            return script

        elif choice == "e":
            print("\n✏️ Opening script for manual editing...")
            try:
                os.startfile(SCRIPT_FILE)
            except Exception:
                print(f"Please open and edit manually: {SCRIPT_FILE}")

            # 🔒 HARD WAIT (no auto proceed)
            input("\n🛑 Press ENTER only AFTER you finish editing the script...")

            # Reload updated script and loop again
            continue

    if not os.path.exists(SCRIPT_FILE):
        with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
            f.write("")
        print(f"⚠️ Script file created: {SCRIPT_FILE}")

    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        script = f.read()

    proceed_event = threading.Event()
    user_choice = ["y"]  # default choice is approve

    def auto_approve():
        for i in range(10): #time here is in seconds
            if proceed_event.is_set():
                return
            time.sleep(1)
        print("\n⏱️ No input detected. Proceeding automatically...")
        proceed_event.set()

    def listen_input():
        print("\nType 'y' to approve or 'e' to edit (auto-proceeds in 10s): ")
        while not proceed_event.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getwch().lower()
                if ch in ["y", "e"]:
                    user_choice[0] = ch
                    proceed_event.set()
                    return

    while True:
        print("\n📄 Current Script:\n")
        print(script or "⚠️ Script is empty.")

        proceed_event.clear()
        user_choice[0] = "y"

        timer_thread = threading.Thread(target=auto_approve)
        input_thread = threading.Thread(target=listen_input)
        timer_thread.start()
        input_thread.start()

        timer_thread.join()
        input_thread.join()

        choice = user_choice[0]

        if choice == "y":
            return script
        elif choice == "e":
            try:
                os.startfile(SCRIPT_FILE)
            except Exception:
                print(f"✏️ Please edit manually: {SCRIPT_FILE}")
            input("Press Enter after editing...")
            with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
                script = f.read()
        else:
            print("❌ Invalid input.")

# ===============================
# Main Pipeline
# ===============================
def main():
    # -------- STEP 0: LINK INPUT & DOWNLOAD --------
    video_link = input("🔗 Enter video link (YT / Kuaishou / etc): ").strip()
    VideoPath = retry_step("Download Video", download_video, video_link)
    print(f"✅ Video downloaded at: {VideoPath}")

    # -------- STEP 1: ANALYZE VIDEO --------
    VideoData = retry_step("Analyze Video", analyze_video, VideoPath)
    print("✅ Video analysis complete.")

    # -------- STEP 2: SCRIPT GENERATION --------
    try:
        from ScriptWriter import ScriptWriter
        GeneratedScript = retry_step("Script Generation", gemini_call, ScriptWriter, VideoData)
        with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
            f.write(GeneratedScript)
        print("✅ Script generated.")
    except Exception as e:
        print("⚠️ Script auto-generation failed:", e)

    # -------- STEP 2b: Script approval --------
    Script = load_or_edit_script()
    print("✅ Script approved.")

    # -------- STEP 3: TEXT TO SPEECH --------
    AudioPath = retry_step("TTS", text_to_speech, Script)
    print(f"✅ Audio generated at: {AudioPath}")

    # -------- STEP 4: TRANSCRIPTION (with Gemini wait) --------
    AudioData = retry_step("Transcription", gemini_call, Transcriber, AudioPath)
    print("✅ Audio transcription complete.")

    # -------- STEP 5: VIDEO BUILDING --------
    retry_step(
        "Video Build",
        gemini_call,
        CommandBuilder,
        AudioPath,
        VideoPath,
        VideoData,
        AudioData
    )
    print("🎬 Final video created")

    # -------- STEP 6: CLEANUP CONFIRMATION --------
    cleanup = input(
        "\n🧹 Delete raw video & audio files? (y + Enter = delete, Enter = keep): "
    ).strip().lower()

    if cleanup == "y":
        try:
            if os.path.exists(VideoPath):
                os.remove(VideoPath)
            if os.path.exists(AudioPath):
                os.remove(AudioPath)
            print("🗑️ Raw video & audio deleted.")
        except Exception as e:
            print("⚠️ Cleanup failed:", e)
    else:
        print("📁 Raw files preserved.")

    print("✅ Pipeline Complete")

# ===============================
# ENTRY POINT
# ===============================
if __name__ == "__main__":
    main()
# ===============================