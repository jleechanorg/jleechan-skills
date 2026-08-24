---
description: /keychain_kill — Terminate macOS SecurityAgent and dismiss all stacked keychain modal prompts
type: llm-orchestration
execution_mode: immediate
---

# /keychain_kill

Immediately dismiss all stacked macOS `SecurityAgent` credential popups by hard-killing their processes, then diagnose the headless keyring root cause.

Read `~/.claude/skills/keychain-kill/SKILL.md` and execute the full workflow.

## Quick reference

| Step | Action |
|------|--------|
| 1 | Hard kill `SecurityAgent` / `universalAccessAuthWarn` immediately |
| 2 | Diagnose headless keyring root cause (locked login keychain) |
| 3 | Apply permanent fix (isolated session keychain / `--bare` / trusted folders) |
| 4 | Inform the user prompts are dismissed |
