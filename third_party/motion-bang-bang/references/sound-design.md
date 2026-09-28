# Sound Design: Effects That Land on the Motion

Narration without effects is a slide deck with a voice. But the failure mode is not "no SFX" — it is SFX placed by eyeballing a scene list, and SFX loud enough to fight the narration. This document covers the three-artifact pipeline that avoids both: a **bundle** of recordings, a **cue sheet** mined from the timeline, and a **mix** muxed onto the finished picture.

## The Pipeline

| Step | Tool | Reads | Writes |
|---|---|---|---|
| 1. Bundle exists | `scripts/elevenlabs_audio.py sfx --spec assets/sfx/library.json` | prompts in `library.json` | `assets/sfx/**/*.wav` + `manifest.json` |
| 2. Mine cues | `scripts/sfx-cues.mjs` | `window.OPENER.tl` in headless Chrome | `assets/sfx-cues.json` |
| 3. Mix | `scripts/sfx-mix.mjs` | cue sheet + rendered MP4 (+ VO) | `final-sfx.mp4`, per-family stems |

Run them in that order, after the picture is rendered. Steps 2 and 3 need only system Chrome and `ffmpeg` — nothing installed.

**Sound is a post-render decision.** The mixer copies the video stream (`-c:v copy`), so retuning audio costs zero frames and the approved picture is bit-for-bit the picture that ships. This is the opposite of the voiceover, which *is* wired into the page (`references/elevenlabs-audio.md`) because the whole timeline is measured against it. Never put `<audio>` effect tags in the composition to "hear it while building" — scrub `index.html` for picture, then mix.

## 1. The Bundle Contract

`assets/sfx/` holds one recording per **kind of motion**, not per event. Twenty takes cover a five-minute explainer. Every file obeys one contract, recorded in `assets/sfx/manifest.json`:

- **48 kHz, stereo, PCM-16 WAV** — matches the render's `adelay`/`asetrate` math exactly.
- **Peak −3 dBFS by pure gain, never a limiter.** Limiting would bake intensity into the recording; intensity must stay a mix-time parameter, so a library click and a library impact differ only by what the mixer applies.
- **Gain-staged *before* the silence trim.** The trim gate is relative to the file's own peak, so if the trim ran first, the gate would be measured on a different signal than the one being delivered — the historical bug here produced files that were provably trimmed yet still shipped wearing 69 ms of head silence.
- **Trim gate `max(peak − 45 dB, −60 dBFS)`**, sample-accurate, one shared function for trim and measurement.
- **One-shot head ≤ 15 ms** (about half a frame at 30 fps). Anything longer and a frame-exact `adelay` placement is a lie.
- **Prompts name source + surface + mic perspective and forbid musical content** (`no reverb, no music, single event`). A tonal stinger collides with any music bed added later.

### Families and their intent

| Family | Gain (dB) | Max hits/s | Duck under speech | Covers |
|---|---|---|---|---|
| `impact` | −6 | 2 | no | objects landing, slams, blocks snapping in |
| `stamp` | −9 | 2 | no | rubber stamp presses, seals |
| `whoosh` | −10 | 1.5 | yes | camera moves, objects flying through air |
| `transition` | −11 | 0.2 | no | risers into a climax — ration it to the one climax moment |
| `accent` | −12 | 1 | no | bell cling, mechanical counter tick |
| `paper` | −13 | 2 | yes | sheet flips, archive rustle, photo placed |
| `pen` | −14 | 1.5 | yes | marker scribble, chalk brush, ink line |
| `ui` | −18 | 3 | yes | soft clicks, sticker pops, toggles |
| `camera` | −19 | 20 | no | shutter clicks and film-advance mech — one per word in a staggered caption |
| `ambience` | −30 | — | no | room-tone bed, looped, sparse or absent |

Gain is relative to the normalised −3 dBFS peak, so the ordering *is* the mix: a `ui` click is 12 dB below an `impact` before either is heard.

`camera` sits at the quiet end and still gets a 20 hits/s cap, which looks contradictory until you read what it covers. A word-by-word caption at `stagger: 0.075` is 13 events per second. Every other family is capped far below that because it marks an *event*; this family marks *texture*, and a cap tuned for events would silently eat two thirds of the roll.

### Hand-generated takes

Not every take has to come from `library.json`. Files produced elsewhere (a dashboard generation, a purchase) can be dropped in as MP3/WAV — then normalise them into the contract with `--renormalize` (**no API call, no billing**) and add their records to `manifest.json` by hand: family, file, triggers, `gain_db`. Keep the source files in an `_originals/` subfolder next to the delivered WAVs so a future re-processing run has something to re-process, and remember that `SOURCES.md` and `_preview.wav` are *derived* from the manifest — regenerate both after editing it.

