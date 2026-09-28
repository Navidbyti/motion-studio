# B3: Artemis I in 30 seconds (edit + motion graphics)

Output: 30 s · 1080×1920 · 30 fps · no voiceover.
Use the quoted text **exactly**. Clip in/out points inside each file are the editor's choice. Scene timings are guides; the total must be 30 s.

| # | Guide | Clip | Motion graphics | Exact on-screen text |
|---|---|---|---|---|
| 1 | ~3 s | `01_rollout_night.mp4` | Title reveal over the rocket | "ARTEMIS I" / "NASA's uncrewed test flight around the Moon" |
| 2 | ~4 s | `02_ignition_closeup.mp4` | Hit the ignition flash with `sfx-impact.wav`; small date/time tag | "Liftoff" / "Nov. 16, 2022 · 1:47 a.m. EST" |
| 3 | ~4 s | `03_liftoff_wide.mp4` | Lower third | "Launch Pad 39B" / "Kennedy Space Center, Florida" |
| 4 | ~5 s | `04_orion_earth.mp4` | Callout pointing at Earth | "Orion looks back at Earth" |
| 5 | ~6 s | `05_orion_moon.mp4` | Animated counter to 268,563, then the second line | "268,563 miles from Earth" / "43,471 miles beyond the far side of the Moon" |
| 6 | ~5 s | `06_splashdown.mp4` | Lower third | "Splashdown" / "Dec. 11, 2022 · off the coast of San Diego" |
| 7 | ~3 s | Freeze, blur or graphic background | End card | "25 days, 10 hours, 53 minutes" / "Footage: NASA" |

## Facts

All come from `sources/nasa-artemis-i.txt` (NASA Artemis I mission page, frozen 2026-09-28).

| On-screen claim | Exact excerpt |
|---|---|
| Uncrewed test flight | "Uncrewed lunar flight test" |
| Liftoff date/time, pad | "launched from Launch Pad 39B at Kennedy Space Center in Florida at 1:47 a.m. EST on Nov. 16, 2022" |
| Distances | "Orion traveled 268,563 miles from Earth and 43,471 miles beyond the far side of the Moon" |
| Splashdown | "splashed down to Earth off the coast of San Diego at 12:40 p.m. EST on Dec. 11, 2022" |
| Duration | "The total mission duration was 25 days, 10 hours, and 53 minutes." |

Do not add a splashdown clock time. The source gives it in EST while the recovery happened in the Pacific time zone, so it is ambiguous.

## Footage traps (deliberate, part of the test)

- The clips mix 1920×1080 at 59.94/60 fps with 1280×720 at 59.94/60 fps. They must be conformed to 30 fps without judder, duplicated frames or stretched pixels.
- `02_ignition_closeup.mp4` has a burned-in camera number ("913") in the top right. The vertical reframe must keep it out of the frame.
- `04_orion_earth.mp4` has black pillarbox bars. They must not appear in the output.
- `01`, `04` and `05` have no audio track, and `02`, `03` and `06` have natural sound. The mix must handle both.
- `01_rollout_night.mp4` is from the August 2022 rollout, not launch night. Do not caption it with a launch date.
