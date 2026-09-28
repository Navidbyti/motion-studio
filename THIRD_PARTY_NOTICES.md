# Third-party notices

Motion Studio is MIT-licensed. It depends on, vendors or references the projects below. Each vendored copy sits in `third_party/<name>/` **unchanged**, with its original LICENSE file. Our own adaptations live under `src/`, `engine/` and `skills/` and credit their origin.

| Name | URL | Commit / version | License | How we use it | Changes |
|---|---|---|---|---|---|
| HyperFrames | https://github.com/heygen-com/hyperframes | npm `hyperframes@0.8.82` (repo `34a6674`) | Apache-2.0 | **Dependency, not vendored.** The only render engine (HTML + GSAP → MP4), plus lint, check, snapshot, preview, transcribe. Pinned in `package.json`. | none |
| GSAP | https://gsap.com | npm `gsap@3.14.2` | GSAP Standard "No Charge" License (not OSS) | Animation runtime inside compositions. Installed from npm and copied into each project's `vendor/`; **not committed** to this repo. Use in a no-code visual animation builder that competes with Webflow is not allowed. Motion Studio is agent-driven code generation, which the license allows. | none |
| motion-video-skill | https://github.com/bestagentkits/motion-video-skill | `a73702b` | MIT | Vendored: `scripts/fit-beat-grid.py`, `verify-arrangement.py`, `measure-mix-balance.py` + tests; references `audio-and-beat-sync.md`, `composition-contract.md`. Grid-fit idea reused in `src/motion_studio/beats.py` (`grid_search`); mix-balance and loudness targets adopted. | none to vendored files |
| Motion Bang Bang (fork of Bang Motion) | https://github.com/lowfatgeek/motion-graphics-skill | `675b58a` | MIT (© lowfatgeek, © Bang Tutorial) | Vendored: `references/*` (concept menu, anti-PPT rules, techniques, sound design), `scripts/sfx-cues.mjs`, `sfx-mix.mjs`, `snap.mjs`, `assets/sfx/**` (SFX library + `library.json` mix table). The SFX library drives `mstudio sound`. The Chrome/CDP approach of `sfx-cues.mjs` is reused in `engine/inspect.mjs`. | none to vendored files |
| Bang Motion (upstream) | https://github.com/bangtutorial/bang-motion | as merged into the fork above | MIT (© Bang Tutorial) | Credited through the fork. | n/a |
| iart-ai kinetic-typography-skills | https://github.com/iart-ai/kinetic-typography-skills | `fccc94b` | MIT | Vendored: `kinetic-typography` skill (reveal recipes). We use only its CSS/GSAP guidance. | none |
| iart-ai motion-design-skills | https://github.com/iart-ai/motion-design-skills | `3c129f7` | MIT | Vendored: animation-principles, beat-sync-editing, color-motion, logo-animation, motion-art-direction, motion-background, shot-composition. Excluded: `remotion-video`, `after-effects`. | none |
| Inter, JetBrains Mono, Vazirmatn | https://github.com/google/fonts (`23e54b5`) | variable TTFs | SIL OFL 1.1 (license files in `assets/fonts/`) | House fonts, copied into each project | none |
| motion-engine | https://github.com/Navidbyti/motion-engine | `5b45ac2` (v0.68.0) | MIT | Predecessor. `src/motion_studio/claims.py` and its schema are ported from it (with an `onScreen` field added); the benchmark suite came from it. | ported, adapted |

## Reference only (no code or text copied)

| Name | URL | License | Why it is not vendored |
|---|---|---|---|
| OpenMontage | https://github.com/calesthio/OpenMontage | AGPL-3.0 | Read for the stage-gate production idea only. Copying AGPL files would put this whole repository under AGPL, and serving it over a network would oblige us to publish all source. Our orchestrator (`AGENTS.md`, `src/motion_studio/project.py`) is written independently. |

## SFX library provenance

`third_party/motion-bang-bang/assets/sfx/SOURCES.md` documents it: every sound was generated with ElevenLabs sound generation on a paid (commercial) plan by the fork's owner, who states that redistribution inside the skill is permitted. The project owner reviewed this on 2026-09-28 and accepted it. Replace the pack with your own generations if a client requires chain-of-title you control.

## Our own assets

- `benchmarks/shared/audio/*.wav` and `tests/synth.py` output: synthesized from code, CC0.
- Benchmark inputs (NASA/NOAA data, NASA footage, GPS.gov and NASA page snapshots): U.S. government works in the public domain. See each benchmark's `SOURCES.md`.
