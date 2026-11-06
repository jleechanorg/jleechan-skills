# Durable Dot Reconciliation Implementation Plan

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

Goal: Retain every actionable user commitment until verified completion or cancellation, and recover it through existing issues/owners and the three account-bound coordinator turns.

Architecture: Extend .claude/skills/dot-coordinator with a standard-library private intake/outbox helper, using existing GitHub issues as the canonical engineering task records and a single configured writer host. Preserve Pi semantic judgment, direct browser transport, CLI configuration and native schedules. Do not restore the removed browser/profile lock framework.

Tech Stack: Python 3 standard library, SQLite, unittest, existing Pi and Chrome DevTools MCP, existing authorized GitHub transport.

## Task 0: Canonical document-review gate
TDD: N/A for read-only review. Run canonical /advice --document docs/superpowers/specs/2026-10-22-durable-dot-reconciliation-design.md --document docs/superpowers/plans/2026-10-22-durable-dot-reconciliation.md against these exact committed bytes, with the primary reviewer pair and full coverage. Record the review artifacts and hashes. Resolve blocking findings before Task 1. A supplemental native review or unavailable reviewer lane is not a passing quorum.

## Task 1: Durable scan and task journal
Files: create .claude/skills/dot-coordinator/scripts/task_journal.py and tests/test_dot_task_journal.py.
1. Write tests for fixed rolling-24h scan window with watermark overlap; page cursor progression; duplicate message handling; incomplete/access-failed scans; old unresolved records; later cancellation winning over old pages, including an immediately durable cancellation tombstone when subsequent pagination fails, authenticated global stop, and secure private journal permissions.
2. Run python3 -m unittest discover -s tests -p test_dot_task_journal.py -v. Expected RED: task_journal module absent, then individual missing behavior assertions after a minimal import shell.
3. Implement SQLite transactions for scan/page/commit, storing only source hashes/references and sanitized task facts. Use no external dependencies or semantic regex classifier.
4. Run the same command. Expected GREEN: all added assertions pass, including reopen after interruption.
5. Commit only this helper and its tests on the source-bound branch. Use the canonical Git tree as the parent and verify remote blob identities; never claim a materialized subset is a complete checkout.

## Task 2: Receipt-bound issue and per-Dot outbox
Files: extend the same helper and tests.
1. Write tests for deterministic intent IDs, verified existing issue recovery, ambiguous issue creation, uncertain send with no blind retry, positive no-send recovery, per-dot receipt isolation, separate recurring delivery generations, successor-version uncertainty fencing and bounded backoff. Verify queued/delivered/picked_up/executing/completed_verified distinctions.
2. Run python3 -m unittest discover -s tests -p test_dot_task_journal.py -v. Expected RED: operations currently have no durable state or accept invalid transitions.
3. Add minimal operation APIs and task progress transitions. Require proof for claimed execution/completion. Preserve owner on thirty-minute stale checks and suppress cancelled task intents.
4. Run focused and full applicable coordinator regression suites. Expected GREEN: no duplicate intents or unsafe retry, old tasks survive and unrelated work remains available.
5. Commit scoped changes on the same source-bound branch and verify the changed remote blobs.

## Task 3: Integrate the existing Pi turn
Files: modify .claude/skills/dot-coordinator/SKILL.md, scripts/ping-dots.py, RENDERING.md and MIGRATION.md; add launcher/contract tests as needed.
1. Write tests asserting the helper/account-bound journal context reaches the existing one Pi turn; original full-24h pagination and issue/owner recovery precede outbound work; unknown sends require readback; no scheduler/provider/profile-lock changes.
2. Run python3 -m unittest discover -s tests -p 'test_*coordinator*.py' -v and python3 -m unittest discover -s tests -p test_simple_dot_ping.py -v. Expected RED: old skill says reminder-only/four hours and launcher lacks journal contract.
3. Replace obsolete reminder-only clauses with the source-backed reconciliation workflow; retain identity, intended conversation, peer-draft and direct-browser checks. Carry mechanical command paths in the private prompt. Render existing host config only after writer/store preconditions are verified.
4. Run task journal, launcher, naming, CLI, renderer, timeout and installer regression tests against the full checkout. No live sends occur in unit tests.
5. Commit the scoped integration and document exact source/test identities.

