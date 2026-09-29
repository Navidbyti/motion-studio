"""New sound effects per project: procedural synthesis (CC0), variations, or ElevenLabs generation.

  mstudio sfx <slug> make whoosh --name swoosh-a --duration 0.8 --seed 3 [--pitch 1.2 --bright 0.7 --pan lr]
  mstudio sfx <slug> vary audio/sfx/hit.wav --count 4            # pitch/tone/length variants of one sound
  mstudio sfx <slug> gen "glass shard snapping, close mic" --duration 1.2   # ElevenLabs (key: `mstudio keys setup elevenlabs`)
  mstudio sfx kinds                                              # list synth kinds

Every synth kind is parameterised and seeded, so each project can have its own
palette without licensing questions. Files land in audio/sfx/ at 48 kHz stereo,
peak -3 dBFS, and are credited automatically.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import secrets
from .util import StudioError, read_json, run, write_json

SR = 48000


def _t(d: float) -> np.ndarray:
    return np.arange(int(d * SR)) / SR


def _lp(x: np.ndarray, cutoff: np.ndarray | float) -> np.ndarray:
    """One-pole low-pass with a time-varying cutoff (vectorised in blocks for speed)."""
    cutoff = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = np.exp(-2 * np.pi * np.clip(cutoff, 10, SR / 2.2) / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def _hp(x: np.ndarray, cutoff: float) -> np.ndarray:
    return x - _lp(x, cutoff)


def _env(n: int, attack: float, release: float, curve: float = 3.0) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    r = np.exp(-np.maximum(0, t - attack) * curve / max(release, 1e-4))
    return a * r


def _stereo(left: np.ndarray, right: np.ndarray | None = None) -> np.ndarray:
    return np.stack([left, left if right is None else right], axis=1)


def _pan(mono: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """Equal-power pan, pos in [-1, 1] per sample."""
    ang = (pos + 1) * np.pi / 4
    return np.stack([mono * np.cos(ang), mono * np.sin(ang)], axis=1)


def whoosh(d, rng, p):
    t = _t(d)
    ph = t / d
    shape = np.sin(np.pi * ph ** (0.6 + 0.8 * rng.random())) ** 2
    noise = rng.standard_normal(len(t))
    cutoff = 250 * p["pitch"] + (3000 + 6000 * p["bright"]) * shape
    body = _lp(noise, cutoff) * shape
    air = _hp(rng.standard_normal(len(t)), 5000) * shape ** 2 * 0.25 * p["bright"]
    pos = {"lr": -1 + 2 * ph, "rl": 1 - 2 * ph, "c": np.zeros_like(ph)}[p["pan"]]
    return _pan(body + air, pos * 0.8)


def riser(d, rng, p):
    t = _t(d)
    ph = t / d
    f = 120 * p["pitch"] * (1 + 7 * ph ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    noise = _lp(rng.standard_normal(len(t)), 300 + 9000 * ph ** 2 * p["bright"])
    env = ph ** 2.2 * np.minimum(1, (d - t) / 0.02)
    mono = (0.35 * tone + noise) * env
    return _stereo(mono, np.roll(mono, int(0.004 * SR)))


def impact(d, rng, p):
    t = _t(d)
    f = 38 * p["pitch"] + 70 * p["pitch"] * np.exp(-t / 0.07)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, d * 0.5, 4)
    crack = _hp(rng.standard_normal(len(t)), 1500) * _env(len(t), 0.001, 0.05, 6) * (0.3 + 0.6 * p["bright"])
    body = _lp(rng.standard_normal(len(t)), 700) * _env(len(t), 0.002, 0.25, 5) * 0.6
    mono = boom + crack + body
    return _stereo(mono, _lp(mono, 9000))


def sub_drop(d, rng, p):
    t = _t(d)
    f = 30 * p["pitch"] + 60 * p["pitch"] * np.exp(-t / (d * 0.35))
    mono = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.005, d * 0.6, 3)
    return _stereo(np.tanh(1.5 * mono))


def hit(d, rng, p):
    t = _t(d)
    tone = sum(np.sin(2 * np.pi * 180 * p["pitch"] * k * t + rng.random()) / k for k in (1, 2.02, 3.1))
    click = _hp(rng.standard_normal(len(t)), 2500) * _env(len(t), 0.0005, 0.02, 8)
    mono = tone * _env(len(t), 0.001, 0.12, 6) + click * (0.4 + 0.6 * p["bright"])
    return _stereo(mono)


def click(d, rng, p):
    t = _t(max(d, 0.03))
    mono = np.sin(2 * np.pi * 2400 * p["pitch"] * t) * _env(len(t), 0.0003, 0.008, 8) + \
        _hp(rng.standard_normal(len(t)), 4000) * _env(len(t), 0.0002, 0.004, 8) * p["bright"]
    return _stereo(mono)


def pop(d, rng, p):
    t = _t(max(d, 0.08))
    f = 420 * p["pitch"] + 700 * p["pitch"] * np.exp(-t / 0.015)
    return _stereo(np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 0.05, 6))


def glitch(d, rng, p):
    n = int(d * SR)
    out = np.zeros(n)
    pos = 0
    while pos < n:
        seg = int(SR * rng.uniform(0.008, 0.05))
        kind = rng.integers(3)
        tt = np.arange(min(seg, n - pos)) / SR
        if kind == 0:
            chunk = np.sign(np.sin(2 * np.pi * rng.uniform(200, 2400) * p["pitch"] * tt))
        elif kind == 1:
            chunk = rng.standard_normal(len(tt))
        else:
            chunk = np.zeros(len(tt))
        out[pos:pos + len(tt)] = chunk * rng.uniform(0.3, 1.0)
        pos += seg
    out = _lp(out, 2000 + 10000 * p["bright"])
    return _stereo(out, np.roll(out, int(0.003 * SR)))


def shimmer(d, rng, p):
    t = _t(d)
    base = 880 * p["pitch"]
    mono = sum(np.sin(2 * np.pi * base * r * t + rng.random() * 6) * np.exp(-t / (d * rng.uniform(0.3, 0.8))) / (i + 1)
               for i, r in enumerate((1, 1.5, 2, 2.5, 3, 4)))
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(5, 9) * t)
    env = _env(len(t), 0.01, d, 2)
    return _stereo(mono * trem * env, np.roll(mono * trem * env, int(0.007 * SR)))


def swell(d, rng, p):
    """Reverse-cymbal style swell that peaks at the end (land it on the hit)."""
    t = _t(d)
    ph = t / d
    noise = _hp(rng.standard_normal(len(t)), 2000 + 3000 * p["bright"])
    tone = np.sin(2 * np.pi * 220 * p["pitch"] * t) * 0.2
    env = ph ** 3 * np.minimum(1, (d - t) / 0.01)
    mono = (noise + tone) * env
    return _stereo(mono, np.roll(mono, int(0.005 * SR)))


def tape_stop(d, rng, p):
    t = _t(d)
    f = 220 * p["pitch"] * (1 - t / d) ** 2 + 20
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    mono = _lp(saw, 600 + 4000 * (1 - t / d) * p["bright"]) * _env(len(t), 0.005, d, 1)
    return _stereo(mono)


def thud(d, rng, p):
    t = _t(d)
    mono = _lp(rng.standard_normal(len(t)), 220 * p["pitch"]) * _env(len(t), 0.001, 0.12, 5) * 3
    mono += np.sin(2 * np.pi * 70 * p["pitch"] * t) * _env(len(t), 0.001, 0.15, 5)
    return _stereo(mono)


def zap(d, rng, p):
    t = _t(d)
    f = 3000 * p["pitch"] * np.exp(-t / (d * 0.3)) + 100
    mono = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * _env(len(t), 0.001, d, 3)
    return _stereo(_lp(mono, 4000 + 8000 * p["bright"]))


KINDS: dict[str, tuple[Callable, float, str]] = {
    "whoosh": (whoosh, 0.7, "air pass; peak in the middle (pan lr/rl/c)"),
    "riser": (riser, 2.0, "tension build into a hit or drop; ends at full level"),
    "swell": (swell, 1.5, "reverse-cymbal swell that peaks on its last frame"),
    "impact": (impact, 1.4, "big low boom + crack for downbeat slams"),
    "sub-drop": (sub_drop, 1.6, "falling sub for drops and scene changes"),
    "thud": (thud, 0.4, "dull body hit for landings and stamps"),
    "hit": (hit, 0.35, "tonal percussive hit for punches"),
    "pop": (pop, 0.12, "bubble pop for entrances"),
    "click": (click, 0.05, "UI tick for counters and micro accents"),
    "glitch": (glitch, 0.4, "digital stutter for data or tech moments"),
    "shimmer": (shimmer, 1.2, "bright sparkle for reveals and logos"),
    "tape-stop": (tape_stop, 0.8, "pitch-down stop for endings and freezes"),
    "zap": (zap, 0.25, "laser-ish sweep for fast transitions"),
}
PEAK_AT_END = {"riser", "swell"}   # align the file's end, not its start, to the hit


def _write(path: Path, x: np.ndarray, peak_db: float = -3.0) -> None:
    x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (peak_db / 20)
    rms_db = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    if rms_db > -18.0:   # dense sounds (glitch, zap) would otherwise be far louder than impulsive ones at the same peak
        x = x * 10 ** ((-18.0 - rms_db) / 20)
    fade = min(len(x) // 4, int(0.004 * SR))
    if fade:
        x[-fade:] *= np.linspace(1, 0, fade)[:, None]
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def make(project: Path, kind: str, *, name: str | None = None, duration: float | None = None, seed: int = 0,
         pitch: float = 1.0, bright: float = 0.6, pan: str = "c") -> dict[str, Any]:
    if kind not in KINDS:
        raise StudioError(f"unknown kind '{kind}' (kinds: {', '.join(KINDS)})")
    fn, default_d, _ = KINDS[kind]
    d = float(duration or default_d)
    rng = np.random.default_rng(seed)
    x = fn(d, rng, {"pitch": pitch, "bright": bright, "pan": pan})
    name = name or f"{kind}-{seed}"
    _check_name(name)
    path = project / "audio" / "sfx" / f"{name}.wav"
    _write(path, x)
    _register(project, path, {"source": "procedural", "kind": kind, "seed": seed, "duration": d, "pitch": pitch, "bright": bright, "pan": pan,
                              "align": "end" if kind in PEAK_AT_END else ("peak" if kind == "whoosh" else "onset")})
    return {"file": f"audio/sfx/{name}.wav", "kind": kind, "duration": d}


def vary(project: Path, source: Path, count: int = 3, seed: int = 0) -> list[str]:
    """Pitch (±2 semitones), tone (filter) and length variants of one sound, so repeats don't sound copied."""
    rng = np.random.default_rng(seed)
    made = []
    for i in range(count):
        semis = rng.uniform(-2, 2)
        rate = 2 ** (semis / 12)
        tone = rng.choice(["lowpass=f=6000", "highpass=f=120", "equalizer=f=3000:t=q:w=1:g=3", "anull"])
        out = project / "audio" / "sfx" / f"{source.stem}-v{i + 1}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-af",
             f"asetrate={int(SR * rate)},aresample={SR},{tone},volume={rng.uniform(-1.5, 0):.2f}dB", "-ac", "2", str(out)])
        _register(project, out, {"source": "variation", "of": source.name, "semitones": round(semis, 2), "tone": tone})
        made.append(f"audio/sfx/{out.name}")
    return made


