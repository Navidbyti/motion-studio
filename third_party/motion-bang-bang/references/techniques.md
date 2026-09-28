# Techniques — Validated Animation and Visual Effect Blueprints

All recipes documented here are expressed in generalized parameters. Numerical values represent battle-tested production baselines, not immutable dogma. Typography, palettes, and brand narratives must always belong to the user's brand.

## Table of Contents

1. Living Typography (Per-character splitting, optional highlights, alternating entrance vectors) + 1b. Background Contrast
2. Directional Motion Blur (`feGaussianBlur` SVG filter)
3. Camera Dynamics: 3D Push-Through
3b. Shot Scale & Framing: Camera to Element (Wide $\leftrightarrow$ Medium Close-Up $\leftrightarrow$ Close-Up)
4. 3D Per-Word Tracking Pans
4b. Scene Transition Architecture & Hierarchy
4c. Menu of Motion Transitions (Depth-driven alternatives to flat wipes)
5. Cinematic Transition Light Leaks
6. Professional Glow Mechanics (Glow on objects; never on headlines)
7. State-Driven Three.js Environments: Nebula, Dust, Floor Grids, 3D Ornaments, Bloom
7b. High-Key Backdrops & Inter-Scene Environment Shifts
7c. Menu of Background Motion Languages (12 kinetic patterns)
7d. Menu of Background Surfaces: Gradients, Lighting, Textures & Grainy Gradients
7e. Object Rendering Style Families (Clay, Glass, Glossy, Isometric, Neon, Flat)
8. Icon Tiles, Dynamic UI Mockups & Camera Tracking User Clicks
9. Deterministic Typewriters, Counters, and Telemetry
9b. Video as Timeline-Locked Footage Layers
10. Catalog of Known Pitfalls and Engine Traps

---

## 1. Living Typography — Validated vs. Failed Formulas

Two contrasting patterns emerge in agent output:
- **Failed Pattern (Stiff)**: All titles ALL-CAPS, single ultra-bold weight 800, centered in every scene, entering with identical character staggers, zero focal emphasis, zero scale variation.
- **Validated Pattern (Living)**: Sentence case at weight 500–600, ONE primary keyword highlighted (or highlighted via word-by-word opacity reveals, scale, or adjacent iconography), punctuation rendered only when semantically required, alternating scale and layout coordinates, with alternating light/dark scenes.

> **Word Highlight Warning**: Word highlights (`pill`, `under`, `marker`, `box`, `color`, `strike`) are **OPTIONAL**. Many premier openers use zero background pill highlights, relying instead on word-by-word entrance pacing, typographic scale, or adjacent UI badges. When highlights are selected in the style brief, maintain one consistent shape throughout the deliverable; decorative accents (stars, sparks) must derive strictly from brand geometry. Never clone pill + sparkle accents across different projects.

### Typography Emphasis Menu (Choose 1 per project in the brief)

| Variant | Aesthetic Quality | Best Suited For |
|---|---|---|
| `none` | Clean, editorial restraint; emphasis driven by scale, timing, or adjacent UI badge | Enterprise SaaS, AI platforms, luxury minimalism |
| `pill` | Solid color block expanding from left | Digital products, consumer tech, mobile apps |
| `under` | Heavy colored underline drawing from left | Editorial journalism, financial tools, productivity |
| `marker` | Angled highlighter stroke with organic opacity | Education, community, culinary brands |
| `box` | Fine stroke border drawing a bounding box | Technical developer tools, hardware engineering |
| `color` | Keyword shifts color directly without container | High fashion, automotive, architecture |
| `strike` | Strike-through line followed by replacement word | Ironic before/after pivots, comparative messaging |

### Typography Implementation (CSS)

