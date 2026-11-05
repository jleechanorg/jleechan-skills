# Markdown instruction review by size and risk

## Outcome

Route Markdown skill, slash-command, and operator-guidance changes by the full changed-line count and subject risk. Keep ordinary low-risk instruction updates reviewable with one or two complete AI source reviews, without requiring separate evidence-generation ceremony that proves no changed claim.

## Non-goals

No changes to executable helpers, tests, CI, configuration, production prompts or schemas, service contracts, evidence publication systems, reviewer transport, or merge authorization. This policy change does not qualify for its own route and retains the existing full review requirements.

## Acceptance

- Pure Markdown instruction changes at or below 150 total added plus deleted lines use one cold independent full-scope AI reviewer when low-risk.
- Pure Markdown instruction changes above 150 total added plus deleted lines use two independent full-scope AI reviewers.
- Sensitive instruction changes use two independent reviewers at every size. Sensitive includes security, permissions, credentials, destructive operations, production evidence, and approval, review, or merge rules.
- Each reviewer receipt records the exact SHA, complete diff coverage, route and risk assessment, relevant before/after scenarios, findings, and verdict. Partial coverage cannot be combined.
- Pure Markdown instruction changes do not require a seven-element PR spec, separate /es or /er adjudication, evidence bundle/publication, runtime or provider test, browser journey, or visual evidence solely due to their file type or size.
- Changed executable examples and claims retain the smallest proof needed to establish them. Mixed Markdown/code PRs, actual production prompt/schema/runtime contract changes, and stricter repository requirements use their applicable routes.
- Visual evidence follows the claim: backend-only changes with no rendered, displayed-data, or interaction claim do not need visual proof; actual rendered or interaction changes retain applicable proof.
- The route is defined in pr-lifecycle. Advice points to it; reviewer-tier identity and coverage rules remain owned by advice and static-review.
- AGENTS.md points to the canonical lifecycle route instead of requiring /cs and Ponytail for a qualified Markdown instruction diff solely because it exceeds 50 changed lines.

## User story

An author updating a small safe skill can obtain one complete independent AI review. A broader update or a sensitive operational rule gets two reviews. Neither author nor reviewer has to generate runtime evidence for claims the change does not make, while any real executable, service, prompt, or visual claim keeps its relevant proof.

## Proof plan

- Run git diff --check and the existing portable-skill verifier.
- Check Markdown links/frontmatter or other structure affected by the diff.
| Scenario | Route / reviewers | Proof and visual applicability |
|---|---|---|
| 75-line low-risk skill update | Markdown instruction route; one cold full-scope reviewer | Source diff and before/after rule scenarios; no separate /es, /er, bundle or runtime proof solely for size/path |
| 400-line low-risk operator manual | Markdown instruction route; two independent full-scope reviewers | Same bounded source/scenario proof; no automatic /cs or runtime proof solely for size |
| 12-line security instruction | Sensitive route; two independent full-scope reviewers | Relevant threat/permission scenario proof; any named domain check remains |
| 40-line internal backend change, no UI or changed service boundary | Normal code route; apply deterministic risk row | Focused behavior proof; no visual evidence because no rendered/displayed/interaction claim changed |
| Backend change that alters a rendered interaction | Changed-claim/service and UI route; reviewer count follows highest risk | Real service/browser and rendered evidence for the changed claim |
| Mixed script and Markdown | Ordinary mixed route; Markdown route is ineligible | Test executable/script behavior plus review all paths; applicable /cs follows repository rules |
| Production prompt contract stored in Markdown | Prompt/schema route; Markdown route is ineligible | Relevant model/prompt contract proof and high-risk independent review |
| Metadata-only later phase; no changed scope or claim | Reuse the prior exact-SHA review if delta assessment confirms applicability | No duplicate reviewer call because the phase changed; current checks and separate merge authority still apply |

Inspect the complete final diff and confirm current advice-tier identity/counting and merge-authority rules remain unchanged.

## Mock

No product UI or runtime behavior is changed. A rendered mock is not applicable. The eight instruction-routing scenarios are the behavioral review fixtures; they are judgments over the written policy, not wording-pin tests.

## Risk

A reader might classify sensitive policy as ordinary prose, or treat a file extension as proof that no runtime claim changed. The route requires classification of the complete diff, explicitly excludes approval/review/security/evidence changes from the one-review allowance, and routes mixed or uncertain changes to the ordinary requirements. Actual claims and stricter repository gates remain controlling.
