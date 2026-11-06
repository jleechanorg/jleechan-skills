# Repository-First PR Workflow and Description Ownership

Status: implementation specification.

## Outcome
A repository's explicit local instructions determine whether and how the shared PR workflow applies. The shared `pr-lifecycle` skill supplies generic defaults where local policy is silent, `pr-workflow-manager` is the discovery/operation entry point, compatibility aliases only route to those owners, and PR-description rules have one normative owner in shared AGENTS guidance.

## Non-goals
No runtime code, tests, scripts, CI, live installation, credential changes, external review calls, deployment, merge, force-push, or destructive cleanup. Do not rewrite historical specs or infer a repository opt-out from its name. Do not change separate authorization rules, source ownership, review quorum, destructive-action gates, or merge authority.

## Acceptance
- Before choosing branch/worktree/PR stages or gates, the entry point inspects repository `AGENTS.md`/`CLAUDE.md` and scoped workflow instructions, including an explicit local opt-out or adapter.
- Explicit repository-specific policy governs its domain. Shared lifecycle rules are fallback defaults where the repository contract is silent; generic policy cannot remove or replace local requirements. Current live user instruction still governs within separately gated permissions.
- An opt-out is followed only when a repository instruction explicitly declares it. Repository names, descriptions, or apparent purpose never imply opt-out. If no declaration exists, use the shared default and its discovery procedure.
- `pr-lifecycle` is the sole normative shared owner for generic PR stages, applicability, evidence reuse, and review routing; `pr-workflow-manager` is the operational entry point and points to lifecycle rather than duplicating its rules.
- Existing aliases remain callable but contain no competing policy. Consumer references resolve to the same owner without changing independent safety/authorization gates.
- Shared AGENTS guidance remains the sole normative owner of PR-description structure. `pr-description-sections` is a concise pointer/implementation aid; `pr-description-format` is a compatibility pointer, not a second section contract. Repository templates may retain repository-specific required fields and CI markers.
- No live user settings or installed skill projection is changed; source-versus-installed differences are recorded and reconciled only through the owning publication workflow.

## User stories
An agent starting work in a repository with explicit workflow instructions follows those local instructions and uses shared lifecycle defaults only for unresolved details. An agent in a repository with an explicit workflow opt-out discovers that before creating a branch or invoking generic PR gates; a repository with no opt-out follows shared defaults. A PR author finds one authoritative description structure while retaining local template fields.

## Proof plan
Inspect the complete Markdown diff and verify all lifecycle/description ownership links, explicit precedence wording, and opt-out discovery ordering. Search scoped shared Markdown for competing canonical-owner language and obsolete alias paths. Run only relevant existing documentation/contract checks if they can validate the final text without modifying tests; report any incompatible assertions as unresolved rather than weakening them. Confirm the worktree contains only the declared Markdown files, and confirm no installed user-scope configuration changed.

## Mock exemption
No product UI or rendered visual behavior changes; screenshots/video and player-facing mocks are not applicable.

## Risk
Conflicting policy text can misroute approvals or silently drop local safety requirements. Keep repository-specific safety, security, evidence, and merge restrictions intact; default only where local policy is silent; keep opt-out explicit and discoverable before workflow actions; preserve all unrelated ownership and installed state.
