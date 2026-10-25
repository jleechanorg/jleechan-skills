# Shared PR workflow skill consolidation

Status: implementation proposal, not review or merge approval.

## Outcome
One reusable, self-contained lifecycle contract in pr-lifecycle (with draft-first-pr retained as a thin compatibility entry point), reached through pr-workflow-manager and thin repository/user-level references.

## Non-goals
No runtime code, new scripts/tests/CI, live installation, credential change, provider call, merge or deployment. No duplicated lifecycle in repository design documents.

## Acceptance
- The existing canonical lifecycle contains the complete opt-in six-stage mapping, title prefixes/labels and specification rules.
- Stage2 is named evidence generation; stage title, label and PR body are synchronized without implying approval.
- Earlier tested/reviewed SHAs remain immutable; reasoned delta/claim assessment determines reuse or affected new proof in both draft and final phases.
- Review quorum, independent coverage, current-candidate CI/mergeability and separate merge authority remain intact.
- pr-workflow-manager references the contract, is referenced back, and contains safe clone-if-absent, draft creation and branch/source verification guidance.
- Known contradictory helper/reset/force-push recipes are removed from routine manager guidance; no missing helper is assumed.
- Related ready/advice/evidence-review/web-advice wording agrees with the canonical applicability rule.
- Existing applicable contract tests preserve their safety intent. The requested /ready and canonical rename include narrow updates to existing obsolete text/path assertions, plus a compatibility-pointer regression; no runtime code or new CI workflow is added.
- Complete-diff risk and claim classification allows narrow docs/copy exceptions and bounded log-emission proof without exempting policy, auth, service-boundary or other high-risk changes.
- Every stage exit links retrievable sanitized gist/artifact evidence in the PR description, with applicable viewable inline media or a specific justified media N/A.
- Backlogged CI can use actual equivalent local checks with per-job command/environment/result/source receipts; failed, dirty-candidate or unproven checks cannot be relabeled PASS.

## User stories
A PR driver can discover the shared skills in a verified checkout and find the current unmet gate. A reviewer can distinguish original proof from its reasoned applicability. No product UI changes, so no player-facing mock is applicable.

## Proof plan
Read the complete changed Markdown diff; verify relative skill references, stage mappings, threshold boundaries, phase ordering and immutable receipt attribution. Run the existing focused coding-lifecycle contract suite using unchanged tests and pinned companion inputs; report absent sibling-checkout coverage separately. Read back published blobs/heads and inspect resulting CI. Independent policy review remains required.

## Mock exemption
This changes agent workflow instructions, not a player-facing screen. Title/label readback is metadata proof, not product UI evidence.

## Risk
Policy changes can misroute evidence or approval. Use one normative skill, explicit applicability records, preserved quorum and repository-specific safety/merge rules. A source push does not prove installed-host synchronization.

## Delivery
Publish this shared skill candidate separately from repository adapter PRs. Repository adapters reference these skills rather than a dated design. Installed/user-level guidance changes require their owning host/source path and scoped verification; preserve unrelated local edits.
