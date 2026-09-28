# Anti-PPT — Rules of Scene Design

This document defines the core reason this skill exists: output that is "technically correct" will still fail if it feels like a PowerPoint presentation.

## Why Models Default to Presentation Slides

Language models are trained to structure INFORMATION hierarchically:
`Headline → Explanation → Supporting Evidence`.

That structure works well for text documents, but is fatal for motion graphics. Promotional video does not explain — it **proclaims**, delivering one punch per shot, letting physical motion, camera dynamics, and audio carry the emotional resonance. If a scene feels "lacking in information," that is often proof the scene is paced correctly for video.

## Violation to Correction Matrix

| Violation | Mechanical Correction |
|---|---|
| Kicker "02 — FEATURES" + 2-line title + 2-line body copy + 4 feature chips, left/right column layout | One short sentence $\le 5$ words centered top + one product hero object rising into center. |
| Three rows of large text displaying claims: "NO MORE …" | 2-word headline + one dynamic presentation method chosen from `opener-konsep.md` (live feature demo, word swap, object metamorphosis, card shuffle, tile grid). |
| Product B adopts Product A's skin (identical palette, glow, nebula, font) inherited from a starter or previous project | Visual style derived from Brand B via style brief: palette from logo/icon, distinctive font character, unique background motion language, unique signature motion (SKILL.md Law #3). |
| All titles ALL-CAPS, wide font weight 800, centered, entering with identical character staggers | Sentence case weight 500–600, emphasis on primary keyword (optional highlight: pill, underline, marker, scale, or adjacent icon), no automatic periods, varying scale/direction/screen coordinates across scenes (`techniques.md` §1). |
| Every title/claim ends with a period, including 2-word fragments | Default to NO period; `?` only for genuine questions; period only when deliberately creating a staccato cadence across two short statements (`techniques.md` §1 Rule 5). |
| 96 white glowing light beams blooming behind title — busy background, unreadable text | Dark pocket directly behind text ($\le 25\%$ luminance), particles drawn from dark brand palette tones, $\le 40$ bright elements visible, bloom applied to objects only (`techniques.md` §1b). |
| Generic dark background with starfield; background never considered per segment | Background derived from brand theme (light gradient, soft tones, solid color block, authentic paper, photos, or deep tones); shifts planned per segment in style brief (`techniques.md` §7b). |
| Repeating identical word highlight (pill + sparkle) across every project and every sentence | Word highlights are optional; when used, choose one shape per video in the brief, do not force onto every sentence, and derive ornaments strictly from brand geometry (`techniques.md` §1). |
| SaaS/App opener only displays static screenshots zooming or panning | Reconstruct UI from native product components, operate it dynamically (cursor, touch, or autonomous UI triggers), populate data, let UI carry transitions (`opener-konsep.md` UI animation guide). |
| Video file embedded full-screen with `autoplay loop`, running on its own clock while web animations freeze | Mount clips via `clip()` helper as timeline-locked footage layers, framed within animated device mockups/containers, with text and annotations active above them (`techniques.md` §9b). |
| Two different products use the same horizontal light streaks ("lane"/"range") as background motion | Select background motion from `techniques.md` §7c menu (shifting gradient, organic blobs, live grain, light sweep, rotating hulls, rising particles, breathing grid). Horizontal streaks reserved only for speed/flow themes. |
| Transitions: giant flat colored block or thin diagonal line wiping across every cut | Select from `techniques.md` §4c: 3D push-through, cards rotating from depth, volumetric objects crossing the lens, branded shape masks, light sweeps; minimum two types, at least one volumetric, $\le 2$ wipes. |
| Flat single-color background (solid dark or solid white) from start to finish | Layered background surface ($\ge 2$ layers from `techniques.md` §7d: horizon glow, diagonal duotone, mesh blobs, spotlight + tint, layered skies, textured grain) with colors from brand palette. |
| Background remains completely static throughout the entire video | Background elements move continuously (`techniques.md` §7c); background color may shift whenever justified by an on-screen trigger: object covering lens, UI action, push into color field, cut on beat (`techniques.md` §7b). |
| Copying color palette, font, and layout directly from a user-supplied reference video | Extract shot rhythm and kinetic energy only; skin must be derived from the product theme. Explicitly state this to the user. |
| Displaying technical metadata (e.g. package name `com.example.app`) in the final CTA scene | Remove completely. Users do not care; if required, display an app store search bar mockup instead. |
| Text animates in and out while the camera remains completely stationary | Vary shot scale to the active storytelling element (`techniques.md` §3b) + choreograph overlapping element timelines (§4b); subtle camera breathing as base layer; push-through used only when narratively motivated ($\sim 1$ per video). |
| "Zoom in/out" implemented as a tiny camera drift ($\sim 2\%$) — video still feels completely static | Execute clear shot scale transitions: camera moves in close to the active subject (medium close-up / close-up), then pulls back to wide when the composition requires the full frame (`techniques.md` §3b). |
| Heavy 4-layer bloom applied to all headlines | Clean white text + subtle drop shadow; reserve bloom for OBJECTS (hero product shapes, UI accents, icons). |
| Warp starfield background with 500+ long white lines | 300 short particles tinted with dark brand colors — background elements must never compete with foreground subjects. |
| Flat uniform blue background | High-contrast vertical gradient: near-black at top, illuminated horizon at bottom. |
| UI elements (e.g. status badges) animate in before the primary headline | Hierarchy of attention: headline first $\rightarrow$ primary hero object second $\rightarrow$ supporting metadata last. |
| Zoom push-through applied to EVERY single transition | Motion vocabulary: spin, 3D yaw, roll, elements flying past lens; push-through only when motivated (e.g., diving into a mockup screen). Uniform transitions across all cuts = PPT template behavior. |
| Whip-pan translation exposes stage edges, revealing a black gap | Reads as "changing pages". NEVER translate the world so far that canvas edges become visible. |
| Jarring spin/yaw/roll cuts (sudden zoom + rotation with blur on every cut) | That is video editing preset behavior, not motion design. Replace with: camera breathing + choreographed element overlap + object wipes. |
| UI demo feels static: full UI fills frame, camera frozen, tiny cursor clicks illegible | Camera follows interaction: push into clicked area (scale 1.4–2.2, 0.6–0.9s ease in-out), click occurs clearly, then pull back or pan to result (`techniques.md` §8). |
| Openers for different products follow identical sequence: zoom text exit left $\rightarrow$ 3 feature tiles $\rightarrow$ typing search bar $\rightarrow$ hook $\rightarrow$ feature $\rightarrow$ feature $\rightarrow$ promise $\rightarrow$ logo $\rightarrow$ CTA | Select 3 concept candidates from `opener-konsep.md`, pick 1 based on product characteristics; structural fingerprint must differ from previous opener; maximum 2 canonical components. |

