"""Voice-over with Gemini 3.8 TTS (Interactions API), one WAV per scene.

The script is a Markdown file (default `vo.md` in the project):

    > voice: Kore
    > style: warm, confident, speaking at a steady pace

    ## hook
    Every launch starts with a countdown.

    ## launch
    > style: urgent, rising excitement
    Three... <short pause> two... one. LIFTOFF!

`## <scene id>` headings split the script into segments (use the beat-map scene
ids so each line can start on its scene's downbeat). `> voice:` / `> style:`
lines set defaults at the top and override them per segment. Text is spoken
verbatim: use `<short pause>`, `<breath>` and similar inline tags for vocal
events, and CAPITALS for emphasis (Gemini 3.8 TTS prompting guide).

Output: audio/vo/<segment>.wav (48 kHz mono, loudness-matched), audio/vo/vo.json
(manifest with durations, model, voice, style, text hashes), and one credits.json
entry. Next step: `mstudio words <slug> audio/vo/<segment>.wav` for word timing.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import secrets
from .util import StudioError, ffprobe, read_json, run, write_json

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODELS = {"flash": "gemini-3.8-flash-tts", "lite": "gemini-3.8-flash-lite-tts"}
DEFAULT_MODEL = MODELS["flash"]
DEFAULT_VOICE = "Kore"
VOICES = {
    "Zephyr": "bright", "Puck": "upbeat", "Charon": "informative", "Kore": "firm", "Fenrir": "excitable",
    "Leda": "youthful", "Orus": "firm", "Aoede": "breezy", "Callirrhoe": "easy-going", "Autonoe": "bright",
    "Enceladus": "breathy", "Iapetus": "clear", "Umbriel": "easy-going", "Algieba": "smooth", "Despina": "smooth",
    "Erinome": "clear", "Algenib": "gravelly", "Rasalgethi": "informative", "Laomedeia": "upbeat", "Achernar": "soft",
    "Alnilam": "firm", "Schedar": "even", "Gacrux": "mature", "Pulcherrima": "forward", "Achird": "friendly",
    "Zubenelgenubi": "casual", "Vindemiatrix": "gentle", "Sadachbia": "lively", "Sadaltager": "knowledgeable",
    "Sulafat": "warm",
}


def parse_script(text: str) -> list[dict[str, str]]:
    """Split a VO script into segments: [{'id', 'text', 'voice', 'style'}]."""
    defaults = {"voice": DEFAULT_VOICE, "style": ""}
    segments: list[dict[str, str]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        meta = re.match(r"^>\s*(voice|style)\s*:\s*(.+)$", line, re.I)
        head = re.match(r"^#{1,6}\s+([A-Za-z][\w.-]*)\s*$", line)
        if head:
            current = {"id": head.group(1), "lines": [], "voice": None, "style": None}
            segments.append(current)
        elif meta:
            target = current if current is not None else defaults
            target[meta.group(1).lower()] = meta.group(2).strip()
        elif line and not line.startswith("<!--"):
            if current is None:
                current = {"id": "main", "lines": [], "voice": None, "style": None}
                segments.append(current)
            current["lines"].append(line)
    out = []
    for s in segments:
        spoken = " ".join(s["lines"]).strip()
        if spoken:
            out.append({"id": s["id"], "text": spoken, "voice": s["voice"] or defaults["voice"], "style": s["style"] or defaults["style"]})
    if not out:
        raise StudioError("the VO script has no spoken text")
    ids = [s["id"] for s in out]
    if len(ids) != len(set(ids)):
        raise StudioError(f"duplicate segment ids in VO script: {ids}")
    return out


def request_body(text: str, voice: str, style: str, model: str) -> dict[str, Any]:
    content: dict[str, Any] = {"type": "text", "text": text}
    if style:
        content["annotations"] = [{"type": "speech_metadata", "style": style}]
    return {
        "model": model,
        "input": [{"type": "user_input", "content": [content]}],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }


def extract_audio(response: dict[str, Any]) -> bytes:
    """Last audio block of the model output (REST: steps[].content[] with type 'audio')."""
    blocks = [c for step in response.get("steps", []) if step.get("type") == "model_output"
              for c in step.get("content", []) if c.get("type") == "audio" and c.get("data")]
    if not blocks:
        output = response.get("output_audio") or {}
        if output.get("data"):
            blocks = [output]
    if not blocks:
        raise StudioError("Gemini returned no audio (check the model name and that the text is speakable)")
    return base64.b64decode(blocks[-1]["data"])


def _post(body: dict[str, Any], key: str, retries: int = 3, timeout: float = 180.0) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(ENDPOINT, data=data, method="POST",
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = secrets.scrub(exc.read().decode("utf-8", errors="replace")[:600])
            if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            hint = {400: "bad request (voice name? text too long?)", 401: "API key not valid: run `mstudio keys setup gemini`",
                    403: "API key not allowed to use this model", 404: "model not found",
                    429: "rate limit or quota reached"}.get(exc.code, "")
            raise StudioError(f"Gemini TTS failed: HTTP {exc.code} {hint}\n{detail}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise StudioError(f"could not reach the Gemini API: {getattr(exc, 'reason', exc)}") from None
    raise StudioError("Gemini TTS failed after retries")


def synthesize(project: Path, script: Path, *, model: str = DEFAULT_MODEL, voice: str | None = None,
               style: str | None = None, only: list[str] | None = None, target_lufs: float = -16.0) -> dict[str, Any]:
    key = secrets.require_key("gemini")
    segments = parse_script(script.read_text(encoding="utf-8"))
    if only:
        segments = [s for s in segments if s["id"] in only]
    out_dir = project / "audio" / "vo"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "vo.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {"segments": {}}
    made = []
    for seg in segments:
        v = voice or seg["voice"]
        if v not in VOICES and not v.startswith(("voice_", "voicekey_")):
            raise StudioError(f"unknown voice '{v}' (prebuilt: {', '.join(VOICES)}; or a custom voice_... id)")
        st = style if style is not None else seg["style"]
        body = request_body(seg["text"], v, st, model)
        wav = extract_audio(_post(body, key))
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.wav"
            raw.write_bytes(wav if wav[:4] == b"RIFF" else _wrap_pcm(wav))
            dest = out_dir / f"{seg['id']}.wav"
            # 48 kHz like the rest of the mix; dialogue loudness ~ -16 LUFS so music can sit 4-6 dB under it
            run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                 f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11,aresample=48000", "-ac", "1", "-c:a", "pcm_s16le", str(dest)])
        dur = ffprobe(dest)["duration"]
        manifest["segments"][seg["id"]] = {"file": f"audio/vo/{seg['id']}.wav", "duration": round(dur, 3), "model": model,
                                           "voice": v, "style": st, "text": seg["text"],
                                           "text_sha256": hashlib.sha256(seg["text"].encode("utf-8")).hexdigest()}
        made.append({"id": seg["id"], "duration": round(dur, 2), "voice": v})
    manifest.update({"script": script.name, "provider": "Google Gemini API (Interactions)"})
    write_json(manifest_path, manifest)
    _credit(project, model)
    return {"segments": made, "manifest": "audio/vo/vo.json"}


def _wrap_pcm(pcm: bytes, rate: int = 24000) -> bytes:
    import struct
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    return header + b"data" + struct.pack("<I", len(pcm)) + pcm


def _credit(project: Path, model: str) -> None:
    path = project / "credits.json"
    credits = read_json(path) if path.is_file() else {"assets": []}
    credits["assets"] = [c for c in credits["assets"] if c.get("path") != "audio/vo"]
    credits["assets"].append({"path": "audio/vo", "what": f"AI voice-over generated with {model}",
                              "source": "Google Gemini API (generated for this project)",
                              "license": "Generated output under the Gemini API Terms of Service; disclose AI voice where platforms require it",
                              "author": "Google Gemini TTS"})
    write_json(path, credits)
