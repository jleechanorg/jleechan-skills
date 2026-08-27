---
name: verify
description: "Self-check your own completed change before independent review — the pre-review sanity pass. Use when you want to check your work, run checks, validate changes, make sure a change is ready, test it end-to-end, run repo guardrails (lint, typecheck, tests, build), exercise the real surface with evidence, and catch obvious self-correctable issues. Produces a `ready for review` / `needs more work` / `blocked` verdict — never a ship decision. Do not use when the repo cannot be booted or exercised reliably, or when auditing someone else's diff, branch, or PR."
---

# Verify

Self-check your own completed change before independent review. Verify proves the change boots, passes guardrails, and survives the real surface; it is not a ship decision.

## Principles

- Verify is the builder's gate before independent review; it does not replace it
- The builder does not grade their own work in the same context — switch into a fresh evaluator context or separate subagent first
- Run repo guardrails first, then hit the real surface
- Keep proof layers separate: local guardrails, focused regression checks, real-surface runtime proof, CI, and live/deploy evidence are related but not interchangeable
- Prefer smoke, integration, contract, or e2e proof over unit tests that mock most of the behavior under test
- Self-correct obvious issues you spot while exercising the change; leave rigorous code-shape judgment to an independent review pass
- Load shared doctrine from the repo's guidance files such as `AGENTS.md`, `CLAUDE.md`, or repo rules before judging the result
- If the infrastructure is too weak to verify reliably, stop and report the readiness gap.

## Handoffs

- Verification passed → report readiness for independent review.
- No stable boot, smoke, or interaction path means the repo needs readiness setup before verification can be trusted.
- Auditing existing code, a diff, branch, or PR you did not author is independent review work.
- Stale AGENTS.md, README, specs, or repo docs are documentation work unless they block verification.

## Before You Start

1. Define the exact change being verified and the expected user-visible behavior
2. Switch into an independent evaluator context before judging your own work
3. Load the target repo's guidance files such as `AGENTS.md`, `CLAUDE.md`, or repo rules, when present
4. Confirm you can boot and interact with the real surface
5. Define the proof boundary: what local, CI, live, or provider-specific claim you are actually verifying
6. Pick the smallest check set that can disprove the change honestly

## Workflow

### 1. Run deterministic guardrails first

- Prefer the repo's built-in entrypoint: `make verify`, `just verify`, `pnpm test`, `cargo test`, or the nearest targeted equivalent
- During iteration, run targeted checks to avoid context flooding; before handoff, run the canonical local gate when it exists and is feasible
- When choosing tests, prefer the strongest cheap proof available: smoke, integration, contract, or e2e checks beat mock-heavy unit suites that mainly replay implementation details
- Swallow boring success output and surface only failures, anomalies, and exact commands

### 2. Exercise the real surface

- UI → run the browser automation, navigate the changed flow, and capture screenshots
- API → hit the local endpoint with a real request such as `curl http://127.0.0.1:3000/health`
- CLI → run the shipped command such as `node dist/cli.js --help` or the repo's packaged entrypoint
- state/config → verify round trips, restart behavior, and config boot paths
- deploy/live wiring → prove the actual configured surface when required; do not imply production readiness from a local build alone

Follow [references/evidence-rules.md](references/evidence-rules.md) when collecting proof.

### 3. Self-correct obvious issues

While exercising the change, fix anything cheap and obvious that you spot:

- A typo in a log line, a stale comment, an unused import, a duplicated helper inside the diff
- An `any`, unsafe `as`, or non-null assertion you can replace with a real type in seconds
- A failure path that swallows errors silently when a one-line `throw` makes the diagnostic useful

Keep this as a self-check pass. Leave substantive code-shape concerns (architecture mismatches, broader duplication, error-classification redesigns) for independent review. Use [references/simplification.md](references/simplification.md) as a short self-check.

### 4. Probe adjacent risk

- Check the main happy path
- Check at least one failure path or edge case
- Check that at least one exercised failure path returns or logs a useful, actionable error instead of a vague or swallowed failure
- Re-test any config, persistence, or restart-sensitive behavior touched by the change

### 5. Synthesize the verdict

Produce one clear outcome:

- `ready for review` — guardrails green, real surface confirmed, no obvious self-correctable issues left
- `needs more work` — the change is not ready to be reviewed; specific issues to address are listed
- `blocked` — verification cannot proceed, usually because infrastructure is too weak

Verify reports readiness for review. If a requested proof surface was unavailable, name that boundary explicitly instead of substituting a weaker check. The independent ship decision belongs to a separate review pass.

## Output

After verification, report in this compact bullet shape:

- `- verdict:` exactly one of `ready for review`, `needs more work`, or `blocked`
- `- evidence:` concise explanations of what checks proved, not full commands
- `- fixed during verify:` only if self-corrections happened
- `- unverified or gaps:` readiness gaps, doc drift, or `none`
- `- next:` independent review, readiness setup, documentation cleanup, more implementation, or `none`

Keep the final answer short:

- Put detailed failures, screenshots, traces, and file references in native findings or the work log, not in the footer
- Summarize command output that already appeared in the terminal
- Keep the footer to 5 labeled lines or fewer
- Omit `fixed during verify` when nothing was corrected
- Summarize passing checks by intent and result, for example `typecheck passed for tv-vite` or `API smoke check returned 200`; include full commands only when they failed, are needed for reproduction, or the user asks for them
- For failures or blocked checks, include the relevant error/status line or response snippet in the report

Example:

```text
- verdict: ready for review
- evidence: retry tests covered success and failure paths; API retry smoke returned 200
- unverified or gaps: none
- next: review-gang
```

## References

- [references/verification.md](references/verification.md) — evaluator pattern, targeted real-surface checks, and cost trade-offs
- [references/evidence-rules.md](references/evidence-rules.md) — what counts as proof and how to report it
- [references/simplification.md](references/simplification.md) — clarity, dedupe, and "fresh-agent readability" checks for changed code