## Task 4: Review and operator deployment handoff
Files: docs/superpowers/specs/2026-10-22-durable-dot-reconciliation-design.md and this plan; private evidence receipt outside exported source.
TDD: N/A for handoff-only documentation. Verify every file hash against final bytes and every stated command against captured output.
1. Run canonical /advice document mode on these two exact paths, then independent source reviews at the actual final commit. If its tooling is unavailable, mark FAILED/WITHHELD and keep deployment gated.
2. Provide the installation operator with the verified base/head, patch or branch, full test commands/results, unresolved integration preconditions and rollback plan.
3. The installation operator verifies current host source/config, takes recoverable backups, preserves unrelated edits/holds, installs reviewed files and compares hashes. No credential/security change, service restart or redundant scheduler is implied.
4. Verify live behavior separately on both hosts and all three bound Dots, including source coverage, receipt recovery and the designated single writer. Report blocked or unobserved acceptance honestly.

## TDD Plan Check
Task 0: TDD N/A because this is a document-review gate; exact inputs and quorum required.
Task 1: exact paths and RED -> implementation -> GREEN -> conditional commit checked.
Task 2: exact same-module paths and receipt/retry/state RED -> implementation -> GREEN -> conditional commit checked.
Task 3: exact launcher/workflow paths and integration RED -> implementation -> GREEN -> conditional commit checked.
Task 4: TDD N/A because it verifies reviews/deployment artifacts rather than adding behavior; checks specified above.

## Implementation Preconditions
See design's exact single writer/observer host roles, approved issue destinations, source pagination, canonical checkout and /advice availability requirements. Implement offline behavior without inventing host config. Offline implementation begins after the canonical document-review gate passes; unknown host configuration does not block those offline tests. Do not activate runtime publication, deploy or claim cross-host guarantees until the deployment requirements are observed.

## Planning self-review
The specification compares three approaches, records recommended defaults, separates source tests from live evidence, and avoids reinstating legacy browser locks. The plan keeps one helper and current launcher, has explicit behavior tests, and retains a conditional deployment gate rather than treating missing infrastructure as a design success.


## Required focused acceptance cases
All below belong in tests/test_dot_task_journal.py or the actual launcher/adapter integration tests, not only prompt-string checks.
- test_uncertain_v1_blocks_v2_create_and_send; test_not_found_is_not_proof_of_no_side_effect.
- test_verified_delivery_can_be_reintroduced_when_due; test_bounded_summary_fairness; test_summary_receipt_is_not_pickup.
- test_two_processes_claim_one_operation; test_crash_after_claim_does_not_release_for_retry.
- test_three_accounts_share_journal_not_identity; test_observer_cannot_dispatch.
- test_cancel_survives_partial_scan_and_restart; test_cancel_after_envelope_creation; test_old_page_cannot_revive_cancelled_task.
- test_seven_day_gap_survives_repeated_timeouts; test_fixed_until_excludes_arrivals_during_scan.
- test_rebuild_mapping_from_older_issue; test_closed_issue_without_acceptance_remains_unresolved; test_newer_github_owner_wins_over_stale_local_snapshot.
- test_same_source_different_proposed_key_reuses_task; test_two_sources_one_task_and_two_accounts_same_message_id; test_authenticated_edit_revises_not_duplicates.
- test_private_task_never_enters_other_account_payload; test_replayed_artifact_does_not_reset_stale_clock; test_receipts_claims_and_wrong_version_proof_do_not_complete; test_stale_owner_is_contacted_not_reassigned.
The integration task replaces obsolete reminder-only/four-hour assertions, while retaining tests that no legacy profile flock, STOP file or account-wide reservation is restored or consumed. Source snapshots and fake transports exercise state transitions without real messages, issues or provider calls.
