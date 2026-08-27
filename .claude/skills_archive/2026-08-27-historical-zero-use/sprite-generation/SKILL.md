# Sprite Generation Skill

## PROBLEM
LLM-based sprite generation (PIL, Grok, MiniMax without proper workflow) produces garbage:
- 2/10 quality sprites
- Horizontal gaps between body parts
- Checkerboard artifacts
- Misalignment
- General-purpose image gen ≠ pixel art

## RIGHT APPROACH (from wiki research)

### Tier 1: BEST QUALITY - ComfyUI SDXL + Pixel Art LoRA
```
System: RTX 4090, ComfyUI 0.20.1, 22GB VRAM
Checkpoint: sd_xl_base_1.0.safetensors
LoRA: pixel_icon_v1.safetensors (or Pixel Art Stylizer SDXL)

Workflow:
CheckpointLoaderSimple → LoraLoader (strength=1.0)
  → CLIPTextEncode (positive + negative) 
  → EmptyLatentImage (128x128)
  → KSampler (steps=25, cfg=8.0, euler)
  → VAEDecode
  → Quantize (cap at 64-256 colors)
  → SaveImage

Generation time: ~2 seconds on RTX 4090
```

### Tier 2: BEST FREE - Pollinations.ai
- 256x256 sprites
- Respects size parameters (unlike Grok)
- Free, no GPU needed
- Use k-means post-process: alpha-binarize FIRST, then k-means k=24-32

### Tier 3: HYBRID (what we've been trying)
- Generate body parts separately via LLM
- Composite with LPC sprites
- **THIS APPROACH FAILS** - wiki explicitly says "body parts pipeline = failed approach"
- Don't use PIL-based generation - produces simple geometric shapes, not pixel art

## WHAT DOESN'T WORK
- ❌ PIL ImageDraw generation (simple shapes, not art)
- ❌ Grok API (ignores size params, returns 1408x768)
- ❌ General LLM image gen without pixel art LoRA
- ❌ k-means without alpha-binarize first (destroys colors)
- ❌ Body parts pipeline (failed approach per wiki)

## WORKING ASSETS ALREADY AVAILABLE
- **Cordon CC0**: 205 sci-fi sprites at 128x128 in `assets/cordon/temp_cordon/sprites/`
- **LPC Sprites**: `assets/generated/body_parts/` (if properly generated)
- **Procedural drawPixelCharacter()**: Works in game_demo.html

## DECISION TREE

1. **Need sprites NOW?** → Use Cordon CC0 assets or procedural fallback
2. **Want quality pixel art?** → Use ComfyUI SDXL + pixel_icon_v1 LoRA
3. **Free only?** → Use Pollinations.ai with proper prompting
4. **Don't use**: PIL generation, Grok, body parts pipeline

## PROPER PROMPTING FOR POLLINATIONS
```
"pixel art, 128x128, knight walk cycle, 8 frames, side view,
transparent background, limited color palette 24 colors,
pixel-perfect edges, no anti-aliasing, no gradients,
medieval armor, fantasy RPG sprite"
```

## POST-PROCESSING (if using LLM output)
1. Alpha-binarize (threshold transparency)
2. k-means palette reduction (k=24-32 for 128x128)
3. Nearest-neighbor upscale if needed
4. Manual cleanup in Aseprite (5 sec/frame)

## REFERENCES
- Wiki: ~/llm_wiki/wiki/sources/comfyui-pixel-art-sprite-pipeline-2026-05-01.md
- Wiki: ~/llm_wiki/wiki/sources/sprite-generation-learnings-2026-05-01.md
- Wiki: ~/llm_wiki/wiki/sources/pixel-art-ai-generation-research-2026-05-01.md
