# Motion Studio: product spec (brief v2)

This is the original build brief (`MOTION-STUDIO-BRIEF.md`, 2026-09-28) revised after an upstream review, with the owner's decisions folded in. `AGENTS.md` is the operational contract. This file explains *why*.

## 1. Goals and non-goals

**Goals**
- Finished MP4 motion graphics (promos, openers, kinetic type, explainers, data pieces, product tours, **footage recaps**) in 9:16, 1:1, 4:5 and 16:9.
- Every cut, slam and reveal lands on a beat, downbeat, spoken word or **footage moment**, measurably: QA verifies every hit's frame.
- Creative-director planning before code; a human approves three gates (or the agent does in express or benchmark mode, and logs why).
- Output looks like our house style or a brand, not generic AI motion.
- Works with Claude Code and Codex (one `AGENTS.md`).
- **Scoped revisions from a prompt**, with frame-level proof that nothing else changed.
- **Exact data and sourced facts** for data-sensitive work.

**Non-goals**
- No text-to-video or diffusion footage.
- No Remotion (license cost at company size; one render engine only).
- **No Adobe export** (dropped from motion-engine, owner decision, 2026-09-28).
- No timeline editor UI in v1. A future editor should build on open source; note GSAP's license bars a no-code visual animation builder that competes with Webflow.

## 2. Owner decisions (2026-09-28)

