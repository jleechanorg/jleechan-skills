---
name: video-edit-letterbox-caption
description: Add burned-in captions to a screen-recording / gameplay video WITHOUT blocking the video content. Use when the user wants captions ABOVE the gameplay (e.g. "put captions above", "don't block the video", "letterbox the captions", "extend the video vertically with a black bar at the top"). Combines two techniques: (a) trim static 5+ second segments via ffmpeg scene-change detection so the final video is tighter, and (b) render letterbox caption PNGs and burn them into a black bar at the top of the video so the game/screen area is 100% unobstructed. Use INSTEAD of the video-caption skill when the user explicitly objects to captions blocking the video.
---

# Video Edit: Letterbox Captions + Static Trim

## When to use this skill (not the basic `video-caption` skill)

Use this skill when the user wants ALL of:

1. **Captions above the video** — explicitly says "above", "letterbox", "black bar at top", "don't block", "extend the video vertically", or otherwise rejects top-overlay captions.
2. **Static 5+ second segments trimmed out** — says "remove the boring parts", "trim where the character isn't moving", "5-second freeze", "cut the static moments".

If only one of the two is needed, prefer the simpler skill:

- Captions only (top overlay OK) → use `~/.claude/skills/video-caption/SKILL.md`
- Trim only, no captions → just run `ffmpeg -vf "select=...,setpts=..."` directly, no skill needed

## Provenance (why this skill exists)

This pattern was first used by the user on **2026-05-16 in Slack `#all-$USER-ai`** for a YouTube walkthrough: *"Lets extend the video vertically by adding a black bar at the top for the new captions so they dont block the video."* It was re-used **2026-07-11** for the `worldai_claw_v60` gameplay capture (Slack thread 1778907665.216479), where the user also added *"lets remove parts of the video where the character isnt moving for 5 seconds or trim"* — hence combining the two into one skill.

## The two-pass workflow

### Pass 1 — Detect static segments

Goal: rank minutes by activity so you can pick which minutes to trim.

```bash
# Per-frame scene-change scores (0.0 = identical, 1.0 = totally different)
ffmpeg -y -i INPUT.mp4 \
  -vf "select='gte(scene\,0)',metadata=print:file=/tmp/scene_scores.txt" \
  -an -vsync vfr -f null - 2>&1 | tail -3

# Parse scores, compute per-second mean, rank minutes by activity
python3 << 'PY'
import re, statistics, json
with open('/tmp/scene_scores.txt') as f:
    pat = re.compile(r'frame:(\d+)\s+pts:\d+\s+pts_time:([\d.]+)\s*\n\s*lavfi\.scene_score=([\d.]+)')
    scores = [{'t': float(m[1]), 's': float(m[2])} for m in pat.findall(f.read())]

# Per-second mean
seconds = {}
for r in scores:
    seconds.setdefault(int(r['t']), []).append(r['s'])
per_sec = [{'sec': k, 'mean': statistics.mean(v), 'max': max(v)} for k, v in seconds.items()]

# Per-minute activity
for start in range(0, 600, 60):
    chunk = [p for p in per_sec if start <= p['sec'] < start+60]
    active = sum(1 for p in chunk if p['mean'] > 0.003 or p['max'] > 0.02)
    avg_mean = statistics.mean(p['mean'] for p in chunk) if chunk else 0
    print(f"min {start//60+1:2d} ({start:3d}-{start+60}s): active={active:2d}/60  mean={avg_mean:.4f}")
PY
```

**Thresholds** (calibrated on the 2026-07-11 `worldai_claw_v60` capture, 30 fps):

| Per-second mean | Verdict |
|---|---|
| `< 0.001` AND no frame > 0.02 | idle / no movement |
| `0.001 – 0.005` | light motion (walking, dialog spinner) |
| `> 0.005` OR frame > 0.02 | active (UI change, scene transition) |

A minute with **< 10 active seconds** out of 60 is a candidate to trim.

### Pass 2 — Trim static minutes

For the boring minutes identified in Pass 1 (e.g. `t=120-180` and `t=420-480`):

```bash
ffmpeg -y -i INPUT.mp4 \
  -vf "select='not(between(t,120,180)+between(t,420,480))',setpts=N/(30*TB)" \
  -an -c:v libx264 -crf 18 -preset fast \
  -movflags +faststart \
  OUTPUT_trimcut.mp4
```

The `setpts=N/(30*TB)` resets timestamps so the output is a contiguous 0-to-(N-1)/30 timeline.

**Always renumber captions for the trimmed timeline** — never carry the original minute numbers over, because they no longer correspond to wall-clock minutes.

### Pass 3 — Render letterbox caption PNGs

Each caption is a 1280×200 opaque black PNG with white 26-pt Helvetica text, vertically centered in the 200px bar. The width matches the source video (1280); height matches the black bar.

```python
from PIL import Image, ImageDraw, ImageFont
import textwrap

VIDEO_W, CAP_H = 1280, 200
font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 26)
avg_char_w = 26 * 0.55
max_chars = int((VIDEO_W - 2*24) / avg_char_w)  # 48px padding

for idx, (start, end, text) in enumerate(captions):
    lines = textwrap.wrap(text, width=max_chars)
    line_h = 26 + 6
    img = Image.new('RGBA', (VIDEO_W, CAP_H), (0, 0, 0, 255))  # opaque black
    draw = ImageDraw.Draw(img)
    total_h = line_h * len(lines)
    y = (CAP_H - total_h) // 2  # vertical center
    for line in lines:
        draw.text((24, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h
    img.save(f'/tmp/caps/cap_{idx:02d}.png')
```

