---
description: /4layer - Four-Layer Minimal Repro Testing Protocol
type: testing
execution_mode: immediate
---

# /4layer [blocker_description]

**When this command is invoked, execute the ladder immediately — this is
not documentation, it is a command to run right now.**

Read `~/.claude/skills/4layer/SKILL.md` and execute the full Four-Layer
Minimal Repro ladder against `<blocker_description>`.

## Testing ladder (stop at first layer that conclusively reproduces)

| Layer | Location | Example |
|---|---|---|
| 1. Unit | `$PROJECT_ROOT/tests/` | `python3 -m pytest $PROJECT_ROOT/tests/test_[relevant].py -q` |
| 2. End-to-end | `$PROJECT_ROOT/tests/test_end2end/` | `python3 -m pytest $PROJECT_ROOT/tests/test_end2end/test_[feature]_end2end.py -q` |
| 3. MCP/HTTP API | `testing_mcp/` | `python3 testing_mcp/[domain]/test_[feature]_real.py` |
| 4. Browser | `testing_ui/` | `python3 testing_ui/[domain]/test_[feature]_browser.py` |

Classification: unit fail → backend logic; end2end fail → integration/API;
MCP fail → server protocol; browser fail → UI/frontend.

## References

- `.claude/skills/pr-blocker-min-repro/SKILL.md` — BYOK-specific starter commands
- `.claude/skills/integration-verification/SKILL.md` — minimum evidence completeness
