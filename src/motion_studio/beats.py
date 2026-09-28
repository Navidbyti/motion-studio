"""Music understanding for beat-synced editing.

`analyze(path)` turns a music (or any audio) file into `beats.json`:
tempo with confidence, every beat with its attack refined on the waveform,
downbeats and bars, per-beat kick / snare / hat detection, energy per bar,
structural sections (intro, build, drop, break, outro) and a ranked list
of hit candidates following the hit hierarchy in skills/house-style.

Method (standard MIR building blocks, implemented with numpy/scipy only,
because librosa's import can hang on Windows):

1. Log-magnitude STFT, spectral flux per band (kick 30-150 Hz,
   snare 1.2-4.5 kHz, hats 6-10.5 kHz) and full band.
2. Tempo from the autocorrelation of the onset envelope, weighted by a
   log-normal prior around 120 BPM (Ellis 2007), octave-checked.
3. Beat tracking by dynamic programming (Ellis 2007), then each beat's
   attack is refined on a 2 ms energy envelope of the waveform. When the
   tempo is steady the beats are replaced by a least-squares constant grid.
4. Downbeat phase from kick weight, backbeat snares and beat-synchronous
   chroma change (chords change on the one).
5. Sections from a Foote checkerboard novelty on bar-level features.
"""
from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d
from scipy.signal import find_peaks

from .util import sha256_file

SR = 22050
N_FFT = 1024
HOP = 256
FRAME_RATE = SR / HOP
BANDS = {"kick": (30.0, 150.0), "snare": (1200.0, 4500.0), "hat": (6000.0, 10500.0)}
SCHEMA_VERSION = 1


class BeatError(RuntimeError):
    pass


# --------------------------------------------------------------------------- signal

def decode(path: str | Path, sr: int = SR) -> np.ndarray:
    try:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
            capture_output=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise BeatError(f"ffmpeg could not decode audio from {path}: {exc.stderr.decode(errors='replace')[-300:]}") from exc
    y = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    if y.size < sr:
        raise BeatError(f"{path}: less than one second of audio")
    return y


