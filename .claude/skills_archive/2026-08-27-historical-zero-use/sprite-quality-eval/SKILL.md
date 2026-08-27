# Sprite Quality Evaluation — Strict Visual Assessment

Evaluate sprite quality via **visual analysis only**. No pixel metrics, no PIL — only `mcp__minimax__understand_image`.

## Usage

```
/sprite-eval <description of what to evaluate>
```

## Required Execution — ALWAYS use subagent

**MANDATORY**: For any sprite quality evaluation, spawn a `minimax-pair-coder` subagent:

```
Agent({ subagent_type: "minimax-pair-coder", prompt: "..." })
```

The subagent must use `mcp__minimax__understand_image` to visually assess the sprite.

## Strict Evaluation Criteria

Score sprites 1-10 on these **specific** dimensions:

1. **Proportions** — anatomy looks right, not boxy or malformed
2. **Color contrast** — sprite reads against background, not camouflaged
3. **Silhouette clarity** — recognizable as a character/object even in silhouette
4. **Shading/depth** — has highlights/shadows, not flat
5. **Style consistency** — matches the game's art direction
6. **Transparency** — alpha channel works, no stray white boxes
7. **Animation readiness** — clear frame boundaries, distinct limb positions

## Scoring Rules

| Score | Meaning | Action |
|-------|---------|--------|
| 9-10 | Excellent — ready for production | PASS |
| 7-8 | Good — minor tweaks needed | PASS with notes |
| 5-6 | Acceptable — functional but flawed | Regenerate if user wants better |
| 3-4 | Poor — major issues, likely fails in-game | Regenerate |
| 1-2 | Unusable — wrong approach entirely | Switch to different asset/library |

**Minimum pass threshold: 6/10**
Below 6/10 is FAIL — do not show to user without warning.

## Subagent Prompt Template

```
Navigate to [URL or path] and take a screenshot.
Use mcp__minimax__understand_image to visually analyze the sprite.
Be STRICT — do not excuse problems. If something looks bad, say so.
Score each dimension 1-10 and give an overall 1-10 score.
Report specific issues by name, not vague descriptions.
```

## Workflow

1. Generate/create sprite
2. Spawn subagent to evaluate via minimax
3. If score < 6: regenerate or switch to real assets (Cordon CC0, etc.)
4. If score >= 6: show to user
5. Never hide a low score — warn before showing anything below 6/10

## Examples of Strict Scoring

**Score 3/10**: "The sprite has a white box around it, wrong proportions, and the arms look like sticks coming out of a refrigerator."

**Score 7/10**: "Good proportions and readability. Helmet lacks metallic highlight. Minor shadow flatness. Acceptable."

**Score 9/10**: "Excellent pixel art — clear silhouette, warm palette, proper shading, transparent background works. Ready for production."

## Important

- Use **minimax-pair-coder** agent type (uses MiniMax-M2.5 via claudem)
- Instruct subagent: "be very strict, do not soften criticism"
- If screenshot needed, navigate first then take screenshot
- When evaluating game demos, assess the sprite IN CONTEXT of the game world, not just in isolation