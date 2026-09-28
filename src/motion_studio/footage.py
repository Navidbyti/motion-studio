"""Supplied footage: analyse, conform, reframe, and find the footage's own beat.

- `analyze()` probes every clip in footage/ and writes footage/footage.json:
  format, audible sound, letterbox/pillarbox content box, and *visual events*
  (flashes, hard cuts, motion peaks) that the beat map can align to music.
  It also writes a 1-fps contact sheet per clip for the director's reframing.
- `conform()` makes constant-frame-rate H.264 copies at the project fps (seek
  accurate, no judder decisions left to the renderer) plus a WAV of any
  natural sound, because HyperFrames plays audio from separate <audio> tags.
- `reframe()` validates footage/reframe.json (crop keyframes in source pixels)
  against the canvas aspect, the content box, "avoid" boxes (burn-ins, logos)
  and upscale limits, then writes reframe.js for Studio.reframe().
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from .util import StudioError, ffprobe, read_json, run, sha256_file, write_json

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
MAX_UPSCALE_WARN = 1.5
MAX_UPSCALE_ERROR = 3.0


def clip_id(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)


def _audible(path: Path) -> float | None:
    proc = run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"], check=False)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", proc.stderr)
    return float(m.group(1)) if m else None


def _content_box(path: Path, w: int, h: int, duration: float) -> list[int]:
    """Picture area without letterbox/pillarbox bars, as [x, y, w, h] in source pixels.

    Bars are constant, near-black and symmetric from the frame edges in every
    frame. Dark picture content (night sky, space) is not symmetric and not
    constant, so it is kept.
    """
    sw = 320
    sh = max(2, int(round(h * sw / w / 2)) * 2)
    n = 12
    import subprocess  # binary output
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={n / max(duration, 0.5):.4f},scale={sw}:{sh},format=gray",
                          "-frames:v", str(n), "-f", "rawvideo", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8)
    if frames.size < sw * sh:
        return [0, 0, w, h]
    frames = frames[: (frames.size // (sw * sh)) * sw * sh].reshape(-1, sh, sw).astype(np.int16)
    col_max = frames.max(axis=(0, 1))
    row_max = frames.max(axis=(0, 2))
    col_std = frames.std(axis=(0, 1))
    row_std = frames.std(axis=(0, 2))

    def run_len(values: np.ndarray, spread: np.ndarray) -> int:
        k = 0
        while k < len(values) and values[k] <= 8 and spread[k] <= 1.5:
            k += 1
        return k

    left, right = run_len(col_max, col_std), run_len(col_max[::-1], col_std[::-1])
    top, bottom = run_len(row_max, row_std), run_len(row_max[::-1], row_std[::-1])
    bar_x = min(left, right) if min(left, right) >= 2 and abs(left - right) <= max(3, 0.03 * sw) else 0
    bar_y = min(top, bottom) if min(top, bottom) >= 2 and abs(top - bottom) <= max(3, 0.03 * sh) else 0
    x0 = int(round(bar_x * w / sw))
    y0 = int(round(bar_y * h / sh))
    return [x0, y0, w - 2 * x0, h - 2 * y0]


def _signal(path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    """Per-frame mean luma (0-255) and frame difference, from a small proxy."""
    proc = run(["ffmpeg", "-nostats", "-i", str(path), "-vf", "scale=160:-2,signalstats,metadata=print:file=-", "-an", "-f", "null", "-"], check=False)
    yavg = [float(x) for x in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", proc.stdout)]
    ydif = [float(x) for x in re.findall(r"lavfi\.signalstats\.YDIF=([\d.]+)", proc.stdout)]
    fps = ffprobe(path)["video"]["fps"] or 30.0
    return np.array(yavg), np.array(ydif), fps


def visual_events(yavg: np.ndarray, ydif: np.ndarray, fps: float) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if len(yavg) < 3:
        return events
    # flashes: luma climbs >= 25 levels within 6 frames to a local maximum
    win = max(2, int(round(fps * 0.2)))
    for i in range(win, len(yavg)):
        rise = yavg[i] - yavg[max(0, i - win):i].min()
        if rise >= 25 and yavg[i] >= yavg[max(0, i - 1)] and (i + 1 >= len(yavg) or yavg[i] >= yavg[i + 1]):
            start = i
            while start > 0 and yavg[start - 1] < yavg[start] - 1.0:
                start -= 1
            if not events or (start / fps) - events[-1]["t"] > 0.5:
                events.append({"kind": "flash", "t": round(start / fps, 4), "peak": round(i / fps, 4), "strength": round(float(rise), 1)})
    # sustained brightening (a launch plume, lights coming up): >= 30 levels within 2 s
    span = int(fps * 2)
    i = 0
    while i + span < len(yavg):
        if yavg[i + span] - yavg[i] >= 30 and not any(e["kind"] == "flash" and abs(e["t"] - i / fps) < 2 for e in events):
            j = i
            while j + 1 < len(yavg) and yavg[j + 1] - yavg[j] < 0.2 and j < i + span:
                j += 1
            events.append({"kind": "rise", "t": round(j / fps, 4), "strength": round(float(yavg[i + span] - yavg[i]), 1)})
            i += span * 2
        else:
            i += 1
    # hard cuts: difference spike far above the clip's typical motion
    if len(ydif) > 5:
        med, mad = np.median(ydif), np.median(np.abs(ydif - np.median(ydif))) + 1e-6
        for i in np.flatnonzero(ydif > med + 12 * mad + 8):
            if i > 0 and not any(abs(e["t"] - i / fps) < 0.3 for e in events if e["kind"] == "cut"):
                events.append({"kind": "cut", "t": round(i / fps, 4), "strength": round(float(ydif[i]), 1)})
        # motion peaks: smoothed difference maxima (camera moves, action beats)
        k = max(3, int(fps * 0.3))
        smooth = np.convolve(ydif, np.ones(k) / k, mode="same")
        from scipy.signal import find_peaks
        peaks, props = find_peaks(smooth, prominence=max(1.0, smooth.std()), distance=int(fps * 0.8))
        for p, prom in zip(peaks, props["prominences"]):
            events.append({"kind": "motion", "t": round(float(p) / fps, 4), "strength": round(float(prom), 2)})
    events.sort(key=lambda e: e["t"])
    counts: dict[str, int] = {}
    for e in events:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        e["n"] = counts[e["kind"]]
        e["ref"] = f"{e['kind']}:{e['n']}"
    return events


def _contact_sheet(path: Path, out: Path, duration: float) -> None:
    cols = 6
    rows = max(1, int(np.ceil((duration + 0.999) / cols)))
    run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf",
         f"fps=1,scale=320:-2,drawbox=x=0:y=0:w=64:h=24:color=black@0.6:t=fill,tile={cols}x{rows}", "-frames:v", "1", "-q:v", "4", str(out)], check=False)


def analyze(project: str | Path) -> dict[str, Any]:
    project = Path(project)
    folder = project / "footage"
    clips = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and p.is_file()) if folder.is_dir() else []
    if not clips:
        raise StudioError("no video files in footage/")
    (folder / "sheets").mkdir(exist_ok=True)
    out: dict[str, Any] = {"clips": {}}
    for path in clips:
        info = ffprobe(path)
        v = info["video"]
        if not v:
            continue
        cid = clip_id(path)
        mean_db = _audible(path) if info["audio"] else None
        yavg, ydif, fps = _signal(path)
        box = _content_box(path, v["width"], v["height"], info["duration"])
        _contact_sheet(path, folder / "sheets" / f"{cid}.jpg", info["duration"])
        out["clips"][cid] = {
            "file": path.name, "sha256": sha256_file(path), "duration": round(info["duration"], 4),
            "width": v["width"], "height": v["height"], "fps": v["fps"], "codec": v["codec"],
            "audio": None if not info["audio"] else {"mean_db": mean_db, "audible": mean_db is not None and mean_db > -60},
            "content_box": box, "bars": box != [0, 0, v["width"], v["height"]],
            "events": visual_events(yavg, ydif, fps), "sheet": f"sheets/{cid}.jpg",
            "luma": {"mean": round(float(yavg.mean()), 1) if len(yavg) else None, "min": round(float(yavg.min()), 1) if len(yavg) else None,
                     "max": round(float(yavg.max()), 1) if len(yavg) else None},
        }
    write_json(folder / "footage.json", out)
    return out


def conform(project: str | Path, fps: float) -> list[str]:
    project = Path(project)
    meta = read_json(project / "footage" / "footage.json")
    dest = project / "footage" / "conformed"
    dest.mkdir(exist_ok=True)
    made = []
    for cid, c in meta["clips"].items():
        src = project / "footage" / c["file"]
        out = dest / f"{cid}.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v:0", "-vf", f"fps={fps}:round=near,format=yuv420p",
             "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-g", str(int(round(fps))), "-bf", "0",
             "-movflags", "+faststart", "-an", "-map_metadata", "-1", str(out)])
        made.append(out.name)
        c["conformed"] = f"conformed/{out.name}"
        if c.get("audio") and c["audio"].get("audible"):
            wav = dest / f"{cid}.wav"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(wav)])
            c["conformed_audio"] = f"conformed/{wav.name}"
            made.append(wav.name)
    meta["conformed_fps"] = fps
    write_json(project / "footage" / "footage.json", meta)
    return made


def _interp(keys: list[dict[str, Any]], t: float) -> list[float]:
    if t <= keys[0]["t"]:
        k = keys[0]
        return [k["x"], k["y"], k["w"], k["h"]]
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            u = (t - a["t"]) / max(1e-9, b["t"] - a["t"])
            return [a[c] + (b[c] - a[c]) * u for c in ("x", "y", "w", "h")]
    k = keys[-1]
    return [k["x"], k["y"], k["w"], k["h"]]


def _intersects(a: list[float], b: list[float]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def reframe(project: str | Path, canvas: tuple[int, int]) -> dict[str, Any]:
    """Validate footage/reframe.json and write reframe.js. Returns {'issues': [...], 'ok': bool}."""
    project = Path(project)
    meta = read_json(project / "footage" / "footage.json")
    spec = read_json(project / "footage" / "reframe.json")
    W, H = canvas
    aspect = W / H
    issues: list[dict[str, str]] = []
    out = {}
    for mid, r in spec.get("media", {}).items():
        cid = r["clip"]
        if cid not in meta["clips"]:
            issues.append({"level": "error", "code": "unknown_clip", "message": f"{mid}: clip {cid} not in footage.json"})
            continue
        c = meta["clips"][cid]
        # the picture fills the whole canvas, or a smaller "frame" box (x, y, w, h in canvas px) for framed layouts
        frame = r.get("frame") or {"x": 0, "y": 0, "w": W, "h": H}
        fw, fh = float(frame["w"]), float(frame["h"])
        aspect = fw / fh
        keys = sorted(r["keys"], key=lambda k: k["t"])
        box = c["content_box"]
        avoid = [list(map(float, a)) for a in r.get("avoid", [])]
        for k in keys:
            if "h" not in k:
                k["h"] = k["w"] / aspect
            if abs((k["w"] / k["h"]) - aspect) > 0.01 * aspect:
                issues.append({"level": "error", "code": "aspect", "message": f"{mid} key t={k['t']}: crop {k['w']}x{k['h']} is not the frame aspect {fw:.0f}:{fh:.0f}"})
            scale = fw / k["w"]
            if scale > MAX_UPSCALE_ERROR:
                issues.append({"level": "error", "code": "upscale", "message": f"{mid} key t={k['t']}: {scale:.2f}x upscale is too soft (max {MAX_UPSCALE_ERROR}x): use a framed layout ('frame' box) or a wider crop"})
            elif scale > MAX_UPSCALE_WARN:
                issues.append({"level": "warning", "code": "upscale", "message": f"{mid} key t={k['t']}: {scale:.2f}x upscale; check sharpness, or frame the clip smaller"})
        dur = max(k["t"] for k in keys) if keys else 0
        steps = np.arange(0, max(dur, 0) + 1e-9, 0.1) if len(keys) > 1 else [keys[0]["t"]] if keys else []
        for t in steps:
            x, y, w, h = _interp(keys, float(t))
            if x < box[0] - 0.5 or y < box[1] - 0.5 or x + w > box[0] + box[2] + 0.5 or y + h > box[1] + box[3] + 0.5:
                issues.append({"level": "error", "code": "outside_content", "message": f"{mid} t={t:.1f}s: crop [{x:.0f},{y:.0f},{w:.0f},{h:.0f}] leaves the picture area {box} (bars or frame edge would show)"})
                break
            hit = next((a for a in avoid if _intersects([x, y, w, h], a)), None)
            if hit:
                issues.append({"level": "error", "code": "avoid_box", "message": f"{mid} t={t:.1f}s: crop includes avoid box {hit} ({r.get('avoid_reason', 'burn-in/logo')})"})
                break
        out[mid] = {"clip": cid, "source": {"w": c["width"], "h": c["height"]}, "canvas": {"w": fw, "h": fh}, "frame": frame,
                    "keys": [{"t": k["t"], "x": k["x"], "y": k["y"], "w": k["w"], "h": k["h"], "ease": k.get("ease", "sine.inOut")} for k in keys]}
    (project / "reframe.js").write_text("// generated by `mstudio footage reframe` from footage/reframe.json; do not edit\nwindow.REFRAME = "
                                        + json.dumps(out, indent=1) + ";\n", encoding="utf-8")
    return {"issues": issues, "ok": not any(i["level"] == "error" for i in issues), "media": list(out)}
