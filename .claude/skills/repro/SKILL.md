---
name: repro
description: "Reproduce a bug, then drive a root-cause-classified fix. Use when asked to /repro a bug, file a REPRO issue, or escalate a regression. Triggers on the words: repro, reproduce, regression, root cause, \"what broke\", \"file an issue\"."
metadata:
  type: skill
---

# /repro

Reproduce a bug end-to-end, classify the root cause, file a REPRO issue, then propose (or drive) the minimal fix. Always root-cause-first; never ship a patch on top of an unverified hypothesis.

## Usage

```
/repro <bug description or PR/issue ref>
/repro --issue <#N>           # reproduce from a known REPRO issue
/repro --pr <#N>              # reproduce from a known PR (use PR's repro context)
```

## 1. Understand the report

- Read the bug description, any linked issues/PRs, and any prior `/repro` outputs.
- Capture: **symptom** (what the user sees), **reporter** (who/when), **environment** (prod/dev URL, build SHA, browser/device if known), and **first-seen**.
- If a regression is suspected, identify the **earliest** merged PR that could plausibly cause it. Use `gh pr list --search "<keyword>"` and `gh pr view <N> --json files,mergedAt`.

## 2. Try to reproduce (Layer 1 → Layer 4)

Climb the minimal repro ladder. **Stop climbing the ladder only when the blocker is conclusively reproduced.**

| Layer | Tool | When to use |
|---|---|---|
| 1. Unit | `pytest <path>::<test>` (mocked/isolated) | Cheap; narrows down the unit. Unit-only evidence is **not sufficient** for a production-fix claim. |
| 2. End-to-end | `pytest <e2e test>` | Hits real callstack with mocks only at external API boundaries. |
| 3. MCP / local server | real curl / mcp client against a running local dev server | When the bug needs the real LLM call path. |
| 4. Browser (final) | `mcp__playwright-mcp` headless against a deployed URL | When the bug is UI/integration-specific or only reproduces in a real browser session. |

If a layer passes but the bug seems environmental, **jump to the highest layer** to verify full stack behavior. Capture exact log lines, screenshots, and HTTP traces.

## 3. Capture smoking gun

Mandatory before moving to classification:
- Exact command(s) run with exit code
- Key log line(s) — verbatim, with timestamp
- If UI: screenshot path + the exact element that misbehaves (selector + observed vs. expected)
- Session id / request id / cdiag event id, if applicable

If you cannot reproduce, say so explicitly. Do not paper over a non-repro with a "probably X" hypothesis.

## 4. File the REPRO issue (if not already filed)

Use this exact title pattern:
```
REPRO: <one-line symptom> — <one-line root-cause hypothesis>
```

Body must include:
- **Summary** — one paragraph
- **Smoking gun** — verbatim log/screenshot/HTTP trace
- **Root cause candidates** — ranked by likelihood (see §7)
- **How to find the real cause** — what extra instrumentation would disambiguate
- **Steps to reproduce** — exact URLs / commands
- **Related tracking** — PRs, issues, prior fix attempts (with their SHA / merge commit)

## 5. Drive the fix (only after root cause is confirmed)

1. Update the issue's "Root cause candidates" → "Confirmed root cause" section with the evidence.
2. Branch from `origin/main` (`git fetch origin && git checkout -B <branch> origin/main`).
3. **Fix prompt/schema/instruction first** before adding backend protection, fallback, clamp, sanitizer, or retry. Backend protection only after documenting why prompt correction is insufficient.
4. Add tests that would have caught the bug (Layer 1 unit + Layer 2 e2e at minimum).
5. Open PR with a body that links the REPRO issue, names the root cause, and shows the new test failing on `origin/main` (RED) and passing on the branch (GREEN).
6. Drive the PR to green; do not stop at "I made the change locally".

## 6. Honest reporting

- Distinguish **observed** from **recommended** at all times.
- If a fix is blocked, say what blocks it (auth, missing evidence, conflicting requirement) — not a vague "I will follow up".
- Past fix attempts that were reverted must be cited: their SHA, the analysis that was wrong, and what the revert taught us.

## 7. Root-cause classification (NEW — 2026-06-16)

Before proposing a fix, **classify the root cause into exactly one of these buckets**. Pick the most specific bucket that fits; the bucket drives which fix-pattern to apply.

### 7.1 Prompt / instruction
- The LLM was given an ambiguous, contradictory, or underspecified prompt.
- Same call with a clearer prompt succeeds.
- **Fix pattern:** clarify the prompt / schema / instruction first. Do not add backend defense.

### 7.2 Backend / business logic
- The server-side code is doing the wrong thing deterministically (bug, race, stale data, missing migration).
- Repro is stable across prompt variations.
- **Fix pattern:** patch the backend. Add a unit test that exercises the code path with the exact input shape from the smoking gun.

### 7.3 External API / provider
- The LLM provider or third-party API returned a wrong/empty/malformed response.
- The shape is "we sent X, we got Y, and the same call 5 minutes later succeeds".
- **Fix pattern:** retry with backoff (only if the call is idempotent) + log the provider's response. Do not paper over with a clamp/sanitizer unless we can prove the response is unrecoverable.

### 7.4 UI / integration
- The bug only reproduces in a real browser session, and the server logs show no anomaly.
- The same data flow works in unit + e2e + mcp layers.
- **Fix pattern:** fix the UI / event handler / state machine. Add a Playwright test that loads the real URL and asserts the expected DOM state.

### 7.5 Environment / config
- A config value, env var, or deployment setting is wrong, missing, or stale.
- Switching environments (dev → prod) or fixing the config eliminates the bug.
- **Fix pattern:** fix the config, audit all environments, add a startup assertion that fails loud if the config is missing.

### 7.6 Unknown / under-instrumented
- We have a symptom but no smoking gun. Logs do not disambiguate.
- **Fix pattern (do NOT propose a fix yet):** add the missing instrumentation first. Ship a no-op PR that adds the events / logs that would have caught this. Then re-`/repro` with the new evidence.

### 7.7 Classification rules (enforced)

- **Root-cause-first invocation:** If classification is **unknown / under-instrumented**, the next action is **always** "add instrumentation", not "guess a fix". Guessing a fix from a weak signal is the exact anti-pattern that produced prior reverted fixes (e.g. PR #7551's 250ms grace, which addressed the wrong race).
- **One root cause per bug:** Pick exactly one bucket. If you think it's both prompt AND backend, you have not classified yet — go back to §2 and reproduce.
- **Past reverted fixes are evidence:** Before proposing a fix, search the repo for prior fix attempts of the same symptom. If any were reverted, cite them in the REPRO issue and explain why this attempt is different.

## 8. Output template (always end with this)

```
## REPRO summary
- Symptom:
- Root cause (bucket 7.x):
- Smoking gun (file:line / log / cdiag id):
- Fix pattern: [prompt | backend | retry+sanitize | UI | config | instrumentation-first]
- Status: [REPRODUCED | NOT_REPRODUCED | UNDER_INSTRUMENTED]
- Next action: [link to issue / PR / next skill]
```
