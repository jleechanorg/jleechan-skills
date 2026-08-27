---
name: harness-postmortem
description: "Harness-fix meta-skill (slash: /meta) — analyze an agent behavior failure (autonomy violation, refusal, premature stopping) and run /harness to fix the agent, NOT the underlying task. Input: Slack thread URL, pasted conversation, or freeform description."
type: quality
execution_mode: deferred
scope: user
---

# harness-postmortem (slash: /meta) — Fix the agent, not the task

**Canonical location:** `~/.hermes/skills/harness-postmortem/SKILL.md` (or its `~/.hermes_prod` equivalent). This file is the Claude-side mirror pointer. **Collision rule:** if a workspace contains `.claude/commands/meta.md`, repo-local content takes precedence over this mirror.

The slash command is `/meta` because that's the user's invocation pattern. Both `meta` and `harness-postmortem` resolve to the same skill.

## Inputs

`$ARGUMENTS` — Slack thread URL, pasted conversation, OR freeform description of agent misbehavior.

## Scope guardrail

`/meta` is scope-locked to the **agent behavior failure**. It never investigates or continues the underlying task the agent was attempting — it only analyzes and fixes the harness (instructions, skills, tests, rules) that let the bad behavior happen.

## Behavior

1. Detect input shape (URL / paste / description).
2. Fetch the thread via `mcp__slack__conversations_replies` if URL.
3. Apply the scope guardrail (NEVER investigate the underlying task).
4. Run the Phase 0/1 protocol: MAST + ETCLOVG classification → Observe → Isolate → Simulate → Evaluate.
5. If user passed `--fix` or used a fullrun trigger (`/a`, `/fullrun`, `/finish`, "don't stop", "iterate until good"), implement + commit + push.
6. Otherwise: output the analysis and wait for approval.

## Implementation reference

Full protocol at `~/.hermes/skills/harness-postmortem/SKILL.md` (canonical — read this for the complete MAST/ETCLOVG taxonomy, phase steps, and anti-patterns). Highlights:

- **Scope guardrail** — top of SKILL.md.
- **Phase 0** — MAST taxonomy (Cemri et al., arXiv:2503.13657) + ETCLOVG layer model (arXiv:2606.06324) classification.
- **Phase 1** — Observe → Isolate → Simulate → Evaluate 4-step spine, with 5-Whys inside Simulate as a prompt heuristic.
- **Phase 2/3 apply + land** — via `hermes-deploy-pipeline` self-merge flow on `jleechanclaw`.
- **Anti-patterns** — end of SKILL.md.
- **Prior art** — Refinex-Space harness-fix, HarnessFix paper, MAST, Reflexion, Observe→Isolate→Simulate→Evaluate pattern.

## Examples

- `/meta` — auto-detect from last conversation; if none, prompt for input.
- `/meta hermes stopped halfway again` — freeform.
- `/meta https://jleechanai.slack.com/archives/C0AH3RY3DK6/p1782941155305869` — Slack thread.
- `/meta --fix <description>` — analyze AND apply harness fix without confirmation.

## Output

Per `finish-the-job` Phase 4 — end-state declaration + proof artifact + judgment calls + zero follow-up question.

## Cross-references

- `/harness` — `~/.claude/commands/harness.md` (the protocol this skill wraps).
- `harness-postmortem` skill (canonical) — `~/.hermes/skills/harness-postmortem/SKILL.md`.
- `harness-engineering` — `~/.hermes/skills/harness-engineering/SKILL.md` (SOUL.md / TOOLS.md rules).
- `finish-the-job` — `~/.hermes/skills/finish-the-job/SKILL.md` (end-state contract).
- `hermes-deploy-pipeline` — `~/.hermes/skills/hermes-deploy-pipeline/SKILL.md` (landing recipe).
