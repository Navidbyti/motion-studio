import numpy as np
import pytest

from motion_studio import beats
from synth import make_track


@pytest.mark.parametrize("bpm", [92, 124, 140, 174])
def test_tempo_beats_downbeats_drops(tmp_path, bpm):
    gt = make_track(tmp_path / "t.wav", bpm=bpm)  # 2-beat pickup, 0.37 s lead silence, drops at bars 8 and 20
    d = beats.analyze(tmp_path / "t.wav")
    assert abs(d["tempo"]["bpm"] - bpm) < 0.5
    got = np.array([b["t"] for b in d["beats"]])
    truth = np.array(gt["beats"])
    inside = got[(got >= truth[0] - 0.05) & (got <= truth[-1] + 0.05)]
    err = np.array([t - truth[np.argmin(np.abs(truth - t))] for t in inside])
    assert len(inside) >= len(truth) - 3
    assert np.median(np.abs(err)) < 0.005          # attack-refined beats within 5 ms
    down = np.array(d["downbeats"])
    matched = np.mean([np.min(np.abs(np.array(gt["downbeats"]) - t)) < 0.03 for t in down])
    assert matched >= 0.9
    for drop in gt["drops"]:
        assert any(abs(drop - x) < 0.1 for x in d["drops"]), (drop, d["drops"])


def test_first_downbeat_at_zero_and_hits(track):
    d = beats.analyze(track[0])
    assert d["first_downbeat"] == pytest.approx(0.0, abs=0.01)
    assert d["meter"] == 4
    tiers = {h["tier"] for h in d["hits"]}
    assert {"big", "punch", "entrance"} <= tiers
    snares = [b for b in d["beats"] if b["snare"]]
    assert snares and sum(b["beat_in_bar"] in (2, 4) for b in snares) >= 0.85 * len(snares)


def test_rejects_silence(tmp_path):
    import wave
    with wave.open(str(tmp_path / "s.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 22050 * 3)
    with pytest.raises(beats.BeatError):
        beats.analyze(tmp_path / "s.wav")
