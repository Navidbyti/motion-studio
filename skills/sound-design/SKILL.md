---
name: sound-design
description: Motion Studio sound design. Gives every project its own sonic identity (original music via Lyria, project-specific SFX via the synth, variations or ElevenLabs), layered hits, and variety rules, on top of beat-accurate placement. Use at the style brief (sound palette) and the beat map (per-hit sounds), and whenever a mix sounds like the last video.
---

# Sound design

Placement is solved: the beat map puts every sound on its frame. This skill is about **what** plays. A viewer should be able to recognise a video from its sound, and a new project should not sound like the last one.

## 1. Sound palette (in the style brief, gate A)

Add a `## Sound` section to `style-brief.md`:

- **Music source:** the client's licensed track, **or an original bed generated for this project** (below). Never reuse a previous project's bed unless it is the brand's music (`brief.music.brand_music: true`). QA's `sound_design` check flags recycled beds.
- **Music prompt**, if generating: genre, 2-4 named instruments, mood arc (intro → build → drop → outro), BPM, key, "instrumental only".
- **Sonic signature:** one sound that belongs to this video only (a synth motif, a processed foley texture, a tonal hit), used on the special moment and the logo.
- **SFX families**, 3-6 of them, matched to the visuals. Paper and pen sounds for sketch styles, glass and metal for premium tech, digital glitches for data, air and body hits for kinetic type. Name where each comes from: synth kind, variation or generated prompt.
- **Ambience** (optional): a low bed that glues scenes together (room tone, space hum, city).
- **Silence:** where the music drops out, and why. A dropout before the drop is the strongest hit you have.

## 2. Make the music

```bash
mstudio music <slug> gen --prompt "Dark cinematic synthwave, pulsing analog bass, gated snare, glassy arpeggio, tense build into a wide drop" --bpm 120 --key "D minor"
#   -> audio/music/bed.wav (Lyria 3 Clip: always 30 s). Longer videos: --full (Lyria 3.5, full song; length steered by the prompt)
mstudio beats <slug> audio/music/bed.wav            # verify tempo and downbeats by ear: generated music drifts sometimes
mstudio music <slug> fit audio/music/bed.wav        # edit to the project length on bar lines with a musical fade (or loop whole bars)
```

- Uses the same Gemini key as voice-over (`mstudio keys setup gemini`). Lyria output carries an inaudible SynthID watermark, and the credits entry says so.
- Generate 2-3 candidates (`--name bed-a/bed-b/bed-c`), pick the one whose energy curve matches the script, and log why in `decisions.md`.
- Don't name artists or ask for copyrighted lyrics. Lyria's safety filters block both.

## 3. Make the sound effects

```bash
mstudio sfx kinds                                                   # whoosh riser swell impact sub-drop thud hit pop click glitch shimmer tape-stop zap
mstudio sfx make <slug> whoosh --name swoosh --count 3 --pan lr     # three different seeds of one family
mstudio sfx make <slug> impact --name slam --pitch 0.8 --bright 0.3 # darker, lower
mstudio sfx vary <slug> audio/sfx/slam.wav --count 4                # pitch/tone variants of a sound you like
mstudio sfx gen <slug> "heavy glass door slamming in a marble hall, close mic" --name door --duration 1.2   # ElevenLabs (optional key)
```

- Synth sounds are CC0, deterministic by seed, and made for this project. Tune `--pitch` (0.5-2) and `--bright` (0-1) to the palette.
- Risers and swells align their **end** to the hit, whooshes their **peak**, and impacts their **onset**. That's automatic for files made with `mstudio sfx`.
- The stock library (`third_party/motion-bang-bang`) is a fallback, not the palette.

## 4. Put sounds on hits (beat map)

```json
{"id": "drop.slam", "tier": "big", "at": {"drop": 0},
 "sfx": ["file:audio/sfx/slam.wav", "file:audio/sfx/sub-drop-2.wav", "file:audio/sfx/shimmer-1.wav"]}
```

- **Layer** big moments: a transient (thud or hit) + body (impact or sub-drop) + tail (shimmer or reverb-ish swell). Extra layers sit 3 dB under the first.
- A **riser or swell** goes into every drop or scene change, cut exactly on the hit (the file's end lands on the impact frame).
- **Vary repeats:** give recurring hits two or three variants (`vary`). The mixer also shifts a repeated file by up to ±1.5 semitones and ±1 dB automatically.
- **Density:** at most one sound per beat in busy passages; let holds breathe. Match intensity to the tier: `big` gets layers, `entrance` a single light sound, `micro` a click or nothing.
- **Duck** the music a few dB under key hits and under voice-over (`music.volume`). The music sets the rhythm, and the effects make the hits land.

## 5. Check

`mstudio qa` → `sound_design` warns when there are fewer than 4 distinct sounds, when one sound carries more than a third of the cues, when a sound repeats unvaried, when every cue comes from the stock library, or when the music bed was used in an earlier delivered project. Then **listen** to the whole mix twice: once for the rhythm, once with your eyes closed for the sound story.

**Benchmarks are the exception.** Benchmark prompts fix the music and SFX (`benchmarks/shared/audio`) so runs stay comparable. There, creativity shows in layering, variation and silence, not in new files.
