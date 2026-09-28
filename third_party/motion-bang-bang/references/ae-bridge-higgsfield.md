# After Effects via Higgsfield MCP Bridge — Building Cartoon Stage Directly in AE

Consult this guide when the user has an Adobe After Effects project open and the Higgsfield MCP bridge (`ae_*`) is connected, requesting an explainer built **directly inside AE**. Benchmark metrics from a production educational cartoon explainer (103s VO, 10 stages, 20 jointed characters, 96 PNG assets): $\sim 67$ minutes from master comp to final contact sheet, $\sim 100$ AE tool calls, 0 Higgsfield credits consumed.
Stylistic laws remain identical to `kartun-panggung.md`; this document governs the execution mechanics of the MCP bridge.

## Capabilities and Limitations of the Bridge

| Capable | Prohibited / Limitations (with workarounds) |
|---|---|
| `ae_build_scene_from_lottie` creates master comps, precomps, and simple background shapes in one shot | Large Lotties ($> 60\text{KB}$) fail — use Lottie strictly for **composition skeletons**; assemble contents via atomic batch ops |
| `ae_batch` executes dozens of operations (`add_shape_layer`, `add_null_layer`, `import_image`, `modify_layer`, `set_keyframes`, `set_expression`) in one call | Calling `apply_gradient`, `get_layer_info`, or `export_frame` inside a batch causes the entire batch to fail; call these standalone |
| `add_shape_layer` supports rectangles (with `roundness`) and ellipses, color `{r, g, b}` normalized 0–1 | Complex paths, polygons, stars, strokes, and gradients cannot be generated directly via shape ops $\rightarrow$ render as external SVGs to PNG, then import |
| `ae_import_image` imports PNG/JPG/WAV (WAV yields a harmless "hidden property" warning) | SVG files ("invalid file type") are unsupported; files inside virtual agent sandboxes are invisible to AE $\rightarrow$ copy assets to a standard local folder (e.g. `C:/aset-ae/`) |
| `ae_apply_gradient` applies 2-stop Ramp / 4-Color Gradients to static background shapes | Gradients on keyframed layers; gradients inside batch calls |
| `set_expression` sets Position, Scale, Rotation, Opacity, and Anchor | Expressions on effect properties or vector paths; `ae_reorder_layers` frequently returns "layer not found" $\rightarrow$ **layer order = creation order; build strictly back-to-front** |
| `ae_export_contact_sheet` (5–8 timestamps) and `ae_export_frame` export directly to r2.dev URLs | Viewing r2.dev URLs where network regions block direct access $\rightarrow$ relay via `media_import_url(url)` in MCP $\rightarrow$ inspect CloudFront PNG. If relay fails, re-export |
| `ae_get_layer_info`, `ae_list_layers`, `ae_list_compositions` for numerical verification | Bridge cannot save project files, execute renders, or delete comps. **User must press Ctrl+S**; render final video via Render Queue or `aerender.exe` |

### Critical Bridge Traps

1. **New Null Layers Default to (960, 540)**: `add_null_layer` followed immediately by parenting causes un-keyframed children to jump by $[-960, -540]$. Immediately call `modify_layer` setting anchorPoint `[0,0]` and position `[0,0]` on the null **BEFORE parenting any child layer**.
2. **Parenting to a Keyframed CAM**: Bakes CAM's current transform into the child, displacing coordinates and scaling. Explicitly reset the child's position and scale immediately after parenting, or parent layers before keyframing CAM.
3. **Keyframes on Parented Layers Use Parent Space**: An eye inside a head layer is not `[932, 472]` (comp space) but `[-28, -2]` (relative to head center). Using comp space shoots facial features off screen.
4. **Partial Batch Failures**: If one operation fails with `stopOnError: false`, subsequent operations still apply. Inspect `results[i].ok` individually rather than blindly resubmitting entire batches.
5. **Lottie Transforms**: Lottie child positions are written in comp space rather than parent space, and Lottie converters strip gradients, images, masks, and expressions. Use Lottie only to establish initial precomp layer `ip/op/st` markers.
6. **Precomp Zoom Blurs Contact Sheets**: Never zoom the master precomp layer; place camera motion on the `CAM` null inside each individual stage precomp.

