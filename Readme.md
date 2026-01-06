# Code FLOW OF GLAN AUTOMATION

#### Step 1 -> Download And Extract the Video Data.

#### Step 2 -> Analyse The Video Data And Make A Script.

#### Step 3 -> Generate a MP3 Voiceover and save in The Audio Folder.

#### Step 4 -> Using AudioListner Tool Generate a Audio Timestamp.

#### Step 5 -> Make a Full (Video + Audio) TimeStamp Data.

#### Step 6 -> Api Call TO Gemini TO Make a Reels by cliping the video File only according to the Voiceover and Generate a FFMPEG Command
#### Step 7 -> Parse THE Response and Run THE Command Save Video in Output Folder.

#### step 8 -> Remove the Mp3 File.


> includes 1 Elleven Labs api CAll 

> includes 3 Gemini Api Call 

> includes 1 open-ai Wishper Local req.


## New React GUI Flow

- API server: `uvicorn Create.api_server:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev` (Vite, React)
- Steps on the GUI:
  1. Paste video link → Download.
  2. Paste your script → Generate ElevenLabs voiceover.
  3. Use the Twick timeline to set cuts, optional BGM, voiceover trim.
  4. Click Render to build the final video (served under `/media/output`).
