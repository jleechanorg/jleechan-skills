---
title: BrowserClaw v2 autonomous-control design (reference summary)
source: doc_f51132550e72_browserclaw-autonomous-browser-control-design.md
date: 2026-07-30
status: design-only — does not authorize implementation
---

> **Current-policy boundary (2026-10-25):** This dated design is historical planning material, not executable browser or authentication guidance. It does not supersede `~/.claude/skills/browser-control/SKILL.md`: personal browser windows, profiles, cookies, and login state remain off-limits; automatic sign-in, desktop-browser recovery, copied-credential API calls, and auth bypass are not authorized by this design. Any task-authorized cookie transfer is limited to exactly one named agent-owned source and the guarded isolated-headless lifecycle in browser-control. Stop if that session needs login, consent, MFA, CAPTCHA, or other user action.

## Why this exists

A 670-line validated design for expanding `browserclaw` from a HAR-capture /
endpoint-inference / `requests.Session`-generator into an agentic,
outcome-driven web controller. This file is a condensed summary so a future
session can pick up the design context in ~3 minutes instead of re-reading
the full doc. It also captures three preference signals from the operator's
review (2026-07-30) that MUST be carried into any implementation PR.

## Three operator preferences (load-bearing — do not silently override)

1. **No cookie extraction / promotion into BrowserClaw-owned storage.**
   Aside owns cookies + auth material; the direct client reuses the session
   Aside holds. When asked "whats this mean? I dont care about using cookies
   or copying them," the operator removed every cookie-promotion language
   from Goals, CredentialBroker, Security and privacy, Recovery, transport
   diagram, and acceptance criteria. **Implementation PR must not reintroduce
   cookie extraction as a BrowserClaw feature.** If a future requirement
   needs cookie material, route through Aside's session context, not a
   browserclaw-owned store.

2. **All notification destinations env-configurable. Default = Hermes DM.**
   Env vars: `BROWSERCLAW_NOTIFICATION_TARGET` (default
   `hermes-dm:<operator_id>`), `BROWSERCLAW_NOTIFICATION_SECONDARY`
   (optional dual-channel), `BROWSERCLAW_DUAL_CHANNEL_FIRST_RESPONSE_WINS`
   (true/false when secondary is set). The operator said "lets have hermes DM
   me and lets make this optional or let it be env variable controlled bcause
   other people may have other setups." **No Slack / email hardcoding
   anywhere in the implementation.**

3. **Automatic auth. Operator never opens a browser unless forced.**
   Login / session recovery / MFA / passkey / SSO / device-confirmation all
   driven autonomously by Aside. Manual fallback only after bounded
   autonomous recovery is exhausted. The operator said "What do you mean
   manual auth only? I want automatic auth and never wanna use my browser
   unless forced." This **supersedes** the prior `browserclaw/CLAUDE.md`
   "Manual auth only" / "No stealth, evasion, or auth bypass features"
   ceiling. The honest-tool intent is preserved; the operational posture
   is automatic rather than manual.

## v1 contract → v2 supersession map

| v1 line (browserclaw/CLAUDE.md, README) | v2 status |
|---|---|
| Manual auth only | **Superseded** by automatic auth + bounded manual fallback |
| No stealth, evasion, or auth bypass features | **Reinterpreted**: no bypass of website security controls (CAPTCHA / MFA policy / access controls), but the operator's own credentials and browser session are fair game. "Auth bypass" now means "bypassing the operator's instructions" — still prohibited |
| `requests.Session`-based generated client | **Superseded** by `httpx`-based direct client + `--transport requests` backward-compat flag |

The implementation PR must also amend `projects/browserclaw/CLAUDE.md` to
match (the design doc carries the new contract; the repo CLAUDE.md is
authoritative for `git` operations).

## Component shape (high-level only)