def gen_elevenlabs(project: Path, prompt: str, *, name: str, duration: float | None = None, influence: float = 0.4,
                   loop: bool = False) -> dict[str, Any]:
    key = secrets.require_key("elevenlabs")
    _check_name(name)
    body: dict[str, Any] = {"text": prompt, "prompt_influence": influence, "model_id": "eleven_text_to_sound_v2"}
    if duration:
        body["duration_seconds"] = max(0.5, min(30.0, duration))
    if loop:
        body["loop"] = True
    req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            audio = resp.read()
    except urllib.error.HTTPError as exc:
        raise StudioError(f"ElevenLabs sound generation failed: HTTP {exc.code} "
                          f"{secrets.scrub(exc.read().decode('utf-8', 'replace')[:300])}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise StudioError(f"could not reach ElevenLabs: {getattr(exc, 'reason', exc)}") from None
    tmp = project / "audio" / "sfx" / f"{name}.mp3"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(audio)
    out = tmp.with_suffix(".wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-ar", str(SR), "-ac", "2", "-af", "silenceremove=start_periods=1:start_threshold=-50dB",
         str(out)])
    tmp.unlink()
    _register(project, out, {"source": "elevenlabs", "prompt": prompt, "duration": duration})
    cpath = project / "credits.json"
    credits = read_json(cpath)
    if not any(c.get("path") == "audio/sfx" for c in credits["assets"]):
        credits["assets"].append({"path": "audio/sfx", "what": "project sound effects (procedural, variations, generated)",
                                  "source": "Motion Studio synth (CC0); ElevenLabs sound generation where listed in audio/sfx/sfx.json",
                                  "license": "CC0 for procedural files; ElevenLabs output per your plan's terms (paid plans allow commercial use)"})
        write_json(cpath, credits)
    return {"file": f"audio/sfx/{out.name}"}


def _check_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", name):
        raise StudioError("sound names use letters, digits, - or _")


def _register(project: Path, path: Path, meta: dict[str, Any]) -> None:
    reg_path = project / "audio" / "sfx" / "sfx.json"
    reg = read_json(reg_path) if reg_path.is_file() else {}
    reg[path.name] = meta
    write_json(reg_path, reg)
    cpath = project / "credits.json"
    if cpath.is_file():
        credits = read_json(cpath)
        if not any(c.get("path") == "audio/sfx" for c in credits["assets"]):
            credits["assets"].append({"path": "audio/sfx", "what": "project sound effects (procedural synth and variations)",
                                      "source": "Motion Studio synth (src/motion_studio/sfx.py)", "license": "CC0-1.0"})
            write_json(cpath, credits)