```css
.line {
  font-size: 112px;
  font-weight: 500;
  letter-spacing: -0.015em;
  color: #fff;
  white-space: nowrap;
  text-shadow: 0 4px 28px rgba(0, 0, 0, 0.5);
  line-height: 1.1;
  opacity: 0;
}
.line.sm { font-size: 74px; }
.line.md { font-size: 92px; }
.line.lg { font-size: 128px; }
.line.xl { font-size: 150px; font-weight: 600; letter-spacing: -0.02em; }
.line.ink { color: var(--ink-dark); text-shadow: none; } /* High-key light scenes */
.wd { display: inline-block; white-space: nowrap; }
.ch { display: inline-block; will-change: transform, opacity, filter; opacity: 0; }
.txt2 { display: inline-block; opacity: 0; } /* Optional punctuation / second clause */

/* Highlight wrappers */
.hl { position: relative; display: inline-block; }
.hl i { position: absolute; transform: scaleX(0); transform-origin: 0 50%; }
.hl-t { position: relative; opacity: 0; }
.hl.pill { padding: 0.02em 0.24em 0.04em; border-radius: 0.26em; }
.hl.pill i {
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(95deg, color-mix(in srgb, var(--accent) 70%, #000), var(--accent) 60%, var(--accent-lit));
}
.hl.pill .hl-t { color: #fff; }
.hl.under i { left: 0; right: 0; bottom: -0.04em; height: 0.14em; border-radius: 0.07em; background: var(--accent); }
.hl.marker i { left: -0.1em; right: -0.1em; top: 0.5em; bottom: -0.02em; background: var(--accent); opacity: 0.55; transform: scaleX(0) rotate(-1.5deg); }
.hl.box i { inset: -0.06em -0.14em; border: 0.04em solid var(--accent); border-radius: 0.12em; background: none; }
.hl.color .hl-t { color: var(--accent); }
```

### Typography Animation Helpers (JS)

```js
const inUp = (ch, el, at, { dur = 0.8, st = 0.024 } = {}) => {
  tl.fromTo(ch, { opacity: 0, yPercent: 60, scaleY: 1.45 },
    { opacity: 1, yPercent: 0, scaleY: 1, duration: dur, ease: 'power4.out', stagger: st, immediateRender: false }, at);
  blurTween(tl, el, at, 30, 0, dur, VERT);
};

const inLeft = (ch, el, at, { dur = 0.75, st = 0.02 } = {}) => {
  tl.fromTo(ch, { opacity: 0, xPercent: -45 },
    { opacity: 1, xPercent: 0, duration: dur, ease: 'power4.out', stagger: st, immediateRender: false }, at);
  blurTween(tl, el, at, 50, 0, dur, { ease: 'power4.out' });
};

const outUp = (ch, el, at, { dur = 0.4, st = 0.01 } = {}) => {
  tl.to(ch, { opacity: 0, yPercent: -70, duration: dur, ease: 'power2.in', stagger: st }, at);
  blurTween(tl, el, at, 0, 45, dur + 0.1, { ease: 'power2.in', ...VERT });
};

const mark = (hl, at) => {
  const i = $('i', hl);
  if (i) tl.fromTo(i, { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: 'power3.out', immediateRender: false }, at);
  tl.fromTo($('.hl-t', hl), { opacity: 0, yPercent: 60 }, { opacity: 1, yPercent: 0, duration: 0.7, ease: 'power4.out', immediateRender: false }, at);
};

const popDot = (el, at) =>
  tl.fromTo(el, { opacity: 0, yPercent: 60 }, { opacity: 1, yPercent: 0, duration: 0.5, ease: 'power4.out', immediateRender: false }, at);
```

### Strict Typographic Rules

1. **Sentence case at weight 500–600**. Reserve all-caps ultra-bold weight 800 for at most ONE climactic scene.
2. **Word highlights are optional**. If omitted, establish visual hierarchy via character stagger cadence, typographic scale, or adjacent product UI elements.
3. **Alternating scene parameters**: Consecutive scenes MUST NOT share identical sizes (`sm`/`md`/`lg`/`xl`), entrance vectors (`inUp`/`inLeft`), or layout coordinates (centered vs. docked adjacent to props).
4. **Titles default to NO trailing periods**. Use `?` only for genuine questions, and periods only when deliberately establishing a staccato rhythm across two short statements.
5. **Positioning adjacent to props**: When text accompanies a mockup or card, position it to the side or above (`.pos` with explicit `left`/`top`), rather than forcing it dead center over the prop.

