# Video Frame Review Skill

## How it works

Claude Code is multimodal: `Read` on a JPEG/PNG renders it visually.
ffmpeg extracts frames → Read individual frames at key timestamps = video review without Gemini or any API.

No external tools needed beyond ffmpeg (already at `/opt/homebrew/bin/ffmpeg`).

## Standard extraction command

```bash
# 1 FPS into a frames/ directory
ffmpeg -i test.webm -vf fps=1 /tmp/review/frames/frame_%04d.jpg

# Scene-change only (cheaper, catches state transitions)
ffmpeg -i test.webm -vf "select='gt(scene,0.4)'" -vsync vfr /tmp/review/scene/scene_%04d.jpg

# Contact sheet (quick visual overview, all frames tiled)
ffmpeg -i test.webm -vf "fps=1,scale=320:-1,tile=4x4" /tmp/review/contact_sheet.jpg
```

## Review strategy

Don't read every frame. Sample strategically:

| Frame | Purpose |
|---|---|
| frame_0001 | Loading state — blank? error? |
| frame_0005 | First meaningful UI state |
| frame_0010, 0020 | Early flow |
| frame_0030–0050 | Mid-flow — key interactions |
| frame_0060–0080 | Late flow |
| frame_last | Final state — did it succeed? |

Read the contact sheet first for a spatial overview, then dive into specific frames.

## What to look for (skeptically)

- **Does the UI actually change?** Same screen across many frames = stuck/frozen
- **Error messages in GM/system responses?** e.g. `[CHARACTER CREATION - No Character Built]`
- **Party/state panels populated correctly?** Placeholder names ("Hero L1") ≠ real character data
- **Chat history grows?** Empty chat for 60% of video duration = long wait or no actions
- **Final frame matches claimed outcome?** Video can be 101s of failure and still have valid ffprobe metadata

## Key insight from first use (2026-02-20)

The `test_full_lifecycle_video` (101.76s) was reported "pass" because ffprobe confirmed a valid .webm file. Frame review revealed every GM response was `[CHARACTER CREATION - No Character Built]` — the game never actually worked. Character creation data was never persisted before the session started.

**File existence + duration ≠ test passed. Frame content is the ground truth.**

## Skill invocation pattern

```
1. ffmpeg extract 1FPS frames to /tmp/review/frames/
2. Read contact sheet for overview
3. Read frame_0001 (load state)
4. Read frame_0005 (first UI)
5. Read frames at 25%, 50%, 75%, 100% of total count
6. Read any frames around timestamps of interest from server logs
7. Report what actually happened on screen
```

## Cost note

Reading ~10 JPEG frames locally costs nothing beyond Claude context. For 34 test videos, batch the review: extract all frames, then sweep through contact sheets first to triage which videos need deep frame inspection.
