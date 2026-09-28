# Cartoon Stage — Educational Flat Cartoon Explainer (One Stage per Scene)

This document governs Style 6 of the explainer family. Benchmark data is drawn from production projects: a 40-second animated story featuring a single character across 5 environments, and an 80-second explainer (7 stages, 2 characters, zero captions).

**Definition**: Each scene is an independent *stage* sized to the viewport frame ($1920\times 1080$ + overscan), illustrated in clean vector shapes, fully reactive ($\ge 10$ moving or interactive elements), with dedicated camera framing. The camera moves strictly **within** the stage (zoom factor $1.08–1.95$, never zooming out to wide). Between stages, use **hard cuts** or a swift 96px/72px directional slide with $\le 10\text{px}$ blur. The voiceover (VO) carries the narrative; visuals provide understanding; **there are zero on-screen captions**.

### Key Differences Between Explainer Modes

| Dimension | Cartoon Collage (`starter-explainer-kartun`) | Cartoon Stage (`starter-explainer-panggung`) |
|---|---|---|
| Scene World | Single large paper canvas with static cutouts | Multiple independent stages, each frame-sized |
| Primary Motion | Camera traverses across static illustrations | Objects and characters act within stage; camera tracks |
| Scene Transitions | Continuous 3D camera push-through | Hard cut or 96px directional slide |
| Background Surface | Cream paper texture + grain + watercolor stains | Clean flat solid colors, zero texture |
| Typography | Display copy + highlight pills | Zero subtitles/captions; diegetic labels only |
| Asset Pipeline | AI-generated illustration $\rightarrow$ cutout | Drawn vector shapes + jointed puppet with raster head |

## Law 1 — One Stage per Scene, Camera Never Zooms Out to Wide

Benchmark camera framing values: $1.95 \rightarrow 1.08 \cdot 1.65 \rightarrow 1.14 \rightarrow 1.18 \cdot 1.90 \rightarrow 1.12 \rightarrow 1.36 \cdot 1.45 \rightarrow 1.57 \rightarrow 1.17$. **The zoom factor must NEVER drop below 1.08.** In close-up, characters occupy $55–65\%$ of frame height; in wider shots, they still occupy $\sim 35\%$.

**Common Failure Mode**: Constructing the entire world as one giant map ($20,000\text{px}$) traversed at zoom levels $0.2–0.7$. While technically moving, half the video reduces to miniature scale: houses appear thumb-sized and empty space covers $60\%$ of the screen. This still feels like a presentation slide. The solution is splitting the narrative into discrete, frame-filling stages.

**Camera Rhythm per Stage**: Hold $0.45–0.7\text{s} \rightarrow$ execute one motivated move per VO beat $\rightarrow$ hold.
Permitted camera moves:
- Push-in toward an active subject ($1.12 \rightarrow 1.45$).
- Tilt up to rooftop or down to underground cross-sections in stages intentionally designed taller than $1080\text{px}$.
- Tracking moving characters (e.g. tracking a jump arc while maintaining loose composition).
- Interpolate zoom logarithmically to ensure smooth, natural perspective shifts.

## Law 2 — Continuous Action Within Stages, Cuts Between Stages

A change in spoken voiceover copy does not require changing stages. As long as spatial logic or cause-and-effect connects the thoughts, stay in the same stage and mutate the **action**: walls lift to reveal interior machinery, gauge needles rise, indicator lights turn green, or plants grow in sequence. Switch stages only when physical location, scale, or explanatory context genuinely changes.
- Benchmark pacing: a 40-second piece uses $\sim 5$ stages; an 80-second piece uses $\sim 7$ stages.

Apply styled transitions only for major spatial changes ($1–2$ times per project); use hard cuts for the remainder.
Benchmark 96px slide parameters:

```
Exit:  0.28s, offset = -d * q²        (q = 0 → 1)
Cut
Enter: 0.42s, offset = +d * (1 - q)³
d = 96px horizontal or 72px vertical; blur ≤ 10px on wrapper;
NO scale bumps; NO extra diagonal wipe geometry.
```

