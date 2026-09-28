"""Regenerate the benchmark audio pack (maintainers only).

Every sound here is synthesized from code, so the pack has no third-party
rights and is dedicated to the public domain (CC0). Benchmark runs must use
the committed WAV files, not a fresh generation: `bench.py verify` checks
their hashes. Requires numpy, which is not a Motion Engine dependency.

    python benchmarks/shared/audio/generate_audio.py
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48_000
OUT = Path(__file__).resolve().parent
RNG = np.random.default_rng(20260928)


def write(name: str, x: np.ndarray, peak: float = 0.7) -> None:
    x = x / max(1e-9, np.max(np.abs(x))) * peak
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"{name}: {len(x) / SR:.2f}s")


def t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def one_pole_lowpass(x: np.ndarray, cutoff: np.ndarray | float) -> np.ndarray:
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def soft_saw(freq: float, tt: np.ndarray, harmonics: int = 7) -> np.ndarray:
    return sum(np.sin(2 * np.pi * freq * k * tt) / k for k in range(1, harmonics + 1))


def music_bed() -> np.ndarray:
    """48 s at 100 BPM, A minor, Am-F-C-G (two bars per chord)."""
    bpm, bars = 100, 20
    beat = 60 / bpm
    bar = 4 * beat
    total = bars * bar
    out = np.zeros(int(total * SR) + SR)
    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]  # Am F C G
    roots = [45, 41, 48, 43]
    for b in range(bars):
        idx = (b // 2) % 4
        start = int(b * bar * SR)
        seg = t(bar + 0.4)
        env = np.minimum(1, seg / 0.35) * np.exp(-np.maximum(0, seg - bar) / 0.15)
        pad = sum(soft_saw(midi(n), seg) + 0.6 * soft_saw(midi(n) * 1.004, seg) for n in chords[idx])
        out[start:start + len(seg)] += 0.10 * pad * env
        if 2 <= b < bars - 1:
            for step in range(8):  # bass eighths
                s = start + int(step * beat / 2 * SR)
                st = t(beat / 2)
                f = midi(roots[idx])
                out[s:s + len(st)] += 0.35 * (np.sin(2 * np.pi * f * st) + 0.3 * np.sin(4 * np.pi * f * st)) * np.exp(-st / 0.18)
            for step in range(8):  # arpeggio eighths
                s = start + int(step * beat / 2 * SR)
                st = t(0.4)
                f = midi(chords[idx][step % 3] + 12)
                out[s:s + len(st)] += 0.06 * np.sin(2 * np.pi * f * st) * np.exp(-st / 0.12)
        if 4 <= b < bars - 1:
            for q in range(4):  # kick on 1 and 3, hats on offbeats
                s = start + int(q * beat * SR)
                if q in (0, 2):
                    kt = t(0.35)
                    sweep = 45 + 75 * np.exp(-kt / 0.04)
                    out[s:s + len(kt)] += 0.55 * np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.exp(-kt / 0.12)
                hs = s + int(beat / 2 * SR)
                ht = t(0.05)
                noise = RNG.standard_normal(len(ht))
                out[hs:hs + len(ht)] += 0.05 * (noise - one_pole_lowpass(noise, 6000)) * np.exp(-ht / 0.015)
    return out[: int(total * SR)]


def whoosh(seconds: float) -> np.ndarray:
    tt = t(seconds)
    phase = tt / seconds
    env = np.sin(np.pi * phase) ** 2
    cutoff = 300 + 5000 * np.sin(np.pi * phase) ** 3
    noise = RNG.standard_normal(len(tt))
    return one_pole_lowpass(noise, cutoff) * env


def pop() -> np.ndarray:
    tt = t(0.12)
    f = 500 + 500 * np.exp(-tt / 0.02)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.03)


def tick() -> np.ndarray:
    tt = t(0.05)
    return np.sin(2 * np.pi * 2400 * tt) * np.exp(-tt / 0.006)


def impact() -> np.ndarray:
    tt = t(1.5)
    f = 35 + 45 * np.exp(-tt / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.45)
    noise = one_pole_lowpass(RNG.standard_normal(len(tt)), 900) * np.exp(-tt / 0.12)
    return boom + 0.8 * noise


def riser() -> np.ndarray:
    tt = t(2.0)
    phase = tt / 2.0
    f = 200 + 1000 * phase ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    noise = one_pole_lowpass(RNG.standard_normal(len(tt)), 400 + 6000 * phase)
    env = phase ** 2 * np.minimum(1, (2.0 - tt) / 0.03)
    return (0.4 * tone + noise) * env


if __name__ == "__main__":
    write("music-bed-100bpm-48s.wav", music_bed(), peak=0.8)
    write("sfx-whoosh-short.wav", whoosh(0.7))
    write("sfx-whoosh-long.wav", whoosh(1.2))
    write("sfx-pop.wav", pop())
    write("sfx-tick.wav", tick(), peak=0.5)
    write("sfx-impact.wav", impact(), peak=0.9)
    write("sfx-riser.wav", riser())
