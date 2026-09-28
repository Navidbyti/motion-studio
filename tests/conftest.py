from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from motion_studio import project as project_mod  # noqa: E402
from synth import make_track  # noqa: E402


@pytest.fixture(scope="session")
def track(tmp_path_factory) -> tuple[Path, dict]:
    """120 BPM, no pickup: intro 2 bars, build 2, drop 4 (drop at 8.0 s)."""
    path = tmp_path_factory.mktemp("music") / "music.wav"
    gt = make_track(path, bpm=120, pickup_beats=0, lead_silence=0.0, sections=(("intro", 2), ("build", 2), ("drop", 4)))
    return path, gt


@pytest.fixture
def proj(tmp_path, track) -> Path:
    p = project_mod.new_project("t-proj", duration=16, mode="benchmark", title="Test", root=tmp_path)
    (p / "audio" / "music.wav").write_bytes(track[0].read_bytes())
    return p
