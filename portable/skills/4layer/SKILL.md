---
name: 4layer
description: "Find the smallest test layer that reproduces a blocker."
---

# Four-layer minimal reproduction

Use this ladder to classify a reported blocker with the smallest relevant test. It is
an evidence workflow, not permission to call providers, mutate shared state, or publish
logs. Read the repository's test layout and runner first; never assume a particular
interpreter, branch, remote, provider, or test directory.

## Ladder

Run the narrowest matching target in order: unit/backend, end-to-end/integration,
protocol/API, then browser/UI. Stop at the first layer that conclusively reproduces the
symptom. Move upward only when the current layer passes or cannot exercise the claimed
boundary. A lower-layer pass does not prove an upper layer works.

For every layer, resolve the command from project documentation or an executable runner
discovery (`pyproject.toml`, package scripts, Makefile, or equivalent). Show the exact
command and working directory before running it. Select one test or smallest test set,
and isolate credentials, users, ports, fixtures, and output directories for parallel
runs.

## Evidence contract

Record an absolute, caller-approved evidence directory, command, revision, environment
summary, pass/fail/unsupported status, duration, and first meaningful failure lines.
Capture screenshots and server logs only when that layer uses them, then check that the
visual and log evidence describe the same run. Redact secrets and user content before
sharing. If a dependency or credential is missing, report `unsupported` with the
missing dependency; do not label the layer passed.

Classify the first reproducing layer as backend logic, integration/API, protocol, or UI.
Layer labels are triage hints, not proof of root cause; use a separate root-cause or
integration-verification workflow before claiming causality. The companion
`pr-blocker-min-repro` workflow supplies optional project-specific examples; it is a
local dependency only when present and authorized.

## Portable boundary

This adapter can design the ladder and inspect existing evidence without a live service.
Execution requires the host's approved runner and isolated target. Never invent provider
calls, read credential files, or infer a successful browser test from an import skip.
