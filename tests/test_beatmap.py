import json

import pytest

from motion_studio import beatmap, beats


def _setup(proj, scenes, rules=None):
    beats.write(beats.analyze(proj / "audio" / "music.wav"), proj / "audio" / "beats.json")
    spec = {"fps": 30, "duration": 16, "music": {"file": "audio/music.wav", "beats": "audio/beats.json"},
            "rules": rules or {}, "scenes": scenes}
    (proj / "beatmap.json").write_text(json.dumps(spec), encoding="utf-8")
    return beatmap.resolve(proj)


GOOD = [
    {"id": "a", "start": {"downbeat": 0}, "end": {"drop": 0}, "events": [
        {"id": "a.t", "tier": "big", "at": {"downbeat": 0}},
        {"id": "a.s", "tier": "entrance", "at": {"beat": 2}},
        {"id": "a.and", "tier": "micro", "at": {"beat": 3, "plus_beats": 0.25}}]},
    {"id": "b", "start": {"drop": 0}, "events": [
        {"id": "b.t", "tier": "scene", "at": {"drop": 0}},
        {"id": "b.p", "tier": "punch", "at": {"bar": 4, "beat": 2}}]},
]


def test_resolves_frames_and_writes_timing(proj):
    r = _setup(proj, GOOD)
    assert r["ok"], r["issues"]
    assert r["events"]["a.t"]["impact_frame"] == 0
    assert r["events"]["a.s"]["impact_frame"] == 30            # beat 2 at 120 BPM = 1.0 s
    assert r["events"]["a.s"]["start_frame"] == 26             # entrance anticipation 4 frames
    assert r["events"]["a.and"]["impact_frame"] == 49           # beat 3 + a quarter beat = 1.625 s
    assert r["events"]["b.t"]["impact_frame"] == 240            # drop at 8.0 s
    assert r["events"]["b.p"]["impact_frame"] == 255            # bar 4 beat 2 = 8.5 s
    assert [s["end_frame"] for s in r["scenes"]] == [240, 480]
    assert "window.TIMING" in (proj / "timing.js").read_text(encoding="utf-8")


def test_rule_violations(proj):
    bad = [
        {"id": "a", "start": {"downbeat": 0}, "end": {"downbeat": 2}, "events": [
            {"id": "a.t", "tier": "entrance", "at": {"beat": 1}},
            {"id": "a.b1", "tier": "big", "at": {"beat": 1}},
            {"id": "a.b2", "tier": "big", "at": {"beat": 2}},
            {"id": "a.free", "tier": "micro", "at": {"time": 1.23}}]},
        {"id": "b", "start": {"downbeat": 2}, "end": {"downbeat": 3}, "events": [{"id": "b.t", "tier": "big", "at": {"downbeat": 2}}]},
    ]
    r = _setup(proj, bad)
    codes = {i["code"] for i in r["issues"] if i["level"] == "error"}
    assert {"no_opening_hit", "too_many_big_hits", "off_grid", "length_mismatch"} <= codes


def test_gap_between_scenes_is_an_error(proj):
    gap = [{"id": "a", "start": {"downbeat": 0}, "end": {"downbeat": 2}, "events": [{"id": "a.t", "tier": "big", "at": {"downbeat": 0}}]},
           {"id": "b", "start": {"drop": 0}, "events": [{"id": "b.t", "tier": "scene", "at": {"drop": 0}}]}]
    r = _setup(proj, gap)
    assert any(i["code"] == "gap" for i in r["issues"])
    assert not r["ok"]


def test_apply_creates_slots_music_and_is_idempotent(proj):
    _setup(proj, GOOD)
    beatmap.apply(proj)
    beatmap.apply(proj)
    html = (proj / "index.html").read_text(encoding="utf-8")
    assert html.count('data-scene="a"') == 1 and html.count('id="music"') == 1
    assert 'data-composition-src="compositions/b.html"' in html
    assert (proj / "compositions" / "a.html").is_file()
    assert 'id="slot-b" data-scene="b" data-composition-id="b" data-composition-src="compositions/b.html" data-start="8" data-duration="8"' in html
    r = json.loads((proj / "beatmap.resolved.json").read_text(encoding="utf-8"))
    b = next(s for s in r["scenes"] if s["id"] == "b")
    assert (b["start_frame"], b["end_frame"]) == (240, 480)


def test_bad_anchor_message(proj):
    with pytest.raises(beatmap.BeatmapError):
        _setup(proj, [{"id": "a", "start": {"downbeat": 999}, "events": []}])
