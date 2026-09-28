"""`mstudio`: the command line the agent drives. Every command is idempotent and prints what to do next."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, audio, beatmap, beats, data, footage, project, qa, render, revise
from .project import RATIOS, current_stage, gate_status, project_dir, state
from .util import StudioError, hyperframes, read_json, write_json


def _p(args: argparse.Namespace) -> Path:
    return project_dir(args.project)


def cmd_doctor(_: argparse.Namespace) -> int:
    from .doctor import doctor
    rows = doctor()
    for r in rows:
        print(f"{'ok ' if r['ok'] else 'FAIL'} {r['check']:<12} {r['detail']}" + (f"\n     fix: {r['fix']}" if r["fix"] else ""))
    bad = [r for r in rows if not r["ok"]]
    print(f"\nmotion-studio {__version__}: " + ("ready" if not bad else f"{len(bad)} problem(s)"))
    return 1 if bad else 0


def cmd_new(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else None
    dest = project.new_project(args.slug, ratio=args.ratio, fps=args.fps, duration=args.duration, mode=args.mode,
                               title=args.title or "", root=root, brand=args.brand)
    _credit_defaults(dest)
    print(f"created {dest}\nnext: fill brief.json, then write style-brief.md (skills/director)")
    return 0


def _credit_defaults(dest: Path) -> None:
    credits = read_json(dest / "credits.json")
    credits["assets"] = [
        {"path": "fonts", "what": "Inter, JetBrains Mono, Vazirmatn variable fonts", "source": "https://github.com/google/fonts",
         "license": "SIL Open Font License 1.1", "author": "Rasmus Andersson; JetBrains; Saber Rastikerdar"},
        {"path": "vendor/gsap.min.js", "what": "GSAP 3.14.2", "source": "https://gsap.com", "license": "GSAP Standard 'No Charge' License"},
    ]
    write_json(dest / "credits.json", credits)


def cmd_refresh(args: argparse.Namespace) -> int:
    done = project.refresh_runtime(_p(args))
    print("refreshed: " + ", ".join(done))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    p = _p(args)
    st = state(p)
    stage, nxt, _ = current_stage(p)
    print(f"{st['slug']}  v{st['version']}  {st['ratio']} {st['fps']}fps {st['duration']}s  mode={st['mode']}")
    for g, s in gate_status(p).items():
        print(f"  gate {g} ({project.GATE_NAMES[g]}): {s}")
    if st.get("revision") and not st["revision"].get("verified"):
        print(f"  open revision v{st['revision']['version']}: scene {st['revision']['scene']}")
    print(f"stage: {stage}\nnext:  {nxt}")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    p = _p(args)
    a = project.approve(p, args.gate, args.by, args.note or "")
    print(f"gate {args.gate.upper()} approved by {a['approved_by']} ({a['sha256'][:12]})")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    project.log_decision(_p(args), args.topic, args.choice, args.why or "", args.alternatives or "")
    print("logged")
    return 0


def cmd_beats(args: argparse.Namespace) -> int:
    p = _p(args)
    src = (p / args.audio) if not Path(args.audio).is_absolute() else Path(args.audio)
    result = beats.analyze(src, min_bpm=args.min_bpm, max_bpm=args.max_bpm, meter=args.meter, bpm_hint=args.bpm_hint)
    out = p / "audio" / (args.out or "beats.json")
    beats.write(result, out)
    print(beats.summary(result))
    print(f"wrote {out.relative_to(p)}")
    return 0


def cmd_words(args: argparse.Namespace) -> int:
    p = _p(args)
    hyperframes(["transcribe", args.audio, "--dir", ".", "--json"] + (["--language", args.language] if args.language else []), cwd=p, timeout=3600)
    transcript = p / "transcript.json"
    words = read_json(transcript)
    words = words.get("words", words) if isinstance(words, dict) else words
    write_json(p / "audio" / "words.json", {"source": args.audio, "words": [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in words]})
    print(f"{len(words)} words -> audio/words.json")
    return 0


def cmd_beatmap(args: argparse.Namespace) -> int:
    p = _p(args)
    resolved = beatmap.resolve(p)
    print(beatmap.report(resolved))
    if resolved["ok"] and args.action == "apply":
        changed = beatmap.apply(p)
        print(f"index.html timing synced ({len(changed)} element(s) updated)")
    return 0 if resolved["ok"] else 1


def cmd_data(args: argparse.Namespace) -> int:
    out = data.bind(_p(args))
    print(f"bound {len(out['values'])} value(s), {len(out['series'])} series -> data.js")
    return 0


def cmd_facts(args: argparse.Namespace) -> int:
    from .claims import verify_claims
    result = verify_claims(_p(args) / "facts" / "claims.json")
    print(json.dumps({k: v for k, v in result.items() if k != "onScreen"}, indent=2))
    return 0 if result["status"] == "source_linked" else 1


def cmd_footage(args: argparse.Namespace) -> int:
    p = _p(args)
    st = state(p)
    if args.action == "analyze":
        d = footage.analyze(p)
        for cid, c in d["clips"].items():
            ev = ", ".join(f"{e['ref']}@{e['t']}s" for e in c["events"][:6]) or "none"
            print(f"{cid}: {c['width']}x{c['height']} {c['fps']}fps {c['duration']}s audio={'yes' if c['audio'] and c['audio']['audible'] else 'no'} "
                  f"picture={c['content_box']}{' (bars)' if c['bars'] else ''} events: {ev}")
        print("contact sheets in footage/sheets/; next: `mstudio footage <slug> conform`")
    elif args.action == "conform":
        made = footage.conform(p, st["fps"])
        print(f"conformed {len(made)} file(s) at {st['fps']} fps into footage/conformed/")
    else:
        w, h = RATIOS[st["ratio"]]
        r = footage.reframe(p, (w, h))
        for i in r["issues"]:
            print(f"{i['level'].upper()} {i['code']}: {i['message']}")
        print(("OK" if r["ok"] else "FAILED") + f": {len(r['media'])} reframed media -> reframe.js")
        return 0 if r["ok"] else 1
    return 0


def cmd_copy(args: argparse.Namespace) -> int:
    p = _p(args)
    items = qa.extract_copy(p)
    write_json(p / "copy.json", {"from": "script.md", "note": "Review: remove non-screen quotes, adjust min_seconds.", "required": items})
    print(f"{len(items)} required string(s) -> copy.json (review it)")
    return 0


def cmd_styleframes(args: argparse.Namespace) -> int:
    p = _p(args)
    times = [float(t) for t in args.at.split(",")] if args.at else []
    if args.events:
        resolved = read_json(p / "beatmap.resolved.json")
        times += [resolved["events"][e]["impact_frame"] / resolved["fps"] + 0.2 for e in args.events.split(",")]
    if not times:
        raise StudioError("pass --at seconds or --events ids")
    names = render.styleframes(p, sorted(times))
    print("styleframes: " + ", ".join(names))
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    p = _p(args)
    render.sync(p)
    out = hyperframes(["preview", ".", "--background"] + (["--port", str(args.port)] if args.port else []), cwd=p, timeout=120)
    print(out.stdout[-800:])
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    rep = render.render(_p(args), draft=args.draft, keep_gain=args.keep_gain, sfx=not args.no_sfx)
    m = rep["master"]
    print(f"renders/master.mp4: {m['video']['width']}x{m['video']['height']} {m['video']['fps']}fps {m['duration']:.2f}s; "
          f"{rep['sound']['cues']} SFX cues; {rep['sound']['master']['integrated_lufs']} LUFS / {rep['sound']['master']['true_peak_dbtp']} dBTP; "
          f"{rep['seconds']['total']} s")
    print("next: `mstudio qa <slug>`")
    return 0


def cmd_sound(args: argparse.Namespace) -> int:
    p = _p(args)
    prev = read_json(p / "renders" / "sound.json").get("gain_db") if args.keep_gain and (p / "renders" / "sound.json").is_file() else None
    rep = audio.mix(p, keep_gain=prev, sfx=not args.no_sfx)
    print(f"{rep['cues']} cues ({rep['dropped']} dropped), gain {rep['gain_db']} dB -> {rep['master']}")
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    p = _p(args)
    report = qa.run(p, skip_media=args.composition_only)
    print(qa.to_markdown(report))
    return 0 if report["pass"] else 1


def cmd_revise(args: argparse.Namespace) -> int:
    p = _p(args)
    if args.action == "start":
        if not args.scene:
            raise StudioError("--scene is required")
        r = revise.start(p, args.scene, args.request or "")
        print(f"opened v{r['version']} for scene {r['scene']}; edit only that scene, then `mstudio render {p.name} --keep-gain` and `mstudio qa`")
    else:
        r = revise.verify(p)
        print(r["summary"])
        for i in r["items"][:20]:
            print("  " + i)
        return 0 if r["ok"] else 1
    return 0


def cmd_deliver(args: argparse.Namespace) -> int:
    s = render.deliver(_p(args))
    print(f"delivered renders/delivery/{s['file']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="mstudio", description=__doc__)
    ap.add_argument("--version", action="version", version=f"motion-studio {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check the toolchain").set_defaults(func=cmd_doctor)
    s = sub.add_parser("new", help="create projects/<slug>")
    s.add_argument("slug")
    s.add_argument("--ratio", default="9:16", choices=list(RATIOS))
    s.add_argument("--fps", type=int, default=30)
    s.add_argument("--duration", type=float, default=30.0)
    s.add_argument("--mode", default="interactive", choices=list(project.MODES))
    s.add_argument("--title")
    s.add_argument("--brand")
    s.add_argument("--root", help="parent folder (default: projects/)")
    s.set_defaults(func=cmd_new)
    for name, fn, hlp in (("status", cmd_status, "stage, gates and the next step"),
                          ("refresh", cmd_refresh, "reinstall runtime files (studio.js, tokens, GSAP, fonts) into a project")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("project")
        s.set_defaults(func=fn)
    s = sub.add_parser("gate", help="record a gate approval")
    s.add_argument("project")
    s.add_argument("gate", choices=["A", "B", "C", "a", "b", "c"])
    s.add_argument("--by", required=True, choices=["human", "agent"])
    s.add_argument("--note")
    s.set_defaults(func=cmd_gate)
    s = sub.add_parser("decide", help="append to decisions.md")
    s.add_argument("project")
    s.add_argument("topic")
    s.add_argument("choice")
    s.add_argument("--why")
    s.add_argument("--alternatives")
    s.set_defaults(func=cmd_decide)
    s = sub.add_parser("beats", help="analyse music -> audio/beats.json")
    s.add_argument("project")
    s.add_argument("audio")
    s.add_argument("--out")
    s.add_argument("--bpm-hint", type=float)
    s.add_argument("--min-bpm", type=float, default=60.0)
    s.add_argument("--max-bpm", type=float, default=200.0)
    s.add_argument("--meter", type=int, choices=[3, 4])
    s.set_defaults(func=cmd_beats)
    s = sub.add_parser("words", help="voice-over word timestamps -> audio/words.json")
    s.add_argument("project")
    s.add_argument("audio")
    s.add_argument("--language")
    s.set_defaults(func=cmd_words)
    s = sub.add_parser("beatmap", help="resolve (validate) or apply the beat map")
    s.add_argument("project")
    s.add_argument("action", choices=["resolve", "apply"], nargs="?", default="resolve")
    s.set_defaults(func=cmd_beatmap)
    s = sub.add_parser("data", help="bind data/bindings.json -> data.js")
    s.add_argument("project")
    s.set_defaults(func=cmd_data)
    s = sub.add_parser("facts", help="verify facts/claims.json")
    s.add_argument("project")
    s.set_defaults(func=cmd_facts)
    s = sub.add_parser("footage", help="analyze | conform | reframe")
    s.add_argument("project")
    s.add_argument("action", choices=["analyze", "conform", "reframe"])
    s.set_defaults(func=cmd_footage)
    s = sub.add_parser("copy", help="extract required on-screen copy from script.md -> copy.json")
    s.add_argument("project")
    s.set_defaults(func=cmd_copy)
    s = sub.add_parser("styleframes", help="snapshot key moments into styleframes/")
    s.add_argument("project")
    s.add_argument("--at")
    s.add_argument("--events")
    s.set_defaults(func=cmd_styleframes)
    s = sub.add_parser("preview", help="start the HyperFrames Studio preview in the background")
    s.add_argument("project")
    s.add_argument("--port", type=int)
    s.set_defaults(func=cmd_preview)
    s = sub.add_parser("render", help="check + render picture + sound + loudness -> renders/master.mp4")
    s.add_argument("project")
    s.add_argument("--draft", action="store_true")
    s.add_argument("--keep-gain", action="store_true", help="reuse the previous loudness gain (revisions)")
    s.add_argument("--no-sfx", action="store_true")
    s.set_defaults(func=cmd_render)
    s = sub.add_parser("sound", help="redo SFX + mix without re-rendering the picture")
    s.add_argument("project")
    s.add_argument("--keep-gain", action="store_true")
    s.add_argument("--no-sfx", action="store_true")
    s.set_defaults(func=cmd_sound)
    s = sub.add_parser("qa", help="run the definition-of-done checks")
    s.add_argument("project")
    s.add_argument("--composition-only", action="store_true", help="skip rendered-media checks (before render)")
    s.set_defaults(func=cmd_qa)
    s = sub.add_parser("revise", help="start | verify a single-scene revision")
    s.add_argument("project")
    s.add_argument("action", choices=["start", "verify"])
    s.add_argument("--scene")
    s.add_argument("--request")
    s.set_defaults(func=cmd_revise)
    s = sub.add_parser("deliver", help="copy the QA-passed master to renders/delivery with poster + manifest")
    s.add_argument("project")
    s.set_defaults(func=cmd_deliver)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except StudioError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
