# Risk-based routing for bounded PRs

## Outcome
Choose focused proof and one complete independent review for bounded low-risk changes before applying total-diff size thresholds. Keep the existing trivial and one-liner paths lighter.

## Non-goals
Do not change merge authority, repository-specific safeguards, installed configuration, CI code, or real-service evidence requirements for claims that need them. This policy change does not exempt itself from normal review.

## Acceptance
- Added regression tests, documentation and mechanically safe offline tooling do not alone trigger a separate specification, media package or duplicate review rounds.
- The independent reviewer confirms eligibility from actual diff effects and safeguards, rather than accepting a label.
- CI/proof-selection changes, agent policy, shared-fixture meaning and weakened assertions or evidence stay outside the compact route.
- Security, trust, credential, deployment, destructive, persistence, model/schema, network and retry-budget changes retain applicable controls.
- Reuse a review only while its scope remains applicable; current checks and merge authority remain separate.

## User story
A contributor extending an existing error-classification branch or offline sampler can finish with meaningful focused checks and clear proof limits, while dangerous changes retain independent scrutiny.

## Proof plan
Run the existing lifecycle contract checks and inspect the complete policy diff independently. Check paired cases: added caller regressions and a safe offline sampler can qualify; skipped assertions, changed shared-fixture meaning, changed CI selection and agent-policy changes cannot. A potentially billable probe still requires explicit execution and action/account/campaign/provider authorization. No test double proves production integration.

## Mock exemption
No rendered interface changes. Source inspection, command output and independent policy review are the applicable evidence; no gameplay or native media is claimed.

## Risks and ownership
Misclassification could weaken proof. The explicit exclusions and independent eligibility assessment address that risk. The lifecycle skill owns the rule; the workflow manager links to it. Repository-specific requirements take precedence. Separate reviewer, credential, spending, destructive-action and merge controls remain unchanged.
