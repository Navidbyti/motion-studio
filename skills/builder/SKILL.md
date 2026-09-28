---
name: builder
description: Motion Studio stages 5-6. Implements the approved beat map as HyperFrames scene sub-compositions (HTML + GSAP) using the Studio runtime helpers; renders styleframes for gate C. Use for any composition code.
---

# Builder (stages 5-6)

You implement. Timing, numbers and crops come from files the director and beat editor approved. You never type them. Read `skills/house-style` and HyperFrames' `/hyperframes-core` skill (`npx hyperframes skills`) before writing HTML.

## Project anatomy

```
index.html            thin host: scene slots (generated), footage <video>/<audio> and music at the root, host timeline "main"
compositions/<id>.html one sub-composition per beat-map scene (created by `mstudio beatmap apply`)
timing.js data.js reframe.js   generated; never edit
studio.js house.css brand.css  runtime helpers and tokens
```

## Scene file rules (HyperFrames contract)

- Everything lives **inside `<template>`**: `<style>`, markup and `<script>`. `<head>` content is dropped.
- The root is `<div id="root" data-composition-id="<scene id>" …>`, styled via `#root`. The timeline registers as `window.__timelines["<scene id>"]`.
- **Prefix every id with the scene id** (`hook-title`). Ids must be unique across the assembled page.
- No `<video>`/`<audio>` inside a timed element. Footage stays at the root of `index.html`.
- Never tween a `.clip` element's `visibility`, `display` or `autoAlpha`. Animate children.
- Don't set a CSS `transform` on an element that GSAP also transforms; use `fromTo`.
- Fonts come from `fonts/` via house.css. Don't add a font without an `@font-face` and a credits entry.

## Timing: always through Studio

```html
<script>
  (function () {
    const S = Studio.forScene("hook");            // scene-local times
    const tl = gsap.timeline({ paused: true });
    S.hit(tl, "hook.title", "#hook-title", { scale: 1.25, opacity: 0, filter: "blur(12px)" },
                                           { scale: 1, opacity: 1, filter: "blur(0px)", ease: "expo.out" });
    S.after(tl, "hook.title", "#hook-title", { letterSpacing: "-0.02em" }, 0.4);   // settle
    S.hit(tl, "hook.sub", "#hook-sub", { yPercent: 60, opacity: 0 }, { yPercent: 0, opacity: 1, ease: "power3.out" });
    S.drift(tl, "hook.hold", "#hook-stack", { scale: 1.015, transformOrigin: "0% 50%" });
    window.__timelines["hook"] = tl;
  })();
</script>
```

- `S.hit(tl, id, target, from, to)` starts `anticipation` frames early and **lands on the impact frame**. On a scene's first frame it becomes an on-the-cut hit (`to.settle` sets the settle time).
- `S.counter(tl, "#n", "<value key>", { from, start: "<event>", impact: "<event>" })` counts up and lands exactly on the bound display string.
- `Studio.fmt(key)` gives a bound value's display text. `Studio.series(name).points` gives chart data.
- Host timeline (`index.html`): `Studio.host.reframe(tl, "<media id>", "#<video id>")` applies the approved crop keyframes.
- Secondary motion that isn't a hit (drift, parallax, grain) may use literal durations **inside** a hit or hold window. Anything that *lands* must be an event.

## Charts and numbers

Follow `skills/data-viz`: build charts in SVG from `Studio.series()`, draw every point, give axes `data-provenance="axis"`, and wrap counters and values in elements whose text comes only from Studio.

## Footage

Follow `skills/footage`: `<video id="v02" data-media="v02" src="footage/conformed/…mp4" muted playsinline>` inside a non-timed full-frame `<div class="frame">` at the root, plus `<audio id="v02-audio" data-media="v02" src="…wav" data-volume="0.5">` for natural sound. `mstudio beatmap apply` writes their timing.

## Stage 5: styleframes (gate C)

Build the 3-5 key moments first (the hook, the special moment, the payoff, and one data or footage scene). Then:

```bash
mstudio styleframes <slug> --events hook.title,launch.flash,payoff.logo
```

Compare the PNGs in `styleframes/` with the style brief (palette sources, type, the two-level text rule, the safe area). Show them in interactive mode, then `mstudio gate <slug> C --by …`.

## Stage 6: build the rest

Build every scene, run `mstudio qa <slug> --composition-only` and fix every error. Preview with `mstudio preview <slug>` (Studio in the background) when you need to scrub. Keep motion purposeful: each tween maps to an event or to the drift of a hold.
