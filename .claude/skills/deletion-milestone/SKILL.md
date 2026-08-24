---
name: deletion-milestone
description: Generic discipline for any deletion or quarantine milestone PR — net LOC enforcement, scope verification, PR lifecycle guards
type: skill
scope: global
---

# Deletion Milestone Skill

## Purpose

Governs ANY PR whose milestone is "delete," "quarantine," "remove," or "cleanup first" — not "add feature" or "refactor in place." Applies to ANY project. Prevents the recurring failure: agents substitute PR lifecycle work (conflict resolution, CR responses) for the actual deletion work, and claim milestone completion without proof.

**Companion concept**: [[ScopeDrift]], [[PragmaticLayerAntiPattern]], [[AgentDrift]], [[Net-Negative-Deletion-Is-Ok]]

## Activation Cues

- Any PR with "M0," "cleanup," "deletion," "quarantine," "remove legacy," "strip" in the title or bead
- Any task bead tagged `deletion`, `cleanup`, `M0`, `legacy-removal`
- Any roadmap section titled "delete first" or equivalent
- When `/harness` surfaces a "commitment substitution" failure on a deletion milestone

## Core Rule

**Deletion milestones must delete. Net production LOC must be ≤ 0 before claiming merge-ready.**

Adding formatter logic, hardening code, or helper utilities while legacy paths still exist is NOT cleanup — it is [[PragmaticLayerAntiPattern]].

## Pre-Flight Scope Verification (Mandatory before starting)

1. Read the governing bead/roadmap doc
2. List the specific files/functions that will be deleted
3. For each: state **adding**, **deleting**, or **modifying in place**
4. If any file has net positive LOC and the milestone is deletion → **STOP**, re-assert scope
5. If scope has drifted from the bead → re-assert with human before proceeding

## Net LOC Protocol

For any PR claiming a deletion milestone:

```bash
# Compute net production LOC (adjust -- path for your language/structure)
git diff --stat origin/main -- "*.py" \
  | grep -v test \
  | grep -v __pycache__ \
  | awk '{ adds+=$1; dels+=$3 } END { print "adds=" adds, "dels=" dels, "net=" adds-dels }'
```

**Rule:** If `net > 0`, the PR is **not ready for merge**. State "net positive — deletion work remaining" explicitly. Do not claim the milestone is complete.

**Exempt:** Tests, documentation, schemas. Production code only.

## PR Lifecycle Time Budget

| Activity | Max time | Why |
|----------|----------|-----|
| Conflict resolution | 30 min | Never let conflict fixing consume actual deletion time |
| CR/Bugbot response | 1 hr | Polish, not scope |
| CI retry | 20 min | Don't chase flaky runners beyond threshold |
| **Actual deletion work** | Remaining | This is the milestone |

**Escalation rule:** If conflict resolution exceeds 30 min, state: "merge conflict requires human decision — I am continuing other work" and stop spending time on it.

## Anti-Patterns

### Do NOT
- Add new formatter logic while legacy paths still exist
- Claim "cleanup complete" if net production LOC increased
- Merge a deletion PR if legacy branches are still reachable without tests
- Let PR lifecycle (conflict resolution, CR responses) consume time that should be deletion work
- Substitute "hardening the new code" for "removing the old code" — these are sequential, not parallel

### The Substitution Trap

This is the #1 recurring failure:
- Agent commits to "delete legacy X" (milestone = deletion)
- PR lifecycle issues arise (conflicts, CRs)
- Agent spends hours on PR lifecycle with no behavioral change
- Agent then says "well I hardened the formatter instead" as partial credit
- Net result: old code still there, new code added, milestone NOT met

**Prevention:** The net LOC check is non-negotiable. If net > 0 on a deletion milestone, the milestone is not complete regardless of what else happened.

## The "Pragmatic Layer N" Anti-Pattern

When a PR is named after a milestone (e.g., "M0 cleanup") but doesn't meet the milestone gates:

| Response | When to use |
|----------|-------------|
| Update the design doc to reflect what was actually done | The milestone scope was intentionally changed |
| Track the original milestone as a follow-up bead | Scope changed but original intent still matters |
| Decline to merge as-is | Named milestone but different behavior — misleading |
| Negotiate new scope with human | Genuinely blocked on original scope |

**Never merge a mislabeled milestone without disclosing the gap.**

## CI Gates for Deletion Milestones

A deletion milestone PR should have, or preceded by:
- Net LOC check gate (compares production code additions vs deletions)
- Legacy branch reachability test (proves old paths are actually dead)
- Regression test for removed behavior (ensures nothing depended on the deleted code)

If these don't exist, the deletion is unproven. A PR that deletes without tests is a PR that hopes the deletion was safe.

## Relationship to Other Skills

| Skill | What it provides |
|-------|-----------------|
| `pr-workflow-manager.md` | General PR lifecycle (upstream, conflict resolution) |
| `harness-engineering/SKILL.md` | General failure pattern analysis + CI gate design |
| `evidence-standards.md` | Real-model evidence requirements |
| Project-specific `*-zfc/SKILL.md` | Project-specific phase checklists (M0/M1/M2/M3) |

This skill provides the **generic deletion discipline**; project skills provide the **specific phase checklists**.

## Commitment Integrity for Harness Itself

**Critical failure mode (3x recurring):** RCA identifies missing CI gates → memory is written → gates are never built → same failure recurs.

When an RCA proposes CI gates:
1. The gates must be added to the **task/bead description** as explicit deliverables
2. Not just "fix the process" — specify WHICH file gets WHICH gate
3. Until the gate exists in code, the harness is still broken

Rule: **Proposed automation is not implemented automation. Memory of a fix is not a fix.**
