# Advice primary runner attempt deadline

## Outcome
Give each supported primary reviewer attempt one monotonic deadline that covers per-reviewer clone setup, reviewer execution, result acceptance, and a reserved cleanup window. A late result cannot count as a vote, even if its subprocess exits successfully.

## User story
No user-facing change. `/advice` receives a more honest, bounded attempt outcome and receipt when setup or review overruns.

## Goals and acceptance
- Add a runner-owned attempt timeout, defaulting to 600 seconds, independent of the existing per-process timeout setting. Callers must pass `--queued-at-epoch-ns` captured when the reviewer request is actually queued or sent; the runner rejects invocations that omit it, so no vote can be counted without a queue boundary. The runner converts elapsed queue time to its monotonic deadline.
- Start the attempt clock before per-reviewer clone setup; bound supported setup subprocesses and reviewer subprocesses by remaining time.
- Bound each reviewer barrier wait by its remaining lane budget and abort the barrier if any worker submission fails, so executor shutdown cannot wait indefinitely for an unpaired lane.
- Reserve a configured bounded portion for cleanup; begin cleanup when the work budget expires, and record deadline, elapsed time, timeout stage, and cleanup outcome.
- Reject results/votes observed after their lane's work deadline and invalidate all votes only when the overall attempt deadline is exceeded; preserve a timely peer vote when another lane enters the cleanup reserve.
- Require consumers to accept votes only when the runner exits zero and a readable receipt exists; disclose when a failed final receipt rewrite may leave stale approval-looking output.
- Keep the existing independent clone and process identity supervision behavior; no new wrapper, watchdog, helper executable, or framework.
- The `/advice` caller captures `QUEUED_AT_NS` after packet preparation and immediately before dispatch, then passes `--queued-at-epoch-ns "$QUEUED_AT_NS"`; the runner refuses calls without this value.
- Preserve actionable partial receipts and report any cleanup uncertainty honestly.

## Non-goals
- Hard real-time guarantees for filesystem deletion or other uninterruptible OS operations.
- Changing reviewer quorum policy, reviewer CLI/account/model, or process-tree containment guarantees for unobserved arbitrary daemons.
- Enforcing that every attempt consumes exactly 600 seconds; fast completion and cleanup remain fast.

## Proof plan
Add focused unit tests first that demonstrate a missing queued timestamp is rejected without dispatch, an already-expired queued timestamp is rejected before clone/reviewer work, setup time consuming the same budget as review, reviewer timeout capped by remaining attempt time, late successful output rejected, and cleanup budget reflected in the receipt. Characterize the baseline by delaying after queue timestamp capture: the old runner can accept a vote beyond the queued-time budget, while the candidate rejects it. Run the focused test module on the isolated source worktree; inspect receipt fields and elapsed bounds. Existing detached-descendant test remains the identity/cleanup regression proof.

## Test and mock rationale
The runner tests use fake local CLI executables and a temporary Git repository to deterministically test subprocess deadlines, receipts, and cleanup without external reviewer services. This is appropriate for the runner-owned timeout contract; it does not claim live reviewer compliance.

## Risks
A subprocess can be interrupted and drained within the remaining process budget, but `shutil.rmtree` and other OS/filesystem operations can exceed a user-space deadline if blocked uninterruptibly. The receipt must distinguish the configured cleanup allowance from a guaranteed wall-clock return bound.
