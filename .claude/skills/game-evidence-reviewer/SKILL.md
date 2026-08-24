---
name: game-evidence-reviewer
description: Review game/demo video evidence against Ragnarok Online quality standards.
---

# Game Evidence Reviewer Skill

Review game/demo video evidence against Ragnarok Online quality standards.

## Wiki Reference
See [[Ragnarok Quality Game Demo Criteria|sources/ragnarok-quality-game-demo-criteria]] for full criteria.

## Activation
```
/game-er [evidence_path]
```
Or invoke when validating any game demo evidence.

## ⚠️ MANDATORY EXECUTION - You MUST run these commands

This skill is WORTHLESS without real analysis. You **MUST** execute the following pipeline:

### Step 1: Extract frames with ffmpeg
```bash
# Extract 3 key frames: first, middle, last
ffmpeg -y -i [video.gif] -vf "select=eq(n\,0)" -frames:v 1 /tmp/game_er_frame0.png 2>/dev/null
ffmpeg -y -i [video.gif] -vf "select=eq(n\,15)" -frames:v 1 /tmp/game_er_frame15.png 2>/dev/null
ffmpeg -y -i [video.gif] -vf "select=eq(n\,29)" -frames:v 1 /tmp/game_er_frame29.png 2>/dev/null
```

### Step 2: Analyze frames with Python
```python
python3 << 'EOF'
from PIL import Image
import os

frames = ['/tmp/game_er_frame0.png', '/tmp/game_er_frame15.png', '/tmp/game_er_frame29.png']
for f in frames:
    if not os.path.exists(f):
        print(f"MISSING: {f}")
        continue
    img = Image.open(f)
    data = list(img.getdata())
    unique = len(set(data))
    
    # Count warm (skin), cool (sky), green (grass), gray pixels
    warm = sum(1 for p in data if p[0] > 150 and p[1] > 80 and p[2] < 150)
    cool = sum(1 for p in data if p[2] > 150 and p[0] < 100)
    green = sum(1 for p in data if p[1] > 80 and p[1] > p[0])
    gray = sum(1 for p in data if abs(p[0]-p[1]) < 10 and abs(p[1]-p[2]) < 10)
    
    print(f"{f}: {img.size}, unique:{unique}, warm:{warm}, cool:{cool}, green:{green}, gray:{gray}")
EOF
```

### Step 3: Verify video properties
```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height,frame_rate [video]
```

### Step 4: Calculate animation frame diff
```python
python3 << 'EOF'
from PIL import Image
import os

f0 = Image.open('/tmp/game_er_frame0.png')
f15 = Image.open('/tmp/game_er_frame15.png')

# Calculate pixel diff between frames
data0 = list(f0.getdata())
data15 = list(f15.getdata())

diff = sum(1 for i in range(len(data0)) if data0[i] != data15[i])
print(f"Frame 0 vs 15 diff: {diff} pixels changed (animation indicator)")

# Higher diff = more animation
if diff > 1000:
    print("✓ ANIMATED")
elif diff > 100:
    print("~ SOME MOVEMENT")
else:
    print("✗ STATIC OR NEARLY STATIC")
EOF
```

## Ragnarok Online Quality Criteria

### 1. Sprite Quality
| Criterion | Ragnarok Standard | Threshold |
|-----------|------------------|-----------|
| Resolution | 256x256 sprites | Check frame dimensions |
| Color depth | 256-color style | Unique colors > 128 |
| Animation frames | 8-frame walk cycle | Frame diff > 500 pixels |

### 2. Animation Quality
| Criterion | Ragnarok Standard | Threshold |
|-----------|------------------|-----------|
| Walk cycle | 8 distinct frames | Frame 0 vs 15 diff > 1000 |
| Smooth motion | 8-12 fps | Consistent timing |
| Character shadow | Ground shadow | Dark blob follows character |

### 3. Environment Quality
| Criterion | Ragnarok Standard | Threshold |
|-----------|------------------|-----------|
| Tile consistency | Clean edges | Sharp boundaries |
| Color harmony | Cohesive palette | No clashing regions |

### 4. Game Feel
| Criterion | Ragnarok Standard | Threshold |
|-----------|------------------|-----------|
| Controls | WASD responsive | Movement visible |
| Collision | Wall blocking | Cannot pass through |

## Pass/Fail Determination

**STRONG PASS** (all must be true):
- [ ] Unique colors > 128
- [ ] Frame diff > 1000 (animated)
- [ ] Warm pixels present (character skin tones)
- [ ] Green/grass pixels present (environment)
- [ ] Video plays without corruption

**WEAK PASS** (core works, minor gaps):
- [ ] Animation present but frame diff < 1000
- [ ] Sprites visible but colors < 128 unique

**FAIL** (any one = fail):
- [ ] Frame diff < 100 (static or broken)
- [ ] No warm pixels (no character rendered)
- [ ] Video is blank/black/corrupted
- [ ] Unique colors < 32 (severely degraded)

## Output Format

```markdown
## Game Evidence Review

**File**: [path]
**Duration**: Xs | **Size**: WxH | **FPS**: X

### Frame Analysis
| Frame | Unique Colors | Warm Pixels | Green Pixels |
|-------|-------------|-------------|--------------|
| 0     | XXX         | XXX         | XXX          |
| 15    | XXX         | XXX         | XXX          |
| 29    | XXX         | XXX         | XXX          |

### Animation Check
- Frame 0 vs 15 diff: XXXX pixels
- Status: [ANIMATED / SOME MOVEMENT / STATIC]

### Sprite Quality: [PASS/FAIL]
- Unique colors: XXX (>128 = good)
- Warm pixels: XXX (character present)

### Environment: [PASS/FAIL]
- Green pixels: XXX (grass/environment)
- Tile edges: [sharp/blurry]

### Game Feel: [PASS/FAIL]
- Animation movement: [visible/not visible]
- Controls responsive: [inferred from movement]

## OVERALL: [STRONG/WEAK/FAIL]
**Reason**: [specific statement]
```

## Example Usage

```
/game-er /tmp/game_demo_evidence/animated_demo.gif
/game-er /tmp/game_demo_evidence/level_demo.gif
```

## Critical Rules

1. **You MUST extract frames** - don't just describe the commands, actually run ffmpeg
2. **You MUST run the Python analysis** - get actual pixel counts
3. **You MUST report specific numbers** - "some warm pixels" is useless, say "2,847 warm pixels"
4. **You MUST calculate frame diff** - animation verification is not optional
5. **Blank video = FAIL immediately** - don't continue analyzing
6. **Static image = FAIL** - frame diff < 100 means no animation