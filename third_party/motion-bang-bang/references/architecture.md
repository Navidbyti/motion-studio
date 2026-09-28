# Architecture — Project Structure and Design Rationale

Every decision documented here originated from real development errors before finding the correct solution. Understanding the **why** behind each choice is more critical than the code snippets themselves.

## Directory Structure

```
project/
├── index.html          Markup for all scenes + SVG motion blur filters
├── css/app.css         Color tokens, scene layouts, initial hidden states
├── js/three-scene.js   State-driven WebGL world (background, particles, ornaments, bloom)
├── js/timeline.js      The SOLE location where time is defined (GSAP master timeline)
├── js/util.js          splitChars + blurTween (directional motion blur)
├── js/main.js          Glue: stage fitting, render loop, developer panel
└── tools/
    ├── serve.py        Local zero-cache dev server (Cache-Control: no-store)
    └── export-frames.mjs Frame-by-frame exporter (Puppeteer)
```

For rapid prototypes, this can be bundled into a single file (see `assets/starter-opener.html`). Split into the modular structure above when a project exceeds 3 complex scenes.

## Fixed Stage: 1920×1080 Scaled Uniformly

```css
#stage {
  position: fixed;
  left: 50%;
  top: 50%;
  width: 1920px;
  height: 1080px;
  transform: translate(-50%, -50%) scale(var(--fit));
  overflow: hidden;
}
```
```js
const s = Math.min(innerWidth / 1920, innerHeight / 1080);
document.documentElement.style.setProperty('--fit', s);
```

**Why**: Visual compositions must never alter based on browser window dimensions. A layout approved on a 27-inch desktop monitor must render bit-for-bit identical when recorded or played on smaller displays. Window dimensions should scale zoom level only, never responsive layout flows.

## Camera Rig: `#world`

```
#stage
└── #world            ← Camera rig: SCALED and TRANSLATED by the timeline
    ├── <canvas>      ← WebGL (3D background, particle systems)
    ├── .bgfx         ← Gradient overlays (blend-mode: screen)
    └── #dom          ← All text and UI scenes
├── .leak             ← Light leaks: OUTSIDE the world, top-most viewport layer
├── .vignette, .grain ← Screen-space camera lens textures
```

**Why `#world` encapsulates the canvas**: When the camera zooms into the world, both foreground text AND background environment must scale together in perspective. Zooming text alone creates a fake, synthetic appearance; scaling the entire world feels like an authentic optical camera move.
Conversely, light leaks, film grain, and lens vignettes **MUST remain outside `#world`**: they represent physical lens artifacts and screen-space phenomena, not objects inside the 3D scene.

## State-Driven WebGL Architecture

The Three.js scene must have zero internal concept of time. It exposes a single state object:

```js
const state = {
  grid: 0, dust: 0.5, nebula: 0.6, stars: 0, tunnel: 0, flow: 0,
  camX: 0, camY: 0, camZ: 16, camRoll: 0, bloom: 0.85, shake: 0,
  heroO: 0, heroS: 1, heroX: 0, heroY: 0, heroZ: 6,   // Primary hero ornament
};
```

The GSAP master timeline directly tweens these numerical properties. The WebGL render function receives timeline time: `render(t)` where `t = tl.time()`.

**Why**: This enforces a single source of truth for time. Scrubbing, pausing, reversing, and frame-by-frame exporting function flawlessly because the WebGL canvas possesses no autonomous clock.

**The `flow` Rule**: Continuously flowing objects (particle rain, tunnel travel) must be stored as **DISTANCE** tweened over time (`flow: '+=300'`). The position of each particle is calculated deterministically:
`pos = (seed + flow * speed) % span`.
**NEVER use accumulation**: `pos += speed * dt`. Accumulation introduces frame-rate variance, breaking scrub predictability and frame-accurate exports.

## Timeline: Absolute Seconds

```js
tl.fromTo(chars, { ... }, { ... }, 8.10);   // ← Absolute timestamp, NOT "+=0.3"
```

**Why**: Scene rundowns are structured by absolute timestamps. Writing matching absolute timestamps in code makes the sequence immediately readable at a glance. Shifting the duration of one scene does not accidentally cause unpredictable ripple effects across subsequent scenes. Define a single `DURATION` constant.

## Initial States in CSS, Not GSAP

```css
.hero, .line, .obj, .ornament { opacity: 0; }
```
```js
tl.fromTo(el, { opacity: 0, y: 60 }, { opacity: 1, y: 0, immediateRender: false }, 8.10);
```

**Why**: When paired with `immediateRender: false`, CSS maintains the hidden state of elements before their tween starts. Without this pattern, elements flash on screen during the very first frame before GSAP initializes.

**KNOWN TRAP**: CSS selector specificity clashes. If `.card.ghost { opacity: 0.85; }` overrides `.card { opacity: 0; }`, the ghost card flashes before its cue. Never define opacity rules in selectors that have higher specificity than the initial hidden state; let GSAP set the final animated property.

## Determinism — Prohibition Matrix

