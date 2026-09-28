# Motion Studio benchmark suite (v1)

Three fixed production tasks. They measure how long a build takes to deliver a video, and how good that video is. The prompts, scripts, data, footage and audio are **frozen**, so a result from one build can be compared with a result from any later build. Every run happens in a **fresh coding-agent chat** with no memory of earlier runs.

| Case | What it tests | Inputs | Output |
|---|---|---|---|
| [B1](B1-gps-explainer/) · How GPS finds you | A short prompt turned into a 30 s explainer: diagram animation, exact copy, pacing | Short prompt, on-screen script, 2 frozen GPS.gov pages | 30 s · 1080×1920 · 30 fps |
| [B2](B2-climate-data/) · CO₂ and temperature since 1960 | A data-sensitive piece: line, bar and ranking charts, counters, exact numbers, units, sources | NASA GISTEMP v4 and NOAA Mauna Loa CSV snapshots, derived tables, answer key | 45 s · 1080×1920 · 30 fps |
| [B3](B3-artemis-recap/) · Artemis I in 30 seconds | Editing existing footage: conform, vertical reframing, graphics over video, transitions, sound mix | Six NASA clips (mixed 1080p/720p, 59.94/60 fps), frozen NASA page | 30 s · 1080×1920 · 30 fps |

Each case also has a fixed **revision prompt** (`REVISION.md`) that changes a single scene. It tests whether the build can make a targeted edit without disturbing the rest of the video, and how fast.

All cases share one audio pack in [`shared/audio/`](shared/audio/): a 48 s music bed (100 BPM) and six sound effects. They are synthesized by `generate_audio.py` and dedicated to the public domain (CC0). No case uses a voiceover.

## Running a benchmark (owner)

Open a **new** chat in Claude Code, Codex or Antigravity for **each** case. Do not reuse a chat and do not run two cases in one chat. Paste the message below and change `B1` to the case you want:

> Benchmark run: Motion Studio suite v1, case **B1**.
> First, run `date -u +%Y-%m-%dT%H:%M:%SZ` and remember the result as SESSION_START. Then clone https://github.com/Navidbyti/motion-studio.git into a fresh directory, do the setup that AGENTS.md section 0 describes, open `benchmarks/README.md` and follow its "Agent protocol" exactly for case B1. Do not ask me anything until the run is committed.

