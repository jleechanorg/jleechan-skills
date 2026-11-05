# Harness engineering: worked failure patterns

Incident write-ups moved out of `../SKILL.md`; each preserves one rule that the skill keeps.

## Example: CLI redacts secrets but scripts still export them

**Observable:** Gateway returns `unauthorized` / embedded fallback; logs show token value `__OPENCLAW_REDACTED__` or similar.

**Failure class:** **Silent degradation** plus **knowledge gap**: the CLI intentionally does not echo real secrets.

**Root cause:** `openclaw config get …` returned a redaction sentinel, which the shell exported and the gateway rejected.

**Agent root cause:** The agent trusted a familiar “export then call” recipe without verifying the value or its source.

**Rule:** Never export a secret from output that can be redacted. Use the owning credential source and verify the value is not a sentinel before relying on it.

**Verification:** Run the command path, confirm the value is not a known sentinel, and confirm the gateway returns `status: ok` without embedded fallback.

## Historical: retired Gate 7 trusted aggregate workflow status

**Historical observable:** before the 2026-07-28 policy change, an agent trusted
Green Gate `completed/success` while a separate Skeptic verdict was missing.
This mechanism is retired; current policy is the canonical two-gate `/green`.

**Failure class:** **Silent CI success**: a workflow can exit 0 at job level while an inner step fails; the existing gate reports the wrong thing.

**Root cause:** The gate conflated “trigger posted” with “skeptic evaluated,” swallowing the inner verdict failure.

**Agent root cause:** The harness did not require independent verdict verification, so the agent trusted an aggregate status.

**Rule:** Do not trust aggregate status; follow the owning `/green` procedure and verify current-head conclusions and mergeability independently.

**Current verification:** follow
`~/.claude/skills/pr-green-definition/SKILL.md`; independently verify
current-head CI conclusions and mergeability rather than trusting the Green Gate
display status.