---

## 1b. Contrast: Background Subordinate to Text

A common failure mode is deploying 96 blooming light particles directly behind text, causing white letterforms to lose edge definition against a noisy backdrop.
- **The Text Pocket**: In the physical bounding box behind text, background luminance must be $\le 25\%$ (dark) for white copy, or $\ge 80\%$ (light) for dark copy. If the background contains active visual elements, insert an unobtrusive `.pocket` element (radial gradient: 55% black $\rightarrow$ transparent) beneath the text, fading in with the headline.
- **Background Particles & Noise**: Tint particles with dark tones from the brand palette, keep opacity $\le 0.35$ within text zones, and limit bright elements to $\le 40$ visible items.
- **Grayscale Contrast Test**: Convert a full-text keyframe snapshot to grayscale. If any background element matches the luminance of the headline letterforms, the background is excessively bright.
- **Light/Dark Cadence**: Alternate between dark and light scenes across segments (e.g. high-key off-white product tour $\rightarrow$ deep dark payoff). Inter-scene contrast is vastly more impactful than stacking effects inside a single scene.

---

## 2. Directional Motion Blur (`feGaussianBlur` SVG Filter)

CSS `filter: blur()` blurs isotropically in all directions, looking out-of-focus. Motion blur in professional software blurs strictly **along the vector of motion**.
SVG `feGaussianBlur` accepts distinct `stdDeviation="x y"` parameters:

```js
// Create filter container once per tween and expand filter bounds (default clips blur trails)
f.setAttribute('x', '-70%');
f.setAttribute('y', '-70%');
f.setAttribute('width', '240%');
f.setAttribute('height', '240%');

// Tween standard deviation: 30 → 0 on entrance, 0 → 50 on exit
// Set the perpendicular axis to near zero:
blur.setAttribute('stdDeviation', `${v} ${v * 0.08}`); // Horizontal motion
```

**Performance Rule**: Apply the filter when the tween begins; remove it immediately on completion (`filter: 'none'`). Persistent SVG filters force the browser to re-rasterize DOM elements on every frame.

---

## 3. Camera Dynamics: 3D Push-Through

Push-through transitions should be rationed to $\sim 1$ per video and used only when narratively motivated. Execute across the unified `#world` rig:

```js
const camThrough = (atCut, { push = 2.0, from = 1.5, inDur = 0.5, outDur = 0.95,
                            oOut = '50% 50%', oIn = '50% 50%' } = {}) => {
  tl.set(rig, { transformOrigin: oOut }, atCut - inDur);
  tl.to (rig, { scale: push, duration: inDur, ease: 'power2.in' }, atCut - inDur);
  tl.set(rig, { transformOrigin: oIn, scale: from }, atCut);
  tl.to (rig, { scale: 1, duration: outDur, ease: 'power3.out' }, atCut);
};
```

1. Accelerate IN toward outgoing text (`power2.in`), cut at maximum velocity.
2. Decelerate OUT from incoming text initialized at oversized scale (`power3.out`).
3. Scale discontinuities at the cut point remain invisible because they occur during frame-clearing light leaks or camera occlusions.
4. Set `transformOrigin` to the target subject's coordinate center (e.g. `'50% 22%'` for elevated headlines).

---

## 3b. Shot Scale & Framing: Camera to Element

Zooming in motion design means **changing shot scale**: moving close to an active storytelling element, then pulling back. A subtle $2\%$ camera breathing drift is imperceptible background texture, not a solution for static staging.

### Shot Scale Vocabulary

- **Wide**: Full composition visible; used when multi-element layouts or wide headlines require global viewing.
- **Medium Close-Up**: The primary storytelling subject occupies roughly $35–50\%$ of frame height with surrounding context.
- **Close-Up**: A single detail fills the majority of the frame; used for tactile emphasis, clicks, or micro-interactions.

### Choreographing Scale Shifts

- Focus on the active storytelling element: newly entering text, an incoming prop, or a clicked button.
- Rhythm: Close on Element A $\rightarrow$ pull back to wide as the full scene resolves $\rightarrow$ cut/pan close to Element B.
- New scenes may initialize directly in close-up without prior camera tweening.
- Static holds (logos, concluding CTAs) should maintain slow, continuous forward push (`sine.inOut`) to prevent visual death.

