# Verification

Prove your own changes work on real surfaces. Independent ship decisions belong to a separate review context.

## Sources

- Anthropic evaluator pattern: https://www.anthropic.com/engineering/harness-design-long-running-apps
- Anthropic PR review toolkit (agent-per-concern): https://github.com/anthropics/claude-code/tree/main/plugins/pr-review-toolkit/agents
- Anthropic code simplifier agent: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md
- OpenAI Codex subagents: https://developers.openai.com/codex/concepts/subagents
- HumanLayer context flooding: https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents
- Datadog verification pyramid: https://www.datadoghq.com/blog/ai/harness-first-agents/
- Desloppify: https://github.com/peteromallet/desloppify
- Context rot research: https://research.trychroma.com/context-rot

## Contents

- [Before You Start](#before-you-start)
- [Proof Boundary](#proof-boundary)
- [Checks](#checks)
- [Evaluator Pattern](#evaluator-pattern)
- [Check Selection](#check-selection)
- [Model Selection](#model-selection)
- [Cost Awareness](#cost-awareness)

## Before You Start

1. Check readiness grade: C+ = proceed. D/F = add readiness setup first
2. Can you boot the app?
3. Can you interact with it? (Playwright CLI for UI, curl for APIs, CLI invocation)
4. Can you verify your own work from a fresh evaluator context or separate subagent?
5. If not, flag it as a readiness gap and define the durable check the repo needs

## Proof Boundary

Name the claim before choosing checks:

- **local health** — dependencies install, guardrails pass, the app or package boots locally
- **focused regression** — the changed behavior and at least one relevant failure path are exercised
- **real surface** — shipped CLI, browser flow, API endpoint, worker, device, or simulator was actually used
- **CI status** — the repo's configured remote checks passed on the relevant commit
- **deploy/live status** — the deployed or configured production-like surface is the one being exercised

Do not let one layer imply another. A green build does not prove the browser flow. A local smoke does not prove deploy wiring. A CI board does not prove the preferred provider, device, account state, or live endpoint unless that exact surface was checked.

When the requested proof surface is unavailable, report the best evidence you gathered and the missing boundary plainly.

## Checks

### Real Surface
- Run the shipped CLI, service, or UI flow with representative inputs
- For UI: Playwright CLI or CDP — inspect behavior, structure, legibility, responsiveness
- For services: hit the real local endpoint, confirm full round trip
- Treat this as stronger evidence than a pile of unit tests that mock the seam under change

### Deterministic Guardrails
- Run the repo's built-in verify entrypoint first when it exists
- Prefer targeted checks over full-suite context floods during iteration
- Prefer integration, contract, smoke, and e2e checks over unit tests that mostly stub dependencies
- Mock-heavy unit tests are supporting evidence, not primary proof, when they control the behavior being claimed
- If a deterministic check fails, fix that failure before claiming runtime success

### Code Shape
- Review the changed files for clarity, duplication, and maintainability after behavior is proven
- Delete dead code, stale branches, and unused helpers when they no longer protect a real boundary
- Treat `any`, unsafe casts, and boundary-leaking `unknown` as verification failures unless explicitly allowed
- Prefer parsing external data once at the boundary over scattering validation and casts through core logic
- Classify failures intentionally: validation, not-found, auth, dependency, and programmer errors should not collapse into one vague catch-all
- Prefer user-facing errors that explain what happened and what to try next, while preserving richer diagnostics for logs or operators
- Prefer matching existing language/framework patterns over inventing a new local style
- Delete comments that only compensate for unclear code; keep only durable context the code cannot express
- Ask whether a fresh agent could extend the changed path without reverse-engineering hidden intent

### External Contracts
- Verify field names, enums, response shapes against docs or real responses
- Can't verify a contract detail? Stop and surface the gap

### State and Config
- Verify public interfaces end to end
- Verify persistence/state round trips with real data
- Verify config changes by starting the program with the new config

### Failure Quality
- Exercise at least one real failure path when the change touches validation, IO, auth, network, or external dependencies
- Confirm the surfaced error is actionable: clear cause, stable classification or code where appropriate, and a useful recovery step when the user can do something about it
- Reject swallowed failures, vague "something went wrong" responses, and raw internals dumped directly to end users

### CI Integration
- If the project has CI, push and wait for results before declaring done
- CI failures after verify = verify missed something. Investigate
- If CI is green but a separate live/deploy/provider check is required, keep that as a separate unverified or failing surface

### Smell Test
- Check outputs look plausible to a human
- **Investigate anything odd instead of rationalizing it** — this is the specific failure mode
- Look for: unexpected empty states, wrong user names, stale data, truncated responses, hardcoded test values in production output

### Proof of Work
- Query structured logs, health endpoints, error traces
- Keep screenshots, response logs, traces, sample responses
- Evidence should be reproducible — include exact commands

## Evaluator Pattern

Anthropic's GAN-inspired approach: separate generation from evaluation entirely.

**Three roles**: Planner → Generator → Evaluator
- **Evaluator** is always independent from the builder
- Uses Playwright/CDP, curl, or the shipped CLI to inspect the live result
- Can reject work and send it back with specific feedback
- Success criteria are defined before running the check

**Why it works**: LLMs are terrible self-evaluators — they confidently praise mediocre work. Tuning a standalone evaluator to be skeptical is far more tractable than making a generator self-critical.

**When to use**: complex features, subjective quality, UI work. Not for simple CRUD or config changes.

**Evaluator tuning**: out of the box, Claude identifies issues then talks itself into approving. Multiple rounds of prompt tuning needed — read evaluator logs, find judgment divergences from human expectations, update QA prompt.

### Context Flooding Problem

HumanLayer identified this: running a full test suite floods the context window, causing agents to lose track and hallucinate about test files. Verification must be **context-efficient**:

- Swallow passing output, only surface errors
- Run targeted subsets (< 30 seconds), not the full suite every iteration
- Use hooks that run silently on success, exit with error only on failure

## Check Selection

Pick the smallest set of checks that can honestly disprove the change:

- **UI change** → targeted UI flow, screenshot, responsive spot-check, console scan
- **API/backend** → representative request, error request, schema or contract check; prefer this over handler-level mocks
- **Error-handling change** → exercise one real failure path, inspect classification, and inspect the user/operator message quality
- **CLI/tooling** → shipped command invocation, representative args, exit code, stdout/stderr sanity check
- **State/config** → write/read round trip, restart, boot with changed config, migrate existing state
- **Pure refactor** → deterministic tests plus one surface check that proves behavior parity, then delete stale paths and duplicates exposed by the refactor
- **Generated-looking or overly busy code** → add a code-shape pass on the touched files: clarity, dedupe, dead code, abstraction pressure, comment necessity, and escape-hatch types

## Model Selection

Match model capability to lane complexity:

- **Strong reasoning** (e.g. Opus, GPT-5.4): evaluator orchestration, complex UI judgment, contract-sensitive checks
- **Balanced** (e.g. Sonnet, GPT-5.4-mini): targeted runtime checks, API verification, state/config passes
- **Fast/cheap** (e.g. Haiku, flash): repeated smoke checks, screenshot capture, command re-runs

Use your strongest model for planning/orchestration. Use cheaper models for workers and surface checks.

## Cost Awareness

Anthropic's numbers:
- **Solo agent**: $9 / 20 min
- **Full 3-agent setup**: $200 / 6 hours (22x more)
- **Simplified (Opus 4.6)**: $125 / 4 hours

The evaluator is expensive. Use it for:
- Complex features at the model's capability edge
- Subjective quality (UI design, UX flows)
- High-stakes changes where self-evaluation is dangerous

Skip it for:
- Tasks within the model's comfort zone
- Simple CRUD, config, or migration work
- When deterministic checks (lint, tests, CI) are sufficient

**Key principle**: "Every component in a harness encodes an assumption about what the model can't do on its own, and those assumptions are worth stress testing." As models improve, simplify the infrastructure.
