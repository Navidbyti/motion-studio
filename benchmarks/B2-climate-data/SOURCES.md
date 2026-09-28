# B2 data sources

Snapshots downloaded 2026-09-28. **Never refetch during a benchmark run.** Both publishers revise these files every month.

| File | Publisher | URL | Upstream last-modified | SHA-256 |
|---|---|---|---|---|
| `data/raw/GLB.Ts+dSST.csv` | NASA Goddard Institute for Space Studies, GISTEMP v4 (global land-ocean temperature index, anomalies vs 1951–1980, °C) | https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv | 2026-09-08 | `c9ce0750ca93a8241c42fe86cd5bf54d07b28b21ae650b0ae49a206907018cd9` |
| `data/raw/co2_annmean_mlo.csv` | NOAA Global Monitoring Laboratory, Mauna Loa CO₂ annual mean (ppm) | https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.csv | 2026-09-08 | `897770430ce802e232a0be272bff74b92757c39bfda26be1e213b19cbf71ac04` |

**License:** both datasets are U.S. government works in the public domain. NOAA asks for credit: *NOAA Global Monitoring Laboratory, Mauna Loa Observatory; data before April 1974 from C. David Keeling, Scripps Institution of Oceanography.* NASA suggested citation: *GISTEMP Team, 2026: GISS Surface Temperature Analysis (GISTEMP), version 4. NASA Goddard Institute for Space Studies.*

**Notes**
- The 2026 GISTEMP row is incomplete (`***` for J-D) and is excluded. The last complete year is 2025.
- The NOAA file header notes that measurements after the late-2022 Mauna Loa eruption partly come from Maunakea. We still refer to the series as "Mauna Loa", as NOAA does.
