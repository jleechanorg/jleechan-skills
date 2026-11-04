---
name: 4layer
description: /4layer - Four-Layer Minimal Repro Testing Protocol
---

Workflow type: testing. Execution mode: immediate.

## Purpose

Runs the Four-Layer Minimal Repro ladder to reproduce PR blockers quickly with evidence-backed classification.

This skill owns the protocol for `/4layer` and `four-layer`. Command files are
thin dispatchers, not protocol dependencies; an absent global
`commands/extended-library/4layer.md` does not require a project overlay.
Claude, Codex, and cloud sessions use this same protocol.

Before executing, read both mandatory companions completely, resolving these paths
relative to this skill (on catalog-only runtimes, resolve each exact companion name
and read its returned definition):
- `../pr-blocker-min-repro/SKILL.md` — BYOK-specific starter commands and bead note patterns.
- `../integration-verification/SKILL.md` — minimum evidence completeness.

If either companion is missing, report the missing dependency and do not claim the
workflow is complete.

## Runner discovery

Read the target repository's instructions and discover its documented test runner
(`AGENTS.md`, `README`, `package.json`, `pyproject.toml`, or `Makefile`) before
executing. Do not assume `./vpython` exists. The shell examples here and in the
companions are illustrative, not universal commands, and do not authorize provider
calls or changes to shared state. Show the exact command and
working directory.

If a runner, fixture, credential, or supported execution tool is unavailable, report
`UNSUPPORTED ENVIRONMENT / NO REPRO` with the checked paths instead of inventing one.
Do not count a skip as a pass or use it to bypass the pass-only ladder.

## Minimal Repro Ladder

Run tests in this order and stop at the first layer that conclusively reproduces the blocker:

1. Unit tests (`$PROJECT_ROOT/tests/`, when present)

```bash
python3 -m pytest $PROJECT_ROOT/tests/test_[relevant].py -q
```

2. End-to-end tests (`$PROJECT_ROOT/tests/test_end2end/`)

```bash
python3 -m pytest $PROJECT_ROOT/tests/test_end2end/test_[feature]_end2end.py -q
```

3. MCP/HTTP API tests (`testing_mcp/`): follow the target repository's
   `testing_mcp/CLAUDE.md` for the exact real-service invocation, environment,
   and explicit `PYTHONPATH`. Do not use `vpython`, pytest collection, mocks,
   or the unfiltered suite when that contract forbids them.
4. Browser tests (`testing_ui/`): follow the target repository's
   `testing_ui/CLAUDE.md` for the exact server, account, service, and runner
   requirements; do not substitute a synthetic or bypass-auth route.

## Execution Rules

1. Identify the blocker and target only relevant, minimal tests.
2. Start at Layer 1. Move upward only if the current layer passes.
3. Keep provider/user isolation so parallel runs do not collide.
4. Record absolute evidence paths after each executed layer.
5. Report the first layer that reproduces the issue; do not run unnecessary upper layers.
6. Inspection and packaging do not authorize live provider calls, credential-file
   reads, shared-state mutations, or external publication.

## Evidence Requirements

After each test run, capture:

- Full absolute evidence directory path under a unique run directory. Resolve the
  scratch root, refuse a `/tmp` result, then create a fresh directory beneath it —
  `scratch-dir.sh` returns a stable root, not a per-run path, and it exits 0 even
  when it falls back to `/tmp`:
  ```bash
  # Call the resolver with NO subpath: given one, it runs mkdir -p on the target
  # before returning, so a tmp fallback would already be created before any check.
  SCRATCH_ROOT="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh)" || exit 1
  case "$SCRATCH_ROOT" in
    /tmp|/tmp/*) echo "scratch volume not configured; refusing a tmp workspace" >&2; exit 1 ;;
  esac
  EVIDENCE_DIR="$(mktemp -d "$SCRATCH_ROOT/evidence-run.XXXXXX")" || exit 1
  ```
  See `../scratch-space/SKILL.md` for why `/tmp` workspaces are prohibited.
- Command, revision, environment summary, duration, and each layer's
  pass/fail/unsupported/not-run result.
- Signature failure lines with context (`rg`/`grep` output).
- Screenshot + server log consistency checks where applicable, correlated to the same
  run. Redact secrets and private content before authorized sharing.
- Final decision notes mapping blocker layer to component class. The class is a
  triage hint, not root-cause proof:
  - Unit fail → backend logic
  - End2end fail → integration/API
  - MCP fail → server protocol
  - Browser fail → UI/frontend

## Integration claim gate

For claims that a feature is enabled by standard startup or activates
automatically, provide configuration evidence, trigger evidence, and a
timestamped log from that automatic execution. A manual test does not establish
automatic activation. For manual integration claims, use the lowest sufficient
real-service layer and report exactly what was exercised; do not require
automatic-run evidence unless the claim is about automatic activation.
