---
description: Review evidence artifacts for a claim, then check evidence-standards compliance. Dispatches to codex via orchestration library and hard-aborts if required skills fail to load (no inline fallback).
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/evidence-review/SKILL.md` completely, then execute it with `$ARGUMENTS`.
