"""Definition of done: every check a render must pass before a human sees it.

`run(project)` writes renders/qa/report.json + report.md and returns the report.
Checks (error = fail, warning = report):

  hyperframes      lint / runtime / layout / motion / contrast (HyperFrames' own `check`)
  copy             every required on-screen string (copy.json) appears verbatim, long enough to read
  numbers          no orphan numbers: each number on screen is bound data, a claim or scripted copy
  facts            claim ledger sources hash-match and quotes are verbatim (when facts are needed)
  text_size        no text under the house minimum
  safe_area        opaque text stays inside the platform safe area
  beat_accuracy    every Studio.hit lands on its beat-map frame; unanimated events reported
  console          no JavaScript errors in the composition
  spec             resolution, fps, duration (±1 frame), audio stream
  loudness         integrated −14 LUFS ±1, true peak ≤ −1 dBTP
  black_freeze     no unintended black frames or frozen stretches
  credits          every media/data/font file has a credits.json entry with a license
  revision         after `mstudio revise`, frames outside the revised scene are unchanged
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import claims as claims_mod
from . import data as data_mod
from .project import RATIOS, log_decision, now, state
from .util import REPO, StudioError, ffprobe, find_chrome, loudness, node, read_json, run as sh, write_json

SAFE = {  # at the canvas sizes in project.RATIOS
    "9:16": {"top": 220, "bottom": 380, "side": 72},
    "4:5": {"top": 72, "bottom": 72, "side": 72},
    "1:1": {"top": 72, "bottom": 72, "side": 72},
    "16:9": {"top": 54, "bottom": 54, "side": 96},
}
LUFS_TARGET, LUFS_TOL, TP_MAX = -14.0, 1.0, -1.0
MEDIA_EXT = {".mp4", ".mov", ".webm", ".mkv", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".csv", ".xlsx", ".json", ".txt", ".pdf", ".ttf", ".otf", ".woff2"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')).strip()


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, cid: str, status: str, detail: str, items: list[Any] | None = None) -> None:
        self.checks.append({"id": cid, "status": status, "detail": detail, "items": (items or [])[:40]})


# --------------------------------------------------------------------------- copy extraction

def extract_copy(project: Path) -> list[dict[str, Any]]:
    """Quoted strings from script.md before the facts/notes sections become required copy."""
    text = (project / "script.md").read_text(encoding="utf-8")
    cut = re.search(r"^#+\s*(facts|sources?|visual intent|data rules|footage|notes|references)\b", text, re.I | re.M)
    body = text[: cut.start()] if cut else text
    found = re.findall(r"“([^”]+)”|\"([^\"\n]+)\"", body)
    seen, out = set(), []
    for a, b in found:
        s = _norm(a or b)
        if s and s not in seen and not s.endswith(".md") and not re.fullmatch(r"[\w.-]+\.(mp4|wav|json|csv)", s):
            seen.add(s)
            words = len(s.split())
            out.append({"text": s, "min_seconds": round(min(3.0, max(1.2, words / 3.0)), 2)})
    return out


# --------------------------------------------------------------------------- checks

def _inspect(project: Path) -> dict[str, Any]:
    chrome = find_chrome()
    if not chrome:
        raise StudioError("no Chrome found for the inspector (run `mstudio doctor`)")
    out = project / "renders" / "qa" / "inspect.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    sh([node(), str(REPO / "engine" / "inspect.mjs"), "--project", str(project), "--chrome", chrome, "--out", str(out), "--step-frames", "3"], timeout=1200)
    return read_json(out)


def _runs(samples: list[dict[str, Any]], predicate, step_s: float) -> float:
    """Longest continuous time (s) for which predicate(sample) holds."""
    best = cur = 0.0
    for s in samples:
        if predicate(s):
            cur += step_s
            best = max(best, cur)
        else:
            cur = 0.0
    return best


def check_copy(rep: Report, project: Path, insp: dict[str, Any]) -> list[str]:
    path = project / "copy.json"
    if not path.is_file():
        rep.add("copy", "warning", "no copy.json: run `mstudio copy <slug>` and review it so QA can verify exact text")
        return []
    required = read_json(path)["required"]
    step = insp["step_frames"] / insp["fps"]

    def joined(s: dict[str, Any]) -> str:
        blocks = sorted(s["text"], key=lambda b: (round(b["box"][1] / 20), b["box"][0]))
        return _norm(" ".join(b["text"] for b in blocks if b["opacity"] >= 0.5))

    texts = [joined(s) for s in insp["samples"]]
    missing, short = [], []
    for req in required:
        target = _norm(req["text"])
        run_s = _runs(list(range(len(texts))), lambda i: target in texts[i], step)
        if run_s == 0:
            near = next((t for t in texts if target.lower() in t.lower()), None)
            missing.append(f"\"{target}\"" + (" (appears with different case/punctuation)" if near else ""))
        elif run_s + 1e-6 < req.get("min_seconds", 1.2):
            short.append(f"\"{target}\" readable {run_s:.2f}s < {req.get('min_seconds', 1.2)}s")
    status = "error" if missing else "warning" if short else "pass"
    rep.add("copy", status, f"{len(required) - len(missing)}/{len(required)} required strings on screen; {len(short)} too brief", missing + short)
    return [r["text"] for r in required]


def check_numbers(rep: Report, project: Path, insp: dict[str, Any], copy_texts: list[str], claim_texts: list[str], strict: bool) -> None:
    bound = data_mod.load(project)
    allowed = data_mod.allowed_numbers(bound, copy_texts + claim_texts)
    orphans: dict[str, str] = {}
    counters_wrong = []
    values = (bound or {}).get("values", {})
    last_by_value: dict[str, str] = {}
    for s in insp["samples"]:
        for b in s["text"]:
            if b.get("provenance") in ("axis", "decor", "time", "ignore") or b["opacity"] < 0.3:
                continue
            if b.get("value"):
                last_by_value[b["value"]] = b["text"]
                continue  # counters are checked on their landing value below
            for tok in data_mod.number_tokens(b["text"]):
                if not data_mod.number_allowed(tok, allowed):
                    orphans.setdefault(tok, f"t={s['t']}s in \"{b['text'][:60]}\"")
    for key, shown in last_by_value.items():
        want = values.get(key, {}).get("display")
        if want is not None and _norm(want) not in _norm(shown):
            counters_wrong.append(f"counter {key} ends on \"{shown}\" not \"{want}\"")
    items = [f"{k} ({v})" for k, v in orphans.items()] + counters_wrong
    if not orphans and not counters_wrong:
        rep.add("numbers", "pass", f"every on-screen number traces to data, claims or scripted copy ({len(allowed)} allowed values)")
    else:
        rep.add("numbers", "error" if (strict or counters_wrong) else "warning",
                f"{len(orphans)} orphan number(s), {len(counters_wrong)} counter(s) off target", items)
    if strict and bound is None and any(data_mod.number_tokens(t) for t in copy_texts):
        rep.add("numbers_sourced", "warning", "numbers appear in copy but no data/bindings.json exists; bind them or cite them in facts/claims.json")


def check_facts(rep: Report, project: Path, needed: bool) -> list[str]:
    ledger = project / "facts" / "claims.json"
    if not ledger.is_file():
        rep.add("facts", "error" if needed else "pass", "brief needs facts but facts/claims.json is missing" if needed else "no factual claims declared")
        return []
    result = claims_mod.verify_claims(ledger)
    status = "pass" if result["status"] == "source_linked" else "error"
    rep.add("facts", status, f"{result.get('claimCount', 0)} claims, {result.get('sourceCount', 0)} sources: {result['status']} "
            "(source-linked, semantic review still required)", [i["message"] for i in result.get("issues", [])])
    return result.get("onScreen", [])


def check_text_layout(rep: Report, insp: dict[str, Any], ratio: str) -> None:
    W, H = insp["canvas"]["w"], insp["canvas"]["h"]
    base_w, base_h = RATIOS[ratio]
    k = min(W / base_w, H / base_h)
    min_font = 30 * min(W, H) / 1080 if ratio != "16:9" else 28 * H / 1080
    safe = {key: v * k for key, v in SAFE[ratio].items()}
    small, unsafe = {}, {}
    step = insp["step_frames"] / insp["fps"]
    for s in insp["samples"]:
        for b in s["text"]:
            if b.get("provenance") in ("decor", "ignore") or b["opacity"] < 0.5:
                continue
            if b["font"] < min_font - 0.5:
                small.setdefault(b["text"][:50], f"{b['font']}px at t={s['t']}s")
            x0, y0, x1, y1 = b["box"]
            if b["opacity"] >= 0.95 and (x0 < safe["side"] - 4 or x1 > W - safe["side"] + 4 or y0 < safe["top"] - 4 or y1 > H - safe["bottom"] + 4):
                unsafe.setdefault(b["text"][:50], []).append(s["t"])
    persistent = {t: ts for t, ts in unsafe.items() if len(ts) * step >= 0.5}
    rep.add("text_size", "error" if small else "pass", f"minimum {min_font:.0f}px", [f"\"{t}\" {v}" for t, v in small.items()])
    rep.add("safe_area", "error" if persistent else "pass", f"safe area top {safe['top']:.0f} / bottom {safe['bottom']:.0f} / sides {safe['side']:.0f}px",
            [f"\"{t}\" outside for {len(ts) * step:.1f}s from t={ts[0]}s" for t, ts in persistent.items()])


def check_beats(rep: Report, project: Path, insp: dict[str, Any]) -> None:
    resolved_path = project / "beatmap.resolved.json"
    if not resolved_path.is_file():
        rep.add("beat_accuracy", "warning", "no beat map; timing not verified")
        return
    resolved = read_json(resolved_path)
    fps = resolved["fps"]
    hits = insp["timeline"]["hits"]
    off = []
    for h in hits:
        ev = resolved["events"].get(h["id"])
        if ev is None:
            off.append(f"{h['id']}: not in beat map")
            continue
        if h.get("counter"):
            land = round(h["impact"] * fps)
        elif h.get("mode") == "cut":
            land = round(h["start"] * fps)   # on-the-cut hit: the from-state appears on the impact frame
        else:
            land = round(h["end"] * fps)
        if land != ev["impact_frame"]:
            off.append(f"{h['id']}: lands on frame {land}, beat map says {ev['impact_frame']}")
    used = {h["id"] for h in hits} | set(insp["timeline"].get("events_used", []))
    unanimated = [k for k, v in resolved["events"].items() if k not in used and v["tier"] not in ("hold", "word")]
    total = len(hits)
    status = "error" if off else ("warning" if unanimated else "pass")
    rep.add("beat_accuracy", status, f"{total - len(off)}/{total} hits land on their beat-map frame; {len(unanimated)} beat-map events never animated",
            off + [f"unanimated: {u}" for u in unanimated])


def check_media(rep: Report, project: Path) -> None:
    st = state(project)
    master = project / "renders" / "master.mp4"
    if not master.is_file():
        rep.add("spec", "error", "renders/master.mp4 missing (run `mstudio render`)")
        return
    info = ffprobe(master)
    w, h = RATIOS[st["ratio"]]
    v = info["video"] or {}
    dur_ok = abs(info["duration"] - st["duration"]) <= 1.0 / st["fps"] + 0.05
    spec_ok = v.get("width") == w and v.get("height") == h and abs((v.get("fps") or 0) - st["fps"]) < 0.01 and dur_ok and info["audio"] is not None
    rep.add("spec", "pass" if spec_ok else "error",
            f"{v.get('width')}x{v.get('height')} @ {v.get('fps')} fps, {info['duration']:.3f}s (target {w}x{h} @ {st['fps']}, {st['duration']}s), audio {'yes' if info['audio'] else 'no'}")
    loud = loudness(master)
    i, tp = loud["integrated_lufs"], loud["true_peak_dbtp"]
    ok = i is not None and abs(i - LUFS_TARGET) <= LUFS_TOL and tp is not None and tp <= TP_MAX
    rep.add("loudness", "pass" if ok else "error", f"integrated {i} LUFS (target {LUFS_TARGET}±{LUFS_TOL}), true peak {tp} dBTP (max {TP_MAX})")
    log = sh(["ffmpeg", "-nostats", "-i", str(master), "-vf", "blackdetect=d=0.1:pix_th=0.06:pic_th=0.999,freezedetect=n=0.0003:d=1.5", "-an", "-f", "null", "-"], check=False).stderr
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
    freezes = re.findall(r"freeze_start: ([\d.]+)", log)
    intended = []
    resolved = project / "beatmap.resolved.json"
    if resolved.is_file():
        r = read_json(resolved)
        intended = [(e["impact_frame"] / r["fps"], (e["until_frame"] or e["impact_frame"]) / r["fps"]) for e in r["events"].values()
                    if e["kind"] in ("black", "hold", "freeze")]
    stray_black = [f"{a}-{b}s" for a, b in blacks if not any(s - 0.1 <= float(a) <= e + 0.1 for s, e in intended)]
    stray_freeze = [f"from {a}s" for a in freezes if not any(s - 0.1 <= float(a) <= e for s, e in intended)]
    rep.add("black_freeze", "warning" if (stray_black or stray_freeze) else "pass",
            f"{len(stray_black)} unintended black segment(s), {len(stray_freeze)} frozen stretch(es) ≥1 s", stray_black + stray_freeze)
    # contact sheet for the reviewer
    cols = 10
    rows = max(1, int(-(-(info["duration"] + 0.999) // cols)))
    tw = 216 if h > w else 384
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(master), "-vf", f"fps=1,scale={tw}:-2,tile={cols}x{rows}", "-frames:v", "1", "-q:v", "3",
        str(project / "renders" / "qa" / "contact.jpg")], check=False)


def check_sound_design(rep: Report, project: Path) -> None:
    """Variety, not just placement: distinct sounds per hit type, no copy-paste repeats, no recycled music bed."""
    from . import music as music_mod
    items: list[str] = []
    cues_path = project / "renders" / "sfx-cues.json"
    active = [c for c in read_json(cues_path) if not c.get("dropped")] if cues_path.is_file() else []
    if active:
        files = [c["file"] for c in active]
        distinct = len(set(files))
        library_only = all(f.startswith("@repo/") for f in files)
        exact_repeats = [f for f in set(files) if sum(1 for c in active if c["file"] == f and not c.get("semitones")) > 1]
        heavy = [f"{f.split('/')[-1]} x{files.count(f)}" for f in set(files) if files.count(f) > max(4, len(files) // 3)]
        if distinct < min(4, len(files)):
            items.append(f"only {distinct} distinct sound(s) for {len(files)} cues")
        if heavy:
            items.append("leaning on one sound: " + ", ".join(heavy))
        if exact_repeats:
            items.append(f"{len(exact_repeats)} sound(s) repeat without variation")
        if library_only and len(files) >= 6:
            items.append("every cue comes from the stock SFX library; add project sounds (mstudio sfx make/vary/gen)")
    brief = read_json(project / "brief.json")
    track = (read_json(project / "beatmap.json").get("music") or {}).get("file") if (project / "beatmap.json").is_file() else None
    if track and (project / track).is_file() and not brief.get("music", {}).get("brand_music"):
        others = music_mod.used_elsewhere(state(project)["slug"], project / track)
        if others:
            items.append(f"music bed already used in: {', '.join(others[:5])} (generate a new one: mstudio music gen, or mark brief.music.brand_music)")
    rep.add("sound_design", "warning" if items else "pass",
            f"{len(set(c['file'] for c in active))} distinct sounds across {len(active)} cues" if active else "no SFX cues", items)


def check_credits(rep: Report, project: Path) -> None:
    credits = read_json(project / "credits.json").get("assets", [])
    listed = {c.get("path", "").rstrip("/") for c in credits}
    bad = [c.get("path", "?") for c in credits if not c.get("license") or not c.get("source")]
    unlisted = []
    for folder in ("audio", "footage", "data/raw", "facts/sources", "assets", "fonts"):
        root = project / folder
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in MEDIA_EXT or "conformed" in p.parts or "sheets" in p.parts:
                continue
            rel = p.relative_to(project).as_posix()
            if rel in ("audio/beats.json", "audio/words.json", "footage/footage.json", "footage/reframe.json"):
                continue
            if not any(rel == l or rel.startswith(l + "/") for l in listed):
                unlisted.append(rel)
    status = "error" if (bad or unlisted) else "pass"
    rep.add("credits", status, f"{len(credits)} credit entries; {len(unlisted)} unlisted file(s); {len(bad)} entr(ies) without license/source", unlisted + bad)


def check_revision(rep: Report, project: Path) -> None:
    st = state(project)
    rev = st.get("revision")
    if not rev or rev.get("verified"):
        return
    from .revise import verify
    result = verify(project)
    rep.add("revision", "pass" if result["ok"] else "error", result["summary"], result.get("items", []))


def run(project: Path, *, skip_media: bool = False) -> dict[str, Any]:
    from .render import check as hf_check, sync
    st = state(project)
    brief = read_json(project / "brief.json")
    needs = brief.get("needs", {})
    rep = Report()
    sync(project)
    hf = hf_check(project)
    findings = []
    for section in ("lint", "runtime", "layout", "motion", "contrast"):
        sec = hf.get(section) or {}
        for f in (sec.get("findings") or sec.get("issues") or []) if isinstance(sec, dict) else []:
            findings.append((f.get("severity", "warning"), f"{section}: {f.get('code', '')} {f.get('message', '')}".strip()))
    errs = [m for s, m in findings if s == "error"]
    rep.add("hyperframes", "error" if (errs or hf.get("ok") is False) else ("warning" if findings else "pass"),
            f"hyperframes check: {len(errs)} error(s), {len(findings) - len(errs)} other finding(s)", [m for _, m in findings])
    insp = _inspect(project)
    rep.add("console", "error" if insp["console_errors"] else "pass", f"{len(insp['console_errors'])} JavaScript error(s)", insp["console_errors"])
    claim_texts = check_facts(rep, project, bool(needs.get("facts")))
    copy_texts = check_copy(rep, project, insp)
    check_numbers(rep, project, insp, copy_texts, claim_texts, strict=bool(needs.get("data") or needs.get("facts")))
    check_text_layout(rep, insp, st["ratio"])
    check_beats(rep, project, insp)
    if not skip_media:
        check_media(rep, project)
        check_sound_design(rep, project)
        check_revision(rep, project)
    check_credits(rep, project)
    failed = [c for c in rep.checks if c["status"] == "error"]
    warned = [c for c in rep.checks if c["status"] == "warning"]
    report = {"at": now(), "version": st["version"], "pass": not failed,
              "summary": f"{len(rep.checks) - len(failed) - len(warned)} pass, {len(warned)} warning, {len(failed)} fail",
              "checks": rep.checks}
    write_json(project / "renders" / "qa" / "report.json", report)
    (project / "renders" / "qa" / "report.md").write_text(to_markdown(report), encoding="utf-8")
    log_decision(project, "qa", f"QA v{st['version']}: {report['summary']}.", "")
    return report


def to_markdown(report: dict[str, Any]) -> str:
    icon = {"pass": "PASS", "warning": "WARN", "error": "FAIL"}
    lines = [f"# QA report (v{report['version']}, {report['at']})", "", f"**{'PASSED' if report['pass'] else 'FAILED'}**: {report['summary']}", ""]
    for c in report["checks"]:
        lines.append(f"- **{icon[c['status']]} {c['id']}**: {c['detail']}")
        for item in c["items"][:15]:
            lines.append(f"  - {item}")
    return "\n".join(lines) + "\n"
