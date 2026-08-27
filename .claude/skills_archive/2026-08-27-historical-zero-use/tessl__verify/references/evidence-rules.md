# Evidence Rules

Verification without proof is just flattering yourself.

## What Counts as Evidence

Prefer reproducible proof:

- commands or runtime surfaces exercised, recorded exactly in the work log when needed for reproduction
- screenshots tied to a named flow
- HTTP requests and responses
- representative CLI output for failures or meaningful status lines
- structured logs, traces, or health checks
- concrete error messages, codes, and recovery hints from an exercised failure path
- file references with line numbers for static findings

## Rules

1. **Screenshots are evidence, not verdicts**
   - A nice screenshot does not prove the flow works end to end

2. **Swallow boring success output**
   - Keep success terse; surface failures and anomalies

3. **Tie every finding to impact**
   - say what breaks, who it affects, or why the risk matters

4. **Name the exact surface exercised**
   - page, endpoint, command, state transition, config path

5. **Separate proof layers**
   - distinguish local guardrails, focused regression checks, real-surface proof, CI, and live/deploy evidence

6. **For error-handling findings, capture the surfaced failure**
   - include the actual error text, code/classification, and whether the message helps the user recover

7. **Flag unverified claims honestly**
   - if you could not hit the real surface, say `unverified` and why

8. **Summarize logs by signal**
   - quote only the relevant lines or summarize with exact pointers

9. **Keep final evidence human-readable**
   - in the final footer, summarize passing checks by intent and result; include full commands only for failures, reproduction, or when asked

## Minimum Output Shape

For each meaningful finding:

- severity
- summary
- evidence
- impact
- suggested fix or handoff

For the overall verification:

- verdict: `ready for review` / `needs more work` / `blocked` (independent review owns the `ship it` call)
- change verified
- surfaces exercised
- evidence summary: what passed or failed, not a raw command list unless reproduction requires it
