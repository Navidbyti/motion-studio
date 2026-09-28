---
name: revise
description: Motion Studio scoped revisions. Change one scene (copy, color, layout, timing, a number, a crop) from a prompt and prove every other frame is unchanged. Use for any follow-up edit after a render.
---

# Revise

A revision request changes one thing. The rest of the video is approved and must not move.

```bash
mstudio revise <slug> start --scene <scene id> --request "<the user's words>"
#   edit only compositions/<scene>.html (and the scene's beat-map events, copy or data if the request needs it)
mstudio render <slug> --keep-gain      # keeps last version's loudness gain so other scenes stay identical
mstudio revise <slug> verify           # every changed frame must sit inside that scene's window
mstudio qa <slug>
```

- `start` freezes the current version into `versions/v<n>/` and opens v<n+1>. Earlier versions are never overwritten.
- Map the request to the **smallest edit**: a word → copy + `copy.json`; a color → the scene's style (or a token if the request says "everywhere"); timing → the beat map events of that scene; a number → the binding (then re-run `mstudio data`), never the HTML.
- State targets as absolute values ("the counter takes 2 s", "the title at 96 px"), not relative ones ("a bit slower").
- If the request can't be met inside one scene (for example "make the whole thing faster"), say so, and treat it as a new beat map (gate B again), not a revision.
- `verify` compares every frame with the frozen version (PSNR). Changes outside the scene fail QA's `revision` check. Fix the cause; don't widen the scope silently.
- Log the request and the edit in `decisions.md`.
