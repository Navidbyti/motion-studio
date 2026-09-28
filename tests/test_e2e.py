"""End-to-end: build, render, QA and revise the public hello-beat example (needs Chrome + npm install).

Run with: pytest -m slow
"""
import shutil
from pathlib import Path

import pytest

from motion_studio import qa, render, revise
from motion_studio.util import REPO, find_chrome

pytestmark = pytest.mark.slow


@pytest.mark.skipif(find_chrome() is None, reason="needs Chrome")
def test_hello_beat_renders_passes_qa_and_revises_locally(tmp_path):
    p = tmp_path / "hello-beat"
    shutil.copytree(REPO / "examples" / "hello-beat", p, ignore=shutil.ignore_patterns("renders", "versions"))
    from motion_studio.cli import main
    assert main(["refresh", str(p)]) == 0
    rep = render.render(p)
    assert rep["master"]["video"]["width"] == 1080
    report = qa.run(p)
    assert report["pass"], qa.to_markdown(report)
    checks = {c["id"]: c["status"] for c in report["checks"]}
    assert checks["beat_accuracy"] == "pass" and checks["loudness"] == "pass" and checks["copy"] == "pass"
    revise.start(p, "s2", "make 'hit' teal")
    scene = p / "compositions" / "s2.html"
    scene.write_text(scene.read_text(encoding="utf-8").replace("var(--accent);", "var(--accent-2);"), encoding="utf-8")
    render.render(p, keep_gain=True)
    result = revise.verify(p)
    assert result["ok"] and result["changed_frames"] > 0, result
