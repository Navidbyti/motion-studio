# B2 checklist

## Automatic (`bench.py finish`)
- [ ] 1080×1920, 30 fps, 45.0 s ± 0.5 s, has an audio stream

## Data accuracy (agent-checked against `data/expected-values.json`; list every on-screen number with its frame)
- [ ] Every on-screen number matches the answer key or a derived row exactly, including the decimals
- [ ] CO₂ line plots all 67 annual points (1959–2025), not a smoothed or re-drawn approximation
- [ ] Temperature line plots all 146 annual points (1880–2025), with the zero/1951–1980 baseline labeled
- [ ] Bar heights are proportional to their values on a zero-based axis, and the negative 1960s bar goes below zero
- [ ] The partial decade is labeled "2020–2025". Anomalies are never presented as absolute temperatures.
- [ ] Units (ppm, °C) and the sources end card are visible and readable
- [ ] Nothing was fetched from the internet during the run (the raw file hashes still match `SOURCES.md`)

## Craft (agent-checked)
- [ ] Every line in `script.md` appears exactly and is readable for ≥ 1.5 s. No text overflows or collides with chart labels.
- [ ] Counters land exactly on their final values and hold them
- [ ] Only the shared music and SFX are used. True peak ≤ −1 dBTP.
- [ ] Revision: only scene 5 changed. Values are unchanged, and other scenes are identical to the draft.

## Owner score (1–5 each)
Chart clarity · Data trustworthiness · Visual design · Motion quality · Pacing · Sound · **Would I publish it?** (y/n)