```js
const CAM = { s: 1, fx: W / 2, fy: H / 2 };
const shot = (at, dur, s, fx, fy, ease = 'power2.inOut') => tl.to(CAM, { s, fx, fy, duration: dur, ease }, at);
const cutTo = (at, s, fx, fy) => tl.set(CAM, { s, fx, fy }, at);

function applyCam(t) {
  const s = CAM.s * (1 + 0.01 * Math.sin(t * 0.7)); // Subtle breathing drift
  let tx = W / 2 - CAM.fx * s, ty = H / 2 - CAM.fy * s;
  tx = Math.min(0, Math.max(W - W * s, tx));
  ty = Math.min(0, Math.max(H - H * s, ty));
  world.style.transform = `translate(${tx}px,${ty}px) scale(${s})`;
}
```

---

## 4. 3D Per-Word Tracking Pans

Reserved for 1 (at most 2) special statements: a single headline rendered wider than the viewport, tracked by a sweeping camera while words illuminate as the lens crosses them.

```js
tl.set(line, { x: W / 2, xPercent: -6, rotateY: 10 });
tl.to (line, { xPercent: -94, duration: 2.9, ease: 'power1.inOut' });
tl.to (line, { rotateY: -10, duration: 2.9, ease: 'power1.inOut' });

tl.fromTo(words, { opacity: 0.2, yPercent: 16, scale: 0.96 },
  { opacity: 1, yPercent: 0, scale: 1, duration: 0.55, ease: 'power2.out',
    stagger: panDur / (nWords - 1) * 0.95 });
```

Words ahead of the camera wait dimmed ($\sim 20\%$ opacity); traversed words remain fully illuminated. Animating `rotateY` creates an authentic curved dolly track feel.

---

## 4b. Scene Transition Architecture & Hierarchy

Avoid cheap translation whip-pans that reveal stage borders and jarring rotation cuts. Follow this hierarchy:

1. **Continuous Camera Breathing** (Base layer): Camera rig drifts gently ($\pm 4–5\%$ scale, alternating vectors, continuous `sine.inOut`).
2. **Choreographed Overlapping Elements**: Outgoing elements exit swiftly (`power2.in` with directional blur) WHILE incoming elements begin entering. The temporal overlap creates seamless continuity.
3. **Volumetric Object Wipes**: A physical hero prop sweeps across the lens, momentarily occluding the canvas at the cut timestamp.
4. **Motivated Zooms**: Rapid push-through transitions used strictly when entering a screen, portal, or emblem.

---

## 4c. Menu of Motion Transitions (Depth-Driven)

Select transitions from this menu. Projects must employ at least TWO transition types, at least ONE with 3D depth, with wipes limited to at most two occurrences:

| # | Transition Technique | Execution | Aesthetic Feel |
|---|---|---|---|
| 1 | 3D Push-Through | `camThrough` on layered planes with varied `translateZ` values | Diving into virtual space |
| 2 | Rotating 3D Cards | Next card rotates in from depth (`rotateY: -35° → 0`) while outgoing card recedes | Tactile, premium |
| 3 | Volumetric Object Wipe | Extruded logo or glass tile passes close to lens ($1 \rightarrow 2.5\times$ scale) with directional blur | Cinematic, optical |
| 4 | Soft Light Leak Sweep | Ambient radial bloom sweeping across $40–60\%$ of the frame at the cut point | Gentle, atmospheric |
| 5 | Branded Mask Reveal | Subsequent scene revealed through expanding silhouette of brand symbol | Strong identity reinforcement |
| 6 | Directional Whip Pan | World translates $120–200\text{px}$ with directional blur over $0.3\text{s}$ | Energetic, kinetic |
| 7 | Rack Focus Depth Shift | Outgoing scene blurs and scales back; incoming scene sharpens from foreground | Narrative, cinematic |
| 8 | Overlapping Choreography | Zero cuts: outgoing elements exit while incoming elements assemble in continuous space | Fluid, organic |
| 9 | Background Shift Behind Cut | Shift between dark/light canvases while frame is momentarily occluded | Clean chapter division |

