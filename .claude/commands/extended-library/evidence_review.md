---
description: Review evidence artifacts for a claim, then check evidence-standards compliance. Dispatches to codex via orchestration library and hard-aborts if required skills fail to load (no inline fallback).
aliases: [er]
type: orchestration
execution_mode: immediate
scope: user
---

# /evidence_review — Evidence Review + Evidence Standards

**Usage**: `/evidence_review [subject or path]`

Run an independent evidence review on the current conversation's claims, a
specific file/directory, or a described subject, then check evidence-standards
compliance, and combine both into a single verdict.

Read `~/.claude/skills/evidence-review/SKILL.md` and execute the full workflow
with the provided subject. Also read `~/.claude/skills/evidence-standards/SKILL.md` for the compliance pass.

## 🚨 CODEX MODEL ROUTING (mandatory for Codex sessions)

Policy: `~/.codex/rules/model-routing-policy.md`.
Subagents / dispatches for evidence review MUST set `model` explicitly:
- **Default: `gpt-5.6-terra`** (Mid 5.6 Tier) with `reasoning_effort: medium` for evidence synthesis (`spark` for simple doc/artifact format checks).
- **`gpt-5.6-sol` ONLY when**: an adversarial final pass requires top-tier high-reasoning cross-context validation (state reason explicitly).

## ⚠️ DEDUP GATE (run before starting a new evidence review)

Check for active in-flight evidence review threads using shared helper `~/.codex/hooks/codex-dedup-check.sh "<subject>"`:
```bash
~/.codex/hooks/codex-dedup-check.sh "SUBJECT_KEYWORDS" 1800
# Equivalent SQL:
# sqlite3 ~/.codex/state_5.sqlite "SELECT COUNT(*) FROM threads WHERE (first_user_message LIKE '%PR%' OR first_user_message LIKE '%evidence%') AND tokens_used=0 AND created_at_ms>(unixepoch('now')-1800)*1000;"
```
If count > 0, steer the existing thread instead of spawning a new one.

## Examples

```
/evidence_review
/evidence_review PR 6198
/er $PROJECT_ROOT/tests/test_rewards_engine.py
```
