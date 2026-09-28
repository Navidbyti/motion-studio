---
name: footage
description: Motion Studio supplied footage. Analyse, conform and reframe existing video (mixed resolutions and frame rates, letterbox/pillarbox, burn-ins), find its visual beats, align key moments to the music, and mix natural sound. Use whenever the user supplies video clips.
---

# Footage

Supplied footage is the client's material, not decoration. Keep the subject in frame, never stretch it, never show bars or burn-ins, and cut on the picture's own moments as well as the music's.

## 1. Analyse

```bash
mstudio footage <slug> analyze
```

For each clip `footage/footage.json` records resolution, fps, duration and codec, whether the audio is audible, the **picture area** (`content_box`, which excludes letterbox/pillarbox bars; `bars: true` when they exist) and **visual events**: `flash`, `rise`, `cut` and `motion`, with times in clip seconds. A 1-fps contact sheet per clip goes to `footage/sheets/`. **Look at every sheet.** Note subjects, burn-ins (camera numbers, timecode, watermarks), logos and good in/out points, and log them in `decisions.md`.

## 2. Conform

```bash
mstudio footage <slug> conform
```

This creates constant-frame-rate H.264 copies at the project fps in `footage/conformed/` (59.94/60 → 30 fps, all at once, seek-accurate) plus a 48 kHz WAV of any audible natural sound. Always use the conformed files in the composition.

## 3. Reframe → `footage/reframe.json`

```json
{
  "media": {
    "v02": {
      "clip": "02_ignition_closeup",
      "avoid": [[1600, 20, 300, 110]],
      "avoid_reason": "burned-in camera number 913",
      "keys": [
        {"t": 0.0, "x": 420, "y": 0, "w": 607.5},
        {"t": 3.5, "x": 560, "y": 40, "w": 540, "ease": "sine.inOut"}
      ]
    }
  }
}
```

- Keys are in **source pixels** and clip-local seconds (0 = the media's start in the video). `h` defaults to `w` ÷ canvas aspect (9:16 from 1080p → `w` ≤ 607.5).
- The validator (`mstudio footage <slug> reframe`) rejects crops that leave the picture area (bars would show), touch an `avoid` box, have the wrong aspect or upscale beyond 2.5×. It warns above 1.5×.
- Push or pan slowly (drift rules). Reframe *moves* are camera moves, so tie big ones to beats.
- A crop too tight for a 720p source is a creative problem, not a technical one. A full 9:16 frame from 720p is a 2.67× upscale (the validator warns above 1.5× and fails above 3×). Prefer a **framed layout**: add `"frame": {"x": 0, "y": 420, "w": 1080, "h": 1080}` (canvas px) to the media entry, so the crop keys use the frame's aspect and the clip fills that box. Then position the clip's `.frame` container at the same box, and fill the rest with graphics, a blurred copy or type. Log the decision.

## 4. Place and time

- In `index.html`, at the root and never inside a timed element:
  ```html
  <div class="frame"><video id="v02" data-media="v02" src="footage/conformed/02_ignition_closeup.mp4" muted playsinline></video></div>
  <audio id="v02-audio" data-media="v02" src="footage/conformed/02_ignition_closeup.wav" data-volume="0.6"></audio>
  ```
- The beat map's scene `media` entry gives the clip; `in` or `align` picks the in-point. **Align the picture's own beats to the music**: `"align": {"visual": "02_ignition_closeup:flash:1", "to": {"downbeat": 3}}` puts the ignition flash exactly on downbeat 3. `mstudio beatmap apply` writes `data-start`, `data-duration` and `data-media-start` for the video *and* its audio.
- Apply the crop on the host timeline: `Studio.host.reframe(tl, "v02", "#v02")`.

## 5. Sound

Natural sound (a launch rumble, crowd, water) sells footage. Keep it under the music (`data-volume` 0.4-0.8), let it swell on its moment, and fade the music down by a few dB when natural sound carries the scene. Clips without audio are simply silent; don't add fake sound. SFX from the beat map sit on top.

## Checklist

- [ ] Every clip was used in the intended order and was conformed.
- [ ] No bars, burn-ins or watermarks are visible in any frame (the validator passes, and you checked the contact sheet).
- [ ] The subject is in frame for the whole shot, and the upscale is ≤ 1.5× or justified.
- [ ] Each clip's key moment lands on a musical anchor (or it cuts on action), and the transitions vary.
- [ ] Natural sound is audible where it matters, with no clicks at cut points (use short fades).
