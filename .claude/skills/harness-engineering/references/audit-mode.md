# Harness audit mode (`/harness --audit`)

This mode adds a full sweep of harness files for accumulated drift to the
mandatory analysis protocol and shared Step 7 closure in the parent skill. Scan
`~/.claude/CLAUDE.md`, repo-local `CLAUDE.md`, `~/.codex/AGENTS.md`, workspace
`.claude/commands/`, and `~/.claude/skills/*/` for the full audit; do not apply
optimization mode's focused-reading rule to this sweep. Check for:

- **Stale rules** — instructions that reference files/tools/patterns that no
  longer exist
- **Contradictions** — rules in different files that conflict
- **Gaps** — known failure patterns (from memory) without corresponding
  instructions
- **Duplication** — the same rule stated in multiple places (consolidate to the
  most durable layer per the Decision Rules in the parent skill)

Report findings as a table:

```
| Issue | File | Line | Recommendation |
|-------|------|------|----------------|
| Stale | ~/.claude/CLAUDE.md | 42 | Remove reference to deprecated tool X |
| Gap | repo CLAUDE.md | - | Add rule about Y (corrected 3x in memory) |
```
