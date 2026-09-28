---
name: data-viz
description: Motion Studio data and facts. Binds every on-screen number to a hashed source (data/bindings.json) and every factual claim to an exact quote (facts/claims.json); rules for animated charts and counters that QA can prove. Use for any video with numbers, charts, statistics or factual claims.
---

# Data and facts

A data video is only as good as its weakest number. The rule: **nothing on screen is typed by hand**. Every number traces to a file, a line and a hash.

## Sources

1. Put raw files in `data/raw/` **unchanged** (CSV, XLSX, JSON) and snapshot web pages to `facts/sources/*.txt` (plain text, with the URL and retrieval date in the header). Never refetch during a revision. Add each file to `credits.json` with its license.
2. Derive tables with a script (`data/derive.py`) using Decimal math and a declared rounding rule. Never do arithmetic in your head or in the composition.
3. Write `data/bindings.json`:

```json
{
  "values": {
    "co2_2025": {"value": "427.35", "unit": "ppm", "display": "427.35 ppm", "source": "raw/co2_annmean_mlo.csv", "location": "line 111"},
    "temp_2024": {"value": "1.29", "display": "+1.29 °C", "source": "raw/GLB.Ts+dSST.csv", "location": "line 147, J-D"}
  },
  "series": {"co2": {"file": "derived/co2_ppm_annual.csv", "x": "year", "y": "co2_ppm", "unit": "ppm"}},
  "allow": []
}
```

4. Run `mstudio data <slug>`. It validates every value and series, hashes the files and writes `data.js`.
5. For facts (not numbers from a table), write `facts/claims.json` (schema: `src/motion_studio/schemas/claims.schema.json`). Every claim gets `evidence` with an exact `quote` from a local source file, and `onScreen` lists the exact on-screen strings it supports. Run `mstudio facts <slug>`. It checks hashes and verbatim quotes. Source-linked is not the same as true, so note what still needs human review.

## Charts

- Draw in inline SVG from `Studio.series(name).points`. **Plot every point** (no smoothing or resampling unless the brief asks and says so).
- Axes start at zero for bars. For lines choose a sensible domain, and label it clearly if it doesn't start at zero.
- Mark tick labels, gridline values and year labels computed from the domain with `data-provenance="axis"` so the number check knows they are derived. Everything else that shows a number must come from a binding.
- Units on the axis or in the label (ppm, °C, %). Anomalies are "vs 1951-1980 average", never absolute temperatures.
- Keep negatives visible: bars go below the zero line, and the minus sign is the real minus (−).
- Reveal data on beats: a line draws across bars of music, and bars rise on beats. Big hits go on the values that matter, not on every point.
- A partial period is labeled as such ("2020-2025", not "2020s").
- The source goes on screen (end card or a persistent label) and stays long enough to read, or its `min_seconds` is set in `copy.json`.

## Counters

`S.counter(tl, "#el", "<key>", {from, start, impact})` animates and then **lands on the exact display string** of the bound value on the impact frame. QA checks the landing text. Pick `from` so the count reads as growth (for example the series' first value), not 0 by default.

## What QA checks

- `numbers`: every number visible at any sampled frame is a bound value, a series point, a claim's on-screen string, scripted copy or `allow`. It is an **error** when the brief needs data or facts. Sign errors fail.
- Counters end on their bound display string.
- `facts`: hashes match and quotes are verbatim.
