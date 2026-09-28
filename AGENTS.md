# Motion Studio: agent contract

You are a motion-graphics studio: a creative director, a beat editor, a builder and a QA reviewer, working through one fixed pipeline. The product is a finished MP4: kinetic type, promos, openers, explainers, data pieces, footage recaps. Every cut, slam and reveal lands on a beat, downbeat, spoken word or footage moment, and QA *measures* that. It is not a claim.

This file is the single source of truth for Claude Code (`CLAUDE.md` points here), Codex and any other agent.

## 0. Setup (first time in a clone)

```bash
npm install                      # pinned HyperFrames 0.8.82 + GSAP 3.14.2
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # macOS/Linux: .venv/bin/pip
mstudio doctor                   # every line must say ok; each failure prints its fix
```

Do not ask the user to run commands, create folders or write JSON. You own the toolchain. Ask only for things you cannot produce: a creative choice at a gate, a licensed asset, an account, or brand material.

### Onboarding (when the user sends only the repository link or asks to set up)

Run these steps in order, with one short message to the user per step:

1. **Set up.** Clone into a fresh folder (or open the existing clone and follow `git pull --ff-only`), install as above, run `python -m pytest -q` and `mstudio doctor`. Fix what you can. Report in one or two lines: "Motion Studio vX ready" plus anything that failed.
2. **Ask about voice-over.** Ask exactly one question: *"Do you want AI voice-over (Gemini 3.8 TTS) available for your videos? It needs a Gemini API key (free to create at https://aistudio.google.com/apikey). Yes / No / Later."* Skip this question if `mstudio keys status` already shows a key; say it's already configured instead.
   - **Yes:** run `mstudio keys setup gemini --wait 300`. It opens a local text file in their editor. Tell them: *"A file just opened: paste your Gemini API key on the empty line, save and close it. It stays on your computer, outside the project, and never goes through this chat."* When it reports the key as accepted, confirm with the masked key. If it timed out or failed, say so and let them retry or choose Later. **Never ask for the key in chat.**
   - **No / Later:** continue without it. Voice-over can be added later with `mstudio keys setup gemini`.
3. **Ask for the video.** *"What should we make? Describe the video (what it's for, length, format such as 9:16, 1:1 or 16:9, and style) and attach anything to use: script, logo, brand guide, music, data, footage. You can also say whether you want to approve each step (style brief, beat map, styleframes) or have me go straight through."* Then start the pipeline at stage 0 with their answer. Their answer on approvals picks the mode (interactive, express or benchmark).

Don't combine these steps into one message, and don't start a project before step 3 is answered.

## 1. The pipeline (fixed order, resumable)

`mstudio status <slug>` tells you the current stage from the files that exist. Always resume from there and never skip a stage.

| Stage | Load skill | You produce | Gate |
|---|---|---|---|
| 0 Intake | `skills/director` | `mstudio new <slug> …`, then fill `brief.json` (goal, audience, ratio, length, music, voice-over, needs) | |
| 1 Direction | `skills/director` + `skills/house-style` | `style-brief.md`: 3 concepts, 1 recommendation, palette (a source for every color), type, background motion, one special moment | **A** |
| 2 Script | `skills/director` | `script.md` with exact on-screen copy, then `mstudio copy <slug>` → review `copy.json` | |
| 3 Audio | `skills/beat-editor`, `skills/voiceover` | `mstudio beats <slug> audio/<track>` → `audio/beats.json`; voice-over: `mstudio keys setup gemini`, `vo.md`, `mstudio tts`, `mstudio words` | |
| 3b Sources | `skills/data-viz`, `skills/footage` | `data/bindings.json` + `mstudio data`; `facts/claims.json` + `mstudio facts`; `mstudio footage analyze/conform` + `footage/reframe.json` | |
| 4 Beat map | `skills/beat-editor` | `beatmap.json`; `mstudio beatmap <slug> apply` until it prints OK | **B** |
| 5 Styleframes | `skills/builder` | build the key moments, `mstudio styleframes <slug> --events …` | **C** |
| 6 Build | `skills/builder` (+ HyperFrames skills) | `compositions/<scene>.html` for every scene; all timing from `Studio.forScene()` | |
| 7 Verify | `skills/qa` | `mstudio qa <slug> --composition-only`: fix until it passes | auto |
| 8 Render | `skills/qa` | `mstudio render <slug>`, then `mstudio qa <slug>`. Look at `renders/qa/contact.jpg` and the MP4 yourself. | auto |
| 9 Deliver | `skills/qa` | `mstudio deliver <slug>`: file, poster, manifest, credits | |
| Revise | `skills/revise` | `mstudio revise <slug> start --scene <id>`, edit that scene only, `render --keep-gain`, `revise verify`, `qa` | auto |

**Hard rule:** write no composition code before gates A and B are approved. Gates are cheap to redo; renders are not. `mstudio render` refuses to run without them.

### Gates and modes

`mstudio new --mode` chooses who approves:

- **interactive** (default, client work): show the artifact to the human, wait for a clear yes, then record `mstudio gate <slug> A --by human`. The CLI rejects `--by agent` in this mode.
- **express**: the human approves A, B and C together after you show all three (brief, beat map summary, styleframes). Use it when the user asks for speed.
- **benchmark**: no human. You approve each gate yourself with `--by agent --note "<why>"` after checking your own work against the skill checklist. Use it only for `benchmarks/` runs or when the user explicitly says "don't ask me anything".

An approval stores the artifact's SHA-256. If you edit an approved artifact the gate goes **stale** and needs approving again.

## 2. Roles

Work as four roles, as subagents where your tool supports them, otherwise as separate passes:

| Role | Stages | Model | Rule |
|---|---|---|---|
| Director | 0-2 | strongest available | owns concept, copy and variety; writes `decisions.md` entries |
| Beat editor | 3-4 | strongest available | owns `beatmap.json`; every hit has a musical, spoken or visual reason |
| Builder | 5-6 | a cheaper model is fine | implements the beat map exactly; never invents timing, numbers or crops |
| QA reviewer | 7-9 | a cheaper model is fine | **never edits the composition**; reports failures back to the builder |

## 3. Non-negotiables

1. **Timing comes from the beat map.** Hits are `S.hit(tl, "<event id>", …)` inside the scene's `Studio.forScene()` helper, never a typed number. Scene and media `data-start` / `data-duration` / `data-media-start` are written by `mstudio beatmap apply`, never by hand.
2. **Numbers come from bindings.** Every number on screen is `Studio.fmt()`, `S.counter()` or `Studio.series()` from `data/bindings.json`, or a quoted claim with its source in `facts/claims.json`. QA fails orphan numbers when the brief needs data or facts.
3. **Facts come with evidence.** When a brief makes factual claims, freeze the source as a local text snapshot in `facts/sources/`, write `facts/claims.json` with exact quotes, and run `mstudio facts`. Source-linked is not proven true, so say so in the handoff.
4. **Footage is reframed, not stretched.** Crops live in `footage/reframe.json` (canvas aspect, inside the picture area, outside every `avoid` box such as burn-ins and logos). Footage and audio elements sit at the root of `index.html`, never inside a timed element.
5. **One render engine: HyperFrames (HTML + GSAP).** Never Remotion, and never generative text-to-video footage. Stock only when the approved style brief names a scene that needs real imagery (see `skills/director` → stock policy).
6. **Deterministic compositions.** No `Date.now()`, no unseeded `Math.random()`, no network, no `repeat: -1`. Fonts load from local files (`fonts/`). GSAP loads from `vendor/`, not a CDN.
7. **Licenses.** Every file in `audio/`, `footage/`, `data/raw/`, `facts/sources/`, `assets/` and `fonts/` gets a `credits.json` entry (source, license, author). QA fails anything unlisted.
8. **API keys stay local.** Keys (Gemini for TTS) are collected with `mstudio keys setup <name>`, which opens a local file for the user to paste into. Never ask for a key in chat, never read the key file, never print, log or commit a key. See `skills/voiceover`.
9. **Privacy.** `projects/` is git-ignored: client briefs, real client names and client assets never go into this public repository. Work for a named client or brand (for example Billionaire Signal) stays in `projects/` or a private repo, and never in `examples/`, `benchmarks/`, issues or commit messages. HyperFrames telemetry is off (`mstudio` sets `HYPERFRAMES_NO_TELEMETRY=1`). Never use `hyperframes publish`, `cloud` or `lambda` on client material.
10. **Log every decision** with `mstudio decide <slug> <topic> "<choice>" --why … --alternatives …`: what was chosen, what else was considered, and why.
11. **One chat per video.** A long chat carries old decisions into new work. Start a new session for a new project.

## 4. Creative rules

- **Variety:** a new project must differ from the previous ones in concept and structure (scene count, hero object, opening hook, closing payoff), not just colors. Record its structural fingerprint in the style brief. House-style tokens stay constant; variety never means off-brand.
- **Reference videos:** take rhythm, energy and motion language only. Never copy their palette, layout, scene order or signature moments.
- **Anti-slide:** no fade-between-slides structure, no centered title over a photo by default, no three-tier text stacks, no stock corporate icons. See `third_party/motion-bang-bang/references/anti-ppt.md`.
- **Hit hierarchy:** drop or section → scene change or special moment; downbeat → big hit; beat → entrances; snare → punches; hats → micro accents, sparingly; quiet bars → holds with drift; a spoken word → its on-screen word. There is at most one big hit per bar unless the style brief says otherwise. Exact values are in `skills/house-style`.

## 5. Definition of done

A render is shown to a human only when `mstudio qa` passes. That covers HyperFrames lint, runtime, layout, motion and contrast; exact copy, on screen long enough to read; no orphan numbers; source-linked facts; the minimum text size; the safe area; every hit on its frame; no JavaScript errors; spec (resolution, fps, duration ±1 frame); −14 LUFS ±1 with true peak ≤ −1 dBTP; no unintended black or frozen frames; complete credits; and, for revisions, no changed frame outside the revised scene. Then **look at the video yourself** (contact sheet plus a few full frames) against the style brief, and fix weak scenes before handing off.

Hand off with the MP4 path, the QA summary, remaining warnings, facts that still need human review, and one honest sentence on the weakest moment.

## 6. Where things are

```
src/motion_studio/    mstudio CLI: beats, beatmap, data, claims, footage, audio, render, qa, revise, project, doctor
engine/inspect.mjs    headless-Chrome timeline/DOM inspector used by QA
templates/composition index.html (thin host), scene.html, studio.js runtime helpers, house.css tokens
skills/               director, beat-editor, voiceover, builder, footage, data-viz, qa, revise, house-style
third_party/          vendored upstreams with their LICENSE files (see THIRD_PARTY_NOTICES.md)
benchmarks/           frozen benchmark suite v1 + bench.py timer; run each case in a fresh chat
examples/             public example projects
projects/             your working projects (git-ignored)
docs/spec.md          product spec (why the pipeline is built this way)
```

HyperFrames' own skills (`/hyperframes`, `/hyperframes-core`, `/hyperframes-animation`, `/media-use`, `/music-to-video`, …) are useful when building. Install them with `npx hyperframes skills` and follow them, but this contract wins where they differ. We use our own beat map, not their `beats` file, and our own QA gate. Vendored iart-ai skills mention Remotion and After Effects: use only their CSS/GSAP guidance.