### Audition and repair, free of charge

`--preview _preview.wav` concatenates the entire bundle with 300 ms gaps — one file, one listen, in manifest order. `--renormalize` re-applies the current contract to the files already on disk — **no API call, no billing** — and prints duration, peak, RMS, head and warnings per file. This matters: every gate/scale decision above was reached by re-processing, not regenerating, and a generation run costs credits per requested second.

Existing files are skipped unless `--force`, so `library.json` doubles as an extend-the-library recipe: add an asset block, run the same command, and only the new rows are billed.

## 2. Mining Cues, Not Guessing Them

`scripts/sfx-cues.mjs` walks the GSAP timeline in headless Chrome and never plays it. For each tween it reads what actually moved — position, scale, opacity direction, rotation, filter — plus the tween's `data` tag, and classifies it into a family.

**Motion is mined from the finished timeline, so it cannot drift from the picture.** A hand-written cue list drifts the first time a scene is retimed.

Classification order (first match wins — the order *is* the logic, because one tween satisfies several rules):

1. **Explicit `data:"<verb>"`** on the tween, mapped through each asset's `trigger` list in `library.json`. This is the author's escape hatch — tag a tween and its sound stops being a guess.
2. **Camera rig moves** — tweens on the plain rig object have no DOM element, so travel is measured against the previous rig state → `whoosh`.
3. **Drawn strokes** (`strokeDashoffset`, `pathLength`, `drawSVG`) → `pen`: marker above 0.55 s, thin ink line below.
4. **Slams** — fading in *while* its scale changes by ≥ 0.55 → `impact`, heavy when the change reaches 1.2 or the element covers more than 160 000 px². The hit lands at `--land-at` inside the entrance, not at its start.
5. **Spin** ≥ 4° → `ui` toggle; **travel** ≥ 120 px → `whoosh` (camera take beyond 600 px, object take below).
6. **Wipes** — `clip-path`, `inset`, `width`, `scaleX` with no opacity at all → `paper` for an image, a thin `whoosh` for a rule or highlight. This rule must sit *above* "not fading means silent", or every underline in the video is muted.
7. Whatever still fades in gets `pop` (scale ≥ 0.12), then a `paper` flip/rustle for text and images, then a `ui` click.

Then three pruners, in order: a per-family rate cap (`max_hits_per_s`), a mask window (two sounds inside 60 ms read as one event, and the weaker one is dropped), and a global budget (`--max-per-s`).

**Read the tally before touching the rule table.** It prints candidates → kept, per-family counts, and *why* each cue was dropped (`looping`, `unclassified`, `beyond`, `density`, `masked`, `budget`). `--why` lists the prop signatures that stayed silent, most frequent first — that list is the queue for the next rule or the next `data` tag.

Validated outcome on a 285 s explainer: **824 tweens → 422 candidates → 219 cues** (0.77 cue/s), split `whoosh` 120 / `ui` 43 / `impact` 38 / `paper` 18 — and the 19 camera whooshes inside that matched the 19 camera cuts counted by hand on the delivered cut.

### `--word-clicks`: one sound per word, not per caption

All three pruners assume a cue is an *event*. A staggered reveal breaks that assumption: `say(".line .w", at, {stagger: .075})` is **one tween** whose `child.duration()` already contains the whole spread, and whose listener count is the number of words. Mining it as one event gives a single click for a sentence that visibly types itself out word by word.

With `--word-clicks`, a tween that fades text in, has a stagger, and targets between 2 and 40 elements is unrolled into one cue per element at `at + baseDuration·land-at + i·stagger`, each tagged `verb:"word"` and marked as texture so the mask window and the global budget skip it. Two details carry the whole feature:

- **Per-element duration comes from `vars.duration`, not `child.duration()`** — the latter is the roll's total, and using it drags every click a few hundred milliseconds late off its word.
- **Words fading *out* stay excluded.** `unsay()` staggers the same elements away, and a click on each disappearing word reads as a machine, not a camera.

Word takes rotate through the pool instead of repeating one file: every asset whose `trigger` list contains `word` is used in turn, which is what keeps a 90-click roll from sounding like a stuck shutter. Words inside a highlight span count as one unit (the DOM split, not the count, is what the viewer sees), so a caption's click count can be lower than its word count.

