---
name: fix-completion-deploy
description: Use when a persistent repository, tool, configuration, automation, launcher, wrapper, or installed CLI fix could remain only in a working tree, topic branch, or one machine's live state.
---

# Fix completion and portable deployment

## Core invariant

A persistent fix is not complete while its source of truth exists only in a
working tree, local commit, unmerged topic branch, or one machine's live
configuration.

## Required finish line

1. Identify the owning Git repository before making a persistent change. If
   the live file is generated or machine-local, locate its tracked template,
   installer, migration, or backup source. If no owner exists, establish an
   appropriate tracked owner instead of treating the local patch as durable.
2. Keep secrets and runtime state local, but Git-track enough non-secret source
   and installation logic to reproduce the fix on another machine.
3. Test, commit with required provenance, push, and open or update the PR.
4. When the user asks for `origin/main`, portability, or full completion,
   finish the repository's review gates, merge normally, and verify the remote
   `refs/heads/main` contains the fix. A pushed PR branch is not equivalent.
5. Deploy from the tracked revision. Reinstall packages, sync generated trees,
   restart or reload consumers when required, then probe the actual runtime.
6. Report the owning repository, PR, remote-main commit URL, deployment proof,
   and any intentional machine-local exceptions.

Fail closed when ownership, merge, or deployment cannot be completed: state
the exact blocker, create or keep a tracking bead open, and do not call the
local patch finished.