| Prohibited | Permitted Replacement |
|---|---|
| `Math.random()` in render loops | High-frequency sine wave: `Math.sin(t * 137.2)` |
| `Date.now()` or `performance.now()` | `tl.time()` passed as a parameter |
| `setInterval` for typing/counter text | GSAP tween `{ i: 0 → n }` + `onUpdate` string slice |
| Frame accumulation: `pos += v * dt` | Pure function: `position = f(seed, state.flow)` |
| `Math.random()` during setup only | Permitted: generate fixed seeds once at initialization, never per frame |

## Dev Server Must Be Zero-Cache

Standard servers like `python -m http.server` allow browsers to aggressively cache local ES modules via heuristic caching. Edits appear ignored, leading to phantom debugging.
Always use a development server that explicitly sends `Cache-Control: no-store` headers (`scripts/serve.py`). Because ES modules cannot load over `file://` due to CORS, a local dev server is required during modular development.

## Verification vs. Export: Two Distinct Operations

- **Visual Verification** (run after every batch of changes): `scripts/snap.mjs` captures 6–20 key seconds via `OPENER.seek(t)`. The resulting contact sheet is inspected by eye to verify layout and timing. If Node is absent, use `?debug=1` and capture screenshots manually.
- **Export** (executed only when the user requests an MP4 video file): Renders every individual frame at 60 fps. Never run a full export just to check your work; full exports take significant time and produce thousands of temporary files.

## Video Export Pipeline

Never rely on screen recording for final deliverables (screen capture introduces dropped frames and stutter). Because the entire animation is deterministic:
1. Seek timeline: `tl.time(frame / fps)`.
2. Wait two `requestAnimationFrame` ticks (first for GSAP to apply DOM styles, second for the WebGL canvas to draw).
3. Capture screenshot.
4. Repeat for all frames.

`scripts/export-frames.mjs` automates this via Puppeteer. Stitch into high-quality MP4 using FFmpeg:

```bash
ffmpeg -framerate 60 -i frames/f%05d.png -c:v libx264 -pix_fmt yuv420p -crf 16 out.mp4
```

Always expose `window.OPENER = { tl, DURATION }` globally so export scripts and developer consoles can control playback directly.

## Developer Controls — Hidden by Default

Do not show player UI in the final deliverable.
- Default: Autoplay on load, seamless loop on finish, `R` to restart, `Space` to pause.
- `?debug=1`: Displays playback toggles, scrub slider, and precise timestamp clock (`t.toFixed(2)`).
- `?clean=1`: Disables UI controls and halts autoplay (designed for automated export scripts).

## Standalone Single-File Deliverable (Zero Server Required)

While modular multi-file structures are convenient during development, the final deliverable presented to the user must be a single, standalone `index.html` opened by double-clicking:

- CSS in `<style>` and JS in `<script type="module">` are embedded inline. Chrome blocks external module scripts (`<script type="module" src="...">`) when run over `file://` (null origin CORS error), but permits inline module scripts to import dependencies from HTTPS CDNs.
- Import maps, GSAP, and Three.js load over HTTPS CDN URLs (requires internet access, but zero local server).
- Local assets (SVGs, images) use relative paths (`<img src="icon.png">` works reliably on `file://`).
- Avoid `fetch()` or XHR calls to local files, which are blocked on `file://`.
- Inform users that Node and Python are strictly development utilities; viewing the deliverable requires only a web browser.

## Universal Web Video: Dual-Mode Compatibility (HyperFrames Ready)

Every composition produced by this skill is **Universal Web Video**: it functions simultaneously as a zero-dependency standalone HTML page and as a first-class **HyperFrames** composition without code modification or format conversion.

### The Universal Contract
1. **Composition Root**: `#stage` defines `data-composition-id="main"`, `data-width="1920"`, and `data-height="1080"`.
2. **Timeline Registry**: In addition to `window.OPENER.tl`, the master timeline is registered on `window.__timelines["main"] = tl`.
3. **Environment Sniffing**:
   ```javascript
   const isHF = !!(window.__HYPERFRAMES__ || window.parent?.__HYPERFRAMES__ || location.search.includes('hf'));
   ```
   - **Standalone Mode** (`!isHF`): Autoplay enabled on font load, seamless loop, and optional in-browser scrubber via `?debug=1`.
   - **HyperFrames Studio / Renderer Mode** (`isHF`): Autoplay and in-browser debug UI are automatically suppressed. HyperFrames takes full control of playback and transport via `window.__timelines`.
4. **Seek-Safe Camera & Canvas Updates**:
   ```javascript
   tl.eventCallback('onUpdate', () => { applyCam(); render(); });
   ```
   Ensures that when HyperFrames steps through arbitrary time slices across parallel workers, the camera matrix and WebGL canvas update synchronously before each screenshot.
5. **Decoupled SFX Pipeline**:
   The output MP4—whether rendered via `scripts/export-frames.mjs` (Puppeteer) or `npx hyperframes render` (HyperFrames parallel workers)—is processed post-render by `scripts/sfx-cues.mjs` and `scripts/sfx-mix.mjs` with `-c:v copy`, ensuring zero re-rendering for audio adjustments.
