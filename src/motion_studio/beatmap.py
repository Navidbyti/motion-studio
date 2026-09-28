"""Beat map: the timing contract between the edit and the composition.

The beat editor writes `beatmap.json` with musical anchors ("downbeat 4",
"the snare after bar 6", "the word 'launch'", "clip 02's flash on downbeat 2").
`resolve()` turns every anchor into an exact frame, validates the edit rules,
and writes:

- `beatmap.resolved.json`: frames and seconds for every scene, event and media clip
- `timing.js`: `window.TIMING = {...}` for the composition (read via Studio.at())

`apply()` then writes data-start / data-duration / data-media-start on the
composition elements marked `data-scene="…"` and `data-media="…"`, so the HTML
attributes can never drift from the beat map.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .util import StudioError, read_json, sha256_file, write_json

TIERS = ("scene", "big", "punch", "entrance", "micro", "hold", "word")
DEFAULT_RULES = {
    "anticipation_frames": {"scene": 0, "big": 3, "punch": 2, "entrance": 4, "micro": 1, "hold": 0, "word": 2},
    "max_big_hits_per_bar": 1,
    "max_events_per_bar": 6,
    "min_scene_beats": 2,
    "min_hold_frames": 12,
}


class BeatmapError(StudioError):
    pass


def frame(t: float, fps: float) -> int:
    return int(math.floor(t * fps + 0.5))


# --------------------------------------------------------------------------- anchors

class Clock:
    """Resolves musical, spoken and visual anchors to composition seconds."""

    def __init__(self, beats: dict[str, Any] | None, words: list[dict[str, Any]] | None,
                 visual: dict[str, Any] | None, music_start_at: float, music_offset: float, fps: float):
        self.beats = beats
        self.words = words or []
        self.visual = visual or {}
        self.start_at = music_start_at   # seconds into the music file where the edit starts
        self.offset = music_offset        # composition time at which that music point plays
        self.fps = fps
        if beats:
            self.beat_t = [b["t"] for b in beats["beats"]]
            self.down_t = list(beats["downbeats"])
            self.snare_t = [b["t"] for b in beats["beats"] if b.get("snare")]
            self.kick_t = [b["t"] for b in beats["beats"] if b.get("kick")]
            self.drop_t = list(beats.get("drops", []))
            self.section_t = [s["start"] for s in beats.get("sections", [])]
            self.bar_t = self.down_t
        # anchors count from the music in-point, so "downbeat 0" = first downbeat at/after start_at
        self._skip = {}

    def _music(self, t_music: float) -> float:
        return t_music - self.start_at + self.offset

    def _nth(self, seq: list[float], n: float, name: str) -> float:
        if not self.beats:
            raise BeatmapError(f"anchor '{name}' needs music beats (music.beats in beatmap.json)")
        base = [t for t in seq if t >= self.start_at - 1e-6]
        whole = int(math.floor(n))
        frac = n - whole
        if whole < 0 or whole >= len(base):
            raise BeatmapError(f"{name} {n} is out of range (music has {len(base)} after the in-point)")
        t = base[whole]
        if frac:
            nxt = base[whole + 1] if whole + 1 < len(base) else t + (t - base[whole - 1])
            t = t + frac * (nxt - t)
        return t

    def grid_times(self) -> list[float]:
        if not self.beats:
            return []
        return [self._music(t) for t in self.beat_t]

    def resolve(self, anchor: dict[str, Any], where: str) -> tuple[float, str]:
        """Return (composition seconds, anchor kind)."""
        if not isinstance(anchor, dict) or not anchor:
            raise BeatmapError(f"{where}: anchor must be an object like {{\"downbeat\": 2}}")
        nudge = float(anchor.get("plus_beats", 0.0))
        kind = next((k for k in ("time", "frame", "bar", "downbeat", "beat", "snare", "kick", "drop", "section", "word", "visual") if k in anchor), None)
        if kind is None:
            raise BeatmapError(f"{where}: unknown anchor {anchor}")
        if kind == "time":
            return float(anchor["time"]), "time"
        if kind == "frame":
            return int(anchor["frame"]) / self.fps, "time"
        if kind == "word":
            return self._word(anchor, where), "word"
        if kind == "visual":
            raise BeatmapError(f"{where}: visual anchors are only valid in media 'align'")
        if kind == "bar":
            bar_t = self._nth(self.bar_t, anchor["bar"], "bar")
            idx = min(range(len(self.beat_t)), key=lambda i: abs(self.beat_t[i] - bar_t)) + int(anchor.get("beat", 1)) - 1
            if idx >= len(self.beat_t):
                raise BeatmapError(f"{where}: bar {anchor['bar']} beat {anchor.get('beat', 1)} is past the end of the music")
            t = self.beat_t[idx]
        else:
            seq = {"downbeat": self.down_t, "beat": self.beat_t, "snare": self.snare_t, "kick": self.kick_t,
                   "drop": self.drop_t, "section": self.section_t}[kind]
            t = self._nth(seq, float(anchor[kind]), kind)
        if nudge:
            period = self.beats["tempo"]["beat_period"]
            t += nudge * period
        return self._music(t), kind

    def _word(self, anchor: dict[str, Any], where: str) -> float:
        if not self.words:
            raise BeatmapError(f"{where}: word anchors need words.json (voice-over transcript)")
        if "word_index" in anchor:
            w = self.words[int(anchor["word_index"])]
            return float(w["start"])
        target = _norm(anchor["word"])
        hits = [w for w in self.words if _norm(w["text"]) == target]
        occ = int(anchor.get("occurrence", 1))
        if len(hits) < occ:
            raise BeatmapError(f"{where}: word '{anchor['word']}' occurrence {occ} not in transcript")
        return float(hits[occ - 1]["start"])

    def visual_event(self, ref: str, where: str) -> float:
        """'<clip id>:<kind>:<n>' -> seconds inside that clip."""
        try:
            clip, kind, n = ref.split(":")
            events = [e for e in self.visual[clip]["events"] if e["kind"] == kind]
            return float(events[int(n) - 1]["t"])
        except (KeyError, ValueError, IndexError) as exc:
            raise BeatmapError(f"{where}: visual event '{ref}' not found in footage.json ({exc})") from exc


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


# --------------------------------------------------------------------------- resolve + validate

def resolve(project: str | Path) -> dict[str, Any]:
    root = Path(project)
    spec = read_json(root / "beatmap.json")
    fps = float(spec["fps"])
    duration_frames = frame(float(spec["duration"]), fps)
    rules = {**DEFAULT_RULES, **spec.get("rules", {})}
    rules["anticipation_frames"] = {**DEFAULT_RULES["anticipation_frames"], **spec.get("rules", {}).get("anticipation_frames", {})}
    music = spec.get("music") or {}
    beats = read_json(root / music["beats"]) if music.get("beats") else None
    words = read_json(root / spec["words"])["words"] if spec.get("words") else None
    visual = read_json(root / spec["footage"])["clips"] if spec.get("footage") else None
    clock = Clock(beats, words, visual, float(music.get("start_at", 0.0)), float(music.get("offset", 0.0)), fps)
    issues: list[dict[str, str]] = []

    def issue(level: str, code: str, msg: str) -> None:
        issues.append({"level": level, "code": code, "message": msg})

    grid = clock.grid_times()
    tol = float(rules.get("tolerance_ms", 1000 / fps / 2 + 2)) / 1000

    def on_grid(t: float) -> bool:
        return any(abs(t - g) <= tol for g in grid)

    scenes_out, events_out, media_out = [], {}, {}
    seen: set[str] = set()
    for si, scene in enumerate(spec["scenes"]):
        sid = scene["id"]
        if sid in seen:
            issue("error", "duplicate_id", f"scene id {sid} is used twice")
        seen.add(sid)
        s_t, s_kind = clock.resolve(scene["start"], f"scene {sid} start")
        e_t, _ = clock.resolve(scene["end"], f"scene {sid} end") if "end" in scene else (None, None)
        scenes_out.append({"id": sid, "start": s_t, "start_kind": s_kind, "end": e_t, "purpose": scene.get("purpose", ""),
                           "transition_in": scene.get("transition_in"), "overlap_frames": int(scene.get("overlap_frames", 0))})
        for ev in scene.get("events", []):
            eid = ev["id"]
            if eid in seen:
                issue("error", "duplicate_id", f"event id {eid} is used twice")
            seen.add(eid)
            tier = ev.get("tier", "entrance")
            if tier not in TIERS:
                issue("error", "bad_tier", f"event {eid}: tier must be one of {TIERS}")
            t, kind = clock.resolve(ev["at"], f"event {eid}")
            if kind == "time" and not ev.get("free"):
                issue("error", "off_grid", f"event {eid}: free time anchor; tie it to a beat/downbeat/word or mark \"free\": true with a reason")
            impact = frame(t, fps)
            antic = int(ev.get("anticipation", rules["anticipation_frames"].get(tier, 0)))
            until = None
            if "until" in ev:
                until = frame(clock.resolve(ev["until"], f"event {eid} until")[0], fps)
            events_out[eid] = {"scene": sid, "tier": tier, "kind": ev.get("kind", tier), "anchor": kind,
                               "impact_frame": impact, "start_frame": impact - antic, "until_frame": until,
                               "target": ev.get("target"), "note": ev.get("note", "")}
            if kind not in ("time", "word") and grid and not on_grid(t) and "plus_beats" not in ev["at"]:
                issue("warning", "grid_drift", f"event {eid}: {t:.3f}s is not on the beat grid")
        for m in scene.get("media", []):
            mid = m["id"]
            media_out[mid] = {"scene": sid, "file": m["file"], "spec": m}
    # scene ends: next scene's start, or composition end
    for i, s in enumerate(scenes_out):
        if s["end"] is None:
            s["end"] = scenes_out[i + 1]["start"] if i + 1 < len(scenes_out) else duration_frames / fps
        s["start_frame"] = frame(s["start"], fps)
        s["end_frame"] = frame(s["end"], fps)
        # transitions may overlap the previous scene
        s["enter_frame"] = s["start_frame"] - s["overlap_frames"]
        s["duration_frames"] = s["end_frame"] - s["enter_frame"]
    # media placement and footage alignment
    for mid, m in media_out.items():
        spec_m, scene = m["spec"], next(s for s in scenes_out if s["id"] == m["scene"])
        start_f = scene["enter_frame"] if "start" not in spec_m else frame(clock.resolve(spec_m["start"], f"media {mid} start")[0], fps)
        end_f = scene["end_frame"]
        if "align" in spec_m:
            ev_t = clock.visual_event(spec_m["align"]["visual"], f"media {mid}")
            to_t, _ = clock.resolve(spec_m["align"]["to"], f"media {mid} align")
            media_in = ev_t - (to_t - start_f / fps)
            if media_in < 0:
                issue("error", "align_impossible", f"media {mid}: aligning needs {-media_in:.2f}s before the clip starts; start the scene later or pick another beat")
            m["aligned_event_frame"] = frame(to_t, fps)
        else:
            media_in = float(spec_m.get("in", 0.0))
        clip_len = visual[spec_m.get("clip", "")]["duration"] if visual and spec_m.get("clip") in (visual or {}) else None
        if clip_len is not None and media_in + (end_f - start_f) / fps > clip_len + 1e-6:
            issue("error", "media_too_short", f"media {mid}: needs {(end_f - start_f) / fps:.2f}s from {media_in:.2f}s but clip is {clip_len:.2f}s")
        m.update({"start_frame": start_f, "end_frame": end_f, "media_in": round(max(0.0, media_in), 4)})
        m.pop("spec")

    # ---- rules
    if scenes_out and scenes_out[0]["start_frame"] != 0:
        issue("error", "gap_at_start", f"first scene starts at frame {scenes_out[0]['start_frame']}, not 0")
    if scenes_out and scenes_out[-1]["end_frame"] != duration_frames:
        issue("error", "length_mismatch", f"last scene ends at frame {scenes_out[-1]['end_frame']}, composition is {duration_frames} frames")
    for a, b in zip(scenes_out, scenes_out[1:]):
        if b["start_frame"] < a["start_frame"]:
            issue("error", "scene_order", f"scene {b['id']} starts before {a['id']}")
        elif a["end_frame"] != b["start_frame"]:
            issue("error", "gap", f"scene {a['id']} ends at frame {a['end_frame']} but {b['id']} starts at {b['start_frame']}; "
                                  "scenes must be contiguous (use overlap_frames for transitions)")
    period_frames = beats["tempo"]["beat_period"] * fps if beats else None
    for s in scenes_out:
        if period_frames and (s["end_frame"] - s["start_frame"]) < rules["min_scene_beats"] * period_frames - 1:
            issue("warning", "short_scene", f"scene {s['id']} is shorter than {rules['min_scene_beats']} beats")
        opens = [e for e in events_out.values() if e["scene"] == s["id"] and e["impact_frame"] == s["start_frame"]
                 and e["tier"] in ("scene", "big", "word")]
        if beats and not opens and s["start_kind"] != "time":
            issue("error", "no_opening_hit", f"scene {s['id']}: no scene/big hit on its first frame (downbeat)")
        if beats and s["start_kind"] not in ("downbeat", "drop", "section", "bar", "word") and si_is_music(s):
            issue("warning", "cut_off_downbeat", f"scene {s['id']} cuts on a {s['start_kind']}, not a downbeat/drop/word")
    for eid, e in events_out.items():
        s = next(x for x in scenes_out if x["id"] == e["scene"])
        if not (s["enter_frame"] <= e["impact_frame"] <= s["end_frame"]):
            issue("error", "outside_scene", f"event {eid} (frame {e['impact_frame']}) is outside scene {s['id']} [{s['enter_frame']}, {s['end_frame']}]")
        if e["start_frame"] < s["enter_frame"]:
            # no room to anticipate before the scene exists: the hit lands on the cut (Studio.hit does the same)
            e["start_frame"] = e["impact_frame"]
            e["on_cut"] = True
    if beats:
        bars = [frame(clock._music(t), fps) for t in beats["downbeats"]]
        for i, bf in enumerate(bars):
            nxt = bars[i + 1] if i + 1 < len(bars) else bf + 4 * period_frames
            inside = [e for e in events_out.values() if bf <= e["impact_frame"] < nxt]
            big = [e for e in inside if e["tier"] in ("big", "scene")]
            if len(big) > rules["max_big_hits_per_bar"]:
                issue("error", "too_many_big_hits", f"bar {i} ({bf}-{nxt}): {len(big)} big hits > {rules['max_big_hits_per_bar']}: {[k for k, v in events_out.items() if v in big]}")
            if len(inside) > rules["max_events_per_bar"]:
                issue("warning", "busy_bar", f"bar {i}: {len(inside)} events > {rules['max_events_per_bar']}")
    resolved = {
        "schema_version": 1, "source_sha256": sha256_file(root / "beatmap.json"),
        "fps": fps, "duration_frames": duration_frames, "duration": duration_frames / fps,
        "music": music, "rules": rules,
        "scenes": [{k: (round(v, 5) if isinstance(v, float) else v) for k, v in s.items()} for s in scenes_out],
        "events": events_out, "media": media_out,
        "issues": issues, "ok": not any(i["level"] == "error" for i in issues),
    }
    write_json(root / "beatmap.resolved.json", resolved)
    timing = {"fps": fps, "duration": resolved["duration"], "frames": duration_frames,
              "scenes": {s["id"]: {"start": s["enter_frame"] / fps, "cut": s["start_frame"] / fps, "end": s["end_frame"] / fps} for s in scenes_out},
              "events": {k: {"scene": v["scene"], "start": v["start_frame"] / fps, "impact": v["impact_frame"] / fps,
                             "until": None if v["until_frame"] is None else v["until_frame"] / fps, "tier": v["tier"]} for k, v in events_out.items()},
              "media": {k: {"start": v["start_frame"] / fps, "end": v["end_frame"] / fps, "in": v["media_in"], "file": v["file"]} for k, v in media_out.items()}}
    (root / "timing.js").write_text("// generated by `mstudio beatmap` from beatmap.json; do not edit\nwindow.TIMING = "
                                     + json.dumps(timing, indent=1) + ";\n", encoding="utf-8")
    return resolved


def si_is_music(scene: dict[str, Any]) -> bool:
    return scene["start_kind"] != "time"


# --------------------------------------------------------------------------- apply to composition

_TAG = re.compile(r"<(?P<tag>[a-zA-Z][\w-]*)(?P<attrs>[^<>]*?\bdata-(?P<kind>scene|media)=\"(?P<id>[^\"]+)\"[^<>]*?)(?P<close>/?)>")


def _set_attr(attrs: str, name: str, value: str) -> str:
    pattern = re.compile(rf'\s{re.escape(name)}="[^"]*"')
    if pattern.search(attrs):
        return pattern.sub(f' {name}="{value}"', attrs)
    return attrs + f' {name}="{value}"'


def apply(project: str | Path) -> list[str]:
    """Sync data-start/data-duration(/data-media-start) of marked elements with the resolved beat map."""
    root = Path(project)
    resolved = read_json(root / "beatmap.resolved.json")
    fps = resolved["fps"]
    scenes = {s["id"]: s for s in resolved["scenes"]}
    media = resolved["media"]
    html_path = root / "index.html"
    html = html_path.read_text(encoding="utf-8")
    html = _ensure_scene_slots(root, html, [s["id"] for s in resolved["scenes"]])
    changed: list[str] = []
    found: set[str] = set()

    def fix(m: re.Match) -> str:
        kind, ident, attrs = m.group("kind"), m.group("id"), m.group("attrs")
        if kind == "scene" and ident in scenes:
            s = scenes[ident]
            start, dur = s["enter_frame"] / fps, s["duration_frames"] / fps
            attrs = _set_attr(_set_attr(attrs, "data-start", _num(start)), "data-duration", _num(dur))
        elif kind == "media" and ident in media:
            mm = media[ident]
            # HyperFrames: a numeric data-start is absolute composition time, also for nested clips
            attrs = _set_attr(attrs, "data-start", _num(mm["start_frame"] / fps))
            attrs = _set_attr(attrs, "data-duration", _num((mm["end_frame"] - mm["start_frame"]) / fps))
            attrs = _set_attr(attrs, "data-media-start", _num(mm["media_in"]))
        else:
            return m.group(0)
        found.add(f"{kind}:{ident}")
        new = f"<{m.group('tag')}{attrs}{m.group('close')}>"
        if new != m.group(0):
            changed.append(f"{kind}:{ident}")
        return new

    html = _TAG.sub(fix, html)
    html = _sync_music(html, resolved)
    root_dur = resolved["duration"]
    html = re.sub(r'(<[^<>]*\bdata-composition-id="main"[^<>]*\bdata-duration=")[^"]*(")', rf"\g<1>{_num(root_dur)}\2", html)
    html_path.write_text(html, encoding="utf-8")
    missing = [f"scene:{k}" for k in scenes if f"scene:{k}" not in found] + [f"media:{k}" for k in media if f"media:{k}" not in found]
    if missing:
        raise BeatmapError("composition has no element for: " + ", ".join(missing) + " (mark them with data-scene / data-media)")
    return changed


def _sync_music(html: str, resolved: dict[str, Any]) -> str:
    """The music bed follows beatmap.music: in-point, offset and length are written, never hand-typed."""
    music = resolved.get("music") or {}
    if not music.get("file"):
        return html
    start = float(music.get("offset", 0.0))
    attrs = {"src": music["file"], "data-start": _num(start), "data-media-start": _num(float(music.get("start_at", 0.0))),
             "data-duration": _num(resolved["duration"] - start), "data-track-index": "10"}
    tag = re.search(r'<audio\b[^>]*\bid="music"[^>]*>', html)
    if tag:
        new = tag.group(0)
        for k, v in attrs.items():
            new = new[:-1] if new.endswith(">") else new
            new = _set_attr(new, k, v) + ">"
        return html.replace(tag.group(0), new)
    el = ('      <audio id="music" data-timeline-role="music" ' + " ".join(f'{k}="{v}"' for k, v in attrs.items())
          + f' data-volume="{music.get("volume", 1)}"></audio>\n')
    marker = "      <!-- /media -->"
    return html.replace(marker, el + marker) if marker in html else html.replace("</body>", el + "</body>")


def _ensure_scene_slots(root: Path, html: str, scene_ids: list[str]) -> str:
    """Create a sub-composition slot and compositions/<id>.html for every beat-map scene that lacks one."""
    from .util import REPO
    w = re.search(r'data-composition-id="main"[^>]*?data-width="(\d+)"', html)
    h = re.search(r'data-composition-id="main"[^>]*?data-height="(\d+)"', html)
    W, H = (w.group(1) if w else "1080"), (h.group(1) if h else "1920")
    template = (REPO / "templates" / "composition" / "scene.html").read_text(encoding="utf-8")
    (root / "compositions").mkdir(exist_ok=True)
    for sid in scene_ids:
        if not re.fullmatch(r"[A-Za-z][\w-]*", sid):
            raise BeatmapError(f"scene id '{sid}' must start with a letter and use letters, digits, - or _")
        if f'data-scene="{sid}"' not in html:
            slot = (f'      <div id="slot-{sid}" data-scene="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
                    f'data-start="0" data-duration="1" data-track-index="1" data-width="{W}" data-height="{H}"></div>\n')
            marker = "      <!-- /scenes -->"
            html = html.replace(marker, slot + marker) if marker in html else html.replace("</body>", slot + "</body>")
        scene_file = root / "compositions" / f"{sid}.html"
        if not scene_file.is_file():
            scene_file.write_text(template.replace("{{SCENE}}", sid).replace("{{W}}", W).replace("{{H}}", H), encoding="utf-8")
    return html


def _num(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def report(resolved: dict[str, Any]) -> str:
    lines = [f"{len(resolved['scenes'])} scenes, {len(resolved['events'])} events, {len(resolved['media'])} media, "
             f"{resolved['duration_frames']} frames @ {resolved['fps']} fps"]
    for s in resolved["scenes"]:
        lines.append(f"  {s['id']:<12} frames {s['start_frame']:>5}-{s['end_frame']:<5} ({s['start_kind']})")
    for i in resolved["issues"]:
        lines.append(f"  {i['level'].upper():7} {i['code']}: {i['message']}")
    lines.append("OK" if resolved["ok"] else "FAILED")
    return "\n".join(lines)