**Texture must not spend the event budget.** The mask window and the global budget exist to protect events from each other, so a texture cue is exempt from both — and it must also stay invisible to them. Measuring the gap against "the last cue kept of any kind" instead of "the last *event*" let the clicks eat the 0.625 s the following whoosh needed: the first version of this feature printed 275 cues and had silently dropped 12 whooshes and one impact to a caption. The tally therefore splits events from texture, and the event rate is what gets compared against the same project mined without the flag.

Validated outcome, same 285 s explainer re-mined with the flag: **219 → 288 cues**, `whoosh` 120 / `camera` 91 / `ui` 40 / `impact` 37 — 1.009/s total but **0.764 event/s against 0.767/s without the flag**. 22 text cues changed family (18 `paper`, 3 `ui`, 1 `impact` became clicks) and nothing else moved. The 91 clicks are 21 unrolled rolls covering every caption (70 clicks, every roll verified complete) plus 21 single-block text reveals.

Without the flag nothing changes — the mode is opt-in and the default sheet stays byte-identical.


### Density targets

| Cue/s | Reads as |
|---|---|
| 0.3–0.5 | punctuation only; safe for talking-head or minimal pieces |
| 0.7–0.9 | designed; the default for explainers and promos |
| $> 1.2$ | wasps' nest; the ear stops resolving individual events |

These numbers are **event** density. Texture (a per-word click roll) sits on top of them and does not count: it is a surface, like room tone, and the ear tracks it as one object. A mix at 0.76 event/s plus 0.25 texture/s reads as designed; 1.01/s of events alone would not.

Raise `--max-per-s` only after lowering family gains — loudness, not count, is what makes dense mixes unlistenable.

## 3. Placing and Mixing

`scripts/sfx-mix.mjs` builds **one stereo stem per family** first (stage 1), then mixes the stems against the voice (stage 2).

Stems are the whole design decision. A single 219-input `amix` cannot even be built: every cue needs its own branch, a take used twice needs the pad split, and `asplit` caps at 64 outputs — while a per-family WAV lets a human listen to "all the whooshes" alone and judge them without the picture. Per family, each cue becomes `asetrate` → `volume` → frame-snapped `adelay`; the family's branches are summed in chunks of 40, and the chunks are summed.

Three per-cue touches keep a small bundle from sounding like a small bundle:

- **Frame snap**: `adelay` is computed from the sheet's **`frame`** field, converted to integer milliseconds (`round(frame/fps·1000)`), so a cue lands on a picture frame, never between two. Do not re-derive the frame from `t`: `t` is stored to 3 decimals, so a value ending in `.x5` multiplied by 30 lands exactly on `.5`, and `Math.round` tips those cues one frame late. The seed for the pitch spread is read from the same `frame`, so the two must never disagree.
- **Gain from strength**: `gain_db + (strength − 0.5) · 6`, so a hard slam sits up to 6 dB above a soft one from the same take.
- **Pitch spread**: ±2.5‰ detune seeded from the *frame number*, not the run order, so the same take reused twelve times is never a machine gun, and two runs give identical audio.

### Ducking

The voice is split (`asplit=2`): one copy goes to the output, the other drives a `sidechaincompress` on the ducked families only. Threshold 0.02, attack 25 ms, release 340 ms, `makeup=1` — measured on the delivered mix: **−12.8 dB of ducking under dense narration, 0.4 dB in a narration gap**, on the same stem. The four families marked `duck_under_speech: true` (`whoosh`, `paper`, `pen`, `ui`) are exactly the sustained-texture ones; the percussive families stay unducked on purpose, because a ducked slam is not a slam.

Where narration runs nearly the whole runtime (an explainer with 20 paragraphs does), expect most audible effects to live in the 0.4–1.4 s breaths between sentences. That is not a defect — camera moves already land there, which is why the whoosh count is highest in gaps.

### Ceiling and loudness

The summed bus goes through `apad` → `alimiter` at `--ceiling` (default −1.0 dBFS) → AAC, and is cut to the video's duration with `-t`. Then the script measures the **delivered file**, because that is what ships: FFmpeg prints two `Summary:` blocks per run and only the last is the real one, and `true peak` needs `peak=true` to appear at all.

**AAC adds roughly 0.5 dB of inter-sample overshoot above the PCM the limiter held.** The validated mix limited at −1.0 dBFS and measured −0.4 dBFS true peak on the decoded file. That is normal and is not clipping; the number worth alarming on is proximity to 0 dBFS.

