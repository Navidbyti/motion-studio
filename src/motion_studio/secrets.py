"""Local API keys: stored per user, outside the repository, never printed.

Keys live in ~/.motion-studio/secrets/<name>_api_key.txt (override the folder
with MSTUDIO_HOME). An environment variable (e.g. GEMINI_API_KEY) wins over
the file. Two ways to put a key there without it passing through a chat:

  mstudio keys setup gemini            creates the file with instructions and opens it in the
                                       default text editor; the user pastes the key and saves
  mstudio keys setup gemini --wait 300 same, then waits until the key is saved and validates it
  mstudio keys setup gemini --prompt   hidden terminal input (only in a real terminal)

Agents: never ask for a key in chat, never read the key file, never echo a key.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .util import StudioError

PROVIDERS = {
    "gemini": {
        "env": "GEMINI_API_KEY",
        "label": "Google Gemini API key",
        "get_url": "https://aistudio.google.com/apikey",
        "used_for": "Gemini TTS voice-over (mstudio tts) and Lyria music generation (mstudio music gen)",
    },
    "elevenlabs": {
        "env": "ELEVENLABS_API_KEY",
        "label": "ElevenLabs API key",
        "get_url": "https://elevenlabs.io/app/settings/api-keys",
        "used_for": "generated sound effects (mstudio sfx gen)",
    },
}

MARKER = "# Paste your key on the next line, then save and close this file."


def home() -> Path:
    return Path(os.environ.get("MSTUDIO_HOME") or (Path.home() / ".motion-studio"))


def key_file(name: str) -> Path:
    _provider(name)
    return home() / "secrets" / f"{name}_api_key.txt"


def _provider(name: str) -> dict:
    if name not in PROVIDERS:
        raise StudioError(f"unknown key '{name}' (known: {', '.join(PROVIDERS)})")
    return PROVIDERS[name]


def mask(key: str) -> str:
    return f"{key[:4]}…{key[-4:]}" if len(key) > 12 else "…"


def _read_file_key(path: Path) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line.strip("'\" ")
    return None


def get_key(name: str) -> tuple[str | None, str]:
    """(key, source) where source is 'env', 'file' or 'missing'."""
    p = _provider(name)
    if os.environ.get(p["env"], "").strip():
        return os.environ[p["env"]].strip(), "env"
    key = _read_file_key(key_file(name))
    return (key, "file") if key else (None, "missing")


def require_key(name: str) -> str:
    key, _ = get_key(name)
    if not key:
        p = PROVIDERS[name]
        raise StudioError(f"no {p['label']} yet. Run `mstudio keys setup {name}`: it opens a local file for the user to paste the key "
                          f"into (get one at {p['get_url']}). Never ask for the key in chat.")
    return key


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if os.name != "nt":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        path.parent.chmod(stat.S_IRWXU)


def template(name: str) -> str:
    p = PROVIDERS[name]
    return (f"# Motion Studio: {p['label']}\n"
            f"# Used for: {p['used_for']}\n"
            f"# Get a key: {p['get_url']}\n"
            "# This file stays on this computer, outside the repository. Don't share it.\n"
            f"{MARKER}\n\n")


def open_in_editor(path: Path) -> bool:
    try:
        if os.name == "nt":
            subprocess.Popen(["notepad.exe", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-t", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except OSError:
        return False


def validate(name: str, key: str, timeout: float = 20.0) -> tuple[bool, str]:
    """Cheap authenticated call; never includes the key in the message."""
    if name == "gemini":
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
                                     headers={"x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200, "key accepted by the Gemini API"
        except urllib.error.HTTPError as exc:
            reason = {400: "rejected as malformed", 401: "not valid", 403: "not allowed (check the key's API restrictions)",
                      429: "valid but rate-limited right now"}.get(exc.code, f"HTTP {exc.code}")
            return exc.code == 429, f"key {reason}"
        except (urllib.error.URLError, TimeoutError) as exc:
            return False, f"could not reach the Gemini API ({getattr(exc, 'reason', exc)})"
    if name == "elevenlabs":
        req = urllib.request.Request("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200, "key accepted by ElevenLabs"
        except urllib.error.HTTPError as exc:
            return exc.code == 429, f"key {'valid but rate-limited' if exc.code == 429 else 'rejected'} (HTTP {exc.code})"
        except (urllib.error.URLError, TimeoutError) as exc:
            return False, f"could not reach ElevenLabs ({getattr(exc, 'reason', exc)})"
    return False, "no validator"


def setup(name: str, *, wait: float = 0.0, prompt: bool = False, open_editor: bool = True) -> dict:
    p = _provider(name)
    path = key_file(name)
    if prompt:
        if not sys.stdin.isatty():
            raise StudioError("--prompt needs a real terminal; use the file method (`mstudio keys setup gemini`) from an agent")
        key = getpass.getpass(f"{p['label']} (input hidden): ").strip()
        if not key:
            raise StudioError("no key entered")
        _write_private(path, template(name) + key + "\n")
        ok, msg = validate(name, key)
        return {"path": str(path), "stored": True, "valid": ok, "message": msg, "masked": mask(key)}
    if not _read_file_key(path):
        _write_private(path, template(name))
    opened = open_editor and open_in_editor(path)
    result = {"path": str(path), "opened": opened, "stored": bool(_read_file_key(path))}
    if wait > 0 and not result["stored"]:
        deadline = time.time() + wait
        while time.time() < deadline:
            time.sleep(2)
            if _read_file_key(path):
                result["stored"] = True
                break
    key = _read_file_key(path)
    if key:
        ok, msg = validate(name, key)
        result.update({"valid": ok, "message": msg, "masked": mask(key)})
        if not re.fullmatch(r"[A-Za-z0-9_\-.]{20,}", key):
            result["warning"] = "the saved line doesn't look like an API key (spaces or odd characters?)"
    return result


def status() -> list[dict]:
    rows = []
    for name, p in PROVIDERS.items():
        key, source = get_key(name)
        rows.append({"name": name, "label": p["label"], "source": source, "masked": mask(key) if key else None,
                     "path": str(key_file(name)), "env": p["env"]})
    return rows


def remove(name: str) -> bool:
    path = key_file(name)
    if path.is_file():
        path.unlink()
        return True
    return False


def scrub(text: str) -> str:
    """Remove any configured key from text before it is logged or raised."""
    for name in PROVIDERS:
        key, _ = get_key(name)
        if key:
            text = text.replace(key, mask(key))
    return text


def dumps_safe(obj) -> str:
    return scrub(json.dumps(obj))
