# Grok Bot and Private Reminder Specification

## Outcome

Provide `/grokbot` and `/grokb` as thin entry points to one reusable browser workflow. Keep the existing Dot coordinator's reminder transport while allowing the owner to select exact private reminder text from trusted local configuration. Preserve the shared two-complex, two-short outcome budget without implementing a second task store or admission service.

## Non-goals

- Do not create or schedule Grok messages, launch a live send, or activate a service.
- Do not store private payload text, account identities, conversation identifiers, host configuration, or credentials in the public skill package.
- Do not add another coordinator, task store, queue writer, lease, distributed reservation, or exactly-once mechanism.
- Do not treat the numeric capacity predicate as permission to start work.

## Acceptance

- Both command aliases resolve to the canonical `grokbot` workflow.
- The workflow confirms the expected account and target before acting, allows at most one authorized send attempt, and stops for explicit reconciliation when delivery is uncertain; it never retries automatically.
- The reminder workflow accepts only a trusted local regular UTF-8 file, records and rechecks its SHA-256 before submission, refuses symlinks or invalid/empty selected content, and retains the fixed fallback only when no custom path was selected and the default file is absent.
- Capacity guidance preserves exactly two complex and two short active outcomes. The read-only helper reports `BELOW_CAP`, `REJECT`, or input error; it writes no state and is not admission authority. The designated owner remains responsible for freshness, global occupancy and the existing serialized admission.
- Exported commands and skills contain no machine-specific personal data.

## User story

Before, the coordinator had no reusable Grok bot workflow, and reminder text could not be selected from a trusted private file. After, the owner can invoke one canonical workflow that verifies identity and target, uses exact authorized text, and stops safely on uncertain delivery; the coordinator can consult the shared numeric budget without mistaking the check for a reservation.

## Proof plan

- Run focused offline tests for Grok identity/target and uncertain-send wording, private reminder selection, command forwarding, coordinator recovery, installer integration, and the numeric capacity predicate.
- Run the skill portability scanner over the exported skills.
- Verify the exact diff, line classification, changed-file hashes, and current-head CI result.
- Classify live Grok sends, account authorization, private payload approval, and scheduled activation as unproven unless separately exercised through their authorized runtime paths.

## Mock or exemption

No live provider, browser session, private reminder file, or scheduler is needed to verify these static skill contracts. Offline tests inspect the portable instructions and numeric helper; they do not simulate a real send or claim live activation.

## Risk

An incorrect identity, destination, payload selection, or retry after uncertain delivery could expose private text or duplicate a message. The workflow fails closed on identity/target mismatch, invalid selected payload, changed bytes, and uncertain delivery. The capacity predicate is deliberately advisory; the designated queue owner must validate current evidence and perform serialized admission.