Band worth aiming for, all measured on a real mix: integrated within about 1.5 dB of the VO-only file (−15.1 → −14.1 LUFS), LRA under 3 LU, true peak below −0.1 dBFS, zero samples at full scale.

## 4. Verification — Numbers, Not Ears

The agent cannot listen. Every claim above is checked with a measurement, and these are the checks:

- [ ] **Picture untouched**: extract the raw video payload from both files and compare hashes — `ffmpeg -i F -map 0:v -c copy -f h264 - | md5sum`. Identical means the approved cut shipped.
- [ ] **Duration and frame count unchanged** (`ffprobe -count_frames`), and the output is a *new* filename; the approved file is never overwritten.
- [ ] **Loudness**: `ffmpeg -i OUT -map 0:a -af ebur128=peak=true -f null -` → integrated, LRA, true peak.
- [ ] **Ducking engaged**: measure one stem over a narration-dense window and a gap window, raw and through the sidechain. The gap must be near-unity and the speech window several dB down.
- [ ] **Placement is honest**: run `silencedetect` on a short-decay stem and match event onsets against the cue sheet's `frame / fps`. Median offset must be 0 and maximum under one frame (validated: median 0.0000 s, max 0.017 s against a 0.0333 s frame). An RMS-envelope rise detector agrees with `silencedetect` to the millisecond and additionally survives overlapping cues, which is what a per-word roll is — but run the same detector on the **asset file alone** before believing an outlier: a shutter recording whose energy peak sits 16–21 ms in reports a "late" cue even when `adelay` is exact. Offsets at or above one frame are never the detector's fault; they are a placement bug.
- [ ] **Nothing clipped**: true peak below −0.1 dBFS.
- [ ] **Listen once at the end**: a mix can pass every number above and still be wrong. `--stems sfx-stems` leaves per-family WAVs for exactly this.

## 5. Licensing

Generated audio is a licensing decision, not a technical one, and it belongs to the user:

- ElevenLabs' terms assign ownership of output to the user, and permit using it outside the service — that is what makes bundling possible.
- **Free tiers are non-commercial.** A bundle shipped inside a skill and used in client work needs a paid plan; record the plan tier in `manifest.json` alongside the generation date.
- The Sound Effects product has a separate sublicensing term with an opt-out in the dashboard. Changing it, and changing the plan, is the user's action — the tooling never touches account settings.
- `assets/sfx/SOURCES.md` carries the per-file provenance (prompt, duration, date) so any audit can be answered without re-deriving anything.

## Traps Found the Hard Way

Each of these produced a wrong result that looked correct:

- **`silenceremove` is window-average based.** On soft attacks it leaves tens of milliseconds of latency — a file reported "trimmed" and still missed the frame. Use a sample-accurate cutter (`sfx_cut_silence`).
- **Trim gate applied after gain** measures a different signal than the one delivered. Stage the gain first, then trim, and share one gate function.
- **A loop seam judged over 10 ms** invents a problem: loudness integrates over ~150 ms. The paper bed measured a "+10 dB seam" that was 4 dB of ordinary level variation.
- **`.from()` tweens keep their opening state in `vars.startAt`**, not `vars`. Missing it silenced every slam.
- **A staggered reveal is one tween with the spread already inside its duration.** Reading `child.duration()` as the per-element ramp unrolled a 4-word caption into clicks 0.3 s apart from the words they belonged to.
- **An exempt cue is not automatically an invisible one.** Making texture skip the pruners while still updating "the last kept time" let 91 quiet clicks spend the event budget and cost 12 whooshes and an impact — the tally grew, which is exactly what a loss looks like if you only count what you added.
- **Two roundings of the same time are not the same number.** The sheet stores `t` to 3 decimals *and* `frame`; deriving the frame from `t` again moved `t = 15.55` (frame 466) to frame 467 — one frame late, and invisible in every tally because the cue count never changed. Carry `frame` through and read it once.
- **A bare `{v}` proxy is not a counter** — that pattern is also how blur ramps are driven, and naming it as a counter produced 45 phantom ticks.
- **`-ss` before `-i` applies to one input only.** Slicing a stem and a voice to the same window needs `-ss` before *each* `-i`, or the two halves of the test read different moments.
- **`-af` cannot be attached to a stream that came out of `-filter_complex`** ("Simple and complex filtering cannot be used together"). Put the detector inside the graph.
- **`String.matchAll` needs a global regex**, and FFmpeg prints its `Summary:` more than once — parse the last occurrence, and treat a failed parse as a loud warning rather than an empty field.
