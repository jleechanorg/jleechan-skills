# Shared history retrieval and focused skill loading

## Outcome

Use the existing history helper for supported conversation stores. Keep ordinary
history lookup, resume briefings, and saved-memory searches as distinct entry
points with one shared retrieval owner and conditional detailed instructions.

## Non-goals

No new retrieval framework, provider implementation, global policy, saved model
default, live installation, or merge. The existing title and preview bounds stay
unchanged. Lifecycle and review-owner changes belong to a separate package.

## Acceptance

- History, resume, and memory aliases resolve to their canonical skills from an
  isolated installation, including the installed helper and referenced files.
- Source admission precedes every read; cwd priority is not access isolation.
  Results retain provenance, bounded read-more paths, requested larger previews,
  Pi support, and current-authority checks.
- Supported provider retrieval is implemented by the existing helper. Specialized
  recovery stays available on demand, with read-only Git inspection and the
  existing explicit/configured/current-root selection behavior.
- Memory and harness optimization inspect catalog descriptions before opening
  relevant skill bodies. Explicit full audits and mandatory closure retain their
  scope.

## User story

When a user asks about prior work, the agent currently encounters several
overlapping search procedures. After this change, it selects the relevant
workflow, searches permitted sources, and expands selected evidence when needed.

## Proof plan

Run existing history and installer tests, execute the relocated Git recovery
example through its existing tests, verify links and frontmatter, and install
into an isolated temporary home. Review the complete source diff and scenarios
for denied sources, larger previews, missing helpers, stale approvals, resume
aliases, specialized recovery, and explicit full audits.

## Mock exemption

No application UI changes. Source, executable-example, and installation evidence
cover the claims; screenshots are not needed.

## Risk

Consolidation can remove a useful recovery path or conceal a source-scope limit.
Conditional references retain those paths, and tests continue to execute the
recovery example. Installed hosts remain unchanged until separately synchronized
from the reviewed source with live-only changes reconciled.
