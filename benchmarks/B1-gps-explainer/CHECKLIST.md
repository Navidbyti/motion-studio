# B1 checklist

The agent records **Automatic** and **Agent-checked** results in `run.json`. The owner fills in the **Owner score** after watching.

## Automatic (`bench.py finish`)
- [ ] 1080×1920, 30 fps, 30.0 s ± 0.5 s, has an audio stream

## Agent-checked (evidence required: frame number or file path)
- [ ] Every line in `script.md` appears exactly once, spelled exactly, fully readable (not clipped, not covered, on screen ≥ 1.5 s)
- [ ] No on-screen text or numbers that are not in `script.md`
- [ ] Scene 5 visibly shows the step from one sphere to an intersection of several
- [ ] Only the shared music and SFX files are used; the music fades in and out, with no clipping (true peak ≤ −1 dBTP)
- [ ] No blank, black or frozen frames outside intended holds
- [ ] Revision: only scene 5 changed. Other scenes are frame-identical (or hash-identical modules) to the draft.

## Owner score (1–5 each)
Visual design · Motion quality · Pacing · Clarity of explanation · Sound · **Would I post it?** (y/n)