Apply the translation offset to the stage's camera rig, never by sliding pre-cropped viewport frames. Never execute lengthy 3-second multi-environment pan-zooms across sky and ground; that pattern quickly exhausts the viewer.
Hard cuts between stages do **not** violate Anti-PPT rules so long as each stage is actively alive with kinetic energy.

## Law 3 — Every Stage Features $\ge 10$ Moving Elements

Secondary motion is not decorative; it illustrates environment, function, and systemic relationships.
Validated secondary motion elements:
- Rotating fans (`t * 100°`).
- Vibrating meter needles and pulsing status lights.
- Water droplets traveling **along pipe paths** (parametric `getPointAtLength`, not dash-offset).
- River ripples drifting continuously.
- Rising chimney smoke or steam using keyframed opacity tweens.
- Windborne dust, flying birds, clothes swaying on a clothesline, leaves rustling.
- Walking animals with jointed leg cycles.
- Indicator lights activating in sequence with deterministic micro-blinks.
- Foliage growing then wilting; cracks propagating along surfaces (`stroke-dashoffset`).
- Soil strata accumulating; water tables rising or receding.

**Particle Tween Rule**: Pair one motion tween with one keyframed opacity tween (`keyframes: { opacity: [0, 0.9, 0.9, 0] }`), both set to `repeat: -1`. Overlapping two infinite opacity tweens on the same element will override each other and break particle visibility.

## Law 4 — Jointed Puppet Rigs, Never Static Cutouts

Solid flat illustrations cannot articulate. Use this joint hierarchy (local coordinates, feet at $y=0$):

```
root (pelvis at 0, -214)
├─ thigh_L/R  translate(±26, -214)   thigh 118 → knee at +102
│  └─ shin     translate(0, 102)     shin 108 → ankle at +96
│     └─ foot  translate(0, 96)
└─ torso       translate(0, -214)    torso -152..+8, neck -178..-138
   ├─ arm_R    translate(50, -126)   upper arm 98 → elbow +78   (rendered BEFORE torso)
   │  └─ fore  translate(0, 78)      forearm 90 → wrist +74
   │     └─ hand translate(0, 74)
   ├─ arm_L    (mirror at -50; rendered AFTER torso)
   └─ head     translate(0, -160)    chin on neck joint, 14px overlap onto neck
```

**Subtle Idle Motion**:
- Torso rotation $\pm 1.1^\circ$ over $1.7\text{s}$.
- Head rotation $\pm 1.7^\circ$ over $2.3\text{s}$.
- Arms $\pm 1–1.5^\circ$ over $1.9\text{s}$.
- **Blink every $\sim 3.5\text{s}$ lasting $0.13\text{s}$** (offset per character to prevent synchronous blinking).
- **Walk Cycle**: `step = Math.sin(t * 8)`; thigh `step * 15°`, shin `Math.max(0, step) * 18°`, torso bobbing `Math.abs(step) * 3–4px`, with the foot shadow ellipse translating synchronously.
- **Sentence Gestures**: Pointing (upper arm $6^\circ \rightarrow -72^\circ$ in $0.7\text{s}$), waving, operating machinery (arm yoyo between $-62^\circ$ and $-10^\circ$ + crank rotating `+=180°`), fanning face (forearm oscillating between $-40^\circ$ and $-70^\circ$).
- **Facial Expressions**: Swap discrete head graphics (happy / anxious / surprised); do not attempt vector path morphing. Blinking uses a secondary head layer with closed eyelids toggling opacity $0 \rightarrow 1 \rightarrow 0$.
- **Contact Shadow**: An ellipse (`rx ≈ 72 * scale`, `ry = 16`, `opacity: 0.13`) rendered **beneath** the puppet, tracking the puppet's horizontal position.

## Law 5 — Manual Transform Proxies; GSAP Must Not Touch Joints Directly

Two severe SVG animation traps:
1. **GSAP's `transformOrigin` on SVG elements computes relative to the element's dynamic bounding box**. As child geometry rotates, the bounding box shifts. Consequently, shoulders, necks, fan pivots, and knees rotate around drifting anchor points, tearing characters apart.
2. **GSAP `x`/`y` tweens on an SVG `<g>` with an existing `transform="translate(...)"` overwrite the initial coordinate**, causing elements to jump or reset unexpectedly.

