# ElevenLabs Audio Integration: Voiceover (TTS), Captions (STT) & Sound Effects

Motion Bang Bang features built-in integration with **ElevenLabs** for automated audio production and frame-accurate timeline synchronization:

1. **Text-to-Speech (TTS) with Word Timestamps**: Convert scripts into natural studio-quality voiceover (`assets/vo.mp3`), generating character-, word-, and sentence-level timestamp metadata (`assets/vo-timestamps.json`) to drive GSAP scene cuts, camera movements, and kinetic typography.
2. **Speech-to-Text (STT) via ElevenLabs Scribe**: Transcribe pre-recorded audio or talking-head avatar videos (`.mp4`, `.mov`, `.mp3`, `.wav`), generating word-level timestamps (`assets/transcript.json`), standard subtitle files (`.srt`, `.vtt`), and GSAP kinetic cue arrays.
3. **Sound Effects (SFX)**: Generate and maintain the bundled `assets/sfx/` library from prompts (`scripts/elevenlabs_audio.py sfx`). Placing those effects on an animation is a separate, post-render job — see §8 and `references/sound-design.md`.

---

## 1. Setup & Authentication

The CLI tool `scripts/elevenlabs_audio.py` uses Python's standard library with **zero external pip dependencies**.

Set your API key in your terminal or environment:

```bash
# Windows PowerShell
$env:ELEVENLABS_API_KEY="sk_your_elevenlabs_api_key"

# Windows CMD
set ELEVENLABS_API_KEY="sk_your_elevenlabs_api_key"

# Linux / macOS Bash or Zsh
export ELEVENLABS_API_KEY="sk_your_elevenlabs_api_key"
```

Alternatively, create a `.env` file in the project root:
```env
ELEVENLABS_API_KEY=sk_your_elevenlabs_api_key
```
Or pass it directly using `--api-key <key>` on any command.

Verify your connection and discover available voices:
```bash
python scripts/elevenlabs_audio.py voices
python scripts/elevenlabs_audio.py voices --search george
```

---

## 2. Text-to-Speech (TTS) Workflow

Use TTS when you have a written voiceover script (for an explainer, product promo, or bumper) and need spoken audio synchronized with your visual animations.

### Command Syntax

```bash
# Direct text input
python scripts/elevenlabs_audio.py tts \
  --text "Motion Bang Bang creates cinematic web animations." \
  --voice george \
  --output assets/vo.mp3 \
  --timestamps assets/vo-timestamps.json \
  --cues assets/vo-cues.js

# From a markdown or text script file
python scripts/elevenlabs_audio.py tts \
  --file assets/vo-script.md \
  --voice rachel \
  --output assets/vo.mp3 \
  --timestamps assets/vo-timestamps.json \
  --cues assets/vo-cues.js
```

### Voice Options & Aliases

The tool supports friendly name aliases for common ElevenLabs voices:

| Alias | Description | Voice ID | Best Used For |
|---|---|---|---|
| `george` | Warm British storyteller | `JBFqnCBsd6RMkjVDRZzb` | Educational explainers, documentary, storytelling |
| `rachel` | Calm young American female | `21m00Tcm4TlvDq8ikWAM` | SaaS product tours, corporate explainers, guides |
| `adam` | Deep narrative American male | `pNInz6obpgDQGcFmaJgB` | Cinematic trailers, powerful product promos |
| `sarah` | Reassuring, confident American female | `EXAVITQu4vr4xnSDxMaL` | Professional promos, brand announcements |
| `charlie` | Confident Australian male | `IKne3meq5aSn9XLyUdCD` | Energetic promos, upbeat tech products |
| `brian` | Deep narrator | `nPczCjzI2devNBz1zQrb` | Authoritative explainers, history, science |
| `laura` | Upbeat American female | `FGY2WhTYpPnrIDTdsKH5` | Creative tools, social video explainers |
| `josh` | Young conversational male | `TxGEqnHWrfWFTfGW9XjX` | Gen-Z, app teasers, casual social video |

You can also provide any custom or cloned **Voice ID** from your ElevenLabs dashboard:
```bash
python scripts/elevenlabs_audio.py tts --text "Hello world" --voice "YOUR_VOICE_ID_HERE"
```

### Generated Files

1. **`assets/vo.mp3`**: The generated voiceover audio file.
2. **`assets/vo-timestamps.json`**: Structured timing data containing:
   - `duration`: Total duration in seconds.
   - `words_per_minute`: Speaking tempo (WPM).
   - `sentences`: Array of sentence boundaries (`start`, `end`, `duration`, `text`).
   - `pauses`: Natural gaps $\ge 0.35$s between words—ideal candidate timestamps for scene cuts or camera transitions!
   - `words`: Word-by-word array with exact millisecond start and end times.
3. **`assets/vo-cues.js`** (Optional): Ready-to-import ES module containing `AUDIO_DURATION`, `SENTENCE_CUES`, `WORD_CUES`, and a `buildKineticTypography` helper function.

---

## 3. Speech-to-Text (STT) for Talking-Head Avatars

