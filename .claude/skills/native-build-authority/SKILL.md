---
name: native-build-authority
description: "Use BEFORE starting, refusing, deferring or scheduling any native build: xcodebuild archive/build, simulator install or launch, TestFlight validation, Expo/EAS. Holds the four canary rules on local-build authority, the one-operator simulator lock and its scope guard, load gates, and hosted-build authorization."
---

# Native build authority — canary rules (2026-10-19)

This skill is the full text of the shared-policy section "Native build authority — canary rules" in
`~/.codex/AGENTS.md`. That section keeps the hard limits inline and requires reading this file before
any native-build decision. The text below is mandatory policy, not advice.

A *local* native build (xcodebuild archive/build, simulator install, TestFlight
validation) is **permitted whenever the user or the owning release operator asks
for it**. A local build is the default reading of "use local build and CI".
Resource pressure, runner availability, or a missing remote runner is a
**scheduling** fact, never a prohibition.

- `localbuildallowedwhenrequested` — "local build" instructions authorize local
  builds; do not convert them into a remote-only requirement. Do not refuse a
  local build by citing a policy that does not name its owner, reason and expiry.
- `no competingnativeoperator` — **iOS Simulator only.** One native operator per
  simulator build/device. Before a second lane builds, installs or launches on the
  same simulator UDID or the same app bundle, obtain the chosen UDID and the
  operator lock; never erase, reinstall or relaunch a device another lane is
  proving on.

  **Scope guard (this lock never generalizes):** the operator lock covers the
  simulator UDID and app bundle and nothing else. It does not extend to accounts,
  credentials, environments, campaigns, quotas, or any other shared resource. A
  shared test account is **never reserved**: a ledger, queue, admission, handback,
  or "reserved/held/locked" note is scheduling state, not a permission boundary.
  Exclusivity on any shared resource is only ever *observed* — a verified live
  competing operator you can name — never *declared* by a coordinator.
- `loadgate≠blanketban` — a load/memory/CPU/thermal gate defers a specific heavy
  run and MUST name its recheck condition (threshold plus how/when it is
  re-measured). It never becomes a standing ban. An explicit instruction to build
  changes who decides and requires an explicit recheck decision; it does not waive
  genuine thermal, power or resource-safety protection.
- `Expoheldunlessauthorized` — Expo/EAS **hosted** builds stay unauthorized unless
  the user explicitly authorizes them. Unused EAS credit, an existing profile, or
  a configured token is not authorization. This is the only standing native-build
  prohibition, and it is about *hosted* builds only, not local ones.

If a persisted note, roadmap entry, summary or coordination message states a
blanket "no local build" rule, treat it as stale: mark it superseded with a date
and cite this section. Never delete the historical record.
