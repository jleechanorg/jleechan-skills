---
name: pr-driver-protocol
description: "Use after every `git push` on a PR — enumerates ALL current gate failures, fixes ALL in one local pass, and pushes once. The fix-all-before-push invariant."
---

# PR driver protocol — fix-all before push

A standalone, callable protocol for any agent (worker, babysit, human) that is driving a PR to green. The single rule: **after every push, fix ALL known gate failures in one local pass before the next push**. "CI pending" is not an idle state.

## When to use this protocol

- You just pushed a commit and need to wait for CI to come back
- You see the same gate failure 2+ times in a row (worker or babysit perspective)
- You are babysitting a worker that appears to be partial-fixing
- You are tempted to do "one quick fix and re-push" — **stop, run this protocol first**

## The 5-step loop

```
1. ENUMERATE   — read ALL current gate failures, not just the first
2. CLASSIFY    — group by file + root cause (same root cause = one fix)
3. FIX-ALL     — apply every fix locally; do not push until all are staged
4. VERIFY      — run the local equivalent of each failing gate
5. PUSH        — single commit covering all fixes; then back to step 1
```

### Step 1: ENUMERATE

Do not stop at the first failure. Use `/green <PR>` or read the `failure-class` log and build a complete list. For each failure, capture:

- **Gate name** (Green Gate, Evidence (draft phase, not /green), inline threads; CodeRabbit and Bugbot are optional advisory reviewers: never a gate or a wait, so not enumerated or verified here)
- **File and line** (e.g., `packages/cli/src/doctor.ts:142`)
- **Failure text** (the actual error message, not a paraphrase)
- **Root cause hypothesis** (what is wrong, not just what is failing)

### Step 2: CLASSIFY

Group failures by the underlying root cause. Two failures with the same root cause are one fix:

```
F1: dist/index.js argv shape not recognized in non-canonical check   (cli/doctor.ts:142)
F2: worker binary path resolution fails when global npm is used        (cli/doctor.ts:203)
  → Same root cause: argv path normalization is regex-naive
  → ONE fix: switch to path.basename() comparison
```

Do not push two commits to fix one root cause; that partial-fix-then-push loop is what this protocol stops.

### Step 3: FIX-ALL

Apply every fix in one local working tree. Stage selectively — **never `git add -A`**. The commit message should describe the bundle, not each individual fix; for example, `<repo commit prefix> fix: doctor argv-path handling (resolves gate 1 + 2)` with a body listing the changed lines and the added test.

### Step 4: VERIFY

Run the local equivalent of each failing gate **before** pushing:

| Gate | Local verification |
|---|---|
| Green Gate (CI) | the repository's test command (and the relevant package test) |
| Evidence | Open the PR description: are all claims backed by a gist or media link? |
| Inline threads | `gh api graphql ... isResolved` — every thread resolved? |

If verification fails, **do not push**. Go back to step 3 with the new failures added to the list.

### Step 5: PUSH

One commit, one push, then immediately back to step 1 (the loop continues). While CI is running, **pre-diagnose the next likely failure** by reading:

- The previous run's tail (often the next failure is in the same area)
- Any CodeRabbit comments not yet addressed

## Worked example

Three gate failures arrive together: two share one root cause (a config value), one is separate logic. Partial
pushes would cost three CI round-trips. Instead: enumerate all three, classify them into two fixes, apply both in
one tree, run the repository's test command for each, and push one commit.

## Anti-patterns (will be flagged by the harness)

- ❌ "Push one fix, wait, push another fix" — this is the failure mode
- ❌ `git add -A` to bundle fixes — staging must be selective per file
- ❌ Reading only the first failure in `gh pr checks` — always read the full list
- ❌ "CI pending, I'll wait and see" — CI pending is parallel-fix time, not idle time
- ❌ Generic `ao send` "fix CI" from babysit — DRIVER mode requires file:line + specific change
- ❌ "Let me first rebase, then fix, then push" — rebase is not a fix; do it after the fix-all is staged

## Babysit pairing

The `babysit` skill is archived in this repository, so the observer-side DRIVER-mode pairing is inactive. This
protocol stands alone on the worker side.

## Origin

- **Bead:** `bd-snx3`
