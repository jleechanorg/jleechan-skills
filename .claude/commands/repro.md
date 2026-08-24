---
description: /repro — read repro-evidence skill (canonical); no logic here
type: orchestration
execution_mode: immediate
---

# /repro

<!-- Note: This repo intentionally points to the generic repro-evidence skill rather than the user's personal/global WorldAI-specific skill at ~/.claude/skills/repro-twin-clone-evidence/SKILL.md. -->

Read **`.claude/skills/repro-evidence/SKILL.md`** and execute it according to `$ARGUMENTS`.

All routing, env, isolation/cloning steps, and evidence exports live **only** in that skill — not in this file.
