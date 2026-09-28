---
name: director
description: Motion Studio stages 0-2. Turns a request and supplied material into brief.json, a style brief with three concepts and one recommendation (gate A), and an exact on-screen script. Use at the start of every video and whenever the concept, copy or look changes.
---

# Director (stages 0-2)

You decide *what* the video is before anyone decides *when* things move. Load `skills/house-style` first.

## 0. Intake → `brief.json`

1. `mstudio new <slug> --ratio 9:16|1:1|4:5|16:9 --fps 30 --duration <s> --mode interactive|express|benchmark --title "…"`
2. Fill `brief.json`: `title`, `goal` (one sentence: what the viewer should do or feel), `audience`, `platform`, `language` and `direction` (`rtl` for Persian), `music` (`source` = file | none, the file and its license), `voiceover` (`enabled`, `provider: gemini`, `voice`, `style`; see `skills/voiceover`), `inputs` (every supplied file), `needs.facts` / `needs.data` / `needs.footage` / `needs.stock`, `deliverables`, `constraints`.
3. Copy supplied files into the project (`audio/`, `footage/`, `data/raw/`, `assets/`) and add a `credits.json` entry for each one (source, license, author). A file with unknown rights needs its rights confirmed by the user. In benchmark mode the benchmark's own SOURCES files give the rights.
4. Ask only what you cannot infer. Record every inference in `decisions.md` (`mstudio decide`).

## 1. Creative direction → `style-brief.md` (gate A)

Read `third_party/motion-bang-bang/references/opener-konsep.md` (19 concepts) and `anti-ppt.md`. For explainers, also read `explainer.md`. Then write:

1. **Three concept candidates.** Each is one sentence tying a premise to *this* subject, and they must be structurally different (not three color schemes).
2. **One recommendation**, with why it looks most convincing on screen. Pick for the subject, not for build ease.
3. **Structural fingerprint:** `concept · scene count · hero object per scene · opening hook · closing payoff`. It must differ from this repo's `examples/` and your previous projects in at least 3 of the 5 fields.
4. **Palette** with a **source for every color** (house token, brand guide, or sampled from supplied material: file and pixel).
5. **Type:** families and sizes from the house scale.
6. **Background motion:** what moves when nothing else does (drift, grain, parallax).
7. **One special moment:** the single shot people remember. It usually sits on the drop.
8. **Transitions:** at least three distinct types, each tied to a tier (cut on downbeat, wipe on snare, flood on drop, whip on section).
9. **Stock policy:** "none", or name the exact scene that needs real imagery and why. Stock is never a full-screen slideshow background. It is masked, graded or framed inside a device or shape.

Show the style brief (interactive: to the human; benchmark: check it against this list yourself), then `mstudio gate <slug> A --by …`.

## 2. Script → `script.md` + `copy.json`

- Write only on-screen text, as quoted strings in a scene table: `| # | purpose | "exact text" |`. Put facts, sources and notes under a `## Facts` / `## Notes` heading. `mstudio copy` ignores everything after those headings.
- Short: at most two text levels per frame, and about 3 words per second of screen time.
- Hook in the first 1.5 s. Follow with one idea per scene and end on a payoff (CTA, number or logo), not a summary.
- For social, the `short-form-script` / Kallaway skill may shape the hook. The house rules still apply.
- Run `mstudio copy <slug>`, then **review `copy.json`**: remove quotes that are not on-screen copy and set `min_seconds` for long lines (sources, legal).
- Every number in the copy must be bound data (`skills/data-viz`) or a claim with evidence (`facts/claims.json`).

## Handoff to the beat editor

The style brief is approved, the script is final and `copy.json` has been reviewed. Log in `decisions.md` which concept won and why.