- `RunOrchestrator` — durable state machine (queued → planning → executing →
  verifying → completed; branches: waiting_for_approval, recovery,
  escalated, denied). Journal events carry sanitized input + transport +
  verification result + approval reference.
- `CapabilityCatalog` — endpoint signature, direct request profile,
  preferred transport, auth boundary, result checker, optional Aside
  recipe, safety classification, last verification metadata. **No
  credential values.**
- `AdaptiveExecutor` — picks cheapest verified transport; distinguishes
  transport/auth failure from valid application errors (`400/404/409/422`
  do NOT auto-fall-through); prevents unsafe cross-transport retries.
- `AsideAdapter` — stable interface over Aside MCP / CLI / REPL / account
  selection. BrowserClaw depends on this, not scattered Aside calls.
- `CredentialBroker` — session passthrough to Aside only (per preference 1).
- `LearningEngine` — repairs URL encoding, method/redirect behavior, body
  encoding, safe headers, response parsers, scoped session material.
  Promotes a fast path only after independent safe replay + result-checker
  pass.
- `NotificationRouter` — env-configured target(s) (per preference 2).
- `ApprovalNotifier` — signed, deduplicated approvals; first authenticated
  decision wins; payload hash binds approval to exact action; any
  material payload change invalidates prior approval.

## Transport preference (canonical order)

```text
direct HTTP via the session Aside holds
→ Aside browser-context HTTP
→ constrained in-page execution
→ Aside UI workflow
```

The cache key is "cheapest independently verified transport." Cookies
never enter BrowserClaw storage.

## Failure classifications (13 stable types)

`transient_transport`, `authentication_expired`, `login_required`,
`human_verification_required`, `request_shape_drift`, `browser_only_auth`,
`application_rejection`, `result_unverified`, `mutation_outcome_ambiguous`,
`approval_required`, `approval_denied`, `aside_unavailable`,
`recovery_exhausted`.

`human_verification_required` boundary is NOT yet specified in the design —
that's a known gap to land in the implementation PR's design-section
(CAPTCHA / OTP / WebAuthn step-up detection rules + escalation subtype
mapping).

## Approval policy

Approval required for: payments, deletions, publication, external messages,
bookings, account/permission/identity/security changes, unknown-impact ops.
Before approval: authenticate, prepare reversibly, validate recipient /
amount / content / scope, capture pending state, stop before the
irreversible boundary.

## Runtime modes

CLI default: `browserclaw run "<outcome>"`, `browserclaw status <id>`,
`browserclaw resume <id>`. Optional service: `browserclaw serve`. CLI ↔
service share one execution engine + run journal; a run may begin in one
and resume in the other without re-executing an operation (run-lease
prevents double-execution; expired leases reclaim only after verifying
the previous operation completed — verification primitive for non-GH
mutations is unspecified, see SOUL.md `babysit-cron-self-cancel-discipline`
for the canonical pattern).

## Security / privacy highlights

- Aside password autofill remains invisible to the model.
- Cookie + session material stays in Aside; direct client reuses the
  session Aside holds.
- All secrets redacted from model-visible and durable artifacts.
- In-page execution uses fixed BrowserClaw-controlled code + structured
  args (no arbitrary generated JS).
- URLs, origins, methods, payload sizes, response types validated before
  browser-context or in-page requests.
- No bypass of website security controls.
- Screenshots and notifications sanitized before external delivery via
  `lib/outbound_secret_gate.py` (per SOUL.md `outbound-secret-publication-gate`).

## Cross-references

- Source design doc: `~/.hermes/cache/documents/doc_f51132550e72_browserclaw-autonomous-browser-control-design.md` (670 lines)
- Review / advice synthesis: in-conversation review (slack thread this date) — see session log for full evidence table
- Adjacent skills: `browser-headless-default`, `aside-browser-default`, `advice`, `skillify`
- Operator preferences also encoded in (memory at cap, 2026-07-30): the design doc itself is the durable record; this reference file is the cached-summary mirror.