## Validated Composition Architecture

```
# <title>                     Master comp 1920×1080 30fps, duration = VO
├─ VO (wav)                   Starts at second 0
└─ > P01 … > P10              Precomp layers; ip/op locked to VO pauses, st = ip (local time starts at 0)
     ### P01 <stage_name>     Precomp; duration = segment + 0.6s
     ├─ sky                   Comp-sized rectangle from Lottie → ae_apply_gradient
     ├─ CAM                   Null layer: anchor [0,0], pos [0,0]; ALL world layers parented here
     ├─ hills, ground, …      2× PNGs from SVG, scale 50, anchor from manifest, pos = comp pivot
     ├─ <character> ROOT      AE native shape puppet (29 child shapes; see rig structure)
     └─ light/fire overlay    PNG/rect overlay; rendered LAST (top of stack), keyframed opacity
```

**Camera = CAM Null**: To frame scene coordinate $(x, y)$ at zoom $z$:
`CAM.Position = [960 - x * z, 540 - y * z]`, `CAM.Scale = [100 * z, 100 * z]`. Keyframe with influence 50–75 for smooth easing. Zoom factor must never drop below 1.08 (`kartun-panggung.md` Law 1).

**Reusing Compositions as Subsequent Stages**: Set the precomp layer in the master comp with `st = ip - local_start_time`. Place subsequent scene keyframes at that local timestamp, separated from previous scenes by a dual hold keyframe ($\Delta 1$ frame, e.g. 12.93s $\rightarrow$ 12.967s) to eliminate inter-scene interpolation.

**96px Translation Slide**: Keyframe master precomp Position:
P08: 960 $\rightarrow$ 864 (0.3s, influence 70 $\rightarrow$ 10); P09: 1056 $\rightarrow$ 960 (0.4s, influence 10 $\rightarrow$ 80). Animate Scale 100 $\rightarrow$ 111 and 111 $\rightarrow$ 100 simultaneously to prevent revealing composition boundaries.

## Production Workflow

0. **Lock Rundown to VO Pauses**: Extract audio markers via `vo-pauses.html` or `ffmpeg silencedetect`, establishing camera coordinates $(t, x, y, z)$ per stage.
1. **Scaffold Skeleton via Lightweight Lottie**: Create master comp + stage precomps containing only the `sky` layer, configuring `ip/op/st` on master precomp layers. Import VO audio to master.
2. **Generate Vector Assets from Code** (`scripts/ae/bridge/aset-svg.py`):
   Each asset is drawn via script with defined local pivot coordinates, outputting SVGs and a `manifest.json` containing `{ png, pos, anchor, scale: 50 }`. Render to 2× transparent PNGs via `node scripts/ae/bridge/svg2png.cjs <folder>`.
3. **Assemble Each Stage in a Single `ae_batch` (Back-to-Front)**:
   `add_null_layer CAM` $\rightarrow$ `modify_layer` CAM anchor/pos to `[0,0]` $\rightarrow$ `import_image` + `modify_layer` per asset $\rightarrow$ `modify_layer parentLayerName: "CAM"` $\rightarrow$ `set_keyframes` on CAM & props $\rightarrow$ `set_expression` for idle motion. Apply sky gradients via standalone `ae_apply_gradient` before the batch.
4. **Construct Native Character Rigs**:
   Run `python scripts/ae/bridge/rig-tokoh.py "<comp>" <prefix> <x> <gy> <scale> [variant]` to generate $\sim 90$ atomic batch operations. Parent character ROOT to CAM and reset ROOT transform. Submit as one batch per character ($\sim 15\text{KB}$). Follow with a second batch for keyframed poses and idle expressions.
5. **Verify Stages via Contact Sheets**:
   Call `ae_export_contact_sheet` across 5–8 key timestamps per stage. Inspect: Are puppet joints attached? Did background layers shift? Are overlays positioned on top? Check master composition transitions.