---

## 5. Cinematic Transition Light Leaks

Light leaks must be soft, ambient radial glows bleeding in from viewport edges — never harsh sweeping lasers:
- Circular container $\sim 2400\text{px}$, radial gradient (illuminated core $\rightarrow$ transparent), `filter: blur(64px)`, `mix-blend-mode: screen`.
- **Placed at the absolute TOP of the layer stack** (above vignettes and camera rigs).
- Enter on `sine.in` ($40\%$ duration), exit on `sine.out` ($60\%$ duration), drifting slowly along diagonal vectors.
- Tint with accent colors from the brand palette.

---

## 6. Professional Glow Mechanics

**Applying glow to all headline copy results in muddy, amateurish typography.**
- **Headlines**: Clean, solid white copy + crisp readability shadow: `text-shadow: 0 4px 28px rgba(0, 0, 0, 0.5)`. Zero glow filters.
- **Reserve Glow for Physical Objects**: UI tiles, illuminated badges, spectrum bars, and hardware edges.
- **Realistic UI Elements**: App store badges, form inputs, and system buttons must have ZERO glow.
- **WebGL Post-Processing Bloom**: Maintain `threshold ≥ 0.5`. Low thresholds cause background particles to bloom uncontrollably into a washed-out white frame.

---

## 7. State-Driven Three.js Environments

Layer order (back to front), driven deterministically by `state`:
- **Nebula**: Plane with fractional Brownian motion (fBm) shader, `NormalBlending` (NEVER additive blending, which blows out through bloom filters). Vertical gradient: `exp(-((y - 0.02) * 3.4)^2)` illuminates the horizon while dimming the upper frame by $70\%$.
- **Particle Dust**: 1000–1500 `Points`, scale proportional to $1/z$, shimmering via per-particle sine functions.
- **Perspective Floor Grid**: Shader with `fwidth` antialiasing, fading completely before reaching the horizon line. Opacity maintained at $0.2–0.6$.
- **3D Hero Ornaments**: `Shape` geometry $\rightarrow$ `ExtrudeGeometry` with beveling $\rightarrow$ `MeshStandardMaterial` lit by DirectionalLight. Rock Y-axis oscillation $\pm 0.55\text{ rad}$; do not rotate $360^\circ$ (thin geometry collapses into a 1px line edge-on).
- **Tunnel Speed Particles**: Short particles (length 0.8–2.5), muted brand hues, $\le 300$ elements, opacity $\le 0.6$.
- **Post-Processing Bloom**: `UnrealBloomPass(strength: 0.75–0.95, radius: 0.7, threshold: 0.52)`.

---

## 7b. High-Key Backdrops & Inter-Scene Shifts

Dark canvases are one option among many. Changing background environments across narrative segments creates strong visual pacing (e.g. dark problem statement $\rightarrow$ high-key product demo $\rightarrow$ rich brand color payoff).

```css
.paper {
  position: absolute;
  inset: 0;
  opacity: 0;
  visibility: hidden;
  background: linear-gradient(180deg, #F7FAFF 0%, #EEF4FF 55%, #E6EEFF 100%);
}
.paper .b { position: absolute; border-radius: 50%; pointer-events: none; }
.paper .b1 {
  left: -260px; top: -380px; width: 1100px; height: 1100px;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent-lit) 38%, #fff) 0%, transparent 68%);
}
```

Shift backgrounds **behind transitions**:
```js
tl.set('#paper', { autoAlpha: 1 }, atCut);
tl.to('#gl', { opacity: 0, duration: 0.25 }, atCut);
tl.to('.vignette', { opacity: 0.35, duration: 0.4 }, atCut);
```

---

## 7c. Menu of Background Motion Languages

Background motion must be selected intentionally in the style brief and differ from previous projects:

