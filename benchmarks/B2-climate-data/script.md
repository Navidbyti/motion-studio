# B2: CO₂ and global temperature since 1960 (on-screen copy)

Output: 45 s · 1080×1920 · 30 fps · no voiceover.
Use the quoted text **exactly**. Every number on screen must match `data/expected-values.json` or a row in `data/derived/`. Use the real minus sign (−) for negative values and a plus sign for positive temperature anomalies in callouts. Scene timings are guides; the total must be 45 s.

| # | Guide | Purpose | Visual | Exact on-screen text |
|---|---|---|---|---|
| 1 | ~4 s | Hook | Two thin lines drawing upward | "Two measurements." / "Since 1960, both have climbed." |
| 2 | ~8 s | CO₂ curve | Line chart of `derived/co2_ppm_annual.csv` (1959–2025), y-axis in ppm. Counter runs from 316.91 to 427.35. | "Carbon dioxide in the air, Mauna Loa, Hawaii" / "1960: 316.91 ppm" / "2025: 427.35 ppm" |
| 3 | ~6 s | Milestones | Same curve with markers at 1988 and 2015; big stat | "Passed 350 ppm in 1988" / "Passed 400 ppm in 2015" / "+34.8% since 1960" |
| 4 | ~8 s | Temperature curve | Line chart of `derived/temp_anomaly_c_annual.csv` (1880–2025) with a labeled zero line | "Global surface temperature" / "compared with the 1951–1980 average" / "0 = 1951–1980 average" |
| 5 | ~9 s | Decades | Bar chart of `derived/temp_decade_means_c.csv`, bars labeled with their values in °C | "Average by decade (°C)" / labels "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020–2025" / values "−0.03", "+0.04", "+0.25", "+0.39", "+0.59", "+0.81", "+1.07" |
| 6 | ~6 s | Record years | Ranked bars or podium from `derived/warmest_years_top5.csv` (top 3 only) | "Warmest years in NASA's record since 1880" / "1. 2024 +1.29 °C" / "2. 2025 +1.19 °C" / "3. 2023 +1.17 °C" |
| 7 | ~4 s | Sources | End card | "Data: NASA GISS Surface Temperature Analysis (GISTEMP v4); NOAA Global Monitoring Laboratory, Mauna Loa CO₂ annual mean." / "Snapshot retrieved 28 Sep 2026." |

## Data rules

- `data/raw/` holds the unmodified downloads. `SOURCES.md` lists their URLs, retrieval date and SHA-256.
- `data/derived/` and `data/expected-values.json` are produced by `data/derive.py` (Decimal math, round half up). Charts use the derived tables. Callout numbers use the answer key.
- Temperature values are anomalies (differences from the 1951–1980 mean), not absolute temperatures. Never label them as "temperature: 1.29 °C".
- The last temperature bar covers only 6 years (2020–2025). Its label must say "2020–2025", never "2020s".
- CO₂ milestones are annual means. "Passed 350 ppm in 1988" means 1988 was the first annual mean at or above 350 (351.69 ppm).
- The screen may not show any number that is not in the answer key or the derived tables. Axis tick values are the only exception.
