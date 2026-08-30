---
description: /factory-evolve — analyze conversation + git history to find where cold reviews (codex, Bugbot, CodeRabbit, /reviewdeep) caught issues the factory reviewer nodes missed. Fans out subagents, opens PRs end-to-end, drives each through /green, merges with explicit MERGE APPROVED. Proposes targeted .dot and runner improvements.
type: llm-orchestration
execution_mode: immediate
aliases: [fe]
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/factory-evolve.md` completely, then execute it with `$ARGUMENTS`.