| # | Motion Pattern | Kinetic Character | Implementation |
|---|---|---|---|
| 1 | Textured Surface + Camera Drift | Quiet, premium | Subtle continuous camera breathing over paper/grain |
| 2 | Shifting Multi-Stop Gradients | Modern, fluid | Tween gradient angle or `background-position` over 8–15s |
| 3 | Floating Organic Blobs | Friendly, approachable | 2–4 blurred radial spheres drifting $\pm 60\text{px}$ over 4–6s |
| 4 | Deterministic Film Grain | Physical, cinematic | SVG noise offset updated from timeline `t` |
| 5 | Segment Light Sweep | Polished, elegant | Single diagonal beam sweeping across frame per scene |
| 6 | Rotating Geometric Hulls | Bold, branded | Brand silhouettes rotating slowly ($20–40\text{s}$ period) on 2 parallax planes |
| 7 | Rising Micro-Particles | Atmospheric | Upward drifting embers or dust; opacity $\le 0.35$ behind copy |
| 8 | Breathing Structural Grid | Technical, precise | Grid line scale/opacity oscillating $1.0 \leftrightarrow 1.04$ over 6–10s |
| 9 | Drifting Ghost Typography | Editorial, architectural | Massive semi-transparent letterforms drifting across canvas |
| 10 | Thematic Parallax Photo | Narrative, documentary | Multi-plane photo cutout drift with foreground depth |
| 11 | Horizontal Velocity Streaks | Speed, telemetry | High-speed horizontal streaks (reserved strictly for velocity topics) |
| 12 | Snapping Brand Color Fields | High-energy pop | Rapid planar snaps ($0.15–0.3\text{s}$) triggered by props or beats |

---

## 7d. Menu of Background Surfaces (Layered, Never Flat)

Every background must consist of $\ge 2$ composite layers (base surface + ambient illumination / texture):
- **Horizon Glow**: Near-black base + radial horizon highlight rising from bottom border.
- **Diagonal Duotone**: $160^\circ$ linear gradient transitioning from dark brand shade to base obsidian tone.
- **High-Key Mesh Blobs**: Clean off-white canvas overlaid with 3–4 drifting radial brand color spheres.
- **Spotlight Vignette**: Radial spotlight illuminating center coordinate with tinted ambient falloff.
- **Grainy Gradient**: Deep saturated gradient shapes overlaid with a uniform fine-grain dither layer.

### Grainy Gradient Recipe

```html
<svg width="0" height="0" style="position: absolute">
  <filter id="grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" stitchTiles="stitch" />
    <feColorMatrix type="saturate" values="0" />
  </filter>
</svg>
<div class="grain" id="grain"></div>
```
```css
.grain {
  position: absolute;
  inset: -60px;
  pointer-events: none;
  filter: url(#grain);
  opacity: 0.22;
  mix-blend-mode: overlay;
}
```
```js
// Deterministic grain jitter: updates at 12 fps from timeline time, never Math.random()
const grainAt = t => {
  const k = Math.floor(t * 12);
  grainEl.style.transform = `translate(${k * 37 % 60 - 30}px, ${k * 61 % 60 - 30}px)`;
};
```

---

## 7e. Object Rendering Style Families

Maintain one unified rendering family across all props in a project:
- **Flat Solid**: Clean vector geometry, flat color fills, zero ambient shading.
- **Soft 3D / Clay**: Pastel matte materials, thick rounded geometry, soft ambient occlusion (`MeshStandardMaterial`, roughness 0.8).
- **Glossy Plastic**: Specular highlights, environment map reflections (`MeshPhysicalMaterial`, clearcoat 1.0).
- **Refractive Glass**: Transparent volumes, refractive dispersion, illuminated internal cores.
- **Technical Isometric**: $30^\circ$ isometric projection, orthographic camera alignment.
- **Realistic PBR**: Photoreal materials (brushed metal, marble) imported as pre-rendered 2× assets.
- **Neon Line**: Fine glowing strokes, concentric outlines on dark surfaces.

---

## 8. Dynamic UI Mockups & Camera Tracking User Clicks

