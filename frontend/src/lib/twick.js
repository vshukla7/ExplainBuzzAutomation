export function createSegment(start = 0, end = 5) {
  return {
    video_start: Number(start) || 0,
    video_end: Number(end) || 5,
  };
}

export function secondsToHms(sec = 0) {
  const s = Math.max(0, Number(sec) || 0);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = Math.floor(s % 60);
  return [h, m, r]
    .map((v) => v.toString().padStart(2, "0"))
    .join(":");
}
