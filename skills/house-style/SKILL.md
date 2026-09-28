---
name: house-style
description: Motion Studio house style. Tokens, type scale, named easings, hit-scale values, camera rules, safe areas per ratio, Persian/RTL rules and the banned list. Load before every stage; a brand in brands/<name>/ overrides tokens, never the rules.
---

# House style

The look every Motion Studio video starts from. A project's `brand.css` may redefine the **tokens**. The **rules** (hit scale, easing vocabulary, safe areas, bans) apply to every brand. Tokens live in `templates/composition/house.css` and are copied into each project.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--ink` | `#0b0d10` | background |
| `--ink-2` | `#14181d` | raised surfaces, wipes |
| `--paper` | `#f4f1ea` | primary type |
| `--muted` | `#9aa0a8` | secondary type, axes |
| `--line` | `rgba(244,241,234,.16)` | hairlines, grids |
| `--accent` | `#ff5a1f` | **the one thing to look at**: max one accent object per frame |
| `--accent-2` | `#3dd6c6` | secondary emphasis; never competes with the accent |
| `--data-1..4` | `#ff5a1f #3dd6c6 #f2c14e #8e7cff` | categorical data, in this order |
| `--data-neutral` | `#5c6370` | de-emphasised bars/lines |
| grain | 0.06 | optional film grain overlay |
| radius / stroke | 28px / 4px | cards, frames / lines, rules |

**Every color in a style brief needs a source:** a house token, a brand guideline, or a sampled pixel from supplied material (give the file and coordinates). Invented colors are not allowed.

## Type

- Fonts (OFL, shipped in `fonts/`): **Inter** for display and text, **JetBrains Mono** for numbers, labels and data, **Vazirmatn** for Persian. A brand may swap them, but three families is the maximum.
- Scale at a 1080 px wide canvas: hero 144 · display 112 · h1 88 · h2 64 · body 44 · label 34 · **minimum 30** (QA fails anything smaller; 16:9 minimum 28 at 1080 px high).
- Display: weight 800, tracking −0.035em, line-height 0.95. Labels: mono, uppercase, +0.02em.
- At most **two text levels on screen at once** (headline + one supporting line or label).
- Numbers use tabular figures (`.num`). Negative values use the real minus sign (−); positive changes in callouts get a plus sign.

## Motion vocabulary (GSAP eases)

| Name | Ease | Default duration | Use |
|---|---|---|---|
| `slam` | `expo.out`, from scale 1.25 / blur 12px | anticipation 3 frames, settle 8 frames | big hits on downbeats |
| `settle` | `back.out(1.6)` | 8-12 frames after impact | follow-through after a slam or punch |
| `enter` | `power3.out`, y 24-60px, opacity 0→1 | 12-18 frames | beat entrances |
| `punch` | `back.out(2)`, scale 1.12→1, rotate ±2° | 2 frames anticipation, 8 settle | snare hits, stamps |
| `snap` | `power4.inOut` | 8-12 frames | wipes, panel moves, camera cuts |
| `drift` | `sine.inOut`, scale ≤ 1.02 or ≤ 20px | the whole hold | keeps held frames alive |
| `exit` | `power2.in` | 6-10 frames | leaves before the next downbeat, never after it |

## Hit scale (what each musical tier is allowed to move)

| Tier (beat map) | Musical event | Visual budget |
|---|---|---|
| `scene` | drop / section change | full-frame change: cut, wipe, flood, push-through (≤ 12% camera scale); the special moment lives here |
| `big` | downbeat | one hero element: slam (scale 1.25→1), color-field slam, major type; **max 1 per bar** |
| `punch` | snare / backbeat | text punch, stamp, counter tick: scale ≤ 1.12, rotate ≤ 2° |
| `entrance` | beat | element entrances: y ≤ 60px, opacity, blur ≤ 6px |
| `micro` | 8ths / hats | ≤ 4% scale pops, flickers; **sparingly** (≤ 4 per bar) |
| `hold` | quiet bars | nothing new arrives; drift only |
| `word` | spoken word (VO) | the on-screen word reveals *on the word*, not the beat |

Anticipation: motion that should impact on a beat starts 2-4 frames early so its peak lands on the beat frame. `Studio.hit` does this from the beat map's `anticipation`. Hits on a scene's first frame land on the cut.

## Camera

- Drift ≤ 1.5% scale or ≤ 20px over 4 bars during holds. Stop the drift before a big hit.
- Push-through or whip only on `scene` tier events. The camera *cuts* on downbeats and *moves* between them.
- Never move the camera and the hero element in opposite directions at once.

## Layout and safe areas (QA-enforced)

| Ratio | Canvas | Safe area (top / bottom / sides) | Why |
|---|---|---|---|
| 9:16 | 1080×1920 | 220 / 380 / 72 px | Reels/TikTok/Shorts UI: caption, buttons, profile |
| 4:5 | 1080×1350 | 72 / 72 / 72 | feed |
| 1:1 | 1080×1080 | 72 / 72 / 72 | feed |
| 16:9 | 1920×1080 | 54 / 54 / 96 (title safe 5%) | YouTube, presentations |

Use the `.safe` class. Background plates, floods and footage may bleed; text may not (except elements marked `data-provenance="decor"`).

## Persian / RTL

- `dir="rtl"` on the text block, Vazirmatn font, `letter-spacing: 0`.
- **Never split connected Persian script letter by letter.** Animate by word or line.
- Use Persian digits (۰-۹) where the audience expects them. The number QA reads them.
- Isolate Latin brand names and numbers inside RTL text with `<bdi>` or `unicode-bidi: isolate`.
- Check every Persian frame in the rendered MP4. Shaping bugs don't show up in HTML review.

## Banned

- Fade-between-slides structure; a fade as the *only* section transition.
- Centered title over a photo as the default layout.
- Stock "corporate" icons, clip-art, emoji as graphics.
- More than 3 font families; more than one accent object per frame.
- Text zoom-in-exit-left + 3 feature tiles + typing search bar used together (the template opener). See `third_party/motion-bang-bang/references/opener-konsep.md`, rule 4.
- Motion with no musical, spoken or visual reason.