Mockup screens must replicate the target application's real fonts, colors, and components.
When demonstrating a user interaction, the camera must participate in the action:
1. **Anticipatory Push**: $0.3–0.5\text{s}$ prior to the click, the camera pushes into the target area (scale $1.4–2.2$, `power2.inOut`).
2. **Clear Interaction Beat**: Cursor pauses $0.2\text{s}$, button compresses (scale $0.92 \rightarrow 1.0$) with subtle highlight flash.
3. **Follow the Result**: Camera glides smoothly or pulls back to reveal the resulting interface transformation.

```js
const camTo = (ui, target, at, { s = 1.8, dur = 0.8, fy = 0.45 } = {}) => {
  const W = ui.offsetWidth, H = ui.offsetHeight;
  const cx = target.offsetLeft + target.offsetWidth / 2;
  const cy = target.offsetTop + target.offsetHeight / 2;
  tl.to(ui, { x: W / 2 - cx * s, y: H * fy - cy * s, scale: s, duration: dur, ease: 'power2.inOut' }, at);
};
const camWide = (ui, at, dur = 0.9) =>
  tl.to(ui, { x: 0, y: 0, scale: 1, duration: dur, ease: 'power2.inOut' }, at);
```

---

## 9. Deterministic Typewriters, Counters, and Telemetry

Never use `setInterval` or real-time timestamp accumulation:
- **Typewriter Text**:
  ```js
  tl.fromTo(obj, { i: 0 }, {
    i: str.length,
    ease: 'none',
    onUpdate: () => { el.textContent = str.slice(0, Math.round(obj.i)); }
  }, at);
  ```
- **Incremental Counters**: Compute value strictly as a mathematical function of timeline time: `val = Math.round(startVal + progress * delta)`.
- **Dynamic Waveforms**: Sum discrete high-frequency sine waves: `Math.sin(t * freq1) + Math.sin(t * freq2)`.

---

## 9b. Video as Timeline-Locked Footage Layers

Video files can be deployed as footage layers inside device frames, card containers, and masked shapes:
- Animate the **CONTAINER**, not the `<video>` element directly.
- Mount video clips using the universal `clip()` helper:
  ```js
  clip($('#v1'), { at: 4, in: 1.5, out: 6, rate: 1, hold: false });
  tl.set('#box1', { autoAlpha: 1 }, 4);
  tl.fromTo('#box1', { scale: 0.8 }, { scale: 1, duration: 1, ease: 'power3.out', immediateRender: false }, 4);
  ```
- Timeline scrubber updates video frame seeking deterministically via `OPENER.seekFrame(t)`.

---

## 10. Engine Traps and Solutions

| Symptom | Underlying Cause | Corrective Architecture |
|---|---|---|
| Entire screen washes out to pure white | Low bloom threshold + additive blending | Set bloom threshold $\ge 0.52$; use `NormalBlending` on background shaders |
| Elements flash before animation cue | CSS selector specificity overrides initial `opacity: 0` | Never write `opacity` in high-specificity rules; allow initial CSS state to govern until GSAP animates |
| Edits ignored during local development | Browser heuristic caching of ES modules | Run `scripts/serve.py` with explicit `Cache-Control: no-store` headers |
| 3D planar meshes collapse into 1px lines | Mesh rotated $90^\circ$ flat to camera on Y-axis | Constrain rotation using gentle sine wobbles ($\pm 0.55\text{ rad}$) |
| SVG blur trails clipped by rectangular box | Default SVG filter bounding box too tight ($110\%$) | Expand filter coordinates: `x="-70%" y="-70%" width="240%" height="240%"` |
| Headlines appear dull and washed out | Heavy stacking of glow and shadow filters | Remove glow from typography; use crisp drop shadow only |
| Bright line cutting across horizon | Floor grid lines converging at infinite vanishing point | Fade grid alpha to zero well before the horizon boundary |
| Scrubbing produces non-deterministic frames | Code reads system clock or `Math.random()` | Enforce strict mathematical determinism from `tl.time()` |
| Text splits miscalculate letter widths | Typography split before web fonts finish loading | Wrap execution inside `document.fonts.ready` |
| Elements twitch during numeric updates | Variable proportional numeral widths (e.g. "1" vs "8") | Apply `font-variant-numeric: tabular-nums` and fixed container widths |