### Pass 4 — Pad + overlay (the actual "letterbox")

```bash
# Pad source 1280x900 → 1280x1100 (200px black bar at top), then chain overlays
ffmpeg -y -i TRIMMED.mp4 \
  -i cap_00.png -i cap_01.png -i cap_02.png ... -i cap_07.png \
  -filter_complex "
    [0:v]scale=1280:900,pad=1280:1100:0:200:black[padded];
    [1:v]scale=1280:200[c1];
    [2:v]scale=1280:200[c2];
    ...
    [padded][c1]overlay=0:0:enable='between(t,0,60)'[v1];
    [v1][c2]overlay=0:0:enable='between(t,60,120)'[v2];
    ...
    [v7][c8]overlay=0:0:enable='between(t,420,480)'[vout]
  " \
  -map '[vout]' \
  -c:v libx264 -crf 20 -preset medium -an \
  -movflags +faststart \
  OUTPUT_letterbox.mp4
```

**Critical filter-graph gotchas:**

1. **`enable='...'` MUST be in single quotes** — the commas inside `between(t,A,B)` are parsed as filter-chain separators unless quoted. Symptom: `Error: No such filter: '0'`.
2. **`pad=1280:1100:0:200:black`** — args are `output_w:output_h:x:y:color`. `x=0, y=200` means "place the original video in the bottom 900px, leaving 200px black at top".
3. **Each caption PNG needs an explicit `scale=1280:200`** before overlay — ffmpeg doesn't auto-scale PNG inputs.

## Working example

Captured **2026-07-11** for `$HOME/Downloads/worldai_claw_v60_gameplay_20260711.mp4` (58 min, 1280×900, 30 fps, no audio):

1. Identified 35:00–45:00 as the most-engaging 10-min window (engagement peaks at 39:00 quest hook and 15:00 Dain Fletcher smithy).
2. Extracted 600 frames at 1 fps for 35:00–45:00.
3. Dispatched 10 parallel agents (1 per minute) for chunk descriptions + burn captions.
4. Ran scene-change detection — minute 3 (120–180s, 2 active sec/60) and minute 8 (420–480s, 0 active sec/60) were the most static.
5. Trimmed those 2 minutes → 480 s output.
6. Renumbered captions: old minutes 1, 2, 4, 5, 6, 7, 9, 10 → new minutes 1–8.
7. Rendered 8 letterbox caption PNGs (1280×200 each).
8. Pad+overlay → 1280×1100, 8 min, captions ABOVE the game area.

Final outputs (in `~/Documents/`):
- `worldai_v60_35-45_letterbox.mp4` (37 MB) — captions above, game unobstructed
- `worldai_v60_35-45_trimcut.mp4` (39 MB) — trimmed, no captions

## Quick reference

| Step | Tool | Key detail |
|---|---|---|
| Scene scores | `ffmpeg -vf "select='gte(scene\\,0)',metadata=print"` | per-frame 0–1 score; aggregate to per-second mean |
| Rank minutes | Python `statistics.mean` | active_sec > 0.003 mean OR > 0.02 max = active |
| Trim | `select='not(between(t,A,B)+...)',setpts=N/(30*TB)` | renumber captions after trim |
| Render captions | PIL `Image.new('RGBA', (W, H), (0,0,0,255))` | opaque black, vertical-center text |
| Letterbox pad | `pad=1280:1100:0:200:black` | args: out_w:out_h:x:y:color |
| Overlay chain | `[prev][cap]overlay=0:0:enable='between(t,A,B)'` | **single-quote the enable expression** |

## Common mistakes

- **Putting captions in a transparent overlay on top of the video** — that's the `video-caption` skill. Don't use it here; the user has explicitly rejected that.
- **Forgetting `setpts=N/(30*TB)` after `select=`** — output plays at wrong speed; ffmpeg tries to fill the original duration with fewer frames.
- **Unquoted commas in `between(t,A,B)`** — `[AVFilterGraph] No such filter: '0'`. Always wrap the enable expression in single quotes.
- **Pad x/y wrong direction** — `pad=1280:1100:0:200:black` puts video at the BOTTOM. `pad=1280:1100:0:0:black` would put it at the top with black at bottom. Always make `y = CAP_H` so video stays put.
- **Caption PNG not scaled** — overlay draws at the PNG's native size. If your PNG is 640×200 but the bar is 1280×200, text fills only half the bar. Always `scale=1280:200` before `overlay=`.

## Files & references

- `scripts/render_and_burn.py` — full Python pipeline that does passes 2–4 in one shot. Adapted from `/tmp/wai_v60_caps/captions_v2.py`.
- `references/static-detection.md` — deeper notes on the scene-change threshold calibration, including the per-second analysis table from the 2026-07-11 run.
- See also: `~/.claude/skills/video-caption/SKILL.md` (overlay-on-top variant, use when blocking is OK).