# B1: How GPS finds you (on-screen copy)

Output: 30 s · 1080×1920 · 30 fps · no voiceover.
Use the quoted text **exactly** (spelling, numbers, units and punctuation). Line breaks and emphasis are up to the director. Scene timings are guides; the total must be 30 s.

| # | Guide | Purpose | Exact on-screen text |
|---|---|---|---|
| 1 | ~3 s | Hook | "How does your phone know where you are?" |
| 2 | ~4 s | The constellation | "31 GPS satellites orbit Earth" / "about 20,200 km up" |
| 3 | ~4 s | What they send | "Each one broadcasts two things:" / "the exact time" / "its exact position" |
| 4 | ~5 s | Measuring distance | "Your phone times how long each signal takes to arrive" / "travel time × speed of light = distance" |
| 5 | ~6 s | Trilateration | "One distance: you're somewhere on a sphere" / "Three distances: your position" / "A fourth satellite corrects your phone's clock" |
| 6 | ~4 s | Accuracy | "Typical smartphone accuracy under open sky:" / "within 4.9 m (16 ft)" |
| 7 | ~4 s | End card | "GPS: timing, turned into location." / "Source: GPS.gov" |

## Facts and where they come from

All in `sources/`, frozen on 2026-09-28. Do not refetch during a run.

| Claim | Source file | Exact excerpt |
|---|---|---|
| 31 satellites | `gps-gov-space-segment.txt` | "the U.S. Space Force has been flying 31 operational GPS satellites for well over a decade" |
| ~20,200 km | `gps-gov-space-segment.txt` | "at an altitude of approximately 20,200 km (12,550 miles)" |
| ≥4 satellites visible | `gps-gov-space-segment.txt` | "ensures users can view at least four satellites from virtually any point on the planet" |
| 4.9 m | `gps-gov-accuracy.txt` | "GPS-enabled smartphones are typically accurate to within a 4.9 m (16 ft.) radius under open sky" |

The timing and trilateration explanation (scenes 3–5) is the standard textbook description of GPS and needs no citation.

## Visual intent (non-binding)

Earth with satellites on orbit paths → signal pulses traveling to a phone → expanding spheres or circles that intersect at the phone → the phone pin locks with a map-style accuracy ring. Show the numbers as animated counters or labels, not as static paragraphs.
