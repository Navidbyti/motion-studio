import base64
import io
import json
import subprocess

import pytest

from motion_studio import beatmap, beats, secrets, tts, util
from motion_studio.util import StudioError


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MSTUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(secrets, "validate", lambda name, key, timeout=20.0: (True, "key accepted (stub)"))
    return tmp_path / "home"


def test_key_file_setup_read_mask_and_env_precedence(home, monkeypatch):
    r = secrets.setup("gemini", open_editor=False)
    path = secrets.key_file("gemini")
    assert r["stored"] is False and path.is_file() and secrets.MARKER in path.read_text(encoding="utf-8")
    assert str(path).startswith(str(home))                      # outside the repository
    path.write_text(path.read_text(encoding="utf-8") + "AIzaSyTESTKEY000000000000000000000abcd\n", encoding="utf-8")
    key, source = secrets.get_key("gemini")
    assert source == "file" and key.endswith("abcd")
    assert secrets.mask(key) == "AIza…abcd" and key not in secrets.scrub(f"error for {key}")
    monkeypatch.setenv("GEMINI_API_KEY", "envkey-000000000000000000000000")
    assert secrets.get_key("gemini") == ("envkey-000000000000000000000000", "env")


def test_require_key_message_never_asks_for_chat(home):
    with pytest.raises(StudioError, match="keys setup gemini"):
        secrets.require_key("gemini")


def test_hyperframes_never_receives_the_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "should-not-leak")
    assert "GEMINI_API_KEY" not in util.tool_env()


def test_parse_script_segments_voice_and_style():
    segs = tts.parse_script("> voice: Puck\n> style: warm\n\n## hook\nEvery launch starts <short pause> here.\n\n"
                            "## launch\n> style: urgent\nThree... two... one.\n")
    assert [s["id"] for s in segs] == ["hook", "launch"]
    assert segs[0]["voice"] == "Puck" and segs[0]["style"] == "warm" and "<short pause>" in segs[0]["text"]
    assert segs[1]["style"] == "urgent"
    assert tts.parse_script("Just one line.")[0]["id"] == "main"


def test_request_body_matches_interactions_api():
    body = tts.request_body("Hi", "Kore", "cheerful", "gemini-3.8-flash-tts")
    assert body["model"] == "gemini-3.8-flash-tts"
    assert body["input"][0]["content"][0]["annotations"][0] == {"type": "speech_metadata", "style": "cheerful"}
    assert body["response_format"]["type"] == "audio"
    assert body["generation_config"]["speech_config"] == [{"voice": "Kore"}]


def _wav_bytes(seconds=1.0):
    return subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=f=220:d={seconds}:r=24000",
                           "-ac", "1", "-c:a", "pcm_s16le", "-f", "wav", "-"], capture_output=True, check=True).stdout


def test_synthesize_writes_segments_manifest_and_credit(proj, home, monkeypatch):
    secrets.key_file("gemini").parent.mkdir(parents=True, exist_ok=True)
    secrets.key_file("gemini").write_text("AIzaSyTESTKEY000000000000000000000abcd\n", encoding="utf-8")
    sent = []

    def fake_urlopen(req, timeout=0):
        sent.append((req.full_url, req.headers, json.loads(req.data)))
        payload = {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": base64.b64encode(_wav_bytes()).decode()}]}]}
        resp = io.BytesIO(json.dumps(payload).encode())
        resp.status = 200
        resp.__enter__ = lambda *a: resp
        resp.__exit__ = lambda *a: False
        return resp

    monkeypatch.setattr(tts.urllib.request, "urlopen", fake_urlopen)
    (proj / "vo.md").write_text("## hook\nHello there.\n## end\n> voice: Sulafat\nGoodbye.\n", encoding="utf-8")
    r = tts.synthesize(proj, proj / "vo.md")
    assert [s["id"] for s in r["segments"]] == ["hook", "end"]
    assert sent[0][0] == tts.ENDPOINT and sent[0][2]["model"] == "gemini-3.8-flash-tts"
    assert sent[1][2]["generation_config"]["speech_config"] == [{"voice": "Sulafat"}]
    info = util.ffprobe(proj / "audio" / "vo" / "hook.wav")
    assert info["audio"]["sample_rate"] == 48000 and abs(info["duration"] - 1.0) < 0.1
    manifest = json.loads((proj / "audio" / "vo" / "vo.json").read_text(encoding="utf-8"))
    assert manifest["segments"]["end"]["voice"] == "Sulafat"
    credits = json.loads((proj / "credits.json").read_text(encoding="utf-8"))
    assert any(c["path"] == "audio/vo" for c in credits["assets"])


def test_voiceover_placement_and_segment_word_anchor(proj):
    vo = proj / "audio" / "vo"
    vo.mkdir(parents=True)
    (vo / "hook.wav").write_bytes(_wav_bytes(2.0))
    (vo / "hook.words.json").write_text(json.dumps({"words": [{"text": "Every", "start": 0.1, "end": 0.4},
                                                             {"text": "launch", "start": 0.5, "end": 0.9}]}), encoding="utf-8")
    beats.write(beats.analyze(proj / "audio" / "music.wav"), proj / "audio" / "beats.json")
    spec = {"fps": 30, "duration": 16, "music": {"file": "audio/music.wav", "beats": "audio/beats.json", "volume": 0.4},
            "voiceover": [{"id": "hook", "file": "audio/vo/hook.wav", "at": {"downbeat": 1}}],
            "scenes": [{"id": "a", "start": {"downbeat": 0}, "events": [
                {"id": "a.t", "tier": "big", "at": {"downbeat": 0}},
                {"id": "a.launch", "tier": "word", "at": {"word": "launch", "segment": "hook"}}]}]}
    (proj / "beatmap.json").write_text(json.dumps(spec), encoding="utf-8")
    r = beatmap.resolve(proj)
    assert r["ok"], r["issues"]
    assert r["voiceover"]["hook"]["start_frame"] == 60                  # downbeat 1 = 2.0 s
    assert r["events"]["a.launch"]["impact_frame"] == 75                 # 2.0 s + 0.5 s
    beatmap.apply(proj)
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert html.count('data-vo="hook"') == 1 and 'data-start="2"' in html
