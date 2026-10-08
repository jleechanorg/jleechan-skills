# PR 469 conflict resolution

Exact integration inputs:

- PR head: `297d24ad9496ef0067ef2e4a30196fe5ef8628e9`
- Base (`main`): `ae97ab14a8268e511fa374bc13fb63e25b6b65a2`
- Merge base: `5713443ff140cc1d4afce074288c7bfc46fd5207`

All three conflicts were textual add/add conflicts caused by PR 469 and merged
PR 467 independently introducing the `dot` skill after the common merge base.
There were no generated-file or checksum conflicts.

## `.claude/skills/dot/SKILL.md`

**Conflict type:** Documentation and user-visible backend/workflow contract

**Risk level:** Medium

**Original conflict shape:**

```text
PR head:
Headless Chrome only; interactive login, structured limit rotation,
non-destructive lock handling, and whole-message draft matching.
Current main:
Headless Chrome or Aside; dynamic accounts and bidirectional host bridging.
```

**Resolution:** Kept the PR 469 contract. It retains main's dynamic account
configuration and persistent per-account profiles while intentionally retiring
Aside and documenting the PR's login, auth-session, rotation, exit-code, and
concurrency behavior.

**Reasoning:** Retiring Aside and strengthening login/rotation/concurrency are
explicit user-visible goals of PR 469. Restoring main's older backend contract
would silently undo the feature under review.

## `.claude/skills/dot/scripts/dot.sh`

**Conflict type:** Shell entry point and routing implementation

**Risk level:** Medium

**Original conflict shape:**

```text
PR head:
Chrome-only routing with unified profile resolution, login/auth, structured
usage-limit rotation, and Linux-to-Mac fallback.
Current main:
Config-selected Chrome/Aside routing with bidirectional host forwarding.
```

**Resolution:** Kept the PR 469 implementation. It extends main's account and
machine-local configuration model, but applies the PR's deliberate Chrome-only
backend, explicit login recovery, portable timeout handling, and clean-profile
account rotation.

**Reasoning:** The removed Aside and Mac-to-Linux paths conflict with the PR's
declared Chrome-only behavior. Main's portable account/configuration contract
remains present in the resolved implementation.

## `.claude/skills/dot/scripts/dot_chrome.mjs`

**Conflict type:** Browser automation, authentication, and shared-profile safety

**Risk level:** Medium

**Original conflict shape:**

```text
PR head:
In-page auth checks, live-lock waiting without process termination, safer
profile seeding, whole-message matching, and a cancellable 120-second bound.
Current main:
Persistent profiles with orphan-process cleanup, relaxed prefix matching, and
the earlier page-readiness flow.
```

**Resolution:** Kept the PR 469 implementation, including main's dynamic
profile discovery and persistent account isolation plus the PR's stronger auth,
locking, matching, and timeout guarantees.

**Reasoning:** Main's process termination and prefix matching are precisely the
concurrency hazards PR 469 is intended to remove. The resolved code preserves
the current-base profile architecture without weakening the PR safety contract.
