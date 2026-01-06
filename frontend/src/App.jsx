import { useEffect, useRef, useState } from "react";
import api from "./api";
import { createSegment, secondsToHms } from "./lib/twick";

const StepHeader = ({ step, title, caption }) => (
  <div className="step-header">
    <div className="badge">{step}</div>
    <div>
      <div className="step-title">{title}</div>
      {caption && <div className="step-caption">{caption}</div>}
    </div>
  </div>
);

export default function App() {
  const videoRef = useRef(null);
  const audioRef = useRef(null);

  const [videoUrlInput, setVideoUrlInput] = useState("");
  const [downloaded, setDownloaded] = useState(null);
  const [scriptText, setScriptText] = useState("");
  const [audio, setAudio] = useState(null);
  const [segments, setSegments] = useState([]);
  const [audioTrim, setAudioTrim] = useState({ start: 0, end: "" });
  const [bgmPath, setBgmPath] = useState("");
  const [library, setLibrary] = useState({ videos: [], audios: [], outputs: [] });
  const [output, setOutput] = useState(null);
  const [status, setStatus] = useState("");
  const [rendering, setRendering] = useState(false);

  const fetchLibrary = async () => {
    try {
      const res = await api.get("/api/library");
      setLibrary(res.data);
      if (!bgmPath && res.data?.audios?.length) {
        setBgmPath(res.data.audios[0].path);
      }
    } catch (err) {
      setStatus(err.message);
    }
  };

  useEffect(() => {
    fetchLibrary();
  }, []);

  const handleDownload = async () => {
    if (!videoUrlInput.trim()) return;
    setStatus("Downloading video...");
    try {
      const res = await api.post("/api/download", { url: videoUrlInput.trim() });
      setDownloaded(res.data);
      setOutput(null);
      setStatus("Video downloaded. Preview below.");
      setSegments([]);
    } catch (err) {
      setStatus(err.response?.data?.detail || err.message);
    }
  };

  const handleTTS = async () => {
    if (!scriptText.trim()) {
      setStatus("Please paste your script first.");
      return;
    }
    setStatus("Generating voiceover...");
    try {
      const res = await api.post("/api/tts", { script: scriptText.trim() });
      setAudio(res.data);
      setOutput(null);
      setStatus("Voiceover generated.");
    } catch (err) {
      setStatus(err.response?.data?.detail || err.message);
    }
  };

  const addSegment = () => {
    const duration = videoRef.current?.duration || 15;
    setSegments((prev) => [...prev, createSegment(0, duration)]);
  };

  useEffect(() => {
    if (videoRef.current && downloaded) {
      const handler = () => {
        if (segments.length === 0) {
          addSegment();
        }
      };
      const node = videoRef.current;
      node.addEventListener("loadedmetadata", handler, { once: true });
      return () => node.removeEventListener("loadedmetadata", handler);
    }
  }, [downloaded]);

  const updateSegmentField = (idx, field, value) => {
    setSegments((prev) =>
      prev.map((seg, i) =>
        i === idx ? { ...seg, [field]: Number(value) || 0 } : seg
      )
    );
  };

  const removeSegment = (idx) =>
    setSegments((prev) => prev.filter((_, i) => i !== idx));

  const handleRender = async () => {
    if (!downloaded || !audio) {
      setStatus("Download a video and generate voiceover first.");
      return;
    }
    if (!segments.length) {
      setStatus("Add at least one cut segment.");
      return;
    }
    setRendering(true);
    setStatus("Rendering final video...");
    try {
      const payload = {
        video_path: downloaded.video_path,
        audio_path: audio.audio_path,
        bgm_path: bgmPath || null,
        segments: segments.map((s) => ({
          video_start: s.video_start,
          video_end: s.video_end,
        })),
        audio_trim: {
          start: Number(audioTrim.start || 0),
          end: audioTrim.end === "" ? null : Number(audioTrim.end),
        },
      };

      const res = await api.post("/api/render", payload);
      setOutput(res.data);
      setStatus("Render complete. Download your output below.");
      fetchLibrary();
    } catch (err) {
      setStatus(err.response?.data?.detail || err.message);
    } finally {
      setRendering(false);
    }
  };

  const videoDuration = videoRef.current?.duration || 0;

  return (
    <div className="page">
      <header>
        <div>
          <div className="title">Shorts Automation GUI</div>
          <div className="subtitle">
            Download → Paste Script → ElevenLabs TTS → Cut with Twick timeline → Render
          </div>
        </div>
        <div className="status">{status}</div>
      </header>

      <div className="card">
        <StepHeader
          step="1"
          title="Download source video"
          caption="Paste the link and let the backend fetch it."
        />
        <div className="row">
          <input
            value={videoUrlInput}
            onChange={(e) => setVideoUrlInput(e.target.value)}
            placeholder="https://youtube.com/..."
          />
          <button onClick={handleDownload}>Download</button>
        </div>
        {downloaded && (
          <div className="media-block">
            <video
              controls
              ref={videoRef}
              src={downloaded.video_url}
              className="video-player"
            />
            <div className="info">
              <div>Saved at: {downloaded.video_path}</div>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <StepHeader
          step="2"
          title="Provide script and generate ElevenLabs voiceover"
          caption="Paste your approved script. No auto-generation here."
        />
        <textarea
          rows={5}
          value={scriptText}
          onChange={(e) => setScriptText(e.target.value)}
          placeholder="Paste your final Hindi script..."
        />
        <div className="row end">
          <button onClick={handleTTS}>Generate voiceover</button>
        </div>
        {audio && (
          <div className="media-block">
            <audio controls ref={audioRef} src={audio.audio_url} />
            <div className="info">Saved at: {audio.audio_path}</div>
          </div>
        )}
      </div>

      <div className="card">
        <StepHeader
          step="3"
          title="Twick.js timeline"
          caption="Cut video/BGM/voiceover, then send to render."
        />

        <div className="row">
          <button onClick={addSegment}>Add segment</button>
          <label className="field">
            BGM
            <select value={bgmPath} onChange={(e) => setBgmPath(e.target.value)}>
              <option value="">-- no bgm --</option>
              {library.audios?.map((a) => (
                <option key={a.path} value={a.path}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="timeline">
          <div className="timeline-label">Video timeline</div>
          <div className="timeline-bar">
            {segments.map((seg, idx) => {
              const startPct = videoDuration
                ? (seg.video_start / videoDuration) * 100
                : 0;
              const endPct = videoDuration
                ? (seg.video_end / videoDuration) * 100
                : 0;
              return (
                <div
                  className="segment"
                  key={idx}
                  style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
                  title={`${secondsToHms(seg.video_start)} → ${secondsToHms(seg.video_end)}`}
                />
              );
            })}
          </div>
        </div>

        {segments.map((seg, idx) => (
          <div key={idx} className="segment-editor">
            <div className="segment-title">Cut {idx + 1}</div>
            <div className="row">
              <label className="field">
                Start (s)
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={seg.video_start}
                  onChange={(e) => updateSegmentField(idx, "video_start", e.target.value)}
                />
              </label>
              <label className="field">
                End (s)
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={seg.video_end}
                  onChange={(e) => updateSegmentField(idx, "video_end", e.target.value)}
                />
              </label>
              <button className="ghost" onClick={() => removeSegment(idx)}>
                Remove
              </button>
            </div>
          </div>
        ))}

        <div className="segment-editor">
          <div className="segment-title">Voiceover trim</div>
          <div className="row">
            <label className="field">
              Start (s)
              <input
                type="number"
                step="0.1"
                value={audioTrim.start}
                onChange={(e) => setAudioTrim((p) => ({ ...p, start: e.target.value }))}
              />
            </label>
            <label className="field">
              End (s, blank = full)
              <input
                type="number"
                step="0.1"
                value={audioTrim.end}
                onChange={(e) => setAudioTrim((p) => ({ ...p, end: e.target.value }))}
              />
            </label>
          </div>
        </div>

        <div className="row end">
          <button disabled={rendering} onClick={handleRender}>
            {rendering ? "Rendering..." : "Render with Twick cuts"}
          </button>
        </div>
      </div>

      {output && (
        <div className="card">
          <StepHeader
            step="4"
            title="Download final video"
            caption="Generated with your cuts and voiceover."
          />
          <video controls src={output.output_url} className="video-player" />
          <div className="info">Saved at: {output.output_path}</div>
        </div>
      )}
    </div>
  );
}
