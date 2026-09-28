"""Shared helpers: paths, hashing, subprocess, ffprobe, Chrome and HyperFrames discovery."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO = PACKAGE_DIR.parents[1]
HYPERFRAMES_VERSION = "0.8.82"
GSAP_VERSION = "3.14.2"


class StudioError(RuntimeError):
    """A user-facing failure with an actionable message."""


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(cmd: list[str], cwd: str | Path | None = None, env: dict[str, str] | None = None,
        check: bool = True, capture: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=capture, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        raise StudioError(f"command failed ({proc.returncode}): {' '.join(map(str, cmd))}\n{tail}")
    return proc


# --------------------------------------------------------------------------- media

def ffprobe(path: str | Path) -> dict[str, Any]:
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels,duration"
               ":format=duration,size,bit_rate", "-of", "json", str(path)]).stdout
    info = json.loads(out)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = float(Fraction(v["r_frame_rate"])) if v and v.get("r_frame_rate") not in (None, "0/0") else None
    return {
        "duration": float(info.get("format", {}).get("duration") or 0.0),
        "bytes": int(info.get("format", {}).get("size") or 0),
        "video": None if v is None else {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
                                         "fps": round(fps, 3) if fps else None, "fps_fraction": v.get("r_frame_rate")},
        "audio": None if a is None else {"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate") or 0),
                                         "channels": a.get("channels")},
    }


def loudness(path: str | Path) -> dict[str, float | None]:
    proc = run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"], check=False)
    log = proc.stderr
    summary = log[log.rfind("Summary:"):]
    import re
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return {"integrated_lufs": float(i.group(1)) if i else None,
            "lra": float(lra.group(1)) if lra else None,
            "true_peak_dbtp": float(tp.group(1)) if tp and tp.group(1) != "-inf" else None}


# --------------------------------------------------------------------------- tools

def find_chrome() -> str | None:
    """Chrome for HyperFrames and our inspectors: env override, HyperFrames cache, then system Chrome."""
    for key in ("HYPERFRAMES_BROWSER_PATH", "CHROME"):
        if os.environ.get(key) and Path(os.environ[key]).is_file():
            return os.environ[key]
    cache = Path.home() / ".cache" / "hyperframes" / "chrome"
    if cache.is_dir():
        for exe in sorted(cache.rglob("chrome-headless-shell*")):
            if exe.is_file() and exe.suffix in ("", ".exe"):
                return str(exe)
    candidates = {
        "win32": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                  str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe")],
        "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium"],
    }.get(sys.platform, [])
    for c in candidates:
        if Path(c).is_file():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def tool_env() -> dict[str, str]:
    """Environment for every HyperFrames / Chrome child process."""
    env = dict(os.environ)
    # HyperFrames auto-sends snapshot frames to Gemini ("--describe") whenever a Gemini key is in its
    # environment. Client frames must not leave the machine by accident, so it never gets our keys.
    for secret in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "HEYGEN_API_KEY", "HYPERFRAMES_API_KEY", "ELEVENLABS_API_KEY"):
        env.pop(secret, None)
    env.setdefault("HYPERFRAMES_NO_TELEMETRY", "1")  # client work: no usage reporting
    env.setdefault("HYPERFRAMES_SKIP_SKILLS", "1")
    env.setdefault("NODE_NO_WARNINGS", "1")
    chrome = find_chrome()
    if chrome and "HYPERFRAMES_BROWSER_PATH" not in env:
        env["HYPERFRAMES_BROWSER_PATH"] = chrome
    return env


def npx() -> str:
    exe = shutil.which("npx.cmd" if os.name == "nt" else "npx") or shutil.which("npx")
    if not exe:
        raise StudioError("npx not found: install Node.js 22 or newer")
    return exe


def node() -> str:
    exe = shutil.which("node")
    if not exe:
        raise StudioError("node not found: install Node.js 22 or newer")
    return exe


def hyperframes(args: list[str], cwd: str | Path, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
    """Run the pinned HyperFrames CLI (local node_modules first, then npx with an exact pin)."""
    local = REPO / "node_modules" / ".bin" / ("hyperframes.cmd" if os.name == "nt" else "hyperframes")
    cmd = [str(local)] if local.exists() else [npx(), "--yes", f"hyperframes@{HYPERFRAMES_VERSION}"]
    return run(cmd + args, cwd=cwd, env=tool_env(), check=check, timeout=timeout)


def rel(path: str | Path, root: str | Path) -> str:
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
