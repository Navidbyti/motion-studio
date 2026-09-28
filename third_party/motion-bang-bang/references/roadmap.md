# Roadmap — Development Guidelines and System Evolution

This document tracks the origin, validated foundations, and future evolution of the Motion Bang Bang skill for both human maintainers and AI coding agents.

## Core Design Principle

The rules in `anti-ppt.md` and techniques in `techniques.md` originated from a single fundamental challenge: generated web animations repeatedly felt like corporate presentation slides.
**Only generalized, production-tested principles enter this skill** — never project-specific brand assets, colors, or copy.

## Validated Foundations (Non-Negotiable Baselines)

Do not regress on any of these core architectural decisions:
- **One statement + maximum one hero object per scene**.
- **Unified camera rig (`#world`)**: The background scales and translates in perspective alongside foreground subjects; push-through used only when narratively motivated.
- **Rationed climax effects**: 3D per-word tracking and complex transitions reserved for 1–2 key climax moments.
- **Directional motion blur**: Implemented via SVG filters on entrance/exit tweens.
- **Strict determinism**: All animations calculated strictly as a pure mathematical function of master timeline time (`tl.time()`), enabling frame-accurate scrubbing and export.
- **Visual verification protocol**: Mandatory inspection of keyframe contact sheets prior to presenting deliverables.
- **Authentic brand extraction**: Official vector paths, color tokens, and product claims extracted from verified sources rather than invented.
- **Sound is a post-render decision**: Effects are mined from the finished animation timeline and mixed onto the rendered MP4 with the video stream copied. The approved picture is never re-rendered to change audio, and effect audio never lives inside `index.html`.
- **One contract per audio bundle**: Every take is gain-staged to the same peak by pure gain, then trimmed sample-accurately against one shared gate, so intensity stays a mix-time parameter instead of a property of the recording. Adding a sound to a library costs a prompt, not a re-balance.
- **Audio claims are measured**: Loudness, true peak, ducking depth, and cue placement are verified with FFmpeg output, not with "sounds fine".

## Strategic Roadmap

1. **Precomputed Audio Analysis**:
   - Transition from procedural BPM sine approximations to offline FFT audio analysis.
   - Load audio $\rightarrow$ precalculate FFT frequency bins per frame offline $\rightarrow$ serialize to JSON $\rightarrow$ pass into deterministic render loop. Never execute real-time FFT analysis inside the render loop, which breaks scrubbing and frame export.
2. **Expanded Transition Vocabulary**:
   - Add horizontal whip-pans, camera rig rolls, rack-focus blurs, geometric match-cuts, and letterform zoom portals to complement existing push-through and light leaks.
3. **Menu of Concepts, Never Prescriptive Templates**:
   - Avoid standardized rundown templates (e.g. hook $\rightarrow$ feature $\rightarrow$ feature $\rightarrow$ promise $\rightarrow$ CTA), which result in identical structures. Continue expanding the menu in `opener-konsep.md` with diverse conceptual models.
4. **Modular Multi-File Starters**:
   - While `assets/starter-opener.html` is single-file for portability, provide modular folder templates as agent environments evolve.
5. **Enhanced Video Export Pipelines**:
   - Explore WebCodecs `VideoEncoder` and headless `canvas.captureStream` alongside existing Puppeteer pipelines, plus vertical (9:16) rendering presets.
6. **Automated Review Tooling**:
   - Automated scripts that capture $N$ key timestamps (`tl.time(t)`) and generate composite contact sheets for rapid visual inspection.
7. **Failure/Remedy Library Expansion**:
   - Continuously update the anti-pattern table in `anti-ppt.md` with real failure cases and their exact architectural fixes.
8. **Sound Design Follow-Ups**:
   - Music bed routing next to the SFX bus — the bundle forbids tonal content in every prompt precisely so this stays collision-free.
   - Cue review: let a human edit one row of `assets/sfx-cues.json` (drop, move, re-family) and re-mix without re-mining the timeline.
   - Grow `data:"<verb>"` tagging in the style libraries until heuristic classification is the exception, not the rule.

## Tempting Anti-Patterns to Avoid

- **Overly finished starter templates**: Starters with complete narrative examples cause AI models to copy structures verbatim. Starters must remain structurally bare and unopinionated regarding scene order.
- **Single "correct" answers per failure**: Providing a single fix turns that fix into a new template. Always offer a menu of diverse solutions.
- **Feature and effect inflation**: Every visual technique must serve camera choreography or narrative revelation. Gimmicky effects age rapidly.
- **Rules without rationales**: Enforce rules by documenting the specific failure modes that produced them. Directives without context are frequently discarded by LLMs.
- **Library lock-in**: GSAP and Three.js are practical defaults, not dogmas. The core principles (anti-PPT, camera rigs, determinism) apply equally to Remotion, Motion One, or pure Canvas.
- **Sound effects as page audio**: `<audio>` tags for whooshes and clicks look like the obvious move and cost the whole project — every retiming needs a re-render, scrub-preview fights autoplay policy, and 200 elements in the DOM do not mix. Effects belong to the post-render mix.

## Portability Across AI Agents

This repository is fully portable: `SKILL.md`, `references/`, `assets/`, and `scripts/` consist of standard Markdown, HTML, scripts, and one regenerable binary bundle (`assets/sfx/` — WAV takes that any `library.json` run rebuilds, so no audio file is the only copy of an idea).
When integrating with an agent lacking native skill folder support:
1. Inject `SKILL.md` into the system prompt.
2. Provide `anti-ppt.md` and `techniques.md` during design sessions.
3. Provide `architecture.md` and the appropriate starter template during coding sessions.
4. Provide `sound-design.md` only when a rendered MP4 needs its sound effects.
