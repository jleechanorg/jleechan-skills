# Proportional exceptions and the documentation-only exceptions

On-demand part of [pr-lifecycle](SKILL.md): load it when classifying a change for a proportional exception,
the one-liner fast path or claim-specific proof (Markdown-only, logging-only, alerting-only, non-production
tests, display copy), or the documentation-only CI and `/er` exceptions.

## Proportional exceptions and fast paths

These claim/risk rules apply to the generic lifecycle and to opted-in repositories; only the stage/title/label machinery is opt-in.

Classify the complete diff by effects and claimed outcomes, not file extension, a non-production label or the latest commit size. For an entirely harmless documentation/mechanical change, or an obvious display-copy-only change, under 50 total additions+deletions, a compact `/es` receipt with source before/after inspection and proportionate checks can suffice. Record `/er` and the extra independent `/dot` lane as `NOT REQUIRED — trivial-change exception`, never a fabricated PASS or reviewer vote. This exception applies at both review phases; explicitly requested reviews remain required. In opted-in repositories the seven-element specification may be concise but stays required in its prescribed location. The review-obligation table controls all remaining classes.

The exception excludes application prompts, schemas, selectors, URLs, interpolation, format/control strings, authentication, permissions, consent, payments, legal meaning, and approval, merge, review, evidence or security policy. Agent instructions that change these rules are not harmless documentation: this workflow policy cannot exempt its own review. A one-line change can be high risk. Mixed diffs follow the requirements of their affected claims.

**One-liner fast path.** A PR qualifies when the trivial-change exception applies and its production change is at most 10 added+deleted lines of display copy, comments, or removal of unused or unreachable text. Eligibility comes from the diff, not the PR's stated claim: the production diff changes only literal text, with no layout, style, component, condition, interpolation, data or control-flow change, and its only non-production changes are the pinning-assertion edits this path requires and literal-text updates in existing tests. The changed text necessarily renders differently and is the claim; any rendered, layout, interaction or displayed-data effect beyond it puts the diff off this path. It is complete when it has:
- current-head CI green, or the documentation-only CI exception;
- a clean merge-tree;
- a PR body that quotes the before/after source lines;
- where a test already covers the text, an assertion that pins the new literal (or, for a pure removal, asserts the removed text is absent) and that fails when run against the old text.

Its claim is source-literal and it publishes no media, so draft gate 4 (`/visual-verification`) and visual review do not apply, and it needs no gist, inline media, committed capture drivers, `/er`, visual-findings table or stamp, or `/dot`; record each as `NOT REQUIRED — one-liner fast path`. A later delta that changes the quoted text, the pinning assertion, or anything that renders the text re-runs these checks; other deltas reuse them under § SHA-binding rule, except that current-head CI is never reused. The compact `/es` receipt and the Stage 2–3 receipts are the PR-body before/after source quote, the pinning assertion's failing output against the old text (an excerpt in the PR body, where a test covers the text), and the current-head CI result; the `**Evidence**:` marker may point to that PR-body section or the PR diff URL with the head SHA instead of a gist. In opted-in repositories the specification may be one line per element and these checks satisfy Stages 2–3; Stage 4 (undraft, comment resolution, conflicts and current-candidate `/green`) still applies before Stage 5. Precedence follows § Precedence and scope: this path overrides a repository's generic "user-visible changes need media, gists or visual approval" wording only where that repository delegates proportional exceptions to this contract (for example a "Shared proportional-evidence applicability" pointer); otherwise the repository's explicit requirement governs. Reviewers must not raise P0/P1 findings for proof this path waives; such notes are P2 at most. Merge authority and the separate merge gates are unchanged, and an explicit user request for proof still applies.