| Question | Decision |
|---|---|
| SFX library provenance (ElevenLabs takes on the fork owner's paid plan) | Accepted as is |
| Client material in a public repo | The repo is public. Benchmarks are public; real clients (e.g. Billionaire Signal) and their briefs stay git-ignored or private |
| HyperFrames version | Pin the newest that passes our tests: **0.8.82** (motion-video-skill pinned 0.7.99) |
| Beat tracker | Build the best: our own analyser (tempo, beats, downbeats, kick/snare/hat, sections, drops) plus the footage's visual beats |
| Benchmarks and gates | Benchmarks measure what a build does with a fixed prompt, so a **benchmark mode** lets the agent self-approve gates |
| Repository | New repo `motion-studio`, built from what worked in motion-engine; motion-engine is marked discontinued |
| Visibility | Public |
| Adobe export | Dropped |

## 3. Sources (verified 2026-09-28)

| Source | License | Role |
|---|---|---|
| HyperFrames `0.8.82` | Apache-2.0 | Only render engine; lint, check, snapshot, preview, transcribe. A dependency, pinned in `package.json` |
| motion-video-skill `a73702b` | MIT | Vendored beat-grid, arrangement and mix-balance scripts + references. Its grid-fit idea is reused in our analyser |
| Motion Bang Bang `675b58a` (fork of Bang Motion) | MIT | Vendored concept references, anti-PPT rules, SFX library and mixer. Its `sfx-cues.mjs` already reads HyperFrames timelines (the brief's milestone 5 note was out of date) |
| iart-ai skill packs | MIT | Vendored craft skills, **excluding** `remotion-video` and `after-effects` |
| OpenMontage | AGPL-3.0 | Reference only. No code or text copied |
| motion-engine v0.68.0 | MIT | Ported: claim ledger + verifier, benchmark suite |

## 4. Architecture

- **CLI (`mstudio`, Python)** owns everything deterministic: analysis, validation, timing, sync, rendering orchestration, sound, QA and revisions. The agent never hand-edits generated files (`timing.js`, `data.js`, `reframe.js`, scene slot timing).
- **Composition** = a thin `index.html` host with one HyperFrames sub-composition per beat-map scene (HyperFrames 0.8.82 rejects nested timed structure in the root). Media and music sit at the root, and footage is never inside a timed element.
- **`studio.js` runtime**: every hit, counter, value and crop comes from generated data. `Studio.forScene(id)` converts to scene-local time.
- **Inspector (`engine/inspect.mjs`)**: headless Chrome over raw CDP. It mounts sub-compositions the way the runtime does, walks the timeline and records visible text, boxes, fonts and the hit registry. This powers copy, number, layout and beat-accuracy QA.

## 5. Pipeline and gates

Intake → **A** direction → script → audio → sources (data, facts, footage) → **B** beat map → **C** styleframes → build → verify → render → deliver → revise. Gate approvals store the artifact hash and go stale when it changes. `render` refuses to run without A and B.

Modes: `interactive` (only a human approves), `express` (one combined human approval), `benchmark` (the agent approves and logs why).

## 6. Beat understanding

`beats.json`: tempo with candidates and an octave check; steady-grid detection by per-quarter phase lock; beats with waveform attack refinement; downbeats (kick + backbeat + chroma change) with confidence; meter 4 or 3; per-beat kick/snare/hat; per-bar energy and quiet flags; sections labelled intro/build/drop/break/outro; drops; hit candidates by tier. On synthetic tracks (92-174 BPM): tempo ±0.02 BPM, median beat error about 1 ms, downbeats and drops correct. Real-track verification is part of every job: the beat editor checks the tempo and first downbeat by ear or waveform, and can pass `--bpm-hint`, `--meter` or a range.

Footage beats: `flash`, `rise`, `cut` and `motion` events per clip. A media `align` in the beat map picks the clip in-point so an event lands on a musical anchor.

**Hit hierarchy and rules:** the brief's table stays, with exact values in `skills/house-style`. Frame snapping is `frame = floor(t × fps + 0.5)`, so a hit can be up to half a frame (≤ 16.7 ms at 30 fps) off the audio. That is the definition of "on target frame". Anticipation is stored per event; hits on a scene's first frame land on the cut.

## 7. Industry practices adopted to fill the gaps

- **Loudness:** EBU R128 / platform practice of −14 LUFS integrated and ≤ −1 dBTP true peak, measured after AAC encoding. The limiter oversamples 4× and iterates.
- **Safe areas:** 9:16 keeps text out of the top 220 px and bottom 380 px (platform UI); 16:9 uses a 5% title-safe margin.
- **Reading time:** on-screen copy needs about 3 words per second, 1.2 s minimum, capped at 3 s unless overridden.
- **Conform before edit:** mixed-rate sources are converted to constant frame rate at the delivery fps before editing; clips never play at their native rate inside the timeline.
- **Upscaling:** a warning above 1.5× and a failure above 3×; framed layouts for low-resolution sources.
- **Versioning:** immutable versions (`versions/v<n>`); a revision never overwrites.
- **Revision locality:** per-frame PSNR against the previous version (≥ 42 dB counts as unchanged, allowing for GPU rasterization noise).
- **Provenance:** hashed sources for data, facts and footage, plus a credits manifest with a license for every asset.
- **Privacy:** telemetry off; no cloud or publish commands on client material; client projects are git-ignored.

## 8. Definition of done

See `AGENTS.md` §5 and `skills/qa`.

## 9. Known risks

- **HyperFrames moves fast** (0.7.99 → 0.8.82 within weeks, with lint contract changes). Pin it and upgrade deliberately with `npx hyperframes@latest upgrade --project . --check` on a branch, then re-run tests and benchmarks.
- **Inspector fidelity:** our sub-composition mount emulates the runtime. HyperFrames' own `check` plus rendered-frame review remain the backstop.
- **Beat detection on real music** varies by genre (rubato, tempo ramps, sparse drums). Variable tempo falls back to DP beats, and the beat editor must verify.
- **Small upstream projects** may go unmaintained. The vendored copies with pinned commits protect us.
- **SFX chain of title** rests on the fork owner's statement (accepted). Replace it with our own generations for clients who need it.

## 10. Roadmap

1. Run benchmarks B1-B3 on 0.1.0 and compare them with the v0.68.0 baseline.
2. A real-music validation set (5-10 licensed tracks across genres) for the beat analyser.
3. Voice-over path end to end (`words.json` → word-anchored hits, music ducking via HyperFrames volume automation).
4. Optional generated music behind our own interface (motion-video-skill's arrangement flow), without changing `beats.json`.
5. Multi-ratio delivery from one beat map (reflow layouts per ratio).
6. An editor UI built on open-source parts, outside GSAP's visual-builder restriction.
