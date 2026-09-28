"""Benchmark timer and recorder for the fixed Motion Engine benchmark suite.

Standard library only; needs ffmpeg/ffprobe on PATH for `finish`.
It deliberately does not import motion_engine, so it keeps working
across rebuilds of the engine.

    python benchmarks/bench.py verify
    python benchmarks/bench.py start B1 --agent "Claude Code" --model claude-opus-5-5 --session-start 2026-09-28T10:00:00Z
    python benchmarks/bench.py mark RUN draft-delivered
    python benchmarks/bench.py mark RUN revision-start
    python benchmarks/bench.py mark RUN revision-delivered
    python benchmarks/bench.py finish RUN --draft path/to/draft.mp4 --revised path/to/revised.mp4 --checks checks.json
    python benchmarks/bench.py score RUN --scores "design=4,motion=3" --publish y
    python benchmarks/bench.py report

RUN is the run directory printed by `start` (benchmarks/results/<run-id>) or just <run-id>.
Maintainers only: `python benchmarks/bench.py manifest` after intentionally changing inputs,
together with a SUITE_VERSION bump.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

SUITE_VERSION = "1"
BENCH = Path(__file__).resolve().parent
REPO = BENCH.parent
RESULTS = BENCH / "results"
MANIFEST = BENCH / "manifest.json"
CASES = {"B1": "B1-gps-explainer", "B2": "B2-climate-data", "B3": "B3-artemis-recap"}
INPUT_ROOTS = [*CASES.values(), "shared"]
EVENTS = ["draft-delivered", "revision-start", "revision-delivered"]


# ---------------------------------------------------------------- helpers

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def seconds_between(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    return round((parse_time(b) - parse_time(a)).total_seconds(), 1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path = REPO) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=False).stdout.strip()
    except OSError:
        return ""


def input_files() -> list[Path]:
    files = []
    for root in INPUT_ROOTS:
        for path in sorted((BENCH / root).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files.append(path)
    return files


def rel(path: Path) -> str:
    return path.relative_to(BENCH).as_posix()


def load_run(ref: str) -> tuple[Path, dict]:
    path = Path(ref)
    if not path.is_dir():
        path = RESULTS / ref
    record = path / "run.json"
    if not record.is_file():
        sys.exit(f"No run.json in {path}")
    return path, json.loads(record.read_text(encoding="utf-8"))


def save_run(path: Path, data: dict) -> None:
    (path / "run.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fmt_duration(value: float | None) -> str:
    if value is None:
        return "–"
    minutes, secs = divmod(int(round(value)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m{secs:02d}s"


# ---------------------------------------------------------------- manifest

def cmd_manifest(_: argparse.Namespace) -> None:
    files = {rel(p): {"sha256": sha256(p), "bytes": p.stat().st_size} for p in input_files()}
    MANIFEST.write_text(json.dumps({"suite_version": SUITE_VERSION, "files": files}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(files)} entries to {MANIFEST.relative_to(REPO)}")


def verify_inputs() -> list[str]:
    if not MANIFEST.is_file():
        return ["manifest.json is missing"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["files"]
    problems = []
    actual = {rel(p): p for p in input_files()}
    for name, meta in expected.items():
        if name not in actual:
            problems.append(f"missing: {name}")
        elif sha256(actual[name]) != meta["sha256"]:
            problems.append(f"changed: {name}")
    for name in actual:
        if name not in expected:
            problems.append(f"unexpected: {name}")
    if manifest.get("suite_version") != SUITE_VERSION:
        problems.append("suite version mismatch between bench.py and manifest.json")
    return problems


def cmd_verify(_: argparse.Namespace) -> None:
    problems = verify_inputs()
    if problems:
        print("Benchmark inputs do NOT match the manifest:")
        print("\n".join(f"  - {p}" for p in problems))
        sys.exit(1)
    print(f"OK: all benchmark inputs match manifest (suite v{SUITE_VERSION}).")


# ---------------------------------------------------------------- run lifecycle

def cli_version() -> str | None:
    """Version reported by the `motion-engine` on PATH, which may be a different install."""
    exe = shutil.which("motion-engine")
    match = re.search(r"\d+\.\d+\.\d+\S*", run([exe, "version"])) if exe else None
    return match.group(0) if match else None


def product_name() -> str:
    pyproject = REPO / "pyproject.toml"
    if pyproject.is_file():
        match = re.search(r'^name\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    return "unknown"


def build_version(override: str | None) -> str:
    """The checkout under test is authoritative, not whatever CLI happens to be on PATH."""
    if override:
        return override
    pyproject = REPO / "pyproject.toml"
    if pyproject.is_file():
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    return cli_version() or "unknown"


def environment() -> dict:
    ffmpeg = run(["ffmpeg", "-version"]).splitlines()
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "ffmpeg": ffmpeg[0] if ffmpeg else None,
    }


def cmd_start(args: argparse.Namespace) -> None:
    case = args.case.upper()
    if case not in CASES:
        sys.exit(f"Unknown benchmark {args.case}; choose from {', '.join(CASES)}")
    problems = verify_inputs()
    if problems and not args.allow_modified_inputs:
        sys.exit("Inputs differ from the manifest; results would not be comparable.\n" + "\n".join(problems))
    case_dir = BENCH / CASES[case]
    spec = json.loads((case_dir / "benchmark.json").read_text(encoding="utf-8"))
    prompt = (case_dir / spec["prompt"]).read_text(encoding="utf-8")
    revision = (case_dir / spec["revision"]).read_text(encoding="utf-8")
    version = build_version(args.build)
    installed = cli_version()
    if installed and installed != version:
        print(f"WARNING: `motion-engine` on PATH reports {installed}, but this checkout is {version}. "
              "Install the checkout (pip install -e .) before producing.", file=sys.stderr)
    commit = run(["git", "rev-parse", "HEAD"]) or None
    dirty = bool(run(["git", "status", "--porcelain", "--untracked-files=no"]))
    started = now()
    if args.session_start and parse_time(args.session_start) > parse_time(started):
        sys.exit(f"--session-start {args.session_start} is in the future; pass UTC (date -u +%Y-%m-%dT%H:%M:%SZ)")
    run_id = f"{started[:16].replace('-', '').replace(':', '')}Z_{case}_v{version}"
    run_dir = RESULTS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    data = {
        "run_id": run_id,
        "suite_version": SUITE_VERSION,
        "benchmark": case,
        "benchmark_title": spec["title"],
        "build": {"product": product_name(), "version": version, "installed_cli_version": installed, "commit": commit, "dirty_worktree": dirty},
        "agent": {"product": args.agent, "model": args.model, "effort": args.effort},
        "environment": environment(),
        "inputs_verified": not problems,
        "prompt": {"file": f"{CASES[case]}/{spec['prompt']}", "sha256": hashlib.sha256(prompt.encode()).hexdigest(), "text": prompt},
        "revision_prompt": {"file": f"{CASES[case]}/{spec['revision']}", "sha256": hashlib.sha256(revision.encode()).hexdigest(), "text": revision},
        "expected": spec["expected"],
        "timeline": {"session_start": args.session_start, "start": started},
        "questions_to_user": [],
        "assumptions": [],
    }
    save_run(run_dir, data)
    print(run_dir.relative_to(REPO).as_posix())


def cmd_mark(args: argparse.Namespace) -> None:
    run_dir, data = load_run(args.run)
    if args.event not in EVENTS:
        sys.exit(f"Unknown event {args.event}; choose from {', '.join(EVENTS)}")
    if args.event in data["timeline"] and not args.force:
        sys.exit(f"{args.event} already recorded at {data['timeline'][args.event]}; pass --force to overwrite")
    data["timeline"][args.event] = now()
    save_run(run_dir, data)
    print(f"{args.event}: {data['timeline'][args.event]}")


def probe(video: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size",
               "-of", "json", str(video)])
    info = json.loads(out or "{}")
    streams = info.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    fps = float(Fraction(vstream["r_frame_rate"])) if vstream.get("r_frame_rate") else None
    result = {
        "width": vstream.get("width"),
        "height": vstream.get("height"),
        "fps": round(fps, 3) if fps else None,
        "duration_s": round(float(info.get("format", {}).get("duration", 0)), 3),
        "video_codec": vstream.get("codec_name"),
        "audio": any(s.get("codec_type") == "audio" for s in streams),
        "bytes": int(info.get("format", {}).get("size", 0)),
    }
    if result["audio"]:
        log = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        summary = log[log.rfind("Summary:"):]
        lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
        peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
        result["integrated_lufs"] = float(lufs.group(1)) if lufs else None
        result["true_peak_dbtp"] = float(peak.group(1)) if peak and peak.group(1) != "-inf" else None
    log = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-vf", "blackdetect=d=0.25:pix_th=0.05,freezedetect=n=0.001:d=1",
                          "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    result["black_segments"] = len(re.findall(r"black_start", log))
    result["freeze_segments"] = len(re.findall(r"freeze_start", log))
    return result


def auto_checks(meta: dict, expected: dict) -> list[dict]:
    checks = [
        {"item": "resolution", "pass": (meta["width"], meta["height"]) == (expected["width"], expected["height"]),
         "evidence": f"{meta['width']}x{meta['height']}"},
        {"item": "fps", "pass": meta["fps"] is not None and abs(meta["fps"] - expected["fps"]) < 0.01,
         "evidence": str(meta["fps"])},
        {"item": "duration", "pass": abs(meta["duration_s"] - expected["duration_s"]) <= expected["duration_tolerance_s"],
         "evidence": f"{meta['duration_s']} s"},
        {"item": "audio stream", "pass": meta["audio"] == expected["audio"], "evidence": str(meta["audio"])},
    ]
    if meta.get("true_peak_dbtp") is not None:
        checks.append({"item": "true peak <= -1 dBTP", "pass": meta["true_peak_dbtp"] <= -1.0,
                       "evidence": f"{meta['true_peak_dbtp']} dBTP"})
    return checks


def keep_evidence(video: Path, run_dir: Path, stem: str, duration: float) -> dict:
    """Store a small proxy and a 1-fps contact sheet in the repo; full-resolution files stay local."""
    proxy = run_dir / f"{stem}-proxy-540x960.mp4"
    sheet = run_dir / f"{stem}-contact-1fps.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k",
                    "-movflags", "+faststart", str(proxy)], check=False)
    rows = max(1, -(-int(duration + 0.999) // 10))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
                    f"fps=1,scale=180:320:force_original_aspect_ratio=decrease,pad=180:320:(ow-iw)/2:(oh-ih)/2,tile=10x{rows}",
                    "-frames:v", "1", "-q:v", "4", str(sheet)], check=False)
    return {"proxy": proxy.name if proxy.is_file() else None, "contact_sheet": sheet.name if sheet.is_file() else None}


def cmd_finish(args: argparse.Namespace) -> None:
    run_dir, data = load_run(args.run)
    timeline = data["timeline"]
    timeline["finish"] = now()
    outputs = {}
    for stem, value in (("draft", args.draft), ("revised", args.revised)):
        if not value:
            continue
        video = Path(value).resolve()
        if not video.is_file():
            sys.exit(f"{stem} video not found: {video}")
        meta = probe(video)
        outputs[stem] = {
            "local_path": str(video),
            "sha256": sha256(video),
            **meta,
            "auto_checks": auto_checks(meta, data["expected"]),
            **keep_evidence(video, run_dir, stem, meta["duration_s"]),
        }
    data["outputs"] = outputs
    if args.checks:
        data["agent_checks"] = json.loads(Path(args.checks).read_text(encoding="utf-8"))
    if args.questions:
        data["questions_to_user"] = args.questions
    if args.assumption:
        data["assumptions"] = args.assumption
    if args.notes:
        data["notes"] = args.notes
    data["durations_s"] = {
        "setup": seconds_between(timeline.get("session_start"), timeline.get("start")),
        "draft": seconds_between(timeline.get("start"), timeline.get("draft-delivered")),
        "revision": seconds_between(timeline.get("revision-start"), timeline.get("revision-delivered")),
        "total": seconds_between(timeline.get("session_start") or timeline.get("start"), timeline["finish"]),
    }
    save_run(run_dir, data)
    write_report()
    print(json.dumps({"durations_s": data["durations_s"],
                      "auto_checks": {k: [c for c in v["auto_checks"] if not c["pass"]] or "all pass" for k, v in outputs.items()}},
                     indent=2))


def cmd_score(args: argparse.Namespace) -> None:
    run_dir, data = load_run(args.run)
    scores = {}
    for part in args.scores.split(","):
        key, _, value = part.partition("=")
        scores[key.strip()] = int(value)
    data["owner_review"] = {"scores": scores, "would_publish": args.publish.lower().startswith("y"),
                            "comment": args.comment, "reviewed_at": now()}
    save_run(run_dir, data)
    write_report()
    print(f"Saved owner review for {data['run_id']}")


# ---------------------------------------------------------------- report

def write_report() -> None:
    runs = []
    for record in sorted(RESULTS.glob("*/run.json")):
        runs.append(json.loads(record.read_text(encoding="utf-8")))
    lines = [
        "# Benchmark results",
        "",
        "Generated by `python benchmarks/bench.py report` from `results/*/run.json`. Do not edit by hand.",
        "Times are wall-clock. **Setup** runs from the new chat's first message to `start`. **Draft** runs from `start` to the delivered first draft.",
        "**Revision** covers the scoped revision prompt. **Auto** means the probe checks on the draft and revised videos passed. **Agent** is the count of self-checks passed.",
        "",
        "| Run (UTC) | Bench | Build | Commit | Agent / model | Setup | Draft | Revision | Total | Auto | Agent | Owner avg | Publish? | Evidence |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(runs, key=lambda r: (r["benchmark"], r["timeline"]["start"])):
        d = r.get("durations_s", {})
        outs = r.get("outputs", {})
        auto = [c["pass"] for o in outs.values() for c in o.get("auto_checks", [])]
        agent = [c.get("pass") for c in r.get("agent_checks", []) if isinstance(c, dict)]
        review = r.get("owner_review")
        avg = f"{sum(review['scores'].values()) / len(review['scores']):.1f}" if review and review["scores"] else "–"
        publish = ("yes" if review["would_publish"] else "no") if review else "–"
        links = " ".join(f"[{k}]({r['run_id']}/{o['contact_sheet']})" for k, o in outs.items() if o.get("contact_sheet"))
        commit = (r["build"].get("commit") or "")[:7] + ("*" if r["build"].get("dirty_worktree") else "")
        lines.append(
            f"| {r['timeline']['start'][:16].replace('T', ' ')} | {r['benchmark']} | {_product(r)} {r['build']['version']} | {commit} | "
            f"{r['agent'].get('product') or '?'} / {r['agent'].get('model') or '?'} | {fmt_duration(d.get('setup'))} | "
            f"{fmt_duration(d.get('draft'))} | {fmt_duration(d.get('revision'))} | {fmt_duration(d.get('total'))} | "
            f"{sum(auto)}/{len(auto) if auto else 0} | {sum(bool(a) for a in agent)}/{len(agent)} | {avg} | {publish} | {links or '–'} |"
        )
    if not runs:
        lines.append("| – | – | – | – | – | – | – | – | – | – | – | – | – | no runs yet |")
    (RESULTS / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _product(r: dict) -> str:
    name = r["build"].get("product") or "motion-engine"   # runs before the product field existed were motion-engine
    return {"motion-engine-spec": "motion-engine"}.get(name, name)


def cmd_report(_: argparse.Namespace) -> None:
    write_report()
    print((RESULTS / "RESULTS.md").relative_to(REPO).as_posix())


# ---------------------------------------------------------------- cli

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Check benchmark inputs against manifest.json").set_defaults(func=cmd_verify)
    sub.add_parser("manifest", help="Maintainers: rewrite manifest.json").set_defaults(func=cmd_manifest)
    sub.add_parser("report", help="Regenerate results/RESULTS.md").set_defaults(func=cmd_report)

    p = sub.add_parser("start", help="Start timing a benchmark run")
    p.add_argument("case", help="B1, B2 or B3")
    p.add_argument("--agent", required=True, help='e.g. "Claude Code", "Codex"')
    p.add_argument("--model", required=True, help="exact model id")
    p.add_argument("--effort", help="reasoning effort / mode, if known")
    p.add_argument("--session-start", help="UTC ISO time of the new chat's first message")
    p.add_argument("--build", help="override the detected build version")
    p.add_argument("--allow-modified-inputs", action="store_true", help="record a non-comparable run anyway")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("mark", help="Record a timeline event")
    p.add_argument("run")
    p.add_argument("event", help=" | ".join(EVENTS))
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("finish", help="Probe outputs, store evidence, compute durations")
    p.add_argument("run")
    p.add_argument("--draft", help="first-draft MP4")
    p.add_argument("--revised", help="revised MP4")
    p.add_argument("--checks", help="JSON list of {item, pass, evidence} from CHECKLIST.md")
    p.add_argument("--questions", action="append", help="each question the agent had to ask the user")
    p.add_argument("--assumption", action="append", help="each assumption the agent made instead of asking")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_finish)

    p = sub.add_parser("score", help="Owner review after watching")
    p.add_argument("run")
    p.add_argument("--scores", required=True, help='comma list, e.g. "design=4,motion=3,pacing=4"')
    p.add_argument("--publish", required=True, help="y/n")
    p.add_argument("--comment")
    p.set_defaults(func=cmd_score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
