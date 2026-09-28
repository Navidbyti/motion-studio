"""Environment check with a concrete fix for every failure."""
from __future__ import annotations

import os
import re
import shutil
import sys
from typing import Any

from .util import GSAP_VERSION, HYPERFRAMES_VERSION, REPO, find_chrome, run


def _version(cmd: list[str]) -> str | None:
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        out = run([exe, *cmd[1:]], check=False, timeout=60)
    except Exception:  # noqa: BLE001 - a broken tool is reported, not raised
        return None
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[0] if text else "?"


def doctor() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, fix: str = "") -> None:
        rows.append({"check": name, "ok": ok, "detail": detail, "fix": "" if ok else fix})

    add("python", sys.version_info >= (3, 11), sys.version.split()[0], "install Python 3.11+")
    nodev = _version(["node", "--version"])
    major = int(re.sub(r"[^\d].*", "", nodev.lstrip("v"))) if nodev else 0
    add("node", major >= 22, nodev or "missing", "install Node.js 22 or newer")
    for tool in ("ffmpeg", "ffprobe"):
        v = _version([tool, "-version"])
        add(tool, v is not None, (v or "missing")[:60], f"install FFmpeg and put {tool} on PATH")
    hf = REPO / "node_modules" / "hyperframes" / "package.json"
    hf_v = re.search(r'"version":\s*"([^"]+)"', hf.read_text(encoding="utf-8")).group(1) if hf.is_file() else None
    add("hyperframes", hf_v == HYPERFRAMES_VERSION, f"{hf_v or 'not installed'} (pinned {HYPERFRAMES_VERSION})", "run `npm install` in the repo root")
    gs = REPO / "node_modules" / "gsap" / "package.json"
    gs_v = re.search(r'"version":\s*"([^"]+)"', gs.read_text(encoding="utf-8")).group(1) if gs.is_file() else None
    add("gsap", gs_v == GSAP_VERSION, f"{gs_v or 'not installed'} (pinned {GSAP_VERSION})", "run `npm install` in the repo root")
    chrome = find_chrome()
    kind = "HyperFrames headless shell" if chrome and ".cache" in chrome else "system Chrome (screenshot capture path)" if chrome else "missing"
    add("chrome", chrome is not None, f"{kind}: {chrome or ''}", "run `npx hyperframes browser ensure`, or install Google Chrome")
    for mod in ("numpy", "scipy", "jsonschema"):
        try:
            __import__(mod)
            add(mod, True, "ok")
        except ImportError:
            add(mod, False, "missing", "pip install -e .")
    from .secrets import get_key, mask
    key, source = get_key("gemini")
    add("gemini key", True, f"{mask(key)} ({source})" if key else "not set (optional: voice-over; `mstudio keys setup gemini`)")
    telemetry = os.environ.get("HYPERFRAMES_NO_TELEMETRY") or "1 (set by mstudio for every HyperFrames call)"
    add("telemetry", True, f"HYPERFRAMES_NO_TELEMETRY={telemetry}")
    sfx = REPO / "third_party" / "motion-bang-bang" / "assets" / "sfx" / "library.json"
    add("sfx library", sfx.is_file(), "third_party/motion-bang-bang/assets/sfx", "restore third_party/ from git")
    add("fonts", all((REPO / "assets" / "fonts" / f).is_file() for f in ("Inter-Variable.ttf", "Vazirmatn-Variable.ttf", "JetBrainsMono-Variable.ttf")),
        "Inter, JetBrains Mono, Vazirmatn (OFL)", "restore assets/fonts/ from git")
    return rows
