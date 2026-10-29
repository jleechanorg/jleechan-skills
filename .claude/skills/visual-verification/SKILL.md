---
name: visual-verification
description: Verify images, sprites, screenshots, and videos with tools that can inspect visual content reliably.
---

# Visual Verification Skill

## Purpose

Handle visual verification with a currently available image-capable tool. Check
the active runtime's tool catalog and the current image's accessible path before
choosing a route; platform and tool availability can change.

## The Problem

Some runtime Read tools may not render PNG/JPG files on some Linux versions.
Treat that as a limitation of the specific route: probe the available image
viewers or approved analysis tools before concluding that visual inspection is
unavailable. Do not generalize a past tool failure to every Linux host or runtime.

## Working Tools

### For Image Analysis
Use an image-capable tool available in the active runtime, such as its native
image viewer or an approved image-analysis MCP when present. Do not assume a
specific provider/tool is installed; verify availability before invoking it.

### For Browser Screenshots
Use the repository's supported browser automation route and save captures to a
directory allocated through the canonical [Scratch Space skill](../scratch-space/SKILL.md).

### For Video Frames
1. Extract frames with ffmpeg into a directory allocated through the canonical
   [Scratch Space skill](../scratch-space/SKILL.md).
2. Inspect the frames with an available image-capable tool.

## Verification Rule — FAIL LOUDLY

If visual verification remains unavailable after probing supported routes, state
the exact route(s) attempted and the limitation. Continue other authorized work;
do not infer that one unavailable tool means all visual inspection is impossible.

Bad behavior (DO NOT DO):
- "The sprite looks good based on pixel values" (you can't see it)
- Analyzing RGB numbers and claiming to assess visual quality
- Saying "I can see it" when Read returns null
- Using subagent pixel analysis as a substitute for actually seeing

Correct behavior:
- Use an available visual-capable tool and identify the method used.
- If it fails, try another supported route available in the active runtime.
- If all supported routes fail, report the exact limitation and leave the visual claim unproven.

## When Assessing Sprites/Game Graphics

1. Capture screenshot or locate sprite file
2. Use a visual-capable tool that is currently available.
3. Report observed content and any tool-derived analysis separately.
4. If no supported route can inspect the image, report that limitation without making a visual claim.

## Sprite Quality Claims

For sprite quality evaluations, use `/sprite-eval` when its current definition is available. Do not make sprite quality claims without actual visual inspection through a working tool.