The suite started on [motion-engine](https://github.com/Navidbyti/motion-engine) (discontinued). Its v0.68.0 runs stay in `results/` as the **baseline**. Inputs are hash-identical, so v0.68.0 and Motion Studio results are directly comparable.

Once the agent reports back, watch the draft and the revised video, then give your score in the same chat:

> Record my owner review for that run: design=4, motion=3, pacing=4, clarity=5, sound=3; publish: no; comment: "…"

The scored dimensions for each case are listed at the bottom of its `CHECKLIST.md`.

All runs are listed in [`results/RESULTS.md`](results/RESULTS.md).

## Agent protocol

You are the agent in a benchmark run. The goal is to measure the build honestly. It is not to make this build look good.

1. **Verify inputs.** Run `python benchmarks/bench.py verify`. It must print `OK`. Never edit anything under `benchmarks/B*/` or `benchmarks/shared/`.
2. **Start the clock.** Run
   `python benchmarks/bench.py start <CASE> --agent "<product>" --model "<exact model id>" --session-start <SESSION_START>`.
   It prints the run directory, called RUN below.
3. **Produce the first draft.** Treat the text of the case's `PROMPT.md` as the user's production request. Treat every file in the case folder, plus `benchmarks/shared/audio/`, as the user's attachments. Then follow the repository's normal production workflow (AGENTS.md and its skills) exactly as you would for a real user. Create the project with `mstudio new <case-slug> --mode benchmark …` and take every stage and gate in order, approving gates yourself (`--by agent --note …`) as benchmark mode allows. The draft is `renders/master.mp4` after `mstudio qa` passes, or after you have recorded why it can't. Rules:
   - Do not ask the user anything. If something is ambiguous, choose the most reasonable option and record it with `--assumption` in step 6.
   - Use only the provided inputs. Do not fetch newer data, download other footage or music, or use paid generation services. Sound effects come from `benchmarks/shared/audio/` only (beat-map `"sfx": "file:audio/sfx/<name>.wav"` after copying them into the project), not the built-in SFX library. If the build cannot do something, deliver the best video it can and record the gap. Do not abandon the run.
   - Do not open `benchmarks/results/` or other cases' outputs. Earlier runs must not influence this one.
   - When the draft MP4 is finished and you have inspected it the way you would before showing a user, run `python benchmarks/bench.py mark RUN draft-delivered`.
4. **Revise.** Immediately run `python benchmarks/bench.py mark RUN revision-start`. Apply the case's `REVISION.md` as the user's follow-up message, using the build's revision workflow. When the revised MP4 is inspected, run `python benchmarks/bench.py mark RUN revision-delivered`.
5. **Self-check.** Go through every *Agent-checked* item in the case's `CHECKLIST.md` against the actual videos: look at frames, run ffprobe, compare text and numbers. Write the results to a JSON file outside the repository in this shape: `[{"item": "…", "pass": true|false, "evidence": "frame 412 shows …"}]`. A failed item with honest evidence is a useful result. An unverified pass is not.
6. **Finish.** Run
   `python benchmarks/bench.py finish RUN --draft <draft.mp4> --revised <revised.mp4> --checks <checks.json> [--assumption "…"]… [--notes "…"]`.
   This probes both videos, runs the automatic checks, stores a 540×960 proxy and a 1-fps contact sheet in RUN, and regenerates `results/RESULTS.md`. Full-resolution videos stay in your local `runs/` workspace.
7. **Commit.** Stage only `RUN/` and `benchmarks/results/RESULTS.md`. Commit them with the message `bench: <CASE> on v<version> (<run-id>)` and push to `main`. If the push is rejected, run `git pull --rebase`. If `RESULTS.md` conflicts, run `python benchmarks/bench.py report`, `git add` the regenerated file and `git rebase --continue`. Then push again. Never force-push.
8. **Report** to the user:
   - setup, draft, revision and total times
   - failed automatic and agent checks
   - assumptions you made
   - local paths of the full-resolution draft and revised MP4s
   - one paragraph on the weakest part of the video

## Owner review (agent side)

When the owner gives scores, run `python benchmarks/bench.py score RUN --scores "design=4,motion=3,…" --publish y|n --comment "…"`. Then commit `RUN/run.json` and `results/RESULTS.md` and push them.

## What is recorded

`RUN/run.json` records:
- the build version and commit
- the agent product and model
- the machine (OS, CPU, Python, FFmpeg)
- the exact prompt texts and their hashes
- every timestamp and computed duration
- the probe results for each output: resolution, fps, duration, integrated LUFS, true peak, black and frozen segments, SHA-256
- the automatic and agent checks, assumptions and questions
- the owner review

**Setup** runs from SESSION_START to `start`. It covers cloning, installing, running tests and the doctor. **Draft** runs from `start` to `draft-delivered`. **Revision** runs from `revision-start` to `revision-delivered`. **Total** runs from SESSION_START to `finish`.

## Changing the suite

Inputs are pinned by `manifest.json` (SHA-256 of every file under `B*/` and `shared/`), and `bench.py start` refuses to run when they differ. Change the inputs only on purpose. In the same commit:
- bump `SUITE_VERSION` in `bench.py`
- run `python benchmarks/bench.py manifest`
- note the change below

Results from different suite versions are not comparable.

| Suite | Date | Change |
|---|---|---|
| v1 | 2026-09-28 | Initial suite: B1 GPS explainer, B2 climate data, B3 Artemis I footage recap. The baseline build is v0.68.0. |

Maintenance scripts (not used during runs): `B2-climate-data/data/derive.py` rebuilds the derived tables and answer key from the raw snapshots. `shared/audio/generate_audio.py` rebuilds the audio pack and needs numpy.
