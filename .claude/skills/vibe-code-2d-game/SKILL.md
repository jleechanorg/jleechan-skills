---
name: vibe-code-2d-game
description: Ship 2D games fast using LLM assistance — rapid prototyping, iterate fast, don't perfect
---

# Vibe Code 2D Game Development

Ship 2D games fast using LLM assistance. "Vibe coding" = rapid prototyping, iterate fast, don't perfect.

## Core Philosophy
- **Ship in days, not months** - 2-week timeline works (proven by capybara game dev)
- **Character + mechanics > graphics** - gameplay > pixel-perfect art
- **LLM assists, human steers** - use AI for code/sprites, human decides direction
- **Iterate based on play** - get something playable, test, improve

## 2D Game Stack (Proven)
- **HTML5 Canvas** - simplest, runs anywhere
- **Vanilla JS** - no framework overhead
- **Pixel art sprites** - LPC (medieval), ComfyUI SDXL (generated), Cordon CC0 (sci-fi)
- **Tile maps** - JSON from LLM, render to canvas

## Sprite Pipeline (Ranked)
| Source | Quality | Speed | Cost |
|--------|---------|-------|------|
| ComfyUI SDXL (local) | ✅ Best | Fast | GPU only |
| Pollinations.ai | Good | ~2s | Free |
| LPC pixel art | Real pixel | Instant | CC0 |
| Grok API | OK | Fast | API key |

## Animation Approach
- **8-frame walk cycles** - sine-wave bob + leg alternation
- **State machine** - idle, walk, run, attack
- **Canvas compositing** - layer sprites (body parts)

## Rapid Development Pattern
```
1. Generate sprites (ComfyUI/Pollinations) → /tmp/sprites/
2. Create canvas game shell (player, movement, collision)
3. Add LLM level generation (tilemap JSON → render)
4. Integrate sprites with animation
5. Play → iterate
```

## Key Learnings from Capybara Dev
- Someone shipped full game in 2 weeks with Claude Code
- "Vibe coding" = trust the LLM, iterate fast
- Game had: character (capybara) + mechanics (delivery) + environment (city)
- The tools work - barrier is low

## Command Reference
```bash
# Start local dev server
python3 -m http.server 8765

# ComfyUI generation
python3 ~/ComfyUI/venv/bin/python3 main.py --force-fp16 --cuda-device 0

# Pollinations sprite
curl -o /tmp/sprite.png "https://image.pollinations.ai/prompt/[prompt]?width=256&height=256"
```

## Sprite Locations (worldai_claw)
- LPC: `assets/sprite_packs/lpc_entry/png/slash/`
- Cordon: `assets/cordon/temp_cordon/sprites/`
- Generated: `/tmp/sprites_batch/`, `assets/generated/`
- Demos: `lpc_character_demo.html`, `game_demo.html`, `cordon_level_demo.html`