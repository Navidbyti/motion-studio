"""Scoped revisions: change one scene, prove the rest did not move.

`start()` freezes the current version under versions/v<n>/ (composition,
beat map, generated timing/data/reframe files, renders) and opens revision
n+1 targeting one scene. After the edit and a new render, `verify()` compares
every frame of the new picture with the frozen one (PSNR; GPU rasterization
is not bit-exact, so near-identical frames count as unchanged) and passes only
when all changed frames sit inside the target scene's window, plus any
transition overlap on its edges.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from .project import log_decision, now, state
from .util import StudioError, read_json, run, write_json

FROZEN = ["index.html", "beatmap.json", "beatmap.resolved.json", "timing.js", "data.js", "reframe.js", "copy.json",
          "brief.json", "script.md", "brand.css", "renders/picture.mp4", "renders/master.mp4", "renders/sound.json", "renders/render.json"]
UNCHANGED_PSNR_DB = 42.0


def start(project: Path, scene: str, request: str) -> dict[str, Any]:
    st = state(project)
    resolved = read_json(project / "beatmap.resolved.json")
    if scene not in {s["id"] for s in resolved["scenes"]}:
        raise StudioError(f"scene '{scene}' is not in the beat map (scenes: {[s['id'] for s in resolved['scenes']]})")
    if not (project / "renders" / "picture.mp4").is_file():
        raise StudioError("render the current version before revising it")
    version = st["version"]
    dest = project / "versions" / f"v{version}"
    if dest.exists():
        raise StudioError(f"{dest} already exists")
    for rel in FROZEN:
        src = project / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
    for folder in ("compositions", "data", "footage"):
        src = project / folder
        if src.is_dir():
            shutil.copytree(src, dest / folder, ignore=shutil.ignore_patterns("conformed", "sheets", "*.mp4", "*.mov", "*.wav"))
    st["version"] = version + 1
    st["revision"] = {"version": version + 1, "base": version, "scene": scene, "request": request, "opened": now(), "verified": False}
    write_json(project / "state.json", st)
    log_decision(project, "revision", f"Opened v{version + 1}: scene {scene}. Request: {request}", "")
    return st["revision"]


def _psnr_per_frame(a: Path, b: Path) -> list[float]:
    proc = run(["ffmpeg", "-nostats", "-i", str(a), "-i", str(b), "-lavfi", "[0:v][1:v]psnr=stats_file=-", "-f", "null", "-"], check=False)
    values = []
    for m in re.finditer(r"psnr_avg:(inf|[\d.]+)", proc.stdout + proc.stderr):
        values.append(float("inf") if m.group(1) == "inf" else float(m.group(1)))
    return values


def verify(project: Path) -> dict[str, Any]:
    st = state(project)
    rev = st.get("revision")
    if not rev:
        raise StudioError("no open revision (`mstudio revise <slug> start --scene ...`)")
    base = project / "versions" / f"v{rev['base']}"
    old, new = base / "renders" / "picture.mp4", project / "renders" / "picture.mp4"
    if not new.is_file() or new.stat().st_mtime <= old.stat().st_mtime:
        raise StudioError("render the revised version first")
    resolved = read_json(project / "beatmap.resolved.json")
    old_resolved = read_json(base / "beatmap.resolved.json")
    scene_new = next(s for s in resolved["scenes"] if s["id"] == rev["scene"])
    scene_old = next(s for s in old_resolved["scenes"] if s["id"] == rev["scene"])
    lo = min(scene_new["enter_frame"], scene_old["enter_frame"])
    hi = max(scene_new["end_frame"], scene_old["end_frame"])
    # the next scene's transition-in may overlap the revised scene's tail
    for s in resolved["scenes"]:
        if s["start_frame"] == scene_new["end_frame"]:
            hi = max(hi, s["start_frame"] + s.get("overlap_frames", 0))
    moved = [s["id"] for s in resolved["scenes"] if s["id"] != rev["scene"]
             and any(o["id"] == s["id"] and (o["start_frame"], o["end_frame"]) != (s["start_frame"], s["end_frame"]) for o in old_resolved["scenes"])]
    psnr = _psnr_per_frame(old, new)
    changed = [i for i, p in enumerate(psnr) if p < UNCHANGED_PSNR_DB]
    outside = [i for i in changed if not (lo <= i < hi)]
    ok = not outside and not moved and len(psnr) > 0
    ranges = _ranges(outside)
    result = {"ok": ok, "scene": rev["scene"], "window": [lo, hi], "changed_frames": len(changed), "outside": len(outside),
              "frames_compared": len(psnr), "moved_scenes": moved,
              "summary": (f"revision v{rev['version']} changed {len(changed)} frame(s), all inside scene {rev['scene']} [{lo}, {hi})"
                          if ok else f"{len(outside)} changed frame(s) outside scene {rev['scene']} [{lo}, {hi}); moved scenes: {moved or 'none'}"),
              "items": [f"frames {a}-{b}" for a, b in ranges] + [f"scene {m} moved" for m in moved]}
    if ok:
        st["revision"]["verified"] = True
        write_json(project / "state.json", st)
    write_json(project / "renders" / "qa" / "revision.json", result)
    return result


def _ranges(frames: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for f in frames:
        if out and f == out[-1][1] + 1:
            out[-1] = (out[-1][0], f)
        else:
            out.append((f, f))
    return out
