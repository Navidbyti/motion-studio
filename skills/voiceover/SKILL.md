---
name: voiceover
description: Motion Studio voice-over with Gemini 3.8 TTS. Collects the user's Gemini API key locally (never in chat), writes a per-scene VO script, generates audio/vo/*.wav, gets word timing, and places each line on the beat in the beat map. Use when the brief has a voice-over or the user asks for narration.
---

# Voice-over (Gemini 3.8 TTS)

## 1. The API key: local only, never in chat

```bash
mstudio keys status                    # is a key configured? (shows a masked key, never the key)
mstudio keys setup gemini --wait 300   # creates ~/.motion-studio/secrets/gemini_api_key.txt, opens it in the
                                       # text editor, waits until the user pastes + saves, then validates it
mstudio keys check gemini              # validate again later
```

Tell the user exactly this: *"A text file just opened in Notepad (or your editor). Paste your Gemini API key on the empty line, save, and close it. It stays on this computer, outside the project. You can get a key at https://aistudio.google.com/apikey."* If `--wait` times out, run `mstudio keys check gemini` once they say it's done.

- **Never** ask for the key in chat, never `cat`/`Read` the key file, never print, log or commit a key. `GEMINI_API_KEY` in the environment also works and wins over the file.
- If the user pastes a key into the chat anyway: don't repeat it, and don't write it anywhere yourself. Ask them to put it in the file, and suggest rotating it in AI Studio because it is now in the chat history.
- In a real terminal the user can instead run `mstudio keys setup gemini --prompt` (hidden input).
- Motion Studio strips keys from every HyperFrames call, because HyperFrames would otherwise send snapshot frames to Gemini.

## 2. Write `vo.md`

```markdown
> voice: Kore
> style: warm, confident, steady pace

## hook
Every launch starts with a countdown.

## launch
> style: urgent, rising excitement
Three... <short pause> two... one. LIFTOFF!
```

- `## <id>`: one segment per line of narration. Use the **beat-map scene ids** so each line can start on its scene's downbeat.
- The text is spoken **verbatim**. Put the delivery in `> style:` (emotion, pace, pitch), not in the text. Use inline tags for moments: `<short pause>`, `<long pause>`, `<breath>`, `<sigh>`, `<laugh>`. Emphasis goes in CAPITALS.
- Voices: `mstudio voices` lists the 30 prebuilt voices (Kore firm, Puck upbeat, Charon informative, Sulafat warm, …). Custom `voice_…` ids from Voice Design also work.
- Languages: auto-detected, 130+ languages including Iranian Persian. Write Persian VO in Persian script.
- Match the on-screen copy: a line the viewer reads while it is spoken should be the same words.

## 3. Generate and time

```bash
mstudio tts <slug>                          # all segments -> audio/vo/<id>.wav (48 kHz, -16 LUFS) + audio/vo/vo.json + credits
mstudio tts <slug> --only launch            # regenerate one line
mstudio tts <slug> --model lite             # gemini-3.8-flash-lite-tts (cheaper)
mstudio words <slug> audio/vo/launch.wav    # word timing -> audio/vo/launch.words.json (local transcription)
```

Listen to every file. Regenerate lines with bad emphasis rather than accepting them, and log the choice in `decisions.md`.

## 4. Place it in the beat map

```json
"music": {"file": "audio/music.wav", "beats": "audio/beats.json", "volume": 0.4},
"voiceover": [
  {"id": "hook",   "file": "audio/vo/hook.wav",   "at": {"downbeat": 0, "plus_beats": 0.5}},
  {"id": "launch", "file": "audio/vo/launch.wav", "at": {"downbeat": 4}}
],
"scenes": [ … {"id": "launch.word", "tier": "word", "at": {"word": "LIFTOFF", "segment": "launch"}} … ]
```

- Each segment starts on a musical anchor. `mstudio beatmap apply` adds and times its `<audio data-vo>` element. It fails when segments overlap or run past the end.
- `{"word": "…", "segment": "<id>"}` anchors land a hit on the spoken word (tier `word`: the on-screen word reveals on the word, not the beat).
- Keep the music about 4-6 dB under the voice. With VO, set `music.volume` around 0.35-0.5 and check the mix by ear. The QA loudness target stays at −14 LUFS for the whole mix.

## 5. Credits and disclosure

`mstudio tts` adds a `credits.json` entry for `audio/vo` (generated with the Gemini API). Some platforms and clients require disclosing an AI-generated voice, so note it in the handoff.
