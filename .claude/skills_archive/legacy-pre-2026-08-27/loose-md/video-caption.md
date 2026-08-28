---
name: video-caption
description: Use when asked to analyze a video file and add visual description captions or text overlays burned into the output video
---

# Video Captioning

## Overview

Analyze a video by extracting frames at intervals, describe each segment visually, then burn captions at the top of the video using PIL-rendered PNG overlays and ffmpeg's `overlay` filter. This approach avoids dependency on ffmpeg's `libass`/`drawtext` filters, which are often absent in Homebrew builds.

## When to Use

- "Add captions to this video"
- "Describe visually what's happening in this video"
- "Annotate this screen recording"

## Workflow

### 1. Inspect the video

```bash
ffprobe -v quiet -print_format json -show_format -show_streams "video.mov" | python3 -c "
import json, sys
d = json.load(sys.stdin)
fmt = d['format']
vs = [s for s in d['streams'] if s['codec_type'] == 'video'][0]
has_audio = any(s['codec_type'] == 'audio' for s in d['streams'])
print(f'Duration: {float(fmt[\"duration\"]):.1f}s, {vs[\"width\"]}x{vs[\"height\"]} @ {vs[\"r_frame_rate\"]}fps, audio={has_audio}')
"
```

Note: track whether audio exists — it affects the final ffmpeg command.

### 2. Extract frames for analysis

```bash
mkdir -p /tmp/video_frames
ffmpeg -i "video.mov" -vf "fps=1/10,scale=1280:-1" -q:v 3 /tmp/video_frames/frame_%03d.jpg -y
```

One frame per 10 seconds is sufficient. Adjust `fps=1/N` for longer videos.

### 3. Read and analyze frames

Use the `Read` tool on each frame image — Claude can view them directly. Read 4 at a time in parallel. Build a timeline:

```
0-10s:  What's happening in the UI/screen/scene
10-20s: What changed, what action is occurring
...
```

### 4. Render caption PNGs with PIL

```python
from PIL import Image, ImageDraw, ImageFont
import textwrap, os

VIDEO_W = 3354   # match your video width
FONT_SIZE = 62
PADDING = 40
FONT = '/System/Library/Fonts/Helvetica.ttc'  # macOS

# captions: list of (start_sec, end_sec, text)
captions = [
    (0, 10, "Description of what's happening..."),
    ...
]

font = ImageFont.truetype(FONT, FONT_SIZE)
os.makedirs('/tmp/caps', exist_ok=True)

for i, (start, end, text) in enumerate(captions):
    avg_char_w = FONT_SIZE * 0.55
    max_chars = int((VIDEO_W - 2 * PADDING) / avg_char_w)
    lines = textwrap.wrap(text, width=max_chars)
    line_h = FONT_SIZE + 10
    cap_h = line_h * len(lines) + 2 * PADDING

    img = Image.new('RGBA', (VIDEO_W, cap_h), (0, 0, 0, 170))  # semi-transparent black
    draw = ImageDraw.Draw(img)
    y = PADDING
    for line in lines:
        draw.text((PADDING, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    img.save(f'/tmp/caps/cap_{i:02d}_{start}_{end}.png')
```

### 5. Burn captions with ffmpeg overlay

```python
import subprocess

# Build inputs and filtergraph
cmd = ['ffmpeg', '-i', 'video.mov']
for start, end, path in [(s, e, f'/tmp/caps/cap_{i:02d}_{s}_{e}.png') for i, (s, e, _) in enumerate(captions)]:
    cmd += ['-i', path]

n = len(captions)
prev = '0:v'
parts = []
for i, (start, end, _) in enumerate(captions):
    out = f'v{i+1}' if i < n - 1 else 'vout'
    parts.append(f"[{prev}][{i+1}:v]overlay=0:0:enable='between(t,{start},{end})'[{out}]")
    prev = out

cmd += ['-filter_complex', ';'.join(parts), '-map', '[vout]']

# Only add audio map if audio stream exists
if has_audio:
    cmd += ['-map', '0:a', '-c:a', 'copy']

cmd += ['-c:v', 'libx264', '-crf', '18', '-preset', 'fast', 'output captioned.mov', '-y']
subprocess.run(cmd, check=True, timeout=600)
```

## Quick Reference

| Step | Tool | Key detail |
|---|---|---|
| Inspect | `ffprobe` | Get duration, resolution, audio presence |
| Extract frames | `ffmpeg fps=1/10` | 1 frame/10s is enough |
| Analyze | `Read` tool | Read 4 frames in parallel |
| Render captions | PIL `Image.new('RGBA')` | Semi-transparent: alpha=170 |
| Burn in | ffmpeg `overlay` + `enable='between(t,s,e)'` | Chain all overlays in one filtergraph |

## Common Mistakes

- **`-map 0:a` without audio** → ffmpeg errors. Check streams first.
- **`subtitles=` or `ass=` filter** → Often absent in Homebrew ffmpeg (no libass). Use PIL+overlay instead.
- **`drawtext` filter** → Also absent if ffmpeg lacks freetype. Same fallback.
- **Caption too long for one line** → Use `textwrap.wrap` with `width = (video_w - 2*padding) / (font_size * 0.55)`.
- **Wrong video width in PIL** → Must match source exactly or overlay misaligns.

## Font Paths (macOS)

```
/System/Library/Fonts/Helvetica.ttc
/System/Library/Fonts/SFNS.ttf
/System/Library/Fonts/SFNSMono.ttf
```
