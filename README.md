# Motion Studio

**Turns Claude Code or Codex into a motion-graphics studio.** Pure motion design in HTML + GSAP (rendered by [HyperFrames](https://github.com/heygen-com/hyperframes)), cut on the beat, planned like a creative director, and checked by a QA gate before anyone sees it.

**v0.3.0** · [changelog](CHANGELOG.md) · [agent contract](AGENTS.md) · [spec](docs/spec.md) · [benchmarks](benchmarks/README.md) · [results](benchmarks/results/RESULTS.md) · successor to the discontinued [motion-engine](https://github.com/Navidbyti/motion-engine)

## Use it

Paste this into a new Claude Code, Codex or Antigravity chat:

> Set up Motion Studio from https://github.com/Navidbyti/motion-studio. Clone it into a fresh folder, then follow the "Onboarding" steps in its AGENTS.md exactly: install and check everything, ask me whether I want Gemini TTS voice-over (and set up my API key locally if I do), then ask me what video I need.

The agent installs everything and asks whether you want AI voice-over. If you do, it opens a local file for your Gemini API key; the key never goes through the chat. Then it asks what to make: describe the video and attach your material (script, logo, music, data, footage).

The agent does the files, the commands, rendering and QA. You approve three things:

1. **A: creative direction.** Three concepts, one recommendation, palette, type and the special moment.
2. **B: beat map.** Every cut, slam and reveal tied to a downbeat, snare, drop, spoken word or footage moment.
3. **C: styleframes.** Stills of the key moments before the full build.

Say "don't ask me anything" and it runs in express or benchmark mode and approves its own gates, logging why. For a change afterwards, ask for it ("make the counter slower in the Moon scene"). The agent revises that scene only and proves every other frame is unchanged.

## What makes it different

- **It actually understands the beat.** `mstudio beats` finds the tempo, every beat (to about 1 ms on test tracks), downbeats, kick, snare and hats, bar energy, quiet bars, and sections: intro, build, drop, break and outro. `mstudio footage analyze` finds the *video's* own beats (flashes, cuts, motion peaks), so the rocket's ignition flash can land exactly on a downbeat.
- **Timing is data, not typing.** A beat map (`beatmap.json`) snaps every event to a frame. The composition reads it through `Studio.hit()`, which lands each motion's impact on its frame. QA proves every hit lands.
- **Numbers and facts are traceable.** Every on-screen number comes from a hashed data binding or a quoted source. QA fails "orphan" numbers, sign errors and counters that stop on the wrong value.
- **Real footage is handled like an editor would.** It conforms mixed frame rates, reframes landscape to vertical with keyframed crops, and refuses crops that show bars, burn-ins or over-upscaled pixels. Natural sound goes under the music.
- **Voice-over with Gemini 3.8 TTS.** Per-scene narration from a script, with 30 voices and 130+ languages including Persian. Each line starts on a beat, and hits can land on spoken words. Your API key is pasted into a local file that opens for you; it never goes through the chat or the repo.
- **Its own sound for every video.** Original music per project (Google Lyria, same Gemini key) is cut to length on bar lines. Unlimited rights-free sound effects come from a built-in synthesizer (13 kinds, seeded, tunable), plus variations and optional ElevenLabs generation. Big hits get layered sounds, repeats are varied automatically, and QA flags recycled beds or repetitive effects.
- **Sound is post-render.** SFX sit on the beat map's hits and loudness is normalized to −14 LUFS / ≤ −1 dBTP, without re-rendering a frame.
- **A definition of done.** HyperFrames lint, layout and contrast, exact copy, reading time, safe areas per platform, text size, beat accuracy, spec, loudness, black and frozen frames, credits, and revision locality. `mstudio qa` must pass before you see a render.

## Example

[`examples/hello-beat`](examples/hello-beat) is a 16-second kinetic-type proof on a synthetic 120 BPM track. Every hit lands on its beat frame, QA passes 11 checks, and a one-scene revision changes only that scene. Preview: [`examples/hello-beat/preview.mp4`](examples/hello-beat/preview.mp4).

```bash
mstudio refresh examples/hello-beat && mstudio render examples/hello-beat && mstudio qa examples/hello-beat
```

## For developers

```bash
git clone https://github.com/Navidbyti/motion-studio.git && cd motion-studio
npm install                                  # HyperFrames 0.8.82 + GSAP 3.14.2 (pinned)
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"    # macOS/Linux: .venv/bin/pip
mstudio doctor
python -m pytest -q                          # fast tests; `-m slow` for the end-to-end render
```

Requirements: Node.js 22+, Python 3.11+, FFmpeg/ffprobe on PATH, and Chrome (HyperFrames' headless shell or system Chrome). Optional: a Gemini API key for voice-over.

| Command | Does |
|---|---|
| `mstudio new <slug> --ratio 9:16 --duration 30 --mode interactive` | creates `projects/<slug>/` (git-ignored) |
| `mstudio status <slug>` | current stage, gates, next step |
| `mstudio beats <slug> audio/track.wav` | music analysis → `audio/beats.json` |
| `mstudio keys setup gemini --wait 300` | opens a local file for the Gemini API key, then validates it (never via chat) |
| `mstudio tts <slug>` · `mstudio voices` | Gemini 3.8 TTS voice-over from `vo.md` → `audio/vo/<scene>.wav` |
| `mstudio music <slug> gen --prompt …` · `fit <file>` | original music with Lyria / edit a track to length on bar lines |
| `mstudio sfx make <slug> <kind>` · `vary` · `gen` · `sfx kinds` | project sound effects: synth (CC0), variations, ElevenLabs |
| `mstudio footage <slug> analyze\|conform\|reframe` | footage analysis, CFR conform, crop validation |
| `mstudio data <slug>` / `mstudio facts <slug>` | bind numbers / verify the claim ledger |
| `mstudio beatmap <slug> apply` | resolve and validate the beat map, generate scene slots, sync timing |
| `mstudio gate <slug> A\|B\|C --by human\|agent` | record an approval (hash-pinned; goes stale if the artifact changes) |
| `mstudio styleframes <slug> --events a,b,c` | stills of key moments |
| `mstudio render <slug>` / `mstudio sound <slug>` | picture + SFX + loudness → `renders/master.mp4` / re-mix only |
| `mstudio qa <slug>` | the definition-of-done gate → `renders/qa/report.md` |
| `mstudio revise <slug> start --scene s3` · `verify` | scoped revision with frame-level proof |
| `mstudio deliver <slug>` | final file, poster and manifest |

Layout: `src/motion_studio/` (CLI), `engine/inspect.mjs` (timeline and DOM inspector), `templates/composition/` (host, scene template, `studio.js`, house tokens), `skills/` (director, beat-editor, builder, data-viz, footage, qa, revise, house-style), `third_party/` (vendored upstreams), `benchmarks/`, `examples/`.

## Credits and licenses

MIT. Built on HyperFrames (Apache-2.0) and GSAP (Standard No-Charge License). It vendors motion-video-skill, Motion Bang Bang / Bang Motion and iart-ai skill packs (all MIT), and the OFL fonts Inter, JetBrains Mono and Vazirmatn. OpenMontage (AGPL-3.0) was read for ideas only. Details in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
