import json
import subprocess

import pytest

from motion_studio import footage, project
from motion_studio.util import StudioError


def _pillarboxed_clip_with_flash(path):
    # 1280x720 at 59.94 fps: 960x720 picture centred between black bars; white flash at 1.0 s
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=960x720:r=60000/1001:d=3",
                    "-f", "lavfi", "-i", "color=c=white:s=960x720:r=60000/1001:d=3",
                    "-filter_complex", "[0:v][1:v]overlay=enable='between(t,1.0,1.25)',pad=1280:720:160:0:black",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_analyze_conform_reframe(proj):
    clip = proj / "footage" / "c1.mp4"
    _pillarboxed_clip_with_flash(clip)
    meta = footage.analyze(proj)
    c = meta["clips"]["c1"]
    assert c["bars"] and abs(c["content_box"][0] - 160) <= 8 and abs(c["content_box"][2] - 960) <= 16
    flash = [e for e in c["events"] if e["kind"] == "flash"]
    assert flash and abs(flash[0]["t"] - 1.0) < 0.05
    footage.conform(proj, 30)
    info = json.loads((proj / "footage" / "footage.json").read_text(encoding="utf-8"))
    assert info["clips"]["c1"]["conformed"] == "conformed/c1.mp4"
    good = {"media": {"v1": {"clip": "c1", "keys": [{"t": 0, "x": 300, "y": 0, "w": 405}]}}}
    (proj / "footage" / "reframe.json").write_text(json.dumps(good), encoding="utf-8")
    assert footage.reframe(proj, (1080, 1920))["ok"]
    bad = {"media": {"v1": {"clip": "c1", "avoid": [[500, 0, 50, 50]], "keys": [{"t": 0, "x": 100, "y": 0, "w": 405}, {"t": 2, "x": 400, "y": 0, "w": 405}]}}}
    (proj / "footage" / "reframe.json").write_text(json.dumps(bad), encoding="utf-8")
    codes = {i["code"] for i in footage.reframe(proj, (1080, 1920))["issues"]}
    assert {"outside_content", "upscale"} <= codes or "avoid_box" in codes


def test_gates_modes_and_staleness(tmp_path):
    p = project.new_project("gates", mode="interactive", root=tmp_path)
    (p / "style-brief.md").write_text("concepts", encoding="utf-8")
    with pytest.raises(StudioError, match="human"):
        project.approve(p, "A", "agent")
    project.approve(p, "A", "human", "looks good")
    assert project.gate_status(p)["A"].startswith("approved")
    (p / "style-brief.md").write_text("concepts v2", encoding="utf-8")
    assert project.gate_status(p)["A"].startswith("stale")
    with pytest.raises(StudioError, match="blocked"):
        project.require_gates(p, "AB")
    assert "gate A" in (p / "decisions.md").read_text(encoding="utf-8")
