---
description: /4layer - Four-Layer Minimal Repro Testing Protocol
type: testing
execution_mode: immediate
---

## Purpose

Runs the Four-Layer Minimal Repro ladder to reproduce PR blockers quickly with evidence-backed classification.

Primary source is the existing command definition and protocol companion:
- `.claude/commands/4layer.md`
- `.claude/skills/pr-blocker-min-repro.md`

## Minimal Repro Ladder

Prerequisite: set `$PROJECT_ROOT` to your repository root, or replace it with the
absolute repository path in the commands below.

Run tests in this order and stop at the first layer that conclusively reproduces the blocker:

1. Unit tests (`$PROJECT_ROOT/tests/`)

```bash
./vpython -m pytest $PROJECT_ROOT/tests/test_[relevant].py -q
```

2. End-to-end tests (`$PROJECT_ROOT/$PROJECT_ROOT/tests/test_end2end/`)

```bash
./vpython -m pytest $PROJECT_ROOT/$PROJECT_ROOT/tests/test_end2end/test_[feature]_end2end.py -q
```

3. MCP/HTTP API tests (`testing_mcp/`)

```bash
./vpython testing_mcp/[domain]/test_[feature]_real.py
```

4. Browser tests (`testing_ui/`)

```bash
./vpython testing_ui/[domain]/test_[feature]_browser.py
```

## Execution Rules

1. Identify blocker and target only relevant, minimal tests.
2. Start at Layer 1. Move upward only if the current layer passes.
3. Keep provider/user isolation so parallel runs do not collide.
4. Record absolute evidence paths after each executed layer.
5. Report the first layer that reproduces the issue; do not run unnecessary upper layers.

## Evidence Requirements

After each test run, capture:

- Full absolute evidence directory path (for example `/tmp/worldarchitectai/<branch>/<test>/latest/`).
  Verify the actual path from test configuration, environment variables, or run output
  because local and CI evidence directories may differ.
- Signature failure lines with context (`rg`/`grep` output).
- Screenshot + server log consistency checks where applicable.
- Final decision notes mapping blocker layer to component class:
  - Unit fail → backend logic
  - End2end fail → integration/API
  - MCP fail → server protocol
  - Browser fail → UI/frontend

## References

- `.claude/skills/testing-layers/SKILL.md` for deciding which layer to write NEW tests in and evidence implications.
- `.claude/skills/pr-blocker-min-repro.md` for BYOK-specific starter commands and bead note patterns.
- `.claude/skills/integration-verification.md` for minimum evidence completeness.
