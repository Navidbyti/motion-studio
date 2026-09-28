# Explainers — Visual Storytelling, Not Promotional Teasers

For flat educational cartoon explainers featuring characters (Style 6, **Cartoon Stage**: one stage per scene, jointed puppet rigs, zero captions), consult [kartun-panggung.md](kartun-panggung.md).
The number of sentences does not dictate the number of camera cuts, and adding more camera motion does not automatically make a video more engaging. The collage recipes below are options, not universal rules for all explainers.

### The Two Most Common Explainer Styles

| Dimension | Cartoon + VO | Visual Journalism (Photos) |
|---|---|---|
| Best Suited For | Science & education, $\sim 75\text{s}$, 9:16 or 16:9 | Investigative journalism, current affairs, $\sim 75\text{s}$ |
| Background Surface | Textured cream paper + subtle color stains | Deep charcoal/black + delicate film grain |
| Imagery | AI-generated flat illustrations $\rightarrow$ background removed to cutout | Authentic licensed photos (Wikimedia Commons, NASA, DVIDS) |
| Typography | Bold display grotesk + expressive handwriting (Caveat) | Heavy condensed sans + monospace kicker labels |
| Accent Elements | Vibrant highlight pills (orange/teal/mustard), marker strokes | Yellow highlighter strokes, red warning rings, dashed paths |
| Audio Setup | Spoken voiceover tightly synchronized to timeline | Zero VO — bold typography drives the story (3–5s reading beats) |

While openers sell an emotional feeling, explainers **deliver an argument**. Anti-PPT rules apply fully, with two practical adjustments: a scene may feature a primary claim plus an explanatory metric or annotation, and technical mockups/maps/charts may contain higher detail because they are perceived as graphic images rather than blocks of text.

## Step Zero: Confirm Style, Aspect Ratio, Duration, and Audio

