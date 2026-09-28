# Changelog

## 0.2.0 (2026-09-28): Gemini TTS voice-over

- **Local API keys** (`mstudio keys setup|check|status|remove`). `setup gemini` creates `~/.motion-studio/secrets/gemini_api_key.txt`, outside the repo and user-only on POSIX, and opens it in Notepad or the default editor for the user to paste into. `--wait N` waits for the save and validates it with a free models-list call. `--prompt` takes hidden terminal input instead. `GEMINI_API_KEY` overrides the file. Keys are masked in all output and scrubbed from API errors. Agents are told never to ask for keys in chat.
- **Gemini 3.8 TTS** (`mstudio tts`, `mstudio voices`): Interactions API (`gemini-3.8-flash-tts`, or `--model lite` for `gemini-3.8-flash-lite-tts`). A `vo.md` script with per-scene `## id` segments and `> voice:` / `> style:` directions; inline vocal tags pass through. Output is `audio/vo/<id>.wav` (48 kHz, −16 LUFS), a `vo.json` manifest with a text hash per segment, and an automatic credits entry. Transient errors are retried.
- **Voice-over in the beat map**: a `voiceover` list places each segment on a musical anchor, and `{"word": …, "segment": id}` anchors hit spoken words. The validator catches overlapping segments, segments running past the end and missing files. `apply` writes the `<audio data-vo>` elements.
- `mstudio words` writes per-segment `audio/vo/<id>.words.json`.
- **Privacy fix**: HyperFrames child processes never receive Gemini, HeyGen or ElevenLabs keys. HyperFrames' `snapshot` otherwise sends frames to Gemini automatically when a key is present.
- New skill: `skills/voiceover`. `brief.json` gets voice-over defaults, and `mstudio doctor` shows key status (optional).

## 0.1.0 (2026-09-28): first build

Motion Studio replaces [motion-engine](https://github.com/Navidbyti/motion-engine) (v0.68.0, now discontinued). It is rebuilt around HyperFrames (HTML + GSAP) as the only render engine, with a creative-director planning layer and beat-accurate editing.

**Pipeline and contract**
- `AGENTS.md` (+ `CLAUDE.md` pointer): one fixed, resumable pipeline (intake → direction → script → audio → beat map → styleframes → build → verify → render → deliver → revise) with gates A/B/C, three modes (interactive, express, benchmark), four roles, a model policy, and privacy and licensing rules.
- Eight stage skills in `skills/`: director, beat-editor, builder, data-viz, footage, qa, revise, house-style.
- `mstudio` CLI: `doctor new status gate decide beats words beatmap data facts footage copy styleframes preview render sound qa revise deliver refresh`.

**Beat understanding** (`mstudio beats`)
- Tempo (autocorrelation with a log-normal prior and an octave check), a constant-grid fit with a per-quarter phase-stability test, DP beat tracking for variable tempo, and attack refinement on a 2 ms envelope. Synthetic tests (92-174 BPM): tempo within ±0.02 BPM, median beat error about 1 ms.
- Downbeats from kick, backbeat and chroma change; per-beat kick/snare/hat (two-stage Otsu); bar energy and quiet bars; sections (intro, build, drop, break, outro) from Foote novelty plus energy jumps; hit candidates mapped to the house hit hierarchy.
- The footage's own beat: flash, rise, cut and motion events per clip, alignable to musical anchors.

**Beat map** (`mstudio beatmap`)
- Anchors: downbeat, beat (+ fractional), bar/beat, snare, kick, drop, section, spoken word, free time (flagged); media `align` puts a footage event exactly on a musical anchor.
- Rules: off-grid, no opening hit, contiguous scenes, one big hit per bar, busy bars, events outside their scene, impossible alignments, length mismatch.
- `apply` generates the scene sub-composition slots and files, and writes every `data-start` / `data-duration` / `data-media-start` plus the music element, so HTML timing cannot drift.

**Composition runtime** (`templates/composition`)
- A thin `index.html` host plus one HyperFrames sub-composition per scene (HyperFrames 0.8.82 lint contract).
- `studio.js`: `Studio.forScene(id).hit/after/drift/counter`, `Studio.host.reframe`, `Studio.fmt/series`. Hits land on the impact frame, or on the cut when there is no room to anticipate.
- House tokens (`house.css`) with OFL fonts shipped locally; GSAP served from `vendor/`.

**Data, facts, footage**
- `data/bindings.json` → `data.js` with hashed sources; a "no orphan numbers" check (signs, grouping, Persian digits).
- A claim ledger ported from motion-engine, with `onScreen` links.
- Footage analysis (bar detection robust to dark footage), CFR conform, and reframe validation (aspect, picture area, avoid boxes such as burn-ins, upscale limits, framed layouts).

**Sound and QA**
- SFX cues from beat-map tiers using the Motion Bang Bang library (family gains, density limits, peak-aligned whooshes). Static-gain loudness to −14 LUFS with an oversampled limiter iterated to ≤ −1 dBTP after AAC. Revisions can keep the previous gain.
- `mstudio qa`: HyperFrames check, JS errors, exact copy and reading time, number provenance, facts, text size, safe area per ratio, beat accuracy (every hit on its frame), spec, loudness, black/frozen frames, contact sheet, credits, and revision locality (per-frame PSNR against the frozen version).

**Other**
- Benchmark suite v1 moved over unchanged (inputs hash-identical), with the v0.68.0 baseline B1 result.
- `examples/hello-beat`: a 16 s beat-synced kinetic-type proof. Every hit lands on its frame, and QA passes.
- Tests: 17 fast + 1 slow end-to-end (render → QA → revision verify).
