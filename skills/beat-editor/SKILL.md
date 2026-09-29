---
name: beat-editor
description: Motion Studio stages 3-4. Analyses the music (and voice-over, and the footage's own visual beats) and authors beatmap.json, the timing contract every scene, hit and clip in-point is snapped to (gate B). Use whenever timing, pacing, music or cut points change.
---

# Beat editor (stages 3-4)

You decide **when**. Nothing moves without a reason you can name: a downbeat, a snare, a drop, a spoken word or a moment in the footage.

## 3. Understand the audio (and the footage)

```bash
mstudio beats <slug> audio/<track>.wav        # -> audio/beats.json + a summary
mstudio words <slug> audio/vo.wav             # only with a voice-over -> audio/words.json
mstudio footage <slug> analyze                # only with footage -> visual events per clip
```

Read the summary before planning: BPM, whether the tempo is steady, meter, first downbeat and its confidence, sections (intro, build, drop, break, outro) and drops. `beats.json` also gives per-beat `kick`, `snare`, `hat`, `energy_db`, per-bar energy and `quiet` bars, plus a ranked `hits` list mapped to the house tiers.

**Check that it is right.** If the downbeat confidence is under 0.5 or the tempo candidates disagree, listen to the track (or inspect the waveform) and re-run with `--bpm-hint`, `--meter` or `--min-bpm/--max-bpm`. Half and double tempo are the usual errors. Log what you did.

Footage analysis lists events per clip: `flash` (ignition, strobe, lights), `rise` (a sustained brightening), `cut` (hard cuts inside the clip) and `motion` (camera or action peaks). These are the video's own beats. Align them to music with `align` (below).

## 4. Author `beatmap.json`

```json
{
  "fps": 30, "duration": 30,
  "music": {"file": "audio/music.wav", "beats": "audio/beats.json", "start_at": 0, "offset": 0, "volume": 0.9},
  "footage": "footage/footage.json",
  "rules": {"max_big_hits_per_bar": 1, "auto_sfx": true},
  "scenes": [
    {"id": "hook", "purpose": "hook", "start": {"downbeat": 0}, "end": {"downbeat": 2}, "events": [
      {"id": "hook.title", "tier": "big", "kind": "slam", "at": {"downbeat": 0}},
      {"id": "hook.sub", "tier": "entrance", "at": {"beat": 2}},
      {"id": "hook.hold", "tier": "hold", "at": {"beat": 4}, "until": {"downbeat": 2}}
    ]},
    {"id": "launch", "purpose": "the launch", "start": {"downbeat": 2}, "overlap_frames": 6,
     "media": [{"id": "v02", "file": "footage/conformed/02_ignition_closeup.mp4", "clip": "02_ignition_closeup",
                "align": {"visual": "02_ignition_closeup:flash:1", "to": {"downbeat": 3}}}],
     "events": [{"id": "launch.cut", "tier": "scene", "at": {"downbeat": 2}},
                {"id": "launch.flash", "tier": "big", "at": {"downbeat": 3}, "sfx": "impact"}]}
  ]
}
```

- **Anchors:** `downbeat n`, `beat n` (use `plus_beats: 0.5` for the "and"), `bar n` + `beat k`, `snare n`, `kick n`, `drop n`, `section n`, `word "launch"` (+ `occurrence`), `time` (only with `"free": true` and a reason in `note`). Counts start at the music in-point (`music.start_at`). `music.offset` is where that point plays in the video.
- **Scenes** start on downbeats, drops or words, and each must open with a `scene` or `big` hit on its first frame. `overlap_frames` lets a transition begin before the cut.
- **Tiers** follow the house hit scale. There is at most one `big` per bar. Use `hold` events (with `until`) for quiet bars, so the builder adds drift instead of new motion.
- **Media:** clips play at the root. `in` sets a fixed in-point. `align` picks the in-point so a footage event (for example the ignition flash) lands exactly on a musical anchor. That is how a cut becomes "on the beat of the video".
- **Sound effects:** give big moments project-made, layered sounds (`"sfx": ["file:audio/sfx/slam.wav", "file:audio/sfx/rise.wav"]`) from `mstudio sfx`; see `skills/sound-design`. With `auto_sfx` every remaining tier gets a matching family from the stock library (fallback only). Override per event with `"sfx": "impact" | "whoosh" | "none" | "file:audio/sfx/x.wav"` and `"sfx_gain_db"`. Benchmarks use `file:` with the shared pack.
- **Pacing:** think in bars. Give each scene at least 2 beats (the validator warns) and let quiet bars breathe. Take the scene count from the script and music, not a quota.

`mstudio beatmap <slug> apply` resolves every anchor to a frame, validates the rules (off-grid, no opening hit, too many big hits, overlaps, length, impossible alignments), writes `beatmap.resolved.json` + `timing.js`, creates `compositions/<scene>.html` stubs and times the scene slots, media and music in `index.html`. Fix everything it reports. Then show the scene table (interactive) and `mstudio gate <slug> B --by …`.

## Checklist before gate B

- [ ] The tempo and first downbeat were verified by ear or waveform, not just trusted.
- [ ] Every scene opens on a downbeat, drop or word with a hit on its first frame.
- [ ] The special moment from the style brief sits on a drop or section change.
- [ ] No bar has more than one big hit, and quiet bars are holds.
- [ ] Each footage clip's key moment is aligned to a musical anchor, or its `in` point is justified in `decisions.md`.
- [ ] The total length equals the brief, and the music in-point and fades make sense (`volume` and `offset`).