**Solution**: Use a dedicated joint proxy helper `J(el, tx, ty)` that writes explicit SVG transform strings on update:

```js
function J(el, tx = 0, ty = 0) {
  const j = {
    el, tx, ty, x: 0, y: 0, r: 0, sx: 1, sy: 1,
    apply() {
      el.setAttribute('transform',
        `translate(${j.tx + j.x},${j.ty + j.y}) rotate(${j.r}) scale(${j.sx},${j.sy})`);
    }
  };
  j.apply();
  return j;
}

// Rotate joint around its local coordinate origin:
tl.to(j, { r: -62, duration: 0.42, onUpdate: j.apply }, at);
```

**Rule**: Separate static placement containers (`<g transform="translate(...)">`) from animated joint containers. GSAP may directly tween `opacity`, attributes (`attr`), and non-transformed primitives (`<circle cx="..." cy="...">`).

## Law 6 — Zero On-Screen Captions; Diegetic Text Only

Never write subtitle copy across the screen. If viewers must read subtitles to understand the story, the visual staging is inadequate.
All on-screen text must exist diegetically within the environment: street signs, equipment labels ("AIRLOCK", "PUMP 02"), building placards, or computer monitors. Text highlight pills belong strictly to collage mode, not cartoon stage.

## Law 7 — Vibrant Flat Palette; No Paper Fibers, No Heavy Grain

Cream paper textures, heavy grain, and watercolor stains belong to *Cartoon Collage*; in *Cartoon Stage*, they look dated and mismatched.
- **Validated Color Schemes**: Pale gradient skies (`#BFDDE3 → #F6EFDD` or `#EDB095 → #F8D8AD`), warm earth tones (`#D88560`, `#E6D5AC`), warm cream (`#FFF3DC`), deep navy (`#345867`), vibrant teal (`#237C80`), fresh mint (`#8DD3C3`), golden yellow (`#F4BC52`), coral (`#E0714F`).
- Flat vector fills, zero stroke outlines, zero surface textures, zero vignette darkening. Shadows are limited to grounding contact ellipses and architectural shading ($0.86–0.9\times$ base surface luminance).

## Character Pipeline: Raster Head + Vector Body

1. **Generate Head Only** (isolated transparent graphic, forward-facing):
   > ONE isolated front-facing cartoon HEAD, centered, generous margin. No body, no neck below the jaw, no shoulders, no text. VERY MINIMAL flat 2D educational-cartoon style: broad softly rounded head, simple small ears, hair as ONE solid silhouette (no strands, no highlights), eyes ONLY TWO SMALL SOLID BLACK DOTS (no sclera, iris, highlights, eyelids), two tiny eyebrow strokes, nose omitted, mouth a tiny curved smile line. Flat fills, ~3 colors, no gradients, no outlines, no shading. A clean silhouette for a cutout animation puppet.
2. **Local Expression Generation** (`scripts/kepala-ekspresi.py`):
   Detects pupils and mouth automatically, generating `<name>-{happy,anxious,surprised}[-blink].png` + metadata. Zero repeated AI image generation needed for expressions.
3. **Assemble Vector Body**: Build vector limbs following the joint hierarchy; mount head via `<image>` with chin pivot at `(0,0)` overlapping the neck joint by $14\text{px}$.
4. If image generation is unavailable, use the built-in SVG vector character generator `character()` in `assets/starter-explainer-panggung.html`.

## Verification Protocol

Capture 20–24 key timestamps using `scripts/snap.mjs` and arrange into a 4-column contact sheet:
- Inspect every frame: Is the camera zoomed out too far ($< 1.08$)? Are character heads or landmarks clipped?
- Are limb joints separating during gestures?
- Did any background elements vanish due to tween specificity bugs?
- Mechanically check code: ensure no `transformOrigin: '0px 0px'` on joints and no `tl.to` on `<g translate="...">` elements.
