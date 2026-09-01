---
name: accept-adapt-reject
description: Triage incoming feedback into Accept / Adapt / Reject buckets with structured verdicts and follow-up actions. Triggers on /aar, /accept-adapt-reject, or review triage.
type: ai
execution_mode: immediate
scope: user
---

# accept-adapt-reject (slash: /aar) — Feedback Triage Protocol

Triage incoming feedback (code review comments, PR feedback, user corrections, design critiques) into structured **ACCEPT**, **ADAPT**, or **REJECT** buckets.

## Purpose

When receiving feedback from reviewers, automated bots, or users, avoid blind acceptance or defensive rejection. Evaluate each item objectively against technical merit, repo standards, and design intent.

## Workflow

1. **Segment Feedback**: Split the feedback into atomic, independent items (one sentence/bullet/finding = one item).
2. **Context Gathering**: For each item, examine the referenced code, intent, constraints, and test suite.
3. **Rubric Evaluation**:
   - Is the feedback factually correct?
   - Does it improve correctness, performance, maintainability, or readability?
   - Is the proposed solution the best approach, or does a better adapted solution exist?
   - What is the regression risk / blast radius?
4. **Structured Verdict**:
   - **ACCEPT**: Agree with finding and proposed fix. Apply directly.
   - **ADAPT**: Agree with underlying problem, but modify the approach to better fit architecture or avoid side effects.
   - **REJECT**: Finding is based on incorrect assumptions, out of scope, or would degrade behavior. Provide factual, reasoned justification.
5. **Execution**: Implement all accepted and adapted items, then verify with automated tests.

## Output Template

```markdown
### Feedback Triage Summary
- Total Items: N
- ACCEPT: X | ADAPT: Y | REJECT: Z

#### Item 1: [Short Title]
- **Source**: [Reviewer / Bot / User]
- **Feedback**: "[Exact quote or summary]"
- **Verdict**: **ACCEPT** | **ADAPT** | **REJECT**
- **Rationale**: [Factual reasoning citing code/tests]
- **Action**: [Concrete change to make, or reason for no change]
```
