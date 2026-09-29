"""Build steps around HyperFrames: sync generated files, check, snapshot, render, deliver."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from . import audio, beatmap, data, footage
from .project import RATIOS, log_decision, now, require_gates, state
from .util import HYPERFRAMES_VERSION, StudioError, ffprobe, hyperframes, read_json, write_json


def sync(project: Path) -> list[str]:
    """Regenerate timing.js / data.js / reframe.js and write beat-map timing into index.html."""
    done = []
    if (project / "beatmap.json").is_file():
        resolved = beatmap.resolve(project)
        if not resolved["ok"]:
            raise StudioError("beatmap has errors:\n" + beatmap.report(resolved))
        beatmap.apply(project)
        done.append("beatmap")
    if (project / "data" / "bindings.json").is_file():
        data.bind(project)
        done.append("data")
    if (project / "footage" / "reframe.json").is_file():
        st = state(project)
        w, h = RATIOS[st["ratio"]]
        r = footage.reframe(project, (w, h))
        if not r["ok"]:
            raise StudioError("reframe.json has errors:\n" + "\n".join(i["message"] for i in r["issues"] if i["level"] == "error"))
        done.append("reframe")
    return done


def check(project: Path) -> dict[str, Any]:
    proc = hyperframes(["check", ".", "--json", "--at-transitions", "--max-transition-samples", "40"], cwd=project, check=False, timeout=900)
    text = proc.stdout.strip()
    start = text.find("{")
    try:
        result = json.loads(text[start:]) if start >= 0 else {}
    except json.JSONDecodeError:
        result = {"ok": False, "raw": text[-3000:]}
    result.setdefault("ok", proc.returncode == 0)
    write_json(project / "renders" / "qa" / "hyperframes-check.json", result)
    return result


def styleframes(project: Path, times: list[float]) -> list[str]:
    out = project / "styleframes"
    out.mkdir(exist_ok=True)
    sync(project)
    hyperframes(["snapshot", ".", "--at", ",".join(f"{t:.3f}" for t in times), "--no-end", "--describe", "false",
                 "--output", "styleframes"], cwd=project, timeout=900)
    return sorted(p.name for p in out.glob("*.png"))


def render(project: Path, *, draft: bool = False, keep_gain: bool = False, sfx: bool = True) -> dict[str, Any]:
    st = state(project)
    require_gates(project, "AB" if st["mode"] != "benchmark" else "AB")
    t0 = time.time()
    synced = sync(project)
    checked = check(project)
    lint_errors = _lint_errors(checked)
    if lint_errors:
        raise StudioError("hyperframes check found errors (fix them before rendering):\n" + "\n".join(lint_errors[:20]))
    renders = project / "renders"
    renders.mkdir(exist_ok=True)
    picture = renders / "picture.mp4"
    t1 = time.time()
    hyperframes(["render", ".", "-o", str(picture), "--fps", str(st["fps"]), "--quality", "draft" if draft else "high",
                 "--no-best-effort"], cwd=project, timeout=3600)
    t2 = time.time()
    prev_gain = None
    if keep_gain and (renders / "sound.json").is_file():
        prev_gain = read_json(renders / "sound.json").get("gain_db")
    sound = audio.mix(project, keep_gain=prev_gain, sfx=sfx)
    t3 = time.time()
    info = ffprobe(renders / "master.mp4")
    report = {"at": now(), "hyperframes": HYPERFRAMES_VERSION, "draft": draft, "synced": synced,
              "seconds": {"prepare_and_check": round(t1 - t0, 1), "render": round(t2 - t1, 1), "sound": round(t3 - t2, 1), "total": round(t3 - t0, 1)},
              "master": info, "sound": sound}
    write_json(renders / "render.json", report)
    log_decision(project, "render", f"Rendered v{st['version']} ({'draft' if draft else 'high'}) in {report['seconds']['total']} s.", "")
    return report


def _lint_errors(checked: dict[str, Any]) -> list[str]:
    errors = []
    lint = checked.get("lint") or {}
    for f in lint.get("findings", []) if isinstance(lint, dict) else []:
        if f.get("severity") == "error":
            errors.append(f"{f.get('code')}: {f.get('message')} ({f.get('selector') or f.get('file', '')})")
    if not errors and checked.get("ok") is False and lint.get("errorCount"):
        errors.append(f"{lint.get('errorCount')} lint errors (see renders/qa/hyperframes-check.json)")
    return errors


def deliver(project: Path) -> dict[str, Any]:
    st = state(project)
    qa_report = project / "renders" / "qa" / "report.json"
    if not qa_report.is_file() or not read_json(qa_report).get("pass"):
        raise StudioError("QA has not passed on the current render: run `mstudio qa` first")
    master = project / "renders" / "master.mp4"
    track = (read_json(project / "beatmap.json").get("music") or {}).get("file") if (project / "beatmap.json").is_file() else None
    if track and (project / track).is_file():
        from .music import record_use
        record_use(st["slug"], project / track)   # lets QA flag a recycled bed on the next project
    dest = project / "renders" / "delivery"
    dest.mkdir(exist_ok=True)
    name = f"{st['slug']}_{st['ratio'].replace(':', 'x')}_v{st['version']}"
    final = dest / f"{name}.mp4"
    shutil.copy2(master, final)
    from .util import run
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(0.0, ffprobe(master)["duration"] * 0.25)), "-i", str(master), "-frames:v", "1",
         "-q:v", "3", str(dest / f"{name}_poster.jpg")])
    credits = read_json(project / "credits.json")
    summary = {"file": final.name, "spec": ffprobe(final), "credits": credits, "qa": read_json(qa_report)["summary"], "delivered": now()}
    write_json(dest / f"{name}.json", summary)
    log_decision(project, "deliver", f"Delivered {final.name}.", "")
    return summary