Use STT when you already have an audio recording or a talking-head video file (e.g. from an AI avatar generator like HeyGen, Synthesia, D-ID, or a live recorded human speaking on camera) and want to:
- Transcribe the dialogue into accurate captions.
- Generate word-by-word kinetic typography that pops dynamically as the person speaks.
- Overlay animated badges, lower-thirds, cards, and scene illustrations locked to what is being said.
- Produce SubRip (`.srt`) and WebVTT (`.vtt`) subtitle tracks.

### Command Syntax

```bash
# Transcribe audio or video with word-level timestamps & subtitles
python scripts/elevenlabs_audio.py stt \
  --file assets/avatar.mp4 \
  --output assets/transcript.json \
  --srt assets/captions.srt \
  --vtt assets/captions.vtt \
  --cues assets/captions-cues.js

# Specifying language and speaker diarization
python scripts/elevenlabs_audio.py stt \
  --file assets/interview.mp4 \
  --language id \
  --diarize \
  --output assets/transcript.json \
  --srt assets/captions.srt
```

Supported input formats: `.mp3`, `.wav`, `.mp4`, `.mov`, `.m4a`, `.webm`, `.aac`.

---

## 4. GSAP Synchronization Architecture

Whether using TTS audio or talking-head video, synchronize the GSAP animation timeline with the media clock to ensure frame-accurate alignment.

### DOM Setup

In your HTML template (e.g. `index.html`):

```html
<!-- Voiceover Audio -->
<audio id="vo" src="assets/vo.mp3" preload="auto"></audio>

<!-- OR Talking-Head Video Background/Layer -->
<div class="video-container">
  <video id="talking-head" src="assets/avatar.mp4" playsinline preload="auto" muted></video>
</div>

<!-- Kinetic Typography & Motion Graphics Overlays -->
<div id="kinetic-captions" class="captions-overlay"></div>
<div id="world">
  <!-- Motion graphics elements: badges, charts, arrows, diagrams -->
</div>
```

### GSAP Timeline & Media Clock Binding

```javascript
import gsap from 'https://cdn.jsdelivr.net/npm/gsap@3.12.5/+esm';

const vo = document.querySelector('#vo');
const video = document.querySelector('#talking-head');
const media = (vo && vo.getAttribute('src')) ? vo : video;

const tl = gsap.timeline({ paused: true });
let mediaReady = false;

// 1. Scene transition markers derived from vo-timestamps.json
// (e.g., natural pauses between sentences)
tl.addLabel('scene_1', 0.0);
tl.addLabel('scene_2', 3.39);
tl.addLabel('scene_3', 7.15);

// 2. Camera or motion cue at scene_2
tl.to('#world', { x: -1920, duration: 0.8, ease: 'power3.inOut' }, 'scene_2');

// 3. Keep GSAP and media clock in lockstep
gsap.ticker.add(() => {
  if (!mediaReady || tl.paused() || !media) return;
  // Re-sync if clock drifts by more than 80ms (e.g. tab stutter)
  const diff = Math.abs(media.currentTime - tl.time());
  if (diff > 0.08) {
    media.currentTime = tl.time();
  }
});

// 4. Safe Autoplay with Interaction Fallback
function startPlayback() {
  tl.play(0);
  if (media) {
    media.currentTime = 0;
    media.play().then(() => mediaReady = true).catch(() => {});
  }
}

if (media) {
  media.play().then(() => {
    mediaReady = true;
    media.currentTime = 0;
    tl.play(0);
  }).catch(() => {
    // Autoplay blocked by browser policy: pause at frame 0 and unlock on first click/key
    const unlock = () => {
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
      startPlayback();
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
  });
} else {
  tl.play(0);
}
```

---

## 5. Kinetic Typography Patterns

Kinetic typography emphasizes spoken words synchronously with speech. Use `WORD_CUES` from `assets/vo-cues.js` or `assets/captions-cues.js`.

### Pattern A: Dynamic Word Pop & Glow

Each word highlights and scales up slightly when spoken, then settles into comfortable reading state:

```javascript
import { WORD_CUES } from './assets/vo-cues.js';

const captionBox = document.querySelector('#kinetic-captions');

// Render word spans into container
captionBox.innerHTML = WORD_CUES.map((cue, idx) => 
  `<span class="k-word" id="kw-${idx}">${cue.word}</span> `
).join('');

// Animate each word on the GSAP timeline
WORD_CUES.forEach((cue, idx) => {
  const el = `#kw-${idx}`;

  // Word entrance / pop when spoken
  tl.fromTo(el,
    { opacity: 0.3, scale: 0.95, color: '#777777', textShadow: 'none' },
    {
      opacity: 1.0,
      scale: 1.12,
      color: '#FFFFFF',
      textShadow: '0 0 16px rgba(255, 215, 0, 0.6)',
      duration: 0.12,
      ease: 'back.out(2)'
    },
    cue.start
  );

  // Settle back to readable white
  tl.to(el,
    {
      scale: 1.0,
      color: '#EEEEEE',
      textShadow: 'none',
      duration: 0.18,
      ease: 'power2.out'
    },
    cue.end
  );
});
```

### Pattern B: Sentence-by-Sentence Card Wipe

For clean, readable subtitles across longer explainers:

```javascript
import { SENTENCE_CUES } from './assets/vo-cues.js';

