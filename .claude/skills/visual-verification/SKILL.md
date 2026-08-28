---
name: visual-verification
description: Verify images, sprites, screenshots, and videos with tools that can inspect visual content reliably.
---

# Visual Verification Skill

## Purpose

Handle all visual verification tasks (images, sprites, screenshots, videos) with the correct tools that actually work on Linux.

## The Problem

Claude Code's Read tool returns `null` for PNG/JPG files on Linux. This is a known bug (#18588, #20822, #55338). Do NOT rely on Read for image files on Linux.

## Working Tools

### For Image Analysis
**Use `mcp__minimax__understand_image` — this works reliably:**
```
mcp__minimax__understand_image({
  image_source: "/path/to/image.png",
  prompt: "Describe what you see. Is it good quality or garbage?"
})
```

### For Browser Screenshots
Use Playwright MCP:
```
mcp__playwright-mcp__browser_navigate({ url: "http://..." })
mcp__playwright-mcp__browser_take_screenshot({ filename: "/tmp/screenshot.png" })
```

### For Video Frames
1. Extract frames with ffmpeg: `ffmpeg -i video.mp4 /tmp/frames/frame_%04d.png`
2. Analyze with `mcp__minimax__understand_image`

## Verification Rule — FAIL LOUDLY

**If you cannot visually verify something, STOP and say so.**

Bad behavior (DO NOT DO):
- "The sprite looks good based on pixel values" (you can't see it)
- Analyzing RGB numbers and claiming to assess visual quality
- Saying "I can see it" when Read returns null
- Using subagent pixel analysis as a substitute for actually seeing

Correct behavior:
- Use `mcp__minimax__understand_image` for visual analysis
- If that fails, admit "I cannot visually verify this"
- If user asks for visual assessment, use the minimax tool first

## When Assessing Sprites/Game Graphics

1. Capture screenshot or locate sprite file
2. Call `mcp__minimax__understand_image` with detailed prompt
3. Report what the model says, not what your pixel analysis suggests
4. If minimax fails, say you cannot verify visually

## Sprite Quality Claims

For sprite quality evaluations, use the `/sprite-eval` skill which mandates visual evidence. Do not make sprite quality claims without actual visual analysis via working tools.

## Test

If you need to verify image viewing works:
```
/test-vision
```
This will test minimax understand_image on a known image.
