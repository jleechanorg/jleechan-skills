# Harbor baseline qualification

The existing [Harbor experiment workflow](harbor-skill-experiments.md) owns the
portable interface. This spec records the acceptance boundary for its isolated
Codex baseline path.

## Outcome

An operator can run a frozen set of constructed baseline cases with the
requested runtime and assess valid, invalid, and missing observations separately.
One unusable attempt does not erase independently valid siblings.

## Non-goals

This path neither runs a treatment nor changes a live product, PR, or account.
It is not a verbatim reconstruction of historical runs, containment for
adversarial subject code, or a claim of forensic erasure.

## Acceptance

The adapter checks source and runtime identities before launch, separates the
agent from the verifier, and admits only the explicitly selected existing
account after qualification and lifetime checks. It releases supported,
sanitized native evidence after cleanup. Scoring binds the observed first turn,
model-visible tool output, fixture collection, and frozen semantic detector to
the attempt. A collected empty fixture ledger is distinct from a missing one.
A cohort with fewer than its scheduled valid attempts is incomplete.

## User story

As an operator, I can tell whether the constructed failure recurs under a new
pinned runtime without mistaking auth errors, reviewer holds, or unverifiable
output for evidence of behavior.

## Proof plan

Run executable regressions and obtain independent review of the exact code.
Qualify the pinned adapter and Docker images with fake credentials and scripted
provider responses; prove actual isolation, route, evidence, and cleanup before
using the existing account. Then run only the frozen baseline schedule and
preserve per-attempt identities, observations, and validity.

## Mock exemption

The adapter, container runtime, Codex process, and released evidence path are
real in qualification. Provider responses and PR/CI/reviewer state are
controlled fixtures. Offline synthetic tests and review calls do not count as
qualification or subject attempts.

## Risks

Unsupported native events, provider limits, changed account lifetime, or missing
fixture evidence may invalidate an attempt. Historical material that cannot be
verified remains a stated experiment limitation. Do not substitute retries or
weaker proof for a missing scheduled observation.
