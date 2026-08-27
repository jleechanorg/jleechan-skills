---
name: spec-intent-confirmation
description: "Use BEFORE infra specs (CI/runner routing/deploy config). Confirm key behavioral decisions explicitly; flag infeasible numeric targets as STOP."
---

# Spec intent confirmation — confirm routing/cost decisions before implementing


Before implementing infra specs (CI workflows, runner routing, deployment config): identify key behavioral decisions and confirm explicitly. "Review and approve it" ≠ user approved design decisions — they may be delegating review to you.

Red flags requiring confirmation: conditional `runs-on`, cost-optimization comments, mixed "ubuntu for PRs / self-hosted for main" patterns.

**Infeasible numeric targets** — If target is physically impossible as stated, STOP. State infeasibility ("floor is already X, Y unreachable"), propose closest feasible interpretation, wait for confirmation. Never silently substitute.