6. **Handoff**:
   Instruct the user to press **Ctrl+S** to save the AE project file. Provide CLI export command:
   ```bash
   "C:/Program Files/Adobe/Adobe After Effects 2026/Support Files/aerender.exe" -project ... -comp "# ..." -output ...mp4
   ```

## Native Character Puppet Rig (`rig-tokoh.py`)

Create shapes at composition coordinates $\rightarrow$ `modify_layer` setting anchor = joint pivot (layer space) and position = joint pivot (comp space) $\rightarrow$ parent to hierarchy. Rotation rotates cleanly around the joint pivot.

```
<p> ROOT (null, pelvis = gy - 214s, anchor [50,50])
├─ thigh-L/R (anchor [0, -52s], hip joint ±24s) → shin (knee gy-112s) → foot (ankle gy-16s)
└─ torso (anchor [0, 76s], pelvis joint)
   ├─ arm-L/R (shoulder ±52s, gy-340s) → forearm (elbow gy-262s) → hand (wrist gy-190s)
   ├─ tunic, neck
   └─ head (anchor [0, 72s], neck gy-398s)
      └─ ears, hair, beard, eyes, eyebrows, nose, mouth
```

**Creation Order = Layer Stack Order**: Back leg (R) $\rightarrow$ Back arm (R) $\rightarrow$ Torso $\rightarrow$ Head & face $\rightarrow$ Front arm (L). Scale presets: 0.75 (distant), 0.85–0.9 (standard stage), 1.15–1.4 (close-up).

### Deterministic Expression and Action Formulas

| Motion | Expression / Keyframe Formula |
|---|---|
| Breathing | Torso Scale: `[value[0], value[1] * (1 + Math.sin(time * 2.4) * 0.015)]` |
| Blinking | Eye Scale: `var c = (time + 0.4) % 3.3; c < 0.12 ? [value[0], value[1] * 0.1] : value` |
| Gated Walk | Thigh `value ± Math.sin((time - t0) * 11) * 24`, shin `Math.max(0, ±Math.sin(... - 1)) * 20`, opposing arm `* 18`, ROOT y `-Math.abs(Math.sin) * 6` — active only within interval `t0 < time < t1` |
| Jump | ROOT Position (0.25s dip-and-rise 55px), thigh `-Math.abs(Math.sin(Math.PI * 2 * t)) * 25`, shin `+35` |
| Arc Throw | Arm Rotation: $0^\circ \rightarrow -20^\circ$ (windup) $\rightarrow 110^\circ$ (release) $\rightarrow 0^\circ$; projectile: 3 Position keyframes (hand $\rightarrow$ apex $\rightarrow$ target) + Rotation $540^\circ–720^\circ$ |
| Wave | Arm Rotation: $-150^\circ \leftrightarrow -120^\circ$ oscillating every 0.3s |
| Anxious / Cuddle | Arm-R $-35^\circ$, forearm-R $-60^\circ$, arm-L $-70^\circ$, forearm-L $-40^\circ$; eyebrow $\pm 15^\circ$; mouth Scale `[70, 60]` |
| Surprised / Excited | Mouth Scale `[130, 260]` within 0.03s; eye Position shifted $\pm 10$ in head space |
| Sleep | ROOT Rotation $-90^\circ$ (hard cut hold), eye Scale `[110, 12]`, breathing 1.6 Hz at amplitude 0.03 |
| Campfire Smoke / Flame | Flame Scale `1 + Math.sin(time * 17) * 0.12`, Rotation `Math.sin(time * 9) * 4.5`; firelight overlay opacity 30, Scale breathing 3% |

## Known Technical Constraints (Inform User Upfront)

- Layer stacking order is strictly determined by creation order; props that pass in front of characters must be generated after the characters.
- Background illustrations are 2× raster PNGs; stylistic updates require editing SVG scripts and re-rendering footage. Characters remain fully native editable vector shapes in AE.
- Motion blur and advanced glow effects are omitted during generation; user may enable native AE motion blur switches on comp layers.