SENTENCE_CUES.forEach((sent) => {
  // Entrance at sentence start
  tl.fromTo('.subtitle-card',
    { opacity: 0, y: 20 },
    { opacity: 1, y: 0, duration: 0.3, ease: 'power2.out' },
    sent.start
  );

  // Exit just before next sentence starts
  tl.to('.subtitle-card',
    { opacity: 0, y: -10, duration: 0.25, ease: 'power2.in' },
    sent.end - 0.25
  );
});
```

---

## 6. Full Talking-Head Avatar Editing Recipe

To turn a raw talking-head avatar video into an engaging viral/social motion graphic:

1. **Place raw video**: Save your avatar video as `assets/avatar.mp4`.
2. **Extract transcription & timing**:
   ```bash
   python scripts/elevenlabs_audio.py stt \
     --file assets/avatar.mp4 \
     --output assets/transcript.json \
     --srt assets/captions.srt \
     --cues assets/captions-cues.js
   ```
3. **Inspect key moments**: Check `assets/transcript.json` for keywords (e.g. stats, product names, core arguments).
4. **Build the composition in HTML**:
   - Background video: `<video id="talking-head" src="assets/avatar.mp4"></video>` styled with a subtle vignette, border radius, or framing card.
   - Lower-third: Name, title, and topic badge entering at 0.5s.
   - Dynamic captions: Kinetic pop typography positioned at the lower-middle or chest zone.
   - B-Roll / Graphics: Infographic pills, icons, and diagrams sliding in from screen right or popping overhead when specific trigger words are spoken.
5. **Verify**: Open `index.html?debug=1`, scrub the timeline, and verify that visual accents pop at the exact millisecond the speaker utters the corresponding word.

---

## 7. Sound Effects (SFX) Bundle

`assets/sfx/` ships 26 takes across 10 motion families (`impact`, `stamp`, `whoosh`, `transition`, `accent`, `paper`, `pen`, `ui`, `camera`, `ambience`). **Use the bundle; do not re-generate it for a project.** The CLI exists to maintain it.

```bash
# Regenerate/maintain from the spec. Existing files are skipped unless --force,
# so adding a block to library.json and re-running bills only the new rows.
python scripts/elevenlabs_audio.py sfx --spec assets/sfx/library.json --preview _preview.wav

# Audit the bundle against the current contract and repair what drifts (no API call,
# no billing) -- prints duration / peak / rms / head per file plus any warning.
python scripts/elevenlabs_audio.py sfx --spec assets/sfx/library.json --renormalize
```

- **`duration_seconds` is what you are billed for, not what you keep.** `"tight": true` one-shots are silence-trimmed afterwards, so request headroom and let the trim decide the length.
- **Every prompt names source + surface + mic perspective and forbids musical content.** A tonal stinger collides with any music bed added later.
- **One contract for all files** (48 kHz / stereo / PCM-16, peak −3 dBFS by pure gain, head ≤ 15 ms) so intensity stays a mix-time parameter rather than a property of the recording. Details and rationale: `references/sound-design.md` §1.
- `manifest.json` records per-file measured provenance (duration, peak, RMS, head, prompt, date); `SOURCES.md` is the human-readable version plus the per-family mix table.
- **Hand-generated takes join the same contract.** Files made in the ElevenLabs dashboard (or anywhere else) go through `--renormalize` like any other, keep their originals in an `_originals/` subfolder, and get their `trigger` words and family written into `manifest.json` by hand — the cue miner only knows a sound exists if a trigger verb points at it. The `camera` family (shutter clicks, film-advance mechanism) arrived this way, so `library.json` has no prompt for it and `manifest.json` is its only record.
- **Licensing is the user's decision.** Output belongs to the user and may be used outside the service, but free tiers are non-commercial, and the Sound Effects sublicensing opt-out lives in the ElevenLabs dashboard. Record the plan tier in `manifest.json`; the tooling never touches account settings.

---

## 8. Placing Effects on the Animation

Placing is **not** an ElevenLabs job and **not** an in-page job. Two zero-dependency scripts do it after the MP4 is rendered — the video stream is copied, so no frame is ever re-rendered and the approved picture ships untouched:

```bash
node scripts/sfx-cues.mjs --why                 # 824 tweens -> 422 candidates -> 219 cues
node scripts/sfx-cues.mjs --word-clicks         # 275 cues: one click per word in a staggered caption
node scripts/sfx-mix.mjs --video final.mp4 --vo assets/vo.wav --stems sfx-stems
```

The cue miner walks `window.OPENER.tl` in system Chrome and classifies each motion by what actually moved; a staggered text reveal unrolls into one cue per element under `--word-clicks`. The mixer renders one stem per family, places every cue from the sheet's `frame` value, ducks `whoosh`/`paper`/`pen`/`ui` under the voice with a sidechain, limits the bus, muxes, then prints the measured loudness. Full pipeline, density targets and the verification checklist: `references/sound-design.md`.
