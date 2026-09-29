"""Post-render sound: SFX cues from the beat map, mix, loudness, mux.

Sound is a post-render decision (the Bang Motion method): the picture render
already carries the music bed and natural sound from the composition's
<audio> elements. This module adds sound effects on the beat map's hit frames
and normalizes loudness, copying the video stream untouched, so changing a
sound never re-renders a frame.

Loudness: measured integrated loudness is corrected with one static gain to
the delivery target (default -14 LUFS), then a true-peak limiter holds the
ceiling (default -1.5 dBTP, which measures at or under -1 dBTP after AAC).
On a revision the previous version's gain can be reused (`keep_gain`) so
unchanged scenes stay sample-identical.
"""
from __future__ import annotations

import json
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .util import REPO, StudioError, ffprobe, loudness, read_json, run, write_json

LIBRARY = REPO / "third_party" / "motion-bang-bang" / "assets" / "sfx"
TIER_TRIGGER = {"scene": "into", "big": "slam", "punch": "pop", "entrance": "fly", "micro": "pop", "counter": "counter"}
TIER_GAIN = {"scene": 1.0, "big": 1.0, "punch": 0.0, "entrance": -2.0, "micro": -4.0, "counter": -2.0}
PEAK_ALIGNED = {"whoosh", "transition"}  # these build into the hit: align their loudest point to the impact


def _library() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec = read_json(LIBRARY / "library.json")
    return spec["assets"], spec["mix"]


def _wav_envelope_peak(path: Path) -> tuple[float, float]:
    """(onset seconds, peak seconds) of a short sound file."""
    import subprocess  # binary PCM on stdout
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True).stdout
    y = np.abs(np.frombuffer(raw, dtype=np.float32))
    if y.size == 0:
        return 0.0, 0.0
    env = np.convolve(y, np.ones(40) / 40, mode="same")
    peak = int(np.argmax(env))
    thresh = 0.1 * env[peak]
    onset = int(np.argmax(env > thresh))
    return onset / 8000, peak / 8000


def _portable(file: Path, project: Path) -> str:
    """Store cue files relative to the project or the repository, never as machine-specific absolute paths."""
    file = file.resolve()
    for base, prefix in ((project.resolve(), ""), (REPO.resolve(), "@repo/")):
        try:
            return prefix + file.relative_to(base).as_posix()
        except ValueError:
            continue
    return str(file)


def _resolve_cue_file(name: str, project: Path) -> str:
    return str(REPO / name[6:]) if name.startswith("@repo/") else str((project / name) if not Path(name).is_absolute() else Path(name))


def _duration(path: Path) -> float:
    return ffprobe(path)["duration"]


def _jitter(*parts: str, span: float = 1.0) -> float:
    """Deterministic value in [-span, span] from a stable hash (same project -> same mix)."""
    import hashlib
    h = int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return (h * 2 - 1) * span


def cues(project: Path) -> list[dict[str, Any]]:
    """Cue sheet from beatmap.json `sfx` fields (plus tier defaults when rules.auto_sfx is on)."""
    spec = read_json(project / "beatmap.json")
    resolved = read_json(project / "beatmap.resolved.json")
    fps = resolved["fps"]
    auto = spec.get("rules", {}).get("auto_sfx", True)
    assets, mix = _library()
    by_trigger: dict[str, list[dict[str, Any]]] = {}
    for a in assets:
        for trig in a.get("trigger", []):
            by_trigger.setdefault(trig, []).append(a)
    raw_events = {ev["id"]: ev for sc in spec["scenes"] for ev in sc.get("events", [])}
    project_sfx = read_json(project / "audio" / "sfx" / "sfx.json") if (project / "audio" / "sfx" / "sfx.json").is_file() else {}
    out = []
    use_count: dict[str, int] = {}
    file_uses: dict[str, int] = {}
    for eid, e in sorted(resolved["events"].items(), key=lambda kv: kv[1]["impact_frame"]):
        want = raw_events.get(eid, {}).get("sfx", "auto" if auto else None)
        if want in (None, "none", False):
            continue
        tier = e["tier"]
        layers = want if isinstance(want, list) else [want]      # a list layers several sounds on one hit
        for layer_i, one in enumerate(layers):
            if one == "auto":
                trig = TIER_TRIGGER.get(tier)
                if not trig or trig not in by_trigger:
                    continue
                pool = by_trigger[trig]
                asset = pool[use_count.get(trig, 0) % len(pool)]  # rotate takes so repeats do not sound mechanical
                use_count[trig] = use_count.get(trig, 0) + 1
                file, family, align_mode = LIBRARY / asset["file"], asset["family"], None
            elif str(one).startswith("file:"):
                file = project / str(one)[5:]
                meta = project_sfx.get(file.name, {})
                family, align_mode = "custom", meta.get("align")
            else:
                pool = [a for a in assets if a["family"] == one]
                if not pool:
                    raise StudioError(f"event {eid}: no SFX family '{one}' (families: {sorted({a['family'] for a in assets})}); "
                                      "or use \"file:audio/sfx/<name>.wav\" for project sounds (mstudio sfx)")
                asset = pool[use_count.get(one, 0) % len(pool)]
                use_count[one] = use_count.get(one, 0) + 1
                file, family, align_mode = LIBRARY / asset["file"], asset["family"], None
            if not file.is_file():
                raise StudioError(f"event {eid}: SFX file {file} missing")
            fam = mix.get(family, {"gain_db": -12, "max_hits_per_s": 2})
            onset, peak = _wav_envelope_peak(file)
            length = _duration(file)
            mode = align_mode or ("peak" if family in PEAK_ALIGNED else "onset")
            align = {"peak": peak, "onset": onset, "end": length}.get(mode, onset)
            t = e["impact_frame"] / fps - align
            gain = fam["gain_db"] + TIER_GAIN.get(tier, 0.0) + float(raw_events.get(eid, {}).get("sfx_gain_db", 0.0)) - 3.0 * (layer_i > 0)
            key = _portable(file, project)
            n = file_uses.get(key, 0)
            file_uses[key] = n + 1
            # a repeated sound gets a small, deterministic pitch/level shift so it never sounds copy-pasted
            semis = 0.0 if n == 0 else _jitter(eid, key, span=1.5)
            out.append({"event": eid, "tier": tier, "family": family if layer_i == 0 else f"{family}+layer", "file": key,
                        "t": round(max(0.0, t), 4), "impact": e["impact_frame"] / fps, "align": mode,
                        "gain_db": round(gain + (0 if n == 0 else _jitter(eid, key + "g", span=1.0)), 2), "semitones": round(semis, 2),
                        "repeat": n, "max_hits_per_s": fam.get("max_hits_per_s", 2)})
    # density: per family, keep the stronger tier when two cues crowd the same second
    order = {"scene": 0, "big": 1, "counter": 2, "punch": 3, "entrance": 4, "micro": 5}
    kept: list[dict[str, Any]] = []
    for c in sorted(out, key=lambda c: (order.get(c["tier"], 9), c["impact"])):
        limit = c["max_hits_per_s"] or 0
        window = [k for k in kept if k["family"] == c["family"] and abs(k["impact"] - c["impact"]) < 1.0]
        if limit and len(window) >= limit:
            c["dropped"] = "family density"
            continue
        if any(abs(k["impact"] - c["impact"]) < 0.06 and k["event"] != c["event"] for k in kept):
            c["dropped"] = "masked by a simultaneous cue"
            continue
        kept.append(c)
    return sorted(kept, key=lambda c: c["t"]) + [c for c in out if c.get("dropped")]


