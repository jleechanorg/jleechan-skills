# Portable Skill Parity Merge

## Outcome

Reconcile eight approved portable skill documents with the useful, reviewed live clauses while preserving current source safeguards, fixing nested evidence-standard references, and routing workspace-shaped output through the canonical Scratch resolver.

## Non-goals

No scripts, tests, runtime code, installs, pushes, pull requests, host-private operational details, or edits to protected and active-owner skills. No new evidence flags, `/tmp` workspace fallback, browser credential transfer, or broad replacement of source documents.

## Acceptance criteria

- Only the eight owned `SKILL.md` files and this spec change.
- `adjustment-proof`, `generatetest`, and `testing-gap-close` point to `.claude/skills/evidence-standards/SKILL.md` where repository-level evidence standards are referenced.
- Workspace-shaped evidence, captures, and clone outputs use canonical dynamic Scratch resolution and fail closed when Scratch is unavailable.
- `browser-control` retains the personal-browser prohibition, task ownership checks, cookie-transfer authorization boundary, and background/no-focus constraints; agent-owned service-account sessions require identity verification.
- `hermes` has one frontmatter description and retains its recovery behavior.
- `scratch-space` distinguishes scratch creation/admission from age-based pruning based on current CLI/help and owner-code evidence.
- All edits remain Markdown and pass portable zero-PII and whitespace checks.

## User stories

- As a skill maintainer, I can export evidence workflows without embedding a personal home or mount path.
- As an agent using browser control, I can verify a task-owned service account while keeping personal profiles and tabs out of scope.
- As a maintainer, I can read one canonical frontmatter description and receive accurate Scratch lifecycle guidance.

## Proof plan

Review the exact eight-file diff, verify only the eight skill files and this spec changed, search the changed files for personal identifiers and host-specific mount/home paths, check all evidence-standard links resolve to the nested skill package, check workspace recipes use the resolver without `/tmp` fallback, and run `git diff --check`. No runtime test is applicable to this documentation-only change.

## Mock exemption

This change contains no product behavior, UI, or design implementation; visual mocks and runtime smoke evidence are not applicable.

## Risks

The existing test evidence helper may not yet support configured Scratch. The skill text therefore requires agents to stop and report that gap rather than inventing an option or falling back to `/tmp`; changing helper behavior is outside this documentation-only scope.