## Common Failure Patterns in Explainers

Consider a 30-second historical explainer with 6 scenes that feels like a presentation slide deck:

| What Was Built | Why It Feels Like PPT | What It Should Be |
|---|---|---|
| $6 \times$ `<section class="scene">` containing full-bleed photos toggled sequentially via `autoAlpha` | Swapping sections = swapping slides, regardless of transition effects. | One continuous flowing world; scenes change because the camera/world moves or whip-pans to another coordinate. |
| Each section: kicker + 2-line title + attribution credits | Three tiers of text = presentation layout. | One large stat/phrase + one diegetic label anchored in the scene world. |
| Motion limited to Ken Burns photo scale (1.08 $\rightarrow$ 1.015) and scale bump on `#world` (1.12 $\rightarrow$ 0.96) at each cut | Identical motion applied to every cut = automated template. | Parallax layers, objects crossing lens, whip cuts, diegetic instruments (maps, gauges, elevation profiles), dynamic camera breathing per beat. |
| Light leaks placed at every single cut | Generic video editor transition preset. | Reserved for at most one high-impact climactic moment. |
| No persistent visual subject across scenes | Nothing for the audience to follow or anchor onto. | Hero subject or continuous canvas remains present $>60\%$ of total duration. |

**Key Takeaway**: Narrative principles alone are insufficient; you must enforce mechanically checkable structural rules (`SKILL.md` "Structural Prohibitions") and scaffold from correct style starters (`assets/starter-explainer-*.html`).

## Principles Applicable to Any Motion Project

1. **One shot = one statement.** A phrase of $\le 5$ words is vastly more powerful than a complete grammatically complex sentence. "Two words. One punch." beats "This application does X, Y, and Z for you."
2. **Attention hierarchy per scene**: Spoken copy/headline first $\rightarrow$ primary hero object next $\rightarrow$ secondary supporting details last. Never invert this order.
3. **Long copy is a bug.** If a claim requires $>6$ words, split it across two scenes or convert it into visual storytelling (icons, numbers, UI demonstration).
4. **Metadata is not content.** Package names, raw URLs, version numbers, footnotes — delete them. Lay viewers do not read them, and technical viewers do not need them.
5. **UI mockups are the exception to text limits.** Application screens may contain small text because they are perceived as an IMAGE rather than read as copy. However, the mockup must faithfully replicate the real product (fonts, tokens, layout).
6. **Motion carries semantic meaning.** Zoom in = emphasis/intimacy; tracking pan = progressive revelation; pull back = context reveal; subtle bounce = playful personality. Choose motion that mirrors the semantics of the message.
7. **Motion designer transitions, not editor presets.** Avoid translation whip-pans that expose stage borders and jarring rotation cuts. Instead use: (a) camera breathing (gentle continuous drift), (b) element choreography (in/out timings overlap across the cut), (c) object wipes (a foreground object crosses the lens, wiping the scene behind it), and (d) motivated zoom transitions (diving into a screen).
8. **The camera is the unifier.** A camera rig that moves the entire canvas makes discrete moments feel like a cohesive film. Without it, even polished graphics feel like an automated slide deck.
9. **Asymmetric entrance and exit timing.** Enter firmly and decisively (0.7–1.3s, `power4.out`), exit quickly (0.35–0.55s, `power2.in`). Symmetric easing feels robotic.
10. **Ration special moments.** Reserve the most expensive visual techniques (3D per-word tracking, full logo build-ons, complex portals) for 1–2 key climax moments. If used everywhere, they lose all impact.
11. **When in doubt, darken the background and enlarge the text.** High visual contrast is the cheapest and most reliable way to achieve professional polish.

## Rapid Heuristic Calibration

Capture a static frame snapshot and evaluate:
- Could this exact frame serve as a corporate presentation slide without modification? $\rightarrow$ If yes, it fails. Redesign.
- Does the viewer's eye know exactly where to focus within 0.2 seconds? $\rightarrow$ If no, reduce visual clutter.
- If all text is hidden, is the background still visually engaging without being noisy? $\rightarrow$ Both must be true.
- Is there motion caused by the CAMERA rather than just elements animating themselves? $\rightarrow$ Must be true across every transition.