For Markdown-only instruction changes, focused proof may use the complete base-to-head source diff, link/heading/structure checks, and scenarios against both text versions. Application runtime, browser/media and real-provider proof are `N/A` only when no changed claim depends on them. Markdown containing automation, prompts, schemas or machine-consumed contracts still needs its applicable proof. Changed agent instructions still need at least one independent adversarial full-scope LLM review, plus any applicable `/advice` quorum and repository-required `/dot` route. Reuse one version-pinned receipt across applicable stages, keeping original SHAs and recording candidate applicability; rerun only proof the delta affects.

For logging-only changes, use bounded execution showing the actual emitted log, level and fields, with original source SHA, command, timestamps and sanitized output; focused `/er` may approve that emission claim without unrelated browser or provider runs. Check privacy and side effects: new sensitive data, destinations, machine-consumed contracts, alerts, expensive expressions, exceptions, mutation or retries need their affected proof. Emission alone does not prove downstream ingestion or alert delivery.

For alerting-only changes, focused `/es` and `/er` may prove the alerting claim with a controlled real trigger through the changed emission or dispatch path and receipt of the actual alert at each claimed destination. Keep the source SHA, environment, timestamp, correlation and delivery IDs when available, sanitized alert text, and logs plus provider or destination receipts. Video, screenshots, browser or native gameplay journeys and paid LLM runs are not required merely to prove an alert fired. Direct sink sends prove transport only; mock, unit and source inspection cannot prove live delivery. Mixed diffs keep the affected proof for non-alert changes; privacy and security checks, CI, code-review, quorum and merge permissions are unchanged. A PR merely named for alerts gets no broad exemption, and an alert-only claim carries no universal mandate for native or player journeys.

Non-production tests, fixtures, drivers and CI changes need proportionate checks of changed assertions and affected contracts, not automatic runtime capture and not automatic exemption. Never weaken assertions or mock away a claimed boundary to qualify.

Source-only display-copy inspection proves the literal change, not rendering, accessibility or localization; media may be explicitly `N/A` for that bounded claim. A claimed static appearance needs real rendered proof and an inline screenshot; interaction or streaming claims keep their applicable video requirements. These narrow exceptions govern generic all-UI-media wording in linked skills; named risk-specific requirements, explicit user-required proof and safety controls still apply.

### Documentation-only CI exception

Documentation-only changes, including instruction/skill documentation, need no CI or runner wait. Apply `../pr-green-definition/SKILL.md` § Documentation-only CI exception for scope, proportionate local validation and SHA-bound reporting. That exception is independent of the narrower `/er` allowlist below and does not remove applicable draft-phase gates, conflict checks or merge authorization.

### Documentation-only `/er` exception (narrow allowlist)

After `/es`, classify the complete changed-path set against the PR's true base. An owner/repository suffix is ambiguous across hosts, so resolve the base through the API, not from a remote name.

With the PR checkout as the working directory, run this skill's `scripts/pr-base-changed-paths.sh <N>` by its path in the loaded skill directory: `"${CLAUDE_HOME:-$HOME/.claude}/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh"` for an installed skill, or `.claude/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh` under a repository checkout. It resolves the base through `gh api` on the pulls endpoint (`clone_url` and `ssh_url`), requires exactly one local remote matching the full host and repository path, and prints `git diff --name-only ${BASE_REMOTE}/${BASE_BRANCH}...HEAD`. Inspect its output; a resolution error leaves the exemption unproven.

For this `/er` exemption, every changed path must be one of:

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/**`

For that class, do not run `/er`: record `/er: NOT REQUIRED — documentation-only (<changed paths>)` on the PR, then continue to `/advice` where Advice applicability requires it. These PRs still need applicable `/es` and verdict coverage for the candidate, then the ready phase under the documentation-only CI exception and separate merge authorization.

The exemption is an exact allowlist, not a file-extension heuristic: changes under `.claude/**`, `.codex/**`, `.github/**`, prompts, tests, scripts, configuration, schemas or source code do not qualify even in Markdown. A mixed diff uses the normal `/er` gate unless the entire diff independently qualifies for the explicit trivial-change exception above.
