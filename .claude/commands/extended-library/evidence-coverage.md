# /evidence-coverage — Logic × Evidence Coverage Matrix

Build a comprehensive table mapping every production logic change in the current PR
to its required testing layer, existing evidence, and coverage gaps.

## Skill

See `.claude/skills/evidence-coverage.md` for the full procedure.

## Quick start

Run the analysis for the current branch:

1. Identify all production file changes vs main
2. Classify each into testing layer (L1/L2/L3/L5)
3. Locate and freshness-check evidence bundles
4. Build the Logic × Evidence Matrix table
5. Report summary stats and recommended actions for gaps

## Example domains to cover

When analyzing a PR, identify the core domains of the logic changes, such as:
- **Routing & Trigger gates**: Cooldowns, turn/time triggers
- **Prompt contracts**: Required or forbidden snippets, new schemas
- **State management**: State pruning, saving state post-LLM
- **New Feature Contracts**: Autonomous detection, scaling, breaking conditions
- **Thread safety**: Locks and concurrency controls

## Output

Markdown table + summary stats + action items with beads for each gap.