def stft_mag(y: np.ndarray) -> np.ndarray:
    pad = N_FFT // 2
    y = np.pad(y, pad, mode="reflect")
    n_frames = 1 + (len(y) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = y[idx] * np.hanning(N_FFT)[None, :]
    return np.abs(np.fft.rfft(frames, axis=1))  # (frames, bins)


def band_flux(logmag: np.ndarray, lo: float, hi: float) -> np.ndarray:
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    sel = (freqs >= lo) & (freqs < hi)
    d = np.diff(logmag[:, sel], axis=0, prepend=logmag[:1, sel])
    return np.maximum(0.0, d).mean(axis=1)


def normalize(env: np.ndarray) -> np.ndarray:
    env = env - uniform_filter1d(env, size=int(FRAME_RATE * 0.5))  # remove slow trend
    env = np.maximum(env, 0.0)
    scale = np.percentile(env, 99) or 1.0
    return env / scale


def chroma(mag: np.ndarray) -> np.ndarray:
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    sel = (freqs >= 60) & (freqs <= 5000)
    pitch = (np.round(12 * np.log2(freqs[sel] / 440.0)) + 9) % 12  # C = 0
    out = np.zeros((mag.shape[0], 12))
    power = mag[:, sel] ** 2
    for pc in range(12):
        out[:, pc] = power[:, pitch == pc].sum(axis=1)
    return out


# --------------------------------------------------------------------------- tempo + beats

def estimate_tempo(onset: np.ndarray, min_bpm: float, max_bpm: float, prior_bpm: float = 120.0) -> list[tuple[float, float]]:
    x = onset - onset.mean()
    n = len(x)
    spec = np.fft.rfft(x, 2 * n)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    ac = ac / (ac[0] or 1.0)
    lags = np.arange(1, n)
    bpm = 60.0 * FRAME_RATE / lags
    ok = (bpm >= min_bpm) & (bpm <= max_bpm)
    prior = np.exp(-0.5 * (np.log2(bpm / prior_bpm) / 0.55) ** 2)
    score = np.where(ok, ac[1:] * prior, -np.inf)
    # parabolic refinement around the best lags
    candidates: list[tuple[float, float]] = []
    order = np.argsort(score)[::-1]
    for lag_i in order:
        if len(candidates) >= 3 or not np.isfinite(score[lag_i]):
            break
        lag = lags[lag_i]
        if any(abs(60 * FRAME_RATE / lag - c[0]) / c[0] < 0.04 for c in candidates):
            continue
        a, b, c = (ac[lag - 1], ac[lag], ac[lag + 1]) if 1 < lag < n - 1 else (0, ac[lag], 0)
        denom = a - 2 * b + c
        frac = 0.5 * (a - c) / denom if denom else 0.0
        true_lag = lag + max(-0.5, min(0.5, frac))
        candidates.append((60.0 * FRAME_RATE / true_lag, float(score[lag_i])))
    if not candidates:
        raise BeatError("no tempo found in range")
    # Octave check: a strong pulse at half the period means the faster tempo is the beat
    # (kick on 1 and 3 with snare on 2 and 4 makes the half-note period win the raw autocorrelation).
    best_bpm = candidates[0][0]
    lag = 60.0 * FRAME_RATE / best_bpm
    half = int(round(lag / 2))
    if 2 * best_bpm <= min(max_bpm, 180.0) and half > 1 and ac[half] >= 0.5 * ac[int(round(lag))]:
        doubled = (best_bpm * 2, candidates[0][1] * 1.0001)
        candidates = [doubled] + [c for c in candidates if abs(c[0] - doubled[0]) / doubled[0] > 0.04]
    top = candidates[0][1]
    return [(round(b, 3), round(s / top, 3) if top > 0 else 0.0) for b, s in candidates]


def track_beats(onset: np.ndarray, bpm: float, tightness: float = 100.0) -> np.ndarray:
    period = 60.0 * FRAME_RATE / bpm
    win = np.arange(-int(period), int(period) + 1)
    kernel = np.exp(-0.5 * (win * 32.0 / period) ** 2)
    local = np.convolve(onset / (onset.std() or 1.0), kernel, mode="same")
    n = len(local)
    backlink = np.full(n, -1, dtype=int)
    cumscore = local.copy()
    lo, hi = int(round(-2 * period)), int(round(-period / 2))
    offsets = np.arange(lo, hi + 1)
    txcost = -tightness * np.log(-offsets / period) ** 2
    first = True
    for i in range(n):
        cand = i + offsets
        valid = cand >= 0
        if not valid.any():
            continue
        scores = np.where(valid, cumscore[np.clip(cand, 0, n - 1)] + txcost, -np.inf)
        j = int(np.argmax(scores))
        if first and local[i] < 0.01 * local.max():
            cumscore[i] = local[i]
            continue
        first = False
        cumscore[i] = local[i] + scores[j]
        backlink[i] = cand[j]
    # last beat: highest cumulative score among local maxima near the end
    peaks = np.flatnonzero((cumscore[1:-1] >= cumscore[:-2]) & (cumscore[1:-1] >= cumscore[2:])) + 1
    tail = peaks[cumscore[peaks] >= 0.5 * np.median(cumscore[peaks])] if peaks.size else np.array([n - 1])
    beats = [int(tail[-1])]
    while backlink[beats[-1]] >= 0:
        beats.append(int(backlink[beats[-1]]))
    beats = np.array(beats[::-1])
    # trim weak leading/trailing beats (silence, fades)
    strength = local[beats]
    thresh = 0.5 * np.sqrt(np.mean(strength ** 2))
    keep = np.flatnonzero(strength >= thresh)
    return beats[keep[0]: keep[-1] + 1] if keep.size else beats


def refine_attack(y: np.ndarray, t: float, search: float = 0.04) -> tuple[float, float]:
    """Return (time, confidence) of the steepest energy rise near t, on a 2 ms envelope."""
    a = max(0, int((t - search) * SR))
    b = min(len(y), int((t + search) * SR))
    seg = y[a:b]
    if seg.size < 64:
        return t, 0.0
    w = max(1, int(0.002 * SR))
    energy = np.sqrt(uniform_filter1d(seg ** 2, size=w) + 1e-12)
    loge = 20 * np.log10(energy + 1e-9)
    rise = np.diff(uniform_filter1d(loge, size=w))
    k = int(np.argmax(rise))
    conf = float(rise[k] / (np.std(rise) * 6 + 1e-9))
    # the attack is where the energy leaves the pre-onset floor on its way to the peak
    pre = loge[max(0, k - int(0.02 * SR)):k + 1]
    floor = float(np.median(pre[: max(1, len(pre) // 3)]))
    peak = float(loge[k: k + int(0.02 * SR)].max())
    target = floor + 0.15 * (peak - floor)
    start = k
    while start > 0 and loge[start] > target:
        start -= 1
    return (a + start) / SR, min(1.0, conf)


def fit_grid(times: np.ndarray) -> tuple[float, float, float]:
    """Least-squares constant grid t_i = t0 + i*T. Returns (T, t0, rms residual in s)."""
    i = np.arange(len(times))
    T, t0 = np.polyfit(i, times, 1)
    resid = times - (t0 + T * i)
    return float(T), float(t0), float(np.sqrt(np.mean(resid ** 2)))


# --------------------------------------------------------------------------- analysis

@dataclass
class Features:
    y: np.ndarray
    onset: np.ndarray
    bands: dict[str, np.ndarray]
    chroma: np.ndarray
    rms_db: np.ndarray
    band_db: dict[str, np.ndarray]


def features(y: np.ndarray) -> Features:
    mag = stft_mag(y)
    logmag = np.log1p(100.0 * mag)
    full = np.maximum(0.0, np.diff(logmag, axis=0, prepend=logmag[:1])).mean(axis=1)
    bands = {name: normalize(band_flux(logmag, lo, hi)) for name, (lo, hi) in BANDS.items()}
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    power = mag ** 2
    rms_db = 10 * np.log10(power.mean(axis=1) + 1e-12)
    band_db = {name: 10 * np.log10(power[:, (freqs >= lo) & (freqs < hi)].mean(axis=1) + 1e-12)
               for name, (lo, hi) in {"low": (20, 250), "mid": (250, 4000), "high": (4000, 11000)}.items()}
    return Features(y, normalize(full), bands, chroma(mag), rms_db, band_db)


def _at(env: np.ndarray, t: float, radius: float = 0.05) -> float:
    a = max(0, int((t - radius) * FRAME_RATE))
    b = min(len(env), int((t + radius) * FRAME_RATE) + 1)
    return float(env[a:b].max()) if b > a else 0.0


def _mean_between(arr: np.ndarray, t0: float, t1: float) -> Any:
    a = max(0, int(t0 * FRAME_RATE))
    b = max(a + 1, min(len(arr), int(t1 * FRAME_RATE)))
    return arr[a:b].mean(axis=0)


def _peaks(env: np.ndarray, min_gap: float, rel: float) -> np.ndarray:
    height = rel * np.percentile(env, 99)
    idx, _ = find_peaks(env, height=height, distance=max(1, int(min_gap * FRAME_RATE)))
    return idx / FRAME_RATE


def two_class_threshold(values: np.ndarray, min_ratio: float = 1.5, _depth: int = 0) -> float:
    """Otsu split of per-beat band strengths (hit vs bleed). Returns +inf when the band has no clear hits."""
    v = np.log(np.maximum(values, 1e-4))
    if len(v) < 4 or np.ptp(v) < 1e-6:
        return float("inf")
    best, best_t = -1.0, float(np.median(v))
    for t in np.linspace(v.min(), v.max(), 64)[1:-1]:
        lo, hi = v[v <= t], v[v > t]
        if len(lo) < 2 or len(hi) < 2:
            continue
        between = len(lo) * len(hi) * (lo.mean() - hi.mean()) ** 2
        if between > best:
            best, best_t = between, float(t)
    lo, hi = v[v <= best_t], v[v > best_t]
    if len(hi) == 0 or len(lo) == 0 or np.exp(hi.mean() - lo.mean()) < min_ratio:
        return float("inf")
    # The first split often separates "drums playing" from "no drums" (intros, breaks). Split the active
    # beats again: hits vs bleed from other instruments (kick into the snare band, bass into the kick band).
    active = values[values > np.exp(best_t)]
    if _depth < 1 and len(active) >= 6:
        inner = two_class_threshold(active, min_ratio, _depth=_depth + 1)
        if np.isfinite(inner):
            return inner
    return float(np.exp(best_t))


def downbeat_phase(beat_times: np.ndarray, f: Features, meter: int) -> tuple[int, float]:
    kick = np.array([_at(f.bands["kick"], t) for t in beat_times])
    snare = np.array([_at(f.bands["snare"], t) for t in beat_times])
    bounds = np.append(beat_times, beat_times[-1] + np.median(np.diff(beat_times)))
    chroma_beats = np.array([_mean_between(f.chroma, bounds[i], bounds[i + 1]) for i in range(len(beat_times))])
    norm = np.linalg.norm(chroma_beats, axis=1, keepdims=True) + 1e-9
    cb = chroma_beats / norm
    novelty = np.r_[0.0, 1.0 - np.sum(cb[1:] * cb[:-1], axis=1)]
    novelty = novelty / (novelty.max() or 1.0)
    best, best_score = 0, -np.inf
    scores = []
    for phase in range(meter):
        on = np.arange(phase, len(beat_times), meter)
        score = 1.0 * kick[on].mean() + 1.5 * novelty[on].mean() - 0.5 * snare[on].mean()
        if meter == 4:
            back = np.r_[np.arange(phase + 1, len(beat_times), 4), np.arange(phase + 3, len(beat_times), 4)]
            score += 0.5 * snare[back].mean() if back.size else 0.0
        scores.append(score)
        if score > best_score:
            best, best_score = phase, score
    ordered = sorted(scores, reverse=True)
    margin = (ordered[0] - ordered[1]) / (abs(ordered[0]) + 1e-9) if len(ordered) > 1 else 1.0
    return best, round(float(min(1.0, max(0.0, margin * 3))), 3)


def sections(bar_times: np.ndarray, f: Features, end_time: float) -> list[dict[str, Any]]:
    bounds = np.append(bar_times, end_time)
    rows = []
    for i in range(len(bar_times)):
        t0, t1 = bounds[i], bounds[i + 1]
        ch = _mean_between(f.chroma, t0, t1)
        ch = ch / (np.linalg.norm(ch) + 1e-9)
        rows.append(np.r_[
            _mean_between(f.rms_db, t0, t1), _mean_between(f.band_db["low"], t0, t1),
            _mean_between(f.band_db["mid"], t0, t1), _mean_between(f.band_db["high"], t0, t1),
            _mean_between(f.onset, t0, t1) * 10, ch * 3,
        ])
    X = np.array(rows)
    X_raw = X.copy()
    if len(X) < 4:
        return [{"start_bar": 0, "end_bar": len(bar_times)}]
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    S = Xn @ Xn.T
    L = 4 if len(X) >= 32 else 2
    sign = np.sign(np.arange(-L, L) + 0.5)
    kernel = np.outer(sign, sign) * np.exp(-0.5 * (np.arange(-L, L)[:, None] ** 2 + np.arange(-L, L)[None, :] ** 2) / (L ** 2))
    Sp = np.pad(S, L, mode="edge")
    nov = np.array([np.sum(Sp[i:i + 2 * L, i:i + 2 * L] * kernel) for i in range(len(X))])
    nov = np.maximum(nov, 0)
    height = nov.mean() + 0.5 * nov.std()
    peaks, _ = find_peaks(nov, height=height, distance=max(2, L))
    rms = X_raw[:, 0]
    low = X_raw[:, 1]
    jumps = [i for i in range(1, len(rms)) if abs(rms[i] - rms[i - 1]) >= 3.0 or abs(low[i] - low[i - 1]) >= 5.0]
    marks = sorted(set(int(p) for p in peaks if 0 < p < len(X)) | set(jumps))
    merged: list[int] = []
    for m in marks:  # keep boundaries at least 2 bars apart, preferring energy jumps
        if merged and m - merged[-1] < 2:
            if m in jumps and merged[-1] not in jumps:
                merged[-1] = m
            continue
        merged.append(m)
    cuts = [0] + merged + [len(X)]
    return [{"start_bar": a, "end_bar": b} for a, b in zip(cuts[:-1], cuts[1:]) if b > a]


def label_sections(secs: list[dict[str, Any]], bar_rms: np.ndarray, bar_low: np.ndarray,
                   bar_times: np.ndarray, end_time: float) -> list[dict[str, Any]]:
    energy = [float(np.median(bar_rms[s["start_bar"]:s["end_bar"]])) for s in secs]
    low = [float(np.median(bar_low[s["start_bar"]:s["end_bar"]])) for s in secs]
    median = float(np.median(bar_rms))
    q = np.percentile(bar_rms, [33, 66])
    out = []
    for i, s in enumerate(secs):
        kind = "section"
        if i > 0 and energy[i] - energy[i - 1] >= 3.0 and low[i] - low[i - 1] >= 3.0:
            kind = "drop"
        elif i > 0 and energy[i] - energy[i - 1] <= -4.0 and i < len(secs) - 1:
            kind = "break"
        elif i == 0 and energy[i] < median - 1.0:
            kind = "intro"
        elif i == len(secs) - 1 and energy[i] < median - 1.0:
            kind = "outro"
        level = "low" if energy[i] <= q[0] else "high" if energy[i] >= q[1] else "mid"
        start_t = float(bar_times[s["start_bar"]])
        end_t = float(bar_times[s["end_bar"]]) if s["end_bar"] < len(bar_times) else end_time
        out.append({"index": i, "kind": kind, "energy": level, "energy_db": round(energy[i], 2),
                    "start_bar": s["start_bar"], "end_bar": s["end_bar"],
                    "start": round(start_t, 4), "end": round(end_t, 4)})
    for i, s in enumerate(out[:-1]):
        if out[i + 1]["kind"] == "drop" and s["kind"] in ("section", "intro"):
            bars = bar_rms[s["start_bar"]:s["end_bar"]]
            if len(bars) >= 2 and np.polyfit(np.arange(len(bars)), bars, 1)[0] > 0.3:
                s["kind"] = "build"
    return out


def grid_search(env: np.ndarray, bpm: float, duration: float, span: float = 0.012) -> tuple[float, float, float]:
    """Constant-tempo grid (bpm, t0) maximizing mean onset energy at grid points (after fit-beat-grid.py)."""
    best = (-np.inf, bpm, 0.0)
    for cand in np.arange(bpm * (1 - span), bpm * (1 + span), 0.01):
        T = 60.0 / cand
        k = np.arange(int(duration / T) + 1)
        phases = np.arange(0.0, T, 0.002)
        pos = (phases[:, None] + T * k[None, :]) * FRAME_RATE
        valid = pos < len(env) - 1
        i0 = np.clip(np.floor(pos).astype(int), 0, len(env) - 2)
        frac = pos - i0
        vals = np.where(valid, env[i0] * (1 - frac) + env[i0 + 1] * frac, 0.0)
        score = vals.sum(axis=1) / np.maximum(1, valid.sum(axis=1))
        j = int(np.argmax(score))
        if score[j] > best[0]:
            best = (float(score[j]), float(cand), float(phases[j]))
    return best[1], best[2], best[0]


def grid_is_stable(env: np.ndarray, T: float, phase: float, duration: float, max_shift: float = 0.02) -> bool:
    """True when every quarter of the track best fits the global grid within ±max_shift seconds."""
    shifts = np.arange(-T / 2, T / 2, 0.002)
    quarters = np.linspace(0, duration, 5)
    locked = 0
    counted = 0
    for a, b in zip(quarters[:-1], quarters[1:]):
        k = np.arange(np.ceil((a - phase) / T), np.floor((b - phase) / T) + 1)
        if len(k) < 4:
            continue
        pos = (phase + T * k[None, :] + shifts[:, None]) * FRAME_RATE
        idx = np.clip(np.round(pos).astype(int), 0, len(env) - 1)
        score = env[idx].mean(axis=1)
        if score.max() < 0.15:          # no drums in this quarter (intro pads, breaks): no evidence either way
            continue
        counted += 1
        locked += abs(shifts[int(np.argmax(score))]) <= max_shift
    return bool(counted > 0 and locked == counted)


def analyze(path: str | Path, *, min_bpm: float = 60.0, max_bpm: float = 200.0,
            meter: int | None = None, bpm_hint: float | None = None) -> dict[str, Any]:
    path = Path(path)
    y = decode(path)
    duration = len(y) / SR
    f = features(y)
    pulse = normalize(f.bands["kick"] + f.bands["snare"] + 0.5 * f.onset)
    candidates = estimate_tempo(pulse, min_bpm, max_bpm, bpm_hint or 120.0)
    bpm = candidates[0][0]
    beat_frames = track_beats(pulse, bpm)
    if len(beat_frames) < 8:
        raise BeatError("fewer than 8 beats found; is this music?")
    dp_times = beat_frames / FRAME_RATE
    ioi = np.diff(dp_times)
    med = float(np.median(ioi))
    # Steady tempo test: fit one constant grid, then check that each quarter of the track locks to the
    # same phase. Music on a click (most produced music) passes; live, rubato or tempo-ramped music drifts.
    g_bpm, g_phase, _ = grid_search(pulse, bpm, duration)
    steady = grid_is_stable(normalize(f.bands["kick"] + f.bands["snare"]), 60.0 / g_bpm, g_phase, duration)
    attack_conf = {}
    if steady:
        bpm, phase0 = g_bpm, g_phase
        T = 60.0 / bpm
        audible = np.flatnonzero(f.rms_db > f.rms_db.max() - 45)
        start = audible[0] / FRAME_RATE if audible.size else 0.0
        end = audible[-1] / FRAME_RATE if audible.size else duration
        k0 = int(np.ceil((start - phase0 - 0.12) / T))
        k1 = int(np.floor((end - phase0) / T))
        times = phase0 + T * np.arange(k0, k1 + 1)
        # sub-frame correction: median attack offset over clearly percussive beats
        offsets = []
        for t in times:
            if _at(f.bands["kick"], t) > 0.3 or _at(f.bands["snare"], t) > 0.3:
                rt, conf = refine_attack(y, t)
                if conf >= 0.35 and abs(rt - t) < 0.03:
                    offsets.append(rt - t)
        shift = float(np.median(offsets)) if len(offsets) >= 4 else 0.0
        times = times + shift
        resid = float(np.std(offsets)) if offsets else 0.0
        attack_conf = {i: 1.0 if (_at(f.bands["kick"], t) > 0.3 or _at(f.bands["snare"], t) > 0.3) else 0.0 for i, t in enumerate(times)}
        times = np.clip(times[times >= -0.02], 0.0, None)
    else:
        refined = []
        for i, t in enumerate(dp_times):
            rt, conf = refine_attack(y, t)
            use = conf >= 0.35 and abs(rt - t) < 0.035
            refined.append(rt if use else t)
            attack_conf[i] = conf if use else 0.0
        times = np.array(refined)
        T = float(np.median(np.diff(times)))
        bpm = 60.0 / T
        resid = float(np.std(np.diff(times)))
    attack_conf = [attack_conf.get(i, 0.0) for i in range(len(times))]

    meters = [meter] if meter else [4, 3]
    choice = {}
    for m in meters:
        phase, conf = downbeat_phase(times, f, m)
        choice[m] = (phase, conf)
    m = meters[0] if meter else (3 if choice[3][1] > choice[4][1] * 1.6 else 4)
    phase, db_conf = choice[m]

    beats = []
    kick = np.array([_at(f.bands["kick"], t) for t in times])
    snare = np.array([_at(f.bands["snare"], t) for t in times])
    hat = np.array([_at(f.bands["hat"], t, 0.03) for t in times])
    thr = {k: two_class_threshold(v) for k, v in (("kick", kick), ("snare", snare), ("hat", hat))}
    hat_onsets = _peaks(f.bands["hat"], 0.06, 0.25)
    for i, t in enumerate(times):
        bar_pos = (i - phase) % m
        nxt = times[i + 1] if i + 1 < len(times) else t + T
        subs = int(np.sum((hat_onsets > t + 0.03) & (hat_onsets < nxt - 0.03)))
        beats.append({
            "i": i, "t": round(float(t), 4), "bar": int((i - phase) // m), "beat_in_bar": int(bar_pos) + 1,
            "downbeat": bar_pos == 0, "strength": round(float(_at(f.onset, t)), 3),
            "kick": bool(kick[i] > thr["kick"] and kick[i] > 0.15), "snare": bool(snare[i] > thr["snare"] and snare[i] > 0.15),
            "hat": bool(hat[i] > thr["hat"] and hat[i] > 0.15), "offbeat_hats": subs,
            "attack_confidence": round(attack_conf[i], 3),
            "energy_db": round(float(_mean_between(f.rms_db, t, nxt)), 2),
        })
    downbeats = [b["t"] for b in beats if b["downbeat"]]
    bar_times = np.array(downbeats)
    bar_bounds = np.append(bar_times, min(duration, bar_times[-1] + m * T)) if len(bar_times) else np.array([0.0])
    bar_rms = np.array([float(_mean_between(f.rms_db, bar_bounds[i], bar_bounds[i + 1])) for i in range(len(bar_times))])
    bar_low = np.array([float(_mean_between(f.band_db["low"], bar_bounds[i], bar_bounds[i + 1])) for i in range(len(bar_times))])
    secs = label_sections(sections(bar_times, f, duration), bar_rms, bar_low, bar_times, duration) if len(bar_times) >= 4 else []
    bar_section = {}
    for s in secs:
        for b in range(s["start_bar"], s["end_bar"]):
            bar_section[b] = s["index"]
    quiet_cut = np.percentile(bar_rms, 25) if len(bar_rms) else 0
    bars = [{"i": i, "t": round(float(t), 4), "energy_db": round(float(bar_rms[i]), 2),
             "low_db": round(float(bar_low[i]), 2), "quiet": bool(bar_rms[i] <= quiet_cut),
             "kicks": int(sum(1 for b in beats if b["bar"] == i and b["kick"])),
             "snares": int(sum(1 for b in beats if b["bar"] == i and b["snare"])),
             "section": bar_section.get(i)} for i, t in enumerate(bar_times)]

    onsets = {name: [round(float(t), 4) for t in _peaks(env, 0.07 if name != "hat" else 0.05, 0.3)]
              for name, env in f.bands.items()}
    hits = hit_candidates(beats, secs)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"file": path.name, "sha256": sha256_file(path), "duration": round(duration, 4)},
        "analysis": {"sample_rate": SR, "hop": HOP, "time_resolution_ms": round(1000 / FRAME_RATE, 2),
                     "attack_refinement_ms": 2, "method": "flux+autocorr tempo, DP beats, waveform attack refinement"},
        "tempo": {"bpm": round(float(bpm), 3), "steady": steady, "timing_spread_ms": round(resid * 1000, 2),
                  "candidates": [{"bpm": b, "score": s} for b, s in candidates],
                  "beat_period": round(float(T), 5)},
        "meter": m,
        "downbeat_confidence": db_conf,
        "beat0": round(float(times[0]), 4),
        "first_downbeat": downbeats[0] if downbeats else None,
        "beats": beats,
        "downbeats": downbeats,
        "bars": bars,
        "sections": secs,
        "drops": [s["start"] for s in secs if s["kind"] == "drop"],
        "onsets": onsets,
        "hits": hits,
    }


def hit_candidates(beats: list[dict[str, Any]], secs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map musical events to the house hit hierarchy (strongest tier wins per time)."""
    tier_of = {}
    for s in secs:
        if s["index"] > 0:
            tier_of[round(s["start"], 4)] = ("scene", "drop" if s["kind"] == "drop" else "section")
    for b in beats:
        t = b["t"]
        if t in tier_of:
            continue
        if b["downbeat"]:
            tier_of[t] = ("big", "downbeat")
        elif b["snare"]:
            tier_of[t] = ("punch", "snare")
        else:
            tier_of[t] = ("entrance", "beat")
    order = {"scene": 0, "big": 1, "punch": 2, "entrance": 3}
    return [{"t": t, "tier": tier, "event": ev} for t, (tier, ev) in sorted(tier_of.items(), key=lambda x: (x[0], order[x[1][0]]))]


def summary(data: dict[str, Any]) -> str:
    t = data["tempo"]
    lines = [
        f"{data['source']['file']}: {t['bpm']:.2f} BPM ({'steady grid' if t['steady'] else 'variable'}; attack spread {t['timing_spread_ms']} ms), "
        f"{data['meter']}/4, first downbeat {data['first_downbeat']} s (confidence {data['downbeat_confidence']})",
        f"{len(data['beats'])} beats, {len(data['bars'])} bars, drops at {data['drops'] or 'none'}",
        "sections: " + ", ".join(f"{s['kind']}[{s['energy']}] bars {s['start_bar']}-{s['end_bar'] - 1} ({s['start']:.2f}s)" for s in data["sections"]),
    ]
    return "\n".join(lines)


def write(data: dict[str, Any], out: str | Path) -> None:
    Path(out).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def frame_of(t: float, fps: float) -> int:
    return int(math.floor(t * fps + 0.5))
