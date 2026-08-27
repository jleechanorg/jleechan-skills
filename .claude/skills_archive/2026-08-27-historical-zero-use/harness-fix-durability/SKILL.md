---
name: harness-fix-durability
description: "Use when /harness is invoked or fixing a harness rule violation. Matches fix durability to severity (nit=memory, wrong=CLAUDE.md, silent-sub=hook+commitment)."
---

# Harness fix durability must match violation severity

| Violation severity | Minimum fix durability |
|---|---|
| Nitpick/style | Memory |
| Wrong approach | CLAUDE.md instruction |
| Commitment integrity | Hook (PreToolUse/PostToolUse) |
| Silent substitution | Hook + commitment file |
| Data loss / security | Hook + CI gate |

When running `/harness`, match the fix to the severity. Instructions alone cannot prevent commitment violations — they need hooks.
