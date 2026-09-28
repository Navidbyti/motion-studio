"""Project workspace, pipeline stages, approval gates and the decision log."""
from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path
from typing import Any

from .util import REPO, StudioError, read_json, sha256_file, write_json

RATIOS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}
MODES = ("interactive", "express", "benchmark")
GATES = {"A": "style-brief.md", "B": "beatmap.json", "C": "styleframes"}
GATE_NAMES = {"A": "creative direction (style brief)", "B": "beat map", "C": "styleframes"}
PROJECTS = REPO / "projects"

STAGES = [
    ("0-intake", "brief.json filled in"),
    ("1-direction", "style-brief.md written and gate A approved"),
    ("2-script", "script.md written"),
    ("3-audio", "audio analysed (audio/beats.json) or brief says no music"),
    ("4-beatmap", "beatmap.json resolves cleanly and gate B approved"),
    ("5-styleframes", "3-5 styleframes in styleframes/ and gate C approved"),
    ("6-build", "index.html composition built from the beat map"),
    ("7-verify", "mstudio qa passes on the composition"),
    ("8-render", "renders/master.mp4 rendered, sound mixed, loudness normalized"),
    ("9-deliver", "delivery files + complete credits.json"),
]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def project_dir(slug_or_path: str) -> Path:
    p = Path(slug_or_path)
    if p.is_dir() and (p / "state.json").is_file():
        return p.resolve()
    candidate = PROJECTS / slug_or_path
    if (candidate / "state.json").is_file():
        return candidate
    raise StudioError(f"no Motion Studio project '{slug_or_path}' (looked in {p} and {candidate})")


