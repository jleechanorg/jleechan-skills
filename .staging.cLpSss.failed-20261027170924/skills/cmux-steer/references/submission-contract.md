# Targeted submission and evidence

Use after resolving an authorized target with the cmux-steer workflow. The
contract applies to cmux-goal's composer fallback as well. Validate these
commands against the installed CLI; these are retained source contracts, not
an assertion that every version implements them.

## Separate typing from submission

`cmux send` types text; it does not press Enter. Build the text as one literal
argument using a supported process-argument API, or safely quote a shell
variable. Never interpolate an untrusted title, path, or prompt into shell
source or hand-built JSON.

```bash
# WS_REF and SURFACE_REF are freshly resolved; TEXT is the approved payload.
cmux send --workspace "$WS_REF" --surface "$SURFACE_REF" "$TEXT"
cmux send-key --workspace "$WS_REF" --surface "$SURFACE_REF" enter
```

Inspect the send result before continuing. If it clearly failed without
typing, diagnose the failure. If its result is uncertain, inspect the target
before sending Enter or repeating text. A successful response proves only
socket acceptance, not that the intended program consumed the input.

After Enter, allow the target a brief opportunity to respond (the source
workflow used roughly 5–15 seconds). Use a supported wait and then read the
same target through the routing checks in cmux-steer. Where the installed
build has independently verified explicit-target capture support, the retained
source form is:

```bash
cmux capture-pane --workspace "$WS_REF" --surface "$SURFACE_REF" --lines 25
```

Do not rely on this form to bypass an unverified read-routing problem. If
focus-then-read is needed, apply that workflow's navigation safeguards.

## What counts as evidence

- **Submitted:** a response tied to the new payload, an unambiguous new turn,
  or direct persisted state showing the requested builtin took effect.
- **Working:** a new processing indicator can corroborate consumption when
  it began after this submission and is attributable to this payload. An old
  or unrelated spinner is not proof, and no spinner alone proves completion.
- **Not submitted:** the complete intended text is visibly still in the
  untouched composer and has not been consumed.
- **Unverified/blocked:** target identity, input state, or post-send routing is
  uncertain. Report that uncertainty rather than retyping the payload.

## Bounded recovery

If the text is demonstrably still in the intended input, there is no new
response, and no intervening draft appeared, one additional targeted Enter
is allowed within the existing send authorization. Re-read afterward.
Do not re-send the text when consumption is ambiguous. If a retry is still
unconfirmed, stop sending and report the exact observed blocker.

Never blindly press Enter on a shell prompt or approval dialog. Never replay
a command that could duplicate a transaction, publication, commit, process
launch, or external message. Re-entering any payload requires evidence the
first typing did not land and that the same action remains authorized.

## Privacy-preserving receipt

Keep the receipt small and sufficient to distinguish typed from submitted:
target window/workspace/surface, payload purpose or non-sensitive excerpt,
Enter sent or not, observed matching response, and verification status.
Retain an exact payload in private task-local evidence only when needed and
permitted. There is no blanket obligation to copy the full terminal or other
agent's conversation to a user-visible message or outside service.
