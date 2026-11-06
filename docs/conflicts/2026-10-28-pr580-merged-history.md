# Prior merge conflict documented for PR #580 history

## `.claude/skills/evidence-review/SKILL.md`
- Evidence-review acceptance additions in merge `3a62ba22a86e11048271fdf3f4d6d49a1d50d50f`: **Kept both** — the merge result preserves main’s independent video-content review requirement and the other parent’s actual-frame visual inspection requirement. They cover different checks and are complementary. The historical merge commit did not contain a resolution document; this entry records the result now because the required conflict-document checker validates every merge in the PR branch range.

## Tests
- Before: `git merge-tree --write-tree --name-only 9ce163c251e2a2570b88c6f647db0a9df248ebd6 aefc5210da3ec1d2dfe0400c3a6981b0098bec2b` → reported a conflict in this file.
- After: `git show 3a62ba22a86e11048271fdf3f4d6d49a1d50d50f:.claude/skills/evidence-review/SKILL.md` → confirms both acceptance additions in the merged file.
