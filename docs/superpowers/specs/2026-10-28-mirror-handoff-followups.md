# Reliable mirror handoff startup

## Outcome

The Linux and Mac mirror skills reject missing handoff context before sending
it over SSH, preserve Pi's context as prompt text, and report `READY` only after
the launched pane survives a short settle check and no Pi project-trust prompt
is visible. Mirrored checkouts and generated agent output resolve to separate
directories under the target host's configured Scratch volume; a registered
unavailable volume or the resolver's unconfigured `/tmp` fallback fails closed.
The launched CLI receives those Scratch variables explicitly in its own
process environment, including a scoped `TMPDIR`; existing tmux servers do not
control the canary's Scratch environment. Session names include the repository
identity, existing sessions are verified before any checkout mutation, and all
derived paths pass canonical containment checks.

## Non-goals

Do not add CLI support, change the existing permission flags, answer Pi's
project-trust prompt, alter git/tmux transport, or claim that `READY` means the
agent received or acted on the handoff context. Do not move tool-owned auth,
transcripts, credentials, or tmux state into Scratch, and do not invent a new
lease protocol when the existing `diskm` interfaces do not provide one for a
fresh mirror clone.

## Acceptance

- Empty context fails locally before push and fails remotely before CLI
  validation; its encoded SSH argument remains nonempty so later arguments
  retain their positions.
- A context beginning with `@` is passed to Pi as message text, not a file
  attachment.
- A non-Claude launcher checks `pane_dead`, waits briefly, and checks it again;
  an early exit cannot produce `READY`.
- A visible Pi `Trust project folder?` prompt produces `FAILED` and leaves the
  pane available for inspection.
- `READY` reports pane liveness only. Fresh agent response remains separate
  proof of handoff receipt.
- The target resolves its canonical Scratch root with `diskm scratch-dir` and
  refuses both registered-unavailable Scratch and the resolver's unconfigured
  `/tmp` fallback; it never returns to `$HOME/mirror`.
- The mirrored checkout is placed under
  `Scratch/mirrors/<repo-key>/<branch-key>/<relative-path>`, while generated agent output
  and disposable test files use the separate
  `Scratch/mirror-output/<repo-key>/<branch-key>` directory. `READY` and
  `RESUMED` include that output path.
- The existing cleanup contract remains authoritative: this change does not
  claim a managed producer lease for the fresh clone. `diskm scratch-new`
  remains the lease-bearing interface where its existing `build`/`evidence`
  allocation contract applies; mirror routing must not pretend that
  `scratch-dir` registered a lease.
- The launched CLI receives `DISKM_SCRATCH`, `CLAUDE_CODE_TMPDIR`,
  `PYTEST_DEBUG_TEMPROOT`, and `TMPDIR` through a scoped `env` prefix on the
  process command; no global environment or unrelated tmux session is changed.
- Before any clone, fetch, checkout, pull, or output-directory creation, an
  existing exact tmux session is checked for its target path, origin, and
  branch. Its session key includes both the repository key and branch key; a
  mismatch or a session that appears during the check fails closed without
  touching the live checkout.
- `diskm scratch-dir <subpath>` is used for target and output allocation; its
  existing realpath/commonpath containment check runs before and after mkdir.
  An existing symlink escape fails closed before clone or write, without a
  duplicate inline containment helper.
- A pre-existing target with tracked or untracked changes is preserved, and a
  local branch that is ahead of or diverged from `origin/$BRANCH` fails closed;
  a behind target may fast-forward only when the final HEAD exactly equals the
  fetched remote branch.

## User story

No product-facing change. Before, a mirror handoff could reject empty context
under the wrong error, treat an `@`-leading Pi brief as a file, report a trust
prompt or fast process exit as ready, or place its checkout and generated
output under the target HOME mirror namespace. After, those states fail
clearly, readiness reports only the pane state it actually checks, and the
checkout/output paths are isolated under configured Scratch.

## Proof plan

Inspect the complete base-to-head diff and both mirrored launcher blocks. Run
`bash -n` on every fenced bash block; use the installed Pi parser to compare a
raw `@` argument with the prefixed message; round-trip empty and nonempty
context through the sentinel encoding; verify the trust marker; and simulate a
pane that exits between liveness probes. Verify the Scratch resolver's
configured, registered-unavailable, and unconfigured-fallback outcomes, the
two stable path namespaces, and the exported Scratch variables. Review the
result against the four reported failure cases and the Scratch routing
contract. Exercise controlled existing-session, cross-repository same-branch,
dirty/ahead target, untracked target, tmux-server environment,
unconfigured/unavailable Scratch, and symlink-escape cases. No provider call or
product-runtime test is needed.

## Mock

No product mock applies. The pane-exit case uses a local stub to test the
readiness branch; Pi argument parsing is checked with the installed CLI parser.

## Risk

The settle check cannot prove that an agent read or answered the prompt, and a
trust marker can change with Pi versions. The instructions state this limit,
fail closed on the installed prompt marker, and require separate response proof.
`diskm scratch-dir` resolves a root but is not a producer-lease allocator. The
existing `scratch-new --kind scratch` contract creates linked worktrees under
the standard worktree root, while `scratch-new --kind build|evidence` creates
leased Scratch directories for its existing repo-scoped allocation flow; this
mirror clone is therefore intentionally not reported as lease-managed. The
current scratch sweepers default to `/tmp`, per-user temp, and configured
project roots rather than mounted Scratch volumes, and their C14/live-cwd/open-
file checks remain the protection boundary if an operator explicitly adds a
Scratch root to a cleanup scope. A future cleanup policy that recursively
targets `Scratch/mirrors` without those checks would be a merge-blocking P0;
this specification does not authorize such a policy change. The explicit
process environment and pre-mutation session checks close the three source
review blockers; live acceptance must still observe the pane environment and
prove the target/output paths on both hosts.

## File justification

GOAL: close the four launcher failures recorded in `bd-kw6`.
MODIFICATION: update the two mirror skill launch blocks and add this required
specification.
NECESSITY: an empty SSH argument shifts the later CLI value; Pi reserves
`@`-leading arguments for files; a pane may exit or stop at a trust prompt
after `tmux new-session` returns success; and mirror checkouts/output must not
consume the host HOME filesystem or claim a lease that the existing CLI did not
create. Existing tmux-server environment inheritance, cross-repository session
collisions, and lexical-only path construction would otherwise break the
Scratch contract despite passing a source-only syntax check.
INTEGRATION PROOF: both skills share the same context, liveness, prompt and
READY contracts; syntax and behavioral canaries cover those paths.