Users often ask: "Make an explainer about X." Left unguided, models invent styles, ratios, and arbitrary durations (sometimes stretching to 10 minutes). Before writing code, ask **ONE consolidated question** (using your agent's structured question mechanism if available) establishing these four parameters:

### Explainer Styles (Include 1-line recommendation based on topic)

| # | Style | Aesthetic Feeling | Best Suited For | Core Asset Pipeline |
|---|---|---|---|---|
| 1 | Cartoon Collage | Cream paper, flat illustration cutouts, color pills, handwriting | Science, education, accessible topics | Generated illustrations $\rightarrow$ background removed to cutouts |
| 2 | Visual Journalism | Deep dark canvas, real photography, highlighter marks, source tags | Investigative news, geopolitical issues | Free licensed photography (Wikimedia/NASA) |
| 3 | White Catalog | High-key white grid, clean product cutouts, mixed type, scribbles | Products, corporate profiles, brands | Product/character cutouts, pure white backdrop |
| 4 | Vintage Sketch | Sepia parchment, fine copperplate engraving, classic serifs, rust accents | History, biography, discoveries | Engraving/etching illustrations with multiply blending |
| 5 | Continuous Action (Vector) | Flowing continuous world, persistent hero, in-world stats, shifting angles | Speed, transit, sports, logistics, workflows | 100% procedural SVG geometry, zero AI generation |
| 6 | Cartoon Stage | Vibrant flat colors, 1 stage per scene, articulated puppets, zero captions | Character-driven educational stories | Vector world & bodies; generated head with local expressions |

### Additional Parameters (Ask in the Same Turn)

| Parameter | Options | Default If Unspecified |
|---|---|---|
| Aspect Ratio | 16:9 (YouTube / Desktop) · 9:16 (Shorts / Reels / TikTok) · 1:1 | 16:9 (Landscape) |
| Target Duration | 30 s · 60 s · 90 s | 60 s |
| Audio Configuration | No audio (text-led) · User will supply VO (build now, retime later) · Music only · VO + sound design (effects on every motion) | No audio, VO script provided in handoff |

**What NOT to ask**: Captions (default to none) and player UI (default to autoplay + loop without on-screen controls).

**Duration Constraints**: Follow user brief and VO pacing. Several sentences can occur within a single evolving stage. Trim excessive content rather than inflating runtimes. If a user requests a 10-minute video, confirm and decompose it into distinct chapters ($\le 90\text{s}$ per chapter).

## Handoff Protocol: Include Complete VO Script

Explainers typically conclude with a voiceover recorded by the user or generated via their preferred TTS engine. The standard protocol:
1. Build the initial animation with comfortable reading tempos.
2. Deliver `index.html` alongside the complete VO script formatted in the closing message.
3. Instruct the user to record/generate their audio and provide it for final timeline synchronization.

Example closing message:
> **Voiceover Script** (1 paragraph = 1 visual scene; spell out numbers as words):
> 1. …
> 2. …
> Record or generate this with your voice of choice. Speak at a natural pace with $\sim 1\text{-second}$ pauses between paragraphs (WAV or MP3 format). Share the audio file back here, and I will synchronize the animation timeline to your voiceover track.

Save the identical script into `vo-script.md` in the project root. Always print the script in the chat message as well.

**If the user chose "VO + sound design"**: say in the same handoff that the effects do not have to be sourced — they ship in `assets/sfx/`, are mined from the finished animation, and are mixed onto the rendered MP4 (`references/sound-design.md`). Never ask the user for whooshes, and never embed effect audio in `index.html`.

## Scaffold from the Correct Style Starter

Always start from the dedicated template in `assets/`:
- `starter-explainer-kartun.html` (Cartoon collage)
- `starter-explainer-jurnalisme.html` (Visual journalism)
- `starter-explainer-katalog.html` (White catalog)
- `starter-explainer-sketsa.html` (Vintage sketch)
- `starter-explainer.html` (Continuous action vector)
- `starter-explainer-panggung.html` (Cartoon stage)

### The Two Motion Paradigms

| Paradigm | Scene Canvas | Primary Motion Mechanics | Used By |
|---|---|---|---|
| **FLOW** | Continuous parallax world strip driven by speed curves; hero stays anchored | World flows past hero; perspective shifts | Continuous action (vector) |
| **COLLAGE** | Large static canvas with layered cutouts/photos | Camera choreographs: `into` $\rightarrow$ `settle` $\rightarrow$ `look` $\rightarrow$ `home` $\rightarrow$ stationary | Cartoon collage, visual journalism, catalog, vintage sketch |

**Timeline Scrubbing Caveat**: GSAP's `tl.pause(t)` suppresses callbacks (`suppressEvents: true`), preventing `onUpdate: applyCam` from firing during static snapshots. Always implement seek helpers as `tl.pause(t, false)` followed by an explicit `applyCam()` call. Never start an explainer from `assets/starter-opener.html` or an empty file.

## Common Misconceptions and Default Rules

- **Aspect Ratio**: Default to 16:9 (1920×1080) or match user display. Use 9:16 ONLY when explicitly requested.
- **Zero On-Screen Player**: Deliverables autoplay and loop seamlessly. Scrub controls appear only via `?debug=1`.
- **Zero On-Screen Subtitles/Captions**: Default to no subtitles running along the bottom. Information is communicated through large statistics, diegetic in-world labels, and graphic visual metaphors.
- **Learn Reference Principles, Do Not Clone Layouts**: Three-column cards, bottom subtitles, or gauge shapes in reference videos are specific examples. Adopt the underlying principle (e.g. stats embedded inside the world) and express it uniquely.
- **Stage Scaling**: Scale `#stage` via:
  ```css
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%) scale(s);
  ```
  Do not use CSS grid `place-items: center`, which fails to scale stage cell heights and clips layouts.

## Universal Explainer Narrative Arc

High-performing collage and visual journalism explainers share a proven narrative structure:
1. **The Hook**: 1 striking graphic + 1 curiosity-inducing premise (surprising metric, anomaly, provocation).
2. **Explicit Question**: Clear headline displayed on screen ("Why now?", "What went wrong?").
3. **Spatial Context**: Map, blueprint, or environment illustration with labels and an accent circle on the critical coordinate.
4. **The Scale Metric**: Large numbers counting up, followed by comparative before/after data bars.
5. **Timeline**: 2–3 milestone dates, 1 concise statement per date.
6. **Animated Chart**: Line graph drawing its trajectory with shaded area fill.
7. **Audience Consequence**: Tangible impact on the viewer's daily life or environment.
8. **Echo Outro**: Closing statement echoing the initial hook + compact attribution credits.

## One Scene = 3 to 5 Cumulative Elements (Never an Isolated Graphic)

A frequent failure mode is placing a single cutout image and a single headline in a scene. Even with camera motion, the viewer cannot grasp the physical reality of the subject. A single symbol is insufficient. High-quality explainers ($\sim 20$ visual beats per 30 seconds) use cumulative layering:

1. **Phrase-by-Phrase Accretion**: Each spoken phrase introduces a new visual element; previously introduced elements remain on screen. Scenes conclude with 3–5 elements that collectively explain the concept: `Subject (photo/cutout) + Evidence (document, news clipping, interface) + Scale (metric or repeating grid) + Date/Stamp Label + Annotation`.
2. **Evidence Over Generic Decoration**: Incorporate concrete artifacts that answer "what does this actually look like?": typed legal documents with stamps, newspaper clippings with highlighted phrases, source badges, device interfaces, date placards. HTML/CSS can render documents directly (cream paper + border + monospace font + rotated red stamp) without generating external images.
3. **Repetition Demonstrating Scale**: Multiply a single cutout into an organized grid using staggered `back.out` entrances (e.g. 1 student expands into dozens of portraits; 1 engine rotor expands into 12).
4. **Photo to Document Reveal**: Camera zooms out from a portrait to reveal it is printed on a historical magazine cover, with a date block popping alongside.
5. **Deterministic Autonomous Elements**: Cipher letters cycling into decoded words, clock hands accelerating toward midnight, counters ticking upward, gavel striking.
6. **Camera Discipline**: Elements accumulate in the same spatial zone; the camera executes subtle `look()` pans ($\pm 200\text{px}$, zoom $1.0–1.15$) to accommodate new elements. A new element requires a micro camera pan, not a cut.
7. **Strict Hierarchy**: 1 large headline + 1 diegetic label per scene. Documents, date stamps, and handwritten post-its containing $\le 3$ short lines count as world objects, not text tiers.
8. **Rapid Photoreal Props**: Generate isolated objects ("studio product photo, isolated on pure white") and composite with `mix-blend-mode: multiply` — the white background vanishes cleanly over grids and paper without needing transparency clipping. (Do not add CSS `drop-shadow` to multiply elements; shadows are already embedded in the photo).

## Technical Implementation Recipes

- **9:16 Vertical Viewport**: Stage dimensions $1080\times 1920$. Headline fonts $88–168\text{px}$, monospace kickers $26\text{px}$, photo credits $20\text{px}$ bottom-left.
- **Word-by-Word Typography (`say/unsay`)**: Each word wrapped in `<span class="wd">` (nowrap) enters via `yPercent: 60 → 0, scaleY: 1.3 → 1`, stagger $0.07–0.12$, with vertical blur. Key terms wrapped in `<span class="wd hl"><i></i>word</span>`, where `<i>` expands `scaleX: 0 → 1` from the left **AFTER** characters finish entering (`hlAt`). Never combine words across line breaks into a single `.wd` wrapper.
- **Photo Animation (`photo()`)**: Set `object-fit: cover`, enter with directional blur, then apply continuous subtle Ken Burns drift (`scale 1 → 1.12–1.25` + slow pan, `ease: 'none'`). Overlay subtle top/bottom gradients (`.dim`, `.top`) to maintain copy legibility. Overlay fine film grain via `mix-blend-mode: overlay`.
- **Vector Cutouts (`enter/leave`)**: Enter from bottom with `back.out(1.4)` overshoot; drop-shadow applied to wrapper container. Color filters (e.g. grayscale) must live on the `<img>` tag, not the wrapper, because motion blur filters overwrite wrapper filter styles.
- **SVG Path Drawing (`draw`)**: Initialize `strokeDasharray = L, strokeDashoffset = L → 0`. Keep `opacity: 0` until animation begins to prevent round line-caps from displaying as stray dots at zero length. For dashed lines, animate a revealing `clip-path: inset()` from the left (`drawDash`).
- **Cartographic Maps**: Use high-resolution public domain satellite imagery (NASA MODIS/Worldview) overlaid with monospace `.tag` badges, yellow leader lines, red focus circles, and dashed route trajectories.
- **Animated Line Charts**: Compute data coordinates in JavaScript, animate `path` stroke with dash-offset, fade in area gradient underneath, pop data points with staggered scales, and label only key inflection points (start, peak, end).
- **Large Dynamic Counters**: Tween a numerical object `{ v: 0 } → { v: target }`, updating `textContent = Math.round(v)` with `font-variant-numeric: tabular-nums`.
- **Scene Color Tints**: Full-viewport `.tint` overlay layers within `#world` with animated opacity changes affordably shift ambient emotional tone (e.g. deep night, cold dawn).
- **Scene Cut Transitions (`cut`)**: Scale world $1.05\times$; new scene enters at $1.08–1.12\times$, settling to $1.0$ over $0.8\text{s}$. Outgoing elements blur upward as incoming elements enter. The camera maintains breathing motion throughout.
- **Retiming to Late-Arriving Voiceover**: Map original scene boundary timestamps `OLD` to new voiceover timestamps `NEW` (derived from `scripts/vo-pauses.html` or `ffmpeg silencedetect` pause intervals $\ge 0.9\text{s}$). Wrap animation start cues in a linear interpolation helper `T(t)`. Tween durations remain unchanged while start timestamps stretch. Compute push-through transitions relative to new cut times (`T(cut) - 0.9`).

## Visual Assets and Photographic Integrity

- **Generated Illustrations** (Style 1 Cartoon): Generate via consistent style prompts ("flat vector, bold outline, warm palette, solid white background"), then process through background removal to transparent PNGs. Generate in single batches to preserve stylistic uniformity.
- **Authentic Archival Photography** (Style 2 Journalism): Fetch high-resolution imagery via Wikimedia Commons API, NASA Worldview, or DVIDS public domain archives. Verify licensing and display attribution on screen. Never substitute blurry television broadcast screenshots.
- **Video B-Roll Inserts**: 3–8 second video clips mounted via `clip()` helper as timeline-locked footage layers (`techniques.md` §9b), nested within stylized borders, annotations, and UI frames.

## Mentioned Entities MUST Be Visualized (Crucial Law)

A severe failure mode is naming people, corporations, or locations without displaying them: mentioning a founder without showing their face, citing "17 factories" without showing a production line, or discussing a product without displaying its packaging.
1. Extract an **Entity Manifest** from the script: persons, corporations, facilities, geographic coordinates, products. Every entity mentioned must have a visual representation.
2. Sourcing Priority: Public domain archives (Commons/NASA) $\rightarrow$ Official press kits $\rightarrow$ User-supplied photos $\rightarrow$ Photoreal synthetic imagery labeled "artist reconstruction" for generic environments (factories, transit hubs). **NEVER generate synthetic faces for real living individuals.**
3. Viral social media photos or news clippings can be cropped and converted into collage cutouts with proper attribution.

## Mobile Legibility Standards (Strict Thresholds)

Vertical 9:16 video is viewed on $\sim 6\text{-inch}$ smartphone screens, and social app safe-area scaling ($0.78$) compresses text further.
**Absolute MINIMUM font sizes on a 1080px stage (before safe-area scaling)**:

| Typography Role | Minimum Pixel Size |
|---|---|
| Explanatory body copy | 44 px |
| Name badges, kickers, date markers | 34 px (sub-labels: 32 px) |
| Source attributions and credits | 30 px (opacity $\ge 0.6$) |
| Handwritten annotations | 48 px |
| Primary headlines | $\ge 100\text{px}$ |

**Never render text smaller than 30px.** If copy does not fit, trim sentences or split across multiple scenes — never shrink font sizes below these thresholds.

## Collage Camera Choreography: Close-Up $\rightarrow$ Travel $\rightarrow$ Zoom Out $\rightarrow$ Settle

1. Camera rig `#world`: Tracks focus coordinate and zoom $C = \{ x, y, z \}$, applied every frame:
   ```js
   transformOrigin: '0 0';
   scale: z;
   x: 540 - sx * z;
   y: 960 - sy * z;
   ```
2. **Scene Rhythm**:
   - Begin close-up on the first asset ($z \approx 1.4$, settling to $1.32$).
   - Pan smoothly to the second asset as it enters.
   - Zoom out to `HOME` framing ($z = 1.0$) as the primary headline appears.
   - **Hold stationary at `HOME`** until the final transition. Do not execute secondary zooms after returning to wide framing; let element annotations carry the action.
3. **Push-Through Transition**:
   - $0.9\text{s}$ before the scene cut, outgoing elements depart and the camera accelerates (`power2.in`) toward the entrance coordinate of the next scene's hero asset.
   - At the cut timestamp, the new scene initializes at that coordinate, and the camera decelerates smoothly (`power3.out`).
4. **Mandatory Sequence: Zoom-Out MUST Complete Before Text Appears**:
   Text revealed while the camera is actively zooming out feels cramped and illegible. Headlines, body copy, and labels must appear $\ge 0.1\text{s}$ **AFTER** the zoom-out to `HOME` has completed. Keep zoom-out transitions concise ($1.0–1.2\text{s}$) to preserve reading time.

## Social Platform Safe Areas (Reels / TikTok / Shorts)

- **Safe Margins**: Wrap scenes in `.safe { transform: scale(0.78); transform-origin: 50% 45%; }` to leave $\sim 190\text{px}$ top and $\sim 230\text{px}$ bottom margins, preventing interface buttons and captions from obscuring content. Canvas backgrounds and grids extend full-bleed.
- **Audio Autoplay Resilience**: Browsers restrict unmuted audio autoplay.
  1. Call `audio.play()` on load; if permitted, playback begins unmuted from second 0.
  2. If blocked, **DO NOT run silently**. Hold on frame 0 with an unobtrusive prompt: "Tap anywhere to play", initiating audio and visual timelines synchronously on first user gesture.

## Style 5: Continuous Action (Vector Flow)

An effective antidote for explainers that feel like slide decks despite camera moves. Exemplified by high-speed sports, logistics, and transit topics: facts are communicated without ever halting physical forward motion.

1. **One Persistent Hero**: The primary subject (athlete, train, delivery courier, vehicle) remains on screen across $100\%$ of the runtime. The surrounding world transforms; the hero never leaves the frame.
2. **Continuous Motion**: Layered parallax backgrounds drift continuously, accompanied by speed lines, particle spray, and organic hero vibration. Not a single frame is completely stationary.
3. **In-World Statistics**: Large metrics exist as physical landmarks in the world (positioned on background parallax planes). The hero drives past them, visually wiping them off screen. Dynamic numbers roll like mechanical odometers.
4. **Shifting Camera Perspectives**:
   - Side profile (anchor shot).
   - Driver cabin POV (speedometer needle sweeps, digital display updates, track flows through windshield).
   - Stylized route simulation map (vector coastline, route draws via dashoffset, tracker moves via `getPointAtLength`, checkpoints pop into view).
   - Elevation profile (cross-section chart slicing through topography, highlighting subterranean tunnels).
   - Comparative map race (multiple markers racing simultaneously along separate routes).
   - Frontal perspective (subject approaches from vanishing point to full frame).
   - Interior perspective (passenger cabin corridor with scrolling scenery outside windows).
5. **No Three Consecutive Identical Perspectives**: Perspective changes represent scene transitions without requiring hard camera cuts.
6. **Two Tiers of Text Only**: Large metric + in-world environmental label. No subtitles; no kicker/body blocks.
