# B3 footage sources

All clips are from the NASA Image and Video Library (https://images.nasa.gov). NASA material is generally not subject to copyright in the United States. Credit "NASA"; do not use the NASA insignia as a graphic element or imply NASA endorsement (see https://www.nasa.gov/nasa-brand-center/images-and-media/).

Each clip was cut from the `~orig` rendition on 2026-09-28 and re-encoded once: H.264 High, CRF 20, yuv420p, AAC 160 kb/s 48 kHz where the source had audible sound. 4K sources were downscaled to 1920×1080 (Lanczos). 720p sources keep their native resolution, and frame rates are unchanged. Silent audio tracks were removed, and metadata was stripped.

| File | NASA ID | Title | Created | Source res/fps | Cut from | Length | Output | Audio |
|---|---|---|---|---|---|---|---|---|
| `01_rollout_night.mp4` | KSC-20220816-MH-RLB01-0001-Artemis_I_Launch_Rollout_AERIALS-3312013 | Artemis I Launch Rollout - Aerials | 2022-08-16 | 3840×2160 @ 60 | 158.0 s | 10 s | 1920×1080 @ 60 | none |
| `02_ignition_closeup.mp4` | KSC-20221116-MH-AJN01-0001-Artemis_I_Isolated_Launch_Views-3314595 | Artemis I Isolated Launch Views | 2022-11-16 | 3840×2160 @ 59.94 | 1008.0 s | 10 s | 1920×1080 @ 59.94 | natural |
| `03_liftoff_wide.mp4` | KSC-20221116-MH-AJN01-0001-Artemis_I_Isolated_Launch_Views-3314595 | Artemis I Isolated Launch Views | 2022-11-16 | 3840×2160 @ 59.94 | 500.0 s | 12 s | 1920×1080 @ 59.94 | natural |
| `04_orion_earth.mp4` | KSC-20221116-MH-NAS01-0001-Artemis_I_Orion_First_Imagery_of_Earth-3314595 | Artemis I Orion First Imagery of Earth | 2022-11-16 | 1280×720 @ 59.94 | 46.0 s | 10 s | 1280×720 @ 59.94 | none |
| `05_orion_moon.mp4` | Artemis_I_Post-RPF_Leaving_Moon_221205_1735009 | Flight Day 20: Orion Completes Lunar Flyby | 2022-12-05 | 1280×720 @ 59.94 | 912.0 s | 10 s | 1280×720 @ 59.94 | none |
| `06_splashdown.mp4` | KSC-20221211-VP-MWC01-001-ARTEMIS-SPLASHDOWN-3296595 | Artemis I Orion Splashdown | 2022-12-11 | 1280×720 @ 60 | 98.0 s | 12 s | 1280×720 @ 60 | natural |

Source URL pattern: `https://images-assets.nasa.gov/video/<NASA ID>/<NASA ID>~orig.mp4`. The SHA-256 of each file is in `benchmarks/manifest.json`.
