"""Deterministic synthetic music with known ground truth, for beat-engine tests."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100


def _kick(n: int) -> np.ndarray:
    t = np.arange(n) / SR
    f = 45 + 90 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.15)


def _snare(n: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - np.convolve(noise, np.ones(8) / 8, mode="same")  # crude high-pass
    return 0.6 * noise * np.exp(-t / 0.08) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)


def _hat(n: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    for _ in range(3):
        noise = noise - np.convolve(noise, np.ones(4) / 4, mode="same")
    return noise * np.exp(-t / 0.02)


def make_track(path: str | Path, bpm: float = 124.0, pickup_beats: int = 2, lead_silence: float = 0.37,
               sections: tuple[tuple[str, int], ...] = (("intro", 4), ("build", 4), ("drop", 8), ("break", 4), ("drop", 4)),
               seed: int = 7) -> dict:
    """Write a WAV and return ground truth: beat times, downbeat times, drop times."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bars = sum(n for _, n in sections)
    total_beats = pickup_beats + bars * 4
    dur = lead_silence + total_beats * beat + 1.5
    y = np.zeros(int(dur * SR))
    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]
    beat_times, downbeats, drops = [], [], []
    bar_kind = ["pickup"] * 0
    kinds = []
    for name, n in sections:
        kinds += [name] * n
    bar_start = 0
    for name, n in sections:
        if name == "drop":
            drops.append(lead_silence + (pickup_beats + bar_start * 4) * beat)
        bar_start += n

    def add(sig: np.ndarray, t: float, gain: float) -> None:
        i = int(round(t * SR))
        j = min(len(y), i + len(sig))
        y[i:j] += gain * sig[: j - i]

    for k in range(total_beats):
        t = lead_silence + k * beat
        beat_times.append(t)
        bar = (k - pickup_beats) // 4
        pos = (k - pickup_beats) % 4
        kind = "intro" if bar < 0 else kinds[bar]
        if pos == 0 and bar >= 0:
            downbeats.append(t)
            # chord for the whole bar
            n = int(4 * beat * SR)
            tt = np.arange(n) / SR
            env = np.minimum(1, tt / 0.02) * np.exp(-tt / 3.0)
            pad = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * tt) for m in chords[bar % 4])
            add(pad * env, t, 0.05 if kind in ("intro", "break") else 0.035)
        loud = {"intro": 0.0, "build": 0.6, "drop": 1.0, "break": 0.0}[kind]
        if kind in ("build", "drop") and pos in (0, 2):
            add(_kick(int(0.4 * SR)), t, 0.9 * max(loud, 0.6))
        if kind == "drop" and pos in (0, 2):
            add(_kick(int(0.4 * SR)), t + 2 * beat / 4 * 0 , 0.0)
        if kind in ("build", "drop") and pos in (1, 3):
            add(_snare(int(0.3 * SR), rng), t, 0.5 * max(loud, 0.5))
        if kind in ("intro", "drop", "build"):
            add(_hat(int(0.06 * SR), rng), t + beat / 2, 0.12)
        if kind == "drop":
            # bass on every beat makes the drop clearly louder in the low band
            n = int(beat * SR)
            tt = np.arange(n) / SR
            f0 = 440 * 2 ** ((chords[max(bar, 0) % 4][0] - 12 - 69) / 12)
            add(np.sin(2 * np.pi * f0 * tt) * np.exp(-tt / 0.3), t, 0.35)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.8
    pcm = (y * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return {"bpm": bpm, "beats": beat_times, "downbeats": downbeats, "drops": drops, "beat": beat}
