---
name: 4layer
description: /4layer - Four-Layer Minimal Repro Testing Protocol
type: testing
execution_mode: immediate
---

## Purpose

Runs the Four-Layer Minimal Repro ladder to reproduce PR blockers quickly with evidence-backed classification.

This skill owns the protocol for `/4layer` and `four-layer`. Command files are
thin dispatchers, not protocol dependencies; an absent global
`commands/extended-library/4layer.md` does not require a project overlay.

Before executing, read both mandatory companions completely, resolving these paths
relative to this skill (on catalog-only runtimes, resolve each exact companion name
and read its returned definition):
- `../pr-blocker-min-repro/SKILL.md`
- `../integration-verification/SKILL.md`

If either companion is missing, report the missing dependency and do not claim the
workflow is complete. Discover actual project runners before using companion examples;
examples do not authorize provider calls or changes to shared state.

## Minimal Repro Ladder

Run tests in this order and stop at the first layer that conclusively reproduces the blocker:

First discover the target project's documented test runner (`AGENTS.md`, `README`,
`package.json`, `pyproject.toml`, or `Makefile`). Do not assume `./vpython` exists.
If no runnable test command or matching layer fixture exists, report
`UNSUPPORTED ENVIRONMENT / NO REPRO` with the checked paths instead of inventing one.

1. Unit tests (`$PROJECT_ROOT/tests/`, when present)

```bash
python3 -m pytest $PROJECT_ROOT/tests/test_[relevant].py -q
```

2. End-to-end tests (`$PROJECT_ROOT/tests/test_end2end/`)

```bash
python3 -m pytest $PROJECT_ROOT/tests/test_end2end/test_[feature]_end2end.py -q
```

3. MCP/HTTP API tests (`testing_mcp/`)

```bash
python3 testing_mcp/[domain]/test_[feature]_real.py
```

4. Browser tests (`testing_ui/`)

```bash
python3 testing_ui/[domain]/test_[feature]_browser.py
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
- Signature failure lines with context (`rg`/`grep` output).
- Screenshot + server log consistency checks where applicable.
- Final decision notes mapping blocker layer to component class:
  - Unit fail → backend logic
  - End2end fail → integration/API
  - MCP fail → server protocol
  - Browser fail → UI/frontend

## References

- `.claude/skills/pr-blocker-min-repro/SKILL.md` for BYOK-specific starter commands and bead note patterns.
- `.claude/skills/integration-verification/SKILL.md` for minimum evidence completeness.

## Integration claim gate

For ANY integration claim, provide all three: configuration evidence that enables the
feature, trigger evidence showing automatic activation, and timestamped log evidence
from an automatic (not manual) execution. Manual test output cannot substitute for
automatic-run logs. If any evidence is missing, the integration is NOT verified.

## Shared runtime boundary

Claude, Codex, and cloud sessions use this same protocol. Read the target repository's
instructions and resolve the documented runner before executing; shell examples are
illustrative, not universal executable commands. Show the exact command and working
directory. If a runner, fixture, credential, or supported execution tool is unavailable,
report `UNSUPPORTED ENVIRONMENT / NO REPRO` with checked paths; do not count a skip as a
pass or bypass the pass-only ladder. Inspection and packaging do not authorize live
provider calls, credential-file reads, shared-state mutations, or external publication.

Record command, revision, environment summary, duration, and each layer's
pass/fail/unsupported/not-run result alongside its evidence. Correlate screenshots and
logs to the same run, redact secrets and private content before authorized sharing,
and treat layer classification as a triage hint rather than root-cause proof.