def mix(project: Path, *, target_lufs: float = -14.0, ceiling_dbtp: float = -1.5, keep_gain: float | None = None,
        sfx: bool = True) -> dict[str, Any]:
    picture = project / "renders" / "picture.mp4"
    if not picture.is_file():
        raise StudioError("renders/picture.mp4 missing: run `mstudio render` first")
    info = ffprobe(picture)
    duration = info["duration"]
    sheet = cues(project) if sfx and (project / "beatmap.resolved.json").is_file() else []
    active = [c for c in sheet if not c.get("dropped")]
    write_json(project / "renders" / "sfx-cues.json", sheet)
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "mix.wav"
        inputs = ["-i", str(picture)]
        base = "[0:a]aresample=48000,aformat=channel_layouts=stereo[base]" if info["audio"] else \
               f"anullsrc=r=48000:cl=stereo,atrim=0:{duration:.4f}[base]"
        chains = [base]
        labels = ["[base]"]
        for i, c in enumerate(active, start=1):
            inputs += ["-i", _resolve_cue_file(c["file"], project)]
            ms = int(round(c["t"] * 1000))
            pitch = f"asetrate={int(48000 * 2 ** (c.get('semitones', 0) / 12))},aresample=48000," if c.get("semitones") else ""
            chains.append(f"[{i}:a]aresample=48000,{pitch}aformat=channel_layouts=stereo,volume={c['gain_db']}dB,adelay={ms}|{ms}[c{i}]")
            labels.append(f"[c{i}]")
        chains.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,atrim=0:{duration:.4f}[mix]")
        run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains), "-map", "[mix]",
             "-c:a", "pcm_s24le", str(stem)])
        measured = loudness(stem)
        if measured["integrated_lufs"] is None:
            raise StudioError("the mix is silent; nothing to normalize")
        master = project / "renders" / "master.mp4"
        # Static gain, then a 4x-oversampled peak limiter (a true-peak approximation). Limiting lowers the
        # integrated level, so re-measure and correct the gain; lower the ceiling if AAC overshoots.
        gain = keep_gain if keep_gain is not None else round(target_lufs - measured["integrated_lufs"], 2)
        ceiling = ceiling_dbtp
        attempts = []
        for _ in range(4):
            limit = 10 ** (ceiling / 20)
            chain = (f"volume={gain}dB,aresample=192000,alimiter=limit={limit:.4f}:attack=2:release=80:level=disabled:asc=1,"
                     "aresample=48000")
            run(["ffmpeg", "-v", "error", "-y", "-i", str(picture), "-i", str(stem), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "copy", "-af", chain, "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart",
                 "-shortest", str(master)])
            final = loudness(master)
            attempts.append({"gain_db": gain, "ceiling_dbtp": ceiling, **final})
            i_ok = keep_gain is not None or abs(final["integrated_lufs"] - target_lufs) <= 0.4
            tp_ok = final["true_peak_dbtp"] is not None and final["true_peak_dbtp"] <= ceiling_dbtp + 0.5
            if i_ok and tp_ok:
                break
            if not tp_ok:
                ceiling -= 0.5
            if not i_ok:
                gain = round(gain + (target_lufs - final["integrated_lufs"]), 2)
    report = {"cues": len(active), "dropped": len(sheet) - len(active), "pre_mix": measured, "gain_db": gain,
              "target_lufs": target_lufs, "ceiling_dbtp": ceiling, "master": final, "attempts": attempts}
    write_json(project / "renders" / "sound.json", report)
    return report
