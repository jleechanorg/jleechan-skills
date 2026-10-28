# Reliable mirror handoff startup

## Outcome

The Linux and Mac mirror skills reject missing handoff context before sending
it over SSH, preserve Pi's context as prompt text, and report `READY` only after
the launched pane survives a short settle check and no Pi project-trust prompt
is visible.

## Non-goals

Do not add CLI support, change the existing permission flags, answer Pi's
project-trust prompt, alter git/tmux transport, or claim that `READY` means the
agent received or acted on the handoff context.

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

## User story

No product-facing change. Before, a mirror handoff could reject empty context
under the wrong error, treat an `@`-leading Pi brief as a file, or report a
trust prompt or fast process exit as ready. After, those states fail clearly,
and readiness reports only the pane state it actually checks.

## Proof plan

Inspect the complete base-to-head diff and both mirrored launcher blocks. Run
`bash -n` on every fenced bash block; use the installed Pi parser to compare a
raw `@` argument with the prefixed message; round-trip empty and nonempty
context through the sentinel encoding; verify the trust marker; and simulate a
pane that exits between liveness probes. Review the result against the four
reported failure cases. No provider call or product-runtime test is needed.

## Mock

No product mock applies. The pane-exit case uses a local stub to test the
readiness branch; Pi argument parsing is checked with the installed CLI parser.

## Risk

The settle check cannot prove that an agent read or answered the prompt, and a
trust marker can change with Pi versions. The instructions state this limit,
fail closed on the installed prompt marker, and require separate response proof.

## File justification

GOAL: close the four launcher failures recorded in `bd-kw6`.
MODIFICATION: update the two mirror skill launch blocks and add this required
specification.
NECESSITY: an empty SSH argument shifts the later CLI value; Pi reserves
`@`-leading arguments for files; and a pane may exit or stop at a trust prompt
after `tmux new-session` returns success.
INTEGRATION PROOF: both skills share the same context, liveness, prompt and
READY contracts; syntax and behavioral canaries cover those paths.
