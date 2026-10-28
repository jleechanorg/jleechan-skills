# Advice primary runner attempt deadline

## Outcome
Give each supported primary reviewer attempt one monotonic deadline that covers per-reviewer clone setup, reviewer execution, result acceptance, and a reserved cleanup window. A late result cannot count as a vote, even if its subprocess exits successfully.

## User story
No user-facing change. `/advice` receives a more honest, bounded attempt outcome and receipt when setup or review overruns.

## Process identity safety follow-up
- **GOAL:** prevent timeout cleanup from signaling an unrelated process after a reviewer PID or process-group ID is reused.
- **MODIFICATION:** bind reviewer roots and descendants to start identities; on Linux, verify parent identity with a pidfd after reading each child’s parent PID and signal descendants only through a pidfd after rechecking identity. Skip process-group signaling after the direct reviewer child has been reaped. Platforms without pidfd never signal tracked descendants by numeric PID and report survivors as unverified.
- **NECESSITY:** exact-head review reproduced both `None == None` admitting an unverified root and a cached parent PID being reused between identity observation and child admission. A child pidfd alone cannot prove that child belonged to the reviewer tree.
- **INTEGRATION PROOF:** add focused regressions for unknown/reused roots, parent-PID reuse, post-pidfd identity mismatch, and safe process-group handling; run the full primary-pair suite and installed smoke suite before the next exact-head review.

## Goals and acceptance
- Add a runner-owned attempt timeout, defaulting to 600 seconds, independent of the existing per-process timeout setting. Callers must capture UTC epoch and same-host monotonic nanoseconds together immediately before dispatch and pass both required queue timestamps; the runner rejects missing or invalid timestamps. UTC is audit-only. Queue elapsed time, reviewer completion acceptance, and attempt deadlines use monotonic time. Caller and runner must share one host monotonic clock; cross-host orchestration accounts for its outer budget separately.
- Start the attempt clock before per-reviewer clone setup; bound supported setup subprocesses and reviewer subprocesses by remaining time.
- Bound each reviewer barrier wait by its remaining lane budget and abort the barrier if any worker submission fails, so executor shutdown cannot wait indefinitely for an unpaired lane.
- Reserve a configured bounded portion for cleanup; begin cleanup when the work budget expires, and record deadline, elapsed time, timeout stage, and cleanup outcome.
- Reject results/votes observed after their lane's work deadline and invalidate all votes only when the overall attempt deadline is exceeded; preserve a timely peer vote when another lane enters the cleanup reserve.
- Require consumers to accept votes only when the runner exits zero and a readable receipt exists; disclose when a failed final receipt rewrite may leave stale approval-looking output.
- Keep the existing independent clone behavior. Strengthen sampled descendant identity and signaling without adding a wrapper, watchdog, helper executable, or framework.
- The `/advice` caller captures `QUEUED_AT_EPOCH_NS` and `QUEUED_AT_MONOTONIC_NS` together after packet preparation and immediately before dispatch. It passes both required options; the runner refuses either missing or invalid timestamp. Monotonic acceptance requires caller and runner on the same host and boot. UTC is audit-only; cross-host orchestration tracks its outer budget separately.
- Preserve actionable partial receipts and report any cleanup uncertainty honestly.

## Non-goals
- Hard real-time guarantees for filesystem deletion or other uninterruptible OS operations.
- Changing reviewer quorum policy, reviewer CLI/account/model, or guaranteeing discovery of arbitrary descendants that escape the sampled process tree.
- Enforcing that every attempt consumes exactly 600 seconds; fast completion and cleanup remain fast.

## Proof plan
Add focused unit tests first that demonstrate a missing queued timestamp is rejected without dispatch, an already-expired queued timestamp is rejected before clone/reviewer work, setup time consuming the same budget as review, reviewer timeout capped by remaining attempt time, late successful output rejected, cleanup budget reflected in the receipt, unknown/reused roots rejected, reused parent identity rejected before descendant admission, and descendant signals bound to a verified pidfd. Characterize the baseline by delaying after queue timestamp capture: the old runner can accept a vote beyond the queued-time budget, while the candidate rejects it. Run the focused test module on the isolated source worktree; inspect receipt fields and elapsed bounds. On platforms without pidfd, verify numeric descendant signals are skipped and surviving descendants invalidate the attempt.

## Test and mock rationale
The runner tests use fake local CLI executables and a temporary Git repository to deterministically test subprocess deadlines, receipts, and cleanup without external reviewer services. This is appropriate for the runner-owned timeout contract; it does not claim live reviewer compliance.

## Risks
A subprocess can be interrupted and drained within the remaining process budget, but `shutil.rmtree` and other OS/filesystem operations can exceed a user-space deadline if blocked uninterruptibly. Linux pidfd signaling pins the target process after acquisition and verifies its start ticks, but sampled discovery is not exhaustive. Platforms without pidfd skip numeric descendant signals; an observed survivor makes the attempt unavailable. The receipt must distinguish the configured cleanup allowance from a guaranteed wall-clock return bound.
