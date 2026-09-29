import base64
import hashlib
import io
import json
import subprocess

import pytest

from motion_studio import audio, beatmap, beats, music, secrets, sfx, util


def test_every_synth_kind_renders_distinct_seeds(proj):
    for kind in sfx.KINDS:
        r = sfx.make(proj, kind, seed=1)
        info = util.ffprobe(proj / r["file"])
        assert info["audio"]["sample_rate"] == 48000 and info["audio"]["channels"] == 2
    a = sfx.make(proj, "impact", name="a", seed=1)
    b = sfx.make(proj, "impact", name="b", seed=2)
    assert hashlib.md5((proj / a["file"]).read_bytes()).digest() != hashlib.md5((proj / b["file"]).read_bytes()).digest()
    reg = json.loads((proj / "audio" / "sfx" / "sfx.json").read_text(encoding="utf-8"))
    assert reg["riser-1.wav"]["align"] == "end" and reg["whoosh-1.wav"]["align"] == "peak"
    assert any(c["path"] == "audio/sfx" and c["license"] == "CC0-1.0" for c in json.loads((proj / "credits.json").read_text(encoding="utf-8"))["assets"])
    assert len(sfx.vary(proj, proj / "audio" / "sfx" / "a.wav", count=2)) == 2


def _map(proj, events):
    beats.write(beats.analyze(proj / "audio" / "music.wav"), proj / "audio" / "beats.json")
    spec = {"fps": 30, "duration": 16, "music": {"file": "audio/music.wav", "beats": "audio/beats.json"}, "rules": {"auto_sfx": False},
            "scenes": [{"id": "a", "start": {"downbeat": 0}, "events": events}]}
    (proj / "beatmap.json").write_text(json.dumps(spec), encoding="utf-8")
    assert beatmap.resolve(proj)["ok"]


def test_layers_alignment_and_repeat_variation(proj):
    sfx.make(proj, "impact", name="slam", seed=3)
    sfx.make(proj, "riser", name="rise", seed=3, duration=1.0)
    _map(proj, [
        {"id": "a.t", "tier": "big", "at": {"downbeat": 0}, "sfx": ["file:audio/sfx/slam.wav", "file:audio/sfx/rise.wav"]},
        {"id": "a.b", "tier": "big", "at": {"downbeat": 2}, "sfx": ["file:audio/sfx/rise.wav", "file:audio/sfx/slam.wav"]},
        {"id": "a.c", "tier": "big", "at": {"downbeat": 3}, "sfx": "file:audio/sfx/slam.wav"},
    ])
    sheet = [c for c in audio.cues(proj) if not c.get("dropped")]
    assert len(sheet) == 5                                    # both layers kept on each hit
    rise = next(c for c in sheet if c["event"] == "a.b" and c["file"].endswith("rise.wav"))
    assert rise["align"] == "end" and abs(rise["t"] - (4.0 - 1.0)) < 0.02   # riser ends on the downbeat at 4.0 s
    slams = [c for c in sheet if c["file"].endswith("slam.wav")]
    assert slams[0]["semitones"] == 0 and all(c["semitones"] != 0 for c in slams[1:])


def test_lyria_generate_parses_steps_and_credits(proj, tmp_path, monkeypatch):
    monkeypatch.setenv("MSTUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaTEST0000000000000000000000000000")
    mp3 = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=330:d=3", "-ac", "2", "-f", "mp3", "-"],
                         capture_output=True, check=True).stdout
    sent = {}

    def fake_post(body, key, retries=3, timeout=180.0):
        sent.update(body)
        return {"steps": [{"type": "model_output", "content": [{"type": "text", "text": "[Intro] ..."},
                                                               {"type": "audio", "data": base64.b64encode(mp3).decode()}]}]}

    monkeypatch.setattr(music, "_post", fake_post)
    meta = music.generate(proj, "warm lo-fi piano with brushed drums", bpm=90, key="F major")
    assert sent["model"] == "lyria-3-clip-preview" and "Instrumental only" in sent["input"] and "90 BPM" in sent["input"]
    assert (proj / "audio" / "music" / "bed.wav").is_file() and (proj / "audio" / "music" / "bed.lyria.txt").is_file()
    assert any(c["path"] == "audio/music/bed.wav" for c in json.loads((proj / "credits.json").read_text(encoding="utf-8"))["assets"])
    assert meta["duration"] == pytest.approx(3.0, abs=0.1)


def test_fit_trims_on_bar_lines_and_registry(proj, tmp_path, monkeypatch):
    monkeypatch.setenv("MSTUDIO_HOME", str(tmp_path / "home"))
    src = proj / "audio" / "music.wav"
    r = music.fit(proj, src, 10.0)
    assert r["duration"] == pytest.approx(10.0, abs=0.05) and "trim" in r["method"]
    r2 = music.fit(proj, src, 24.0, name="long")
    assert r2["duration"] == pytest.approx(24.0, abs=0.05) and "looped" in r2["method"]
    music.record_use("old-project", src)
    assert music.used_elsewhere("new-project", src) == ["old-project"]
    assert music.used_elsewhere("old-project", src) == []


def test_elevenlabs_key_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("MSTUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert secrets.get_key("elevenlabs") == (None, "missing")
    assert "elevenlabs" in secrets.key_file("elevenlabs").name
