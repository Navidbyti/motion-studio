"""Original music per project: generate with Lyria (Gemini API), then fit it to the edit.

  mstudio music <slug> gen --prompt "…" [--full] [--name bed]   -> audio/music/<name>.wav (+ .mp3 source, lyrics/structure)
  mstudio music <slug> fit audio/music/bed.wav --duration 30     -> audio/music/bed.fit.wav, cut and faded on bar lines

Lyria 3 Clip (`lyria-3-clip-preview`) always returns 30 s; Lyria 3.5 (`lyria-3.5`) returns full songs
(a couple of minutes, steer length in the prompt). Output is 44.1 kHz stereo with an inaudible SynthID
watermark. The same Gemini key as voice-over is used (`mstudio keys setup gemini`).
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from . import beats as beats_mod
from . import secrets
from .tts import _post
from .util import StudioError, ffprobe, read_json, run, write_json

MODELS = {"clip": "lyria-3-clip-preview", "full": "lyria-3.5"}


def build_prompt(prompt: str, *, bpm: float | None = None, key: str | None = None, instrumental: bool = True,
                 duration: float | None = None) -> str:
    """Lyria prompting guide: be specific (instruments, BPM, key, mood, structure); say 'Instrumental only' for beds."""
    parts = [prompt.strip().rstrip(".") + "."]
    if bpm:
        parts.append(f"Tempo {bpm:g} BPM, steady and on the grid.")
    if key:
        parts.append(f"Key of {key}.")
    if duration:
        parts.append(f"About {int(round(duration))} seconds long, with a clear intro, a build, a drop and a clean ending.")
    if instrumental and "instrumental" not in prompt.lower():
        parts.append("Instrumental only, no vocals.")
    return " ".join(parts)


def generate(project: Path, prompt: str, *, full: bool = False, name: str = "bed", bpm: float | None = None,
             key: str | None = None, instrumental: bool = True, duration: float | None = None) -> dict[str, Any]:
    api_key = secrets.require_key("gemini")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise StudioError("--name must be letters, digits, - or _")
    model = MODELS["full" if full else "clip"]
    text = build_prompt(prompt, bpm=bpm, key=key, instrumental=instrumental, duration=duration if full else None)
    body: dict[str, Any] = {"model": model, "input": text}
    if full:
        body["response_format"] = {"type": "audio"}
    response = _post(body, api_key, timeout=600)
    audio_blocks, texts = [], []
    for step in response.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for c in step.get("content", []):
            if c.get("type") == "audio" and c.get("data"):
                audio_blocks.append(c)
            elif c.get("type") == "text" and c.get("text"):
                texts.append(c["text"])
    if not audio_blocks:
        raise StudioError("Lyria returned no audio (the prompt may have been blocked by safety filters: avoid artist names and lyrics)")
    raw = base64.b64decode(audio_blocks[-1]["data"])
    out_dir = project / "audio" / "music"
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = ".wav" if raw[:4] == b"RIFF" else ".mp3"
    src = out_dir / f"{name}.source{ext}"
    src.write_bytes(raw)
    wav = out_dir / f"{name}.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(wav)])
    if texts:
        (out_dir / f"{name}.lyria.txt").write_text("\n\n".join(texts), encoding="utf-8")
    meta = {"model": model, "prompt": text, "file": f"audio/music/{name}.wav", "duration": round(ffprobe(wav)["duration"], 3),
            "sha256": hashlib.sha256(wav.read_bytes()).hexdigest(), "watermark": "SynthID (inaudible)"}
    write_json(out_dir / f"{name}.json", meta)
    _credit(project, f"audio/music/{name}.wav", f"Original music generated with {model}", "Google Lyria via Gemini API (generated for this project)",
            "Generated output under the Gemini API Terms of Service; contains a SynthID watermark")
    return meta


def fit(project: Path, source: Path, duration: float, *, fade_bars: float = 1.0, name: str | None = None) -> dict[str, Any]:
    """Cut (or extend by looping whole bars) so the track ends exactly at `duration` on a bar line with a musical fade."""
    analysis = beats_mod.analyze(source)
    bars = [b["t"] for b in analysis["bars"]]
    if len(bars) < 4:
        raise StudioError("not enough bars detected to edit musically; pick a more rhythmic track or cut by hand")
    bar_len = float(np.median(np.diff(bars)))
    first = analysis["first_downbeat"] or 0.0
    total = ffprobe(source)["duration"]
    out = project / "audio" / "music" / f"{name or source.stem}.fit.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    fade = min(duration / 3, fade_bars * bar_len)
    if total - first >= duration:
        # take `duration` from the first downbeat; the fade finishes exactly at the end
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{first:.4f}", "-i", str(source), "-t", f"{duration:.4f}",
             "-af", f"afade=t=in:d=0.02,afade=t=out:st={duration - fade:.4f}:d={fade:.4f}", "-ar", "48000", "-ac", "2", str(out)])
        method = "trim from first downbeat"
    else:
        # loop a whole-bar body (after the intro) with a short crossfade on the downbeat until long enough
        loop_start = bars[min(4, len(bars) - 2)]
        loop_end = bars[-1]
        loop_len = loop_end - loop_start
        if loop_len < 2 * bar_len:
            raise StudioError("track too short to loop musically")
        reps = int(np.ceil((duration - (loop_start - first)) / loop_len)) + 1
        # split the input explicitly: older FFmpeg builds don't allow reusing [0:a] in several chains
        parts = [f"[0:a]asplit={reps}" + "".join(f"[s{i}]" for i in range(reps)),
                 f"[s0]atrim={first:.4f}:{loop_end:.4f},asetpts=PTS-STARTPTS[a0]"]
        labels = ["[a0]"]
        for i in range(1, reps):
            parts.append(f"[s{i}]atrim={loop_start:.4f}:{loop_end:.4f},asetpts=PTS-STARTPTS[a{i}]")
            labels.append(f"[a{i}]")
        chain = labels[0]
        for i, lab in enumerate(labels[1:], start=1):
            parts.append(f"{chain}{lab}acrossfade=d=0.03:c1=tri:c2=tri[x{i}]")
            chain = f"[x{i}]"
        parts.append(f"{chain}atrim=0:{duration:.4f},afade=t=out:st={duration - fade:.4f}:d={fade:.4f}[out]")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-filter_complex", ";".join(parts), "-map", "[out]",
             "-ar", "48000", "-ac", "2", str(out)])
        method = f"looped bars {loop_start:.2f}-{loop_end:.2f}s x{reps - 1}"
    return {"file": str(out.relative_to(project)).replace("\\", "/"), "duration": round(ffprobe(out)["duration"], 3),
            "bpm": analysis["tempo"]["bpm"], "method": method}


def _credit(project: Path, path: str, what: str, source: str, license_text: str) -> None:
    cpath = project / "credits.json"
    credits = read_json(cpath) if cpath.is_file() else {"assets": []}
    credits["assets"] = [c for c in credits["assets"] if c.get("path") != path]
    credits["assets"].append({"path": path, "what": what, "source": source, "license": license_text})
    write_json(cpath, credits)


# ------------------------------------------------------------------ cross-project reuse registry

def registry_path() -> Path:
    return secrets.home() / "music-registry.json"


def fingerprint(path: Path) -> str:
    """Content fingerprint robust to re-encoding: coarse loudness contour of the first 60 s."""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "60", "-ac", "1", "-ar", "2000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    y = np.frombuffer(raw, dtype=np.float32)
    if y.size < 4000:
        return hashlib.sha256(raw).hexdigest()[:16]
    frames = y[: (y.size // 500) * 500].reshape(-1, 500)
    contour = np.sqrt((frames ** 2).mean(axis=1))
    q = np.digitize(20 * np.log10(contour + 1e-6), np.arange(-60, 0, 6))
    return hashlib.sha256(bytes(q[:120].astype(np.uint8))).hexdigest()[:16]


def record_use(slug: str, path: Path) -> None:
    reg_path = registry_path()
    reg = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.is_file() else {}
    fp = fingerprint(path)
    entry = reg.setdefault(fp, {"file": path.name, "projects": []})
    if slug not in entry["projects"]:
        entry["projects"].append(slug)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(reg, indent=1), encoding="utf-8")


def used_elsewhere(slug: str, path: Path) -> list[str]:
    reg_path = registry_path()
    if not reg_path.is_file():
        return []
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    return [p for p in reg.get(fingerprint(path), {}).get("projects", []) if p != slug]