def new_project(slug: str, *, ratio: str = "9:16", fps: int = 30, duration: float = 30.0, mode: str = "interactive",
                title: str = "", root: Path | None = None, brand: str | None = None) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", slug):
        raise StudioError("slug must be lowercase letters, digits and dashes (2-63 chars)")
    if ratio not in RATIOS:
        raise StudioError(f"ratio must be one of {', '.join(RATIOS)}")
    if mode not in MODES:
        raise StudioError(f"mode must be one of {', '.join(MODES)}")
    dest = (root or PROJECTS) / slug
    if dest.exists():
        raise StudioError(f"{dest} already exists; pick another slug or resume it with `mstudio status {slug}`")
    gsap = REPO / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if not gsap.is_file():
        raise StudioError("GSAP is not installed: run `npm install` in the repository root first")
    w, h = RATIOS[ratio]
    tpl = REPO / "templates" / "composition"
    dest.mkdir(parents=True)
    for sub in ("audio", "styleframes", "renders/qa", "data", "facts/sources", "footage", "vendor", "fonts", "versions"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    html = (tpl / "index.html").read_text(encoding="utf-8")
    html = html.replace("{{W}}", str(w)).replace("{{H}}", str(h)).replace("{{RATIO}}", ratio).replace("{{DURATION}}", _num(duration))
    (dest / "index.html").write_text(html, encoding="utf-8")
    for name in ("studio.js", "house.css"):
        shutil.copy2(tpl / name, dest / name)
    brand_css = REPO / "brands" / brand / "brand.css" if brand else None
    shutil.copy2(brand_css if brand_css and brand_css.is_file() else tpl / "brand.css", dest / "brand.css")
    shutil.copy2(gsap, dest / "vendor" / "gsap.min.js")
    for font in (REPO / "assets" / "fonts").glob("*.ttf"):
        shutil.copy2(font, dest / "fonts" / font.name)
    (dest / "timing.js").write_text("window.TIMING = {fps: %d, events: {}, scenes: {}, media: {}};\n" % fps, encoding="utf-8")
    (dest / "data.js").write_text("window.DATA = {values: {}, series: {}};\n", encoding="utf-8")
    (dest / "reframe.js").write_text("window.REFRAME = {};\n", encoding="utf-8")
    write_json(dest / "hyperframes.json", {"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                                           "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
                                           "media": {"autoProxy": True}})
    write_json(dest / "meta.json", {"id": slug, "name": title or slug})
    write_json(dest / "brief.json", {
        "title": title, "goal": "", "audience": "", "platform": "", "ratio": ratio, "fps": fps, "duration": duration,
        "language": "en", "direction": "ltr", "brand": brand or "house",
        "music": {"source": "file", "file": "", "license": ""}, "voiceover": {"enabled": False, "file": "", "script": ""},
        "inputs": [], "needs": {"facts": False, "data": False, "footage": False, "stock": False},
        "deliverables": [ratio], "constraints": [], "notes": "",
    })
    write_json(dest / "state.json", {"slug": slug, "mode": mode, "ratio": ratio, "fps": fps, "duration": duration,
                                     "created": now(), "version": 1, "tool_version": _tool_version()})
    write_json(dest / "approvals.json", {})
    write_json(dest / "credits.json", {"assets": []})
    (dest / "decisions.md").write_text(f"# Decisions: {title or slug}\n\nMode: {mode}. Every creative or technical choice: what was chosen, what else was considered, why.\n\n", encoding="utf-8")
    log_decision(dest, "setup", f"Created {ratio} {fps} fps {_num(duration)} s project in {mode} mode.", "")
    return dest


def refresh_runtime(dest: Path) -> list[str]:
    """(Re)install the runtime files a project needs: studio.js, house.css, GSAP, fonts, default generated files.

    Used for example projects checked out from git (which omit copied/generated files) and after a
    Motion Studio upgrade. Never touches index.html, compositions/, brand.css or project data.
    """
    gsap = REPO / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if not gsap.is_file():
        raise StudioError("GSAP is not installed: run `npm install` in the repository root first")
    tpl = REPO / "templates" / "composition"
    done = []
    for name in ("studio.js", "house.css"):
        shutil.copy2(tpl / name, dest / name)
        done.append(name)
    if not (dest / "brand.css").is_file():
        shutil.copy2(tpl / "brand.css", dest / "brand.css")
    (dest / "vendor").mkdir(exist_ok=True)
    shutil.copy2(gsap, dest / "vendor" / "gsap.min.js")
    (dest / "fonts").mkdir(exist_ok=True)
    for font in (REPO / "assets" / "fonts").glob("*.ttf"):
        shutil.copy2(font, dest / "fonts" / font.name)
    fps = read_json(dest / "state.json").get("fps", 30)
    defaults = {"timing.js": "window.TIMING = {fps: %d, events: {}, scenes: {}, media: {}};\n" % fps,
                "data.js": "window.DATA = {values: {}, series: {}};\n", "reframe.js": "window.REFRAME = {};\n"}
    for name, body in defaults.items():
        if not (dest / name).is_file():
            (dest / name).write_text(body, encoding="utf-8")
    for sub in ("renders/qa", "styleframes", "versions"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
    return done + ["vendor/gsap.min.js", "fonts/"]


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _tool_version() -> str:
    from . import __version__
    return __version__


def state(project: Path) -> dict[str, Any]:
    return read_json(project / "state.json")


def log_decision(project: Path, topic: str, choice: str, why: str, alternatives: str = "") -> None:
    with (project / "decisions.md").open("a", encoding="utf-8") as fh:
        fh.write(f"- **{now()} · {topic}**: {choice}")
        if alternatives:
            fh.write(f" _Considered:_ {alternatives}.")
        if why:
            fh.write(f" _Why:_ {why}")
        fh.write("\n")


# --------------------------------------------------------------------------- gates

def _artifact_hash(project: Path, gate: str) -> str | None:
    target = project / GATES[gate]
    if gate == "C":
        frames = sorted(target.glob("*.png")) if target.is_dir() else []
        if not frames:
            return None
        import hashlib
        h = hashlib.sha256()
        for f in frames:
            h.update(f.name.encode())
            h.update(sha256_file(f).encode())
        return h.hexdigest()
    return sha256_file(target) if target.is_file() else None


def approve(project: Path, gate: str, by: str, note: str = "") -> dict[str, Any]:
    gate = gate.upper()
    if gate not in GATES:
        raise StudioError("gate must be A, B or C")
    mode = state(project)["mode"]
    if by not in ("human", "agent"):
        raise StudioError("--by must be 'human' or 'agent'")
    if by == "agent" and mode == "interactive":
        raise StudioError(f"gate {gate} needs the human's approval in interactive mode: show them {GATES[gate]} and record --by human after they say yes")
    digest = _artifact_hash(project, gate)
    if digest is None:
        raise StudioError(f"gate {gate}: {GATES[gate]} does not exist yet")
    if gate == "B":
        resolved = project / "beatmap.resolved.json"
        if not resolved.is_file() or not read_json(resolved).get("ok"):
            raise StudioError("gate B: run `mstudio beatmap resolve` until it reports OK before approving")
        if read_json(resolved).get("source_sha256") not in (None, digest):
            raise StudioError("gate B: beatmap.json changed after it was resolved; resolve again")
    approvals = read_json(project / "approvals.json")
    approvals[gate] = {"approved_by": by, "at": now(), "note": note, "artifact": GATES[gate], "sha256": digest}
    write_json(project / "approvals.json", approvals)
    log_decision(project, f"gate {gate}", f"{GATE_NAMES[gate]} approved by {by}.", note)
    return approvals[gate]


def gate_status(project: Path) -> dict[str, str]:
    approvals = read_json(project / "approvals.json")
    out = {}
    for gate in GATES:
        a = approvals.get(gate)
        current = _artifact_hash(project, gate)
        if not a:
            out[gate] = "missing artifact" if current is None else "awaiting approval"
        elif a["sha256"] != current:
            out[gate] = "stale: artifact changed after approval"
        else:
            out[gate] = f"approved by {a['approved_by']}"
    return out


def require_gates(project: Path, gates: str) -> None:
    status = gate_status(project)
    missing = [g for g in gates if not status[g].startswith("approved")]
    if missing:
        detail = "; ".join(f"{g} ({GATE_NAMES[g]}): {status[g]}" for g in missing)
        raise StudioError(f"blocked by gate(s) {detail}. No composition code before gates A and B are approved.")


# --------------------------------------------------------------------------- stage detection

def current_stage(project: Path) -> tuple[str, str, list[str]]:
    """Return (stage id, what is needed next, notes)."""
    notes: list[str] = []
    brief = read_json(project / "brief.json")
    gates = gate_status(project)
    if not brief.get("goal") or not brief.get("title"):
        return STAGES[0][0], "fill brief.json (title, goal, audience, music, needs)", notes
    if not (project / "style-brief.md").is_file() or not gates["A"].startswith("approved"):
        return STAGES[1][0], "write style-brief.md (3 concepts + recommendation) and get gate A approved", notes
    if not (project / "script.md").is_file():
        return STAGES[2][0], "write script.md (exact on-screen copy)", notes
    music = brief.get("music", {}).get("source", "file")
    if music != "none" and not (project / "audio" / "beats.json").is_file():
        return STAGES[3][0], "analyse the music: mstudio beats <slug> audio/<track>", notes
    resolved = project / "beatmap.resolved.json"
    if not (project / "beatmap.json").is_file() or not resolved.is_file() or not read_json(resolved).get("ok") or not gates["B"].startswith("approved"):
        return STAGES[4][0], "write beatmap.json, `mstudio beatmap resolve` until OK, get gate B approved", notes
    if not gates["C"].startswith("approved"):
        return STAGES[5][0], "render 3-5 styleframes (mstudio styleframes) and get gate C approved", notes
    html = (project / "index.html").read_text(encoding="utf-8")
    if "Studio.hit(" not in html and "Studio.counter(" not in html:
        return STAGES[6][0], "build index.html from the beat map (Studio.hit for every event)", notes
    qa = project / "renders" / "qa" / "report.json"
    if not qa.is_file() or not read_json(qa).get("pass") or qa.stat().st_mtime < (project / "index.html").stat().st_mtime:
        return STAGES[7][0], "run `mstudio qa <slug>` and fix every failure", notes
    master = project / "renders" / "master.mp4"
    if not master.is_file():
        return STAGES[8][0], "run `mstudio render <slug>` (picture + sound + loudness)", notes
    if not (project / "renders" / "delivery").is_dir():
        return STAGES[9][0], "run `mstudio deliver <slug>`", notes
    return "done", "delivered; revisions go through `mstudio revise`", notes
