---
description: Triage incoming feedback into Accept / Adapt / Reject buckets with structured verdicts and follow-up actions.
type: ai
execution_mode: immediate
---

# /accept-adapt-reject (alias: /aar)

A slash command that wraps the `accept-adapt-reject` skill. Pass any incoming feedback (code review comments, PR feedback, user corrections, design critiques) as the command arguments. The skill produces a structured AAR triage: each discrete piece of feedback is bucketed as **ACCEPT**, **ADAPT**, or **REJECT**, with reasoning and concrete actions. Accepted and adapted items are then executed.

## Usage

```
/accept-adapt-reject <feedback text or reference to a thread/PR/comments>
/aar <feedback text or reference>
```

## Examples

```
/aar "The function is too long. Rename tmp to temporaryValue. We should switch to GraphQL."
/aar PR #1234 review comments
/aar "Stop using const for everything, prefer let"
```

## What it does

1. **Loads the `accept-adapt-reject` skill** for the full AAR algorithm, output template, and priority rules.
2. **Segments the feedback** into atomic items (one bullet/sentence/paragraph = one item).
3. **For each item**, gathers context (original intent, reviewer goal, constraints, prior accepted feedback) and applies the rubric: factually correct? serves the stated goal? is the proposed solution the best? cost of being wrong?
4. **Outputs structured verdicts** — ACCEPT / ADAPT / REJECT with reasoning and concrete actions, then a Summary block with counts and net changes.
5. **Executes** the accepted and adapted items (skips rejected ones, with a short rationale).

## When to invoke

- After receiving a code review or PR review comment thread.
- When the user asks to "process this feedback", "triage these comments", or "decide what to do with this review".
- When multiple conflicting opinions need reconciliation.
- When the user expresses uncertainty about whether to apply feedback.

## When NOT to invoke

- Pure compliments ("looks good!") — no triage needed.
- Questions, not feedback ("why did you choose X?") — answer the question directly instead.
- Bug reports that need debugging first — use `systematic-debugging` to find the root cause, then come back to AAR if feedback is involved.

## Full skill

For the complete algorithm, priority rules, anti-patterns, and worked examples, see the canonical skill at:

```
~/.hermes/skills/accept-adapt-reject/SKILL.md
```

The skill is the source of truth. This command is a thin launcher.