# Advice cleanup assertion separation

## Outcome

Keep the metadata-mutation regression specific to its healthy path: it expects exit 3, the metadata-change diagnostic, and an empty descendant-cleanup failure receipt. Keep cleanup failure independently covered: an injected unverified-supervision result must produce exit 7, a `codex` failure receipt, and the cleanup-verification diagnostic. The detached-descendant test judges cleanup from the receipt rather than Python API availability.

## Non-goals

- Change the advice runner or production behavior.
- Claim a live reviewer/provider call or an advice approval.
- Resolve or characterize every historical Linux full-suite failure.

## Acceptance

- The healthy hooks-path mutation case requires exit 3 and `descendant_termination_failures == []`.
- The injected unverified-supervision case requires exit 7, `descendant_termination_failures == ["codex"]`, and the exact cleanup-verification diagnostic.
- A timed-out detached-descendant attempt that verifies cleanup must show the child discovered and terminated, no survivors, an empty failure receipt, and exit 0. If cleanup is unverified, it must show exit 7, a `codex` failure receipt, no claim that the child was terminated, and survivor or supervision-error evidence. The attempt remains bounded by its existing elapsed-time assertion.

## User story

No user-facing change — this change strengthens deterministic test expectations only.

## Proof plan

Run the metadata-mutation, injected-unverified-supervision, and detached-descendant unittest cases on Linux Python 3.13.12, with the process `TMPDIR` on Scratch. The three cases passed in 5.326 seconds. The focused 77-test module run before the detached-descendant assertion fix had one failure because the test equated missing pidfd APIs with failed cleanup; the receipt showed verified process-group fallback cleanup. No test run after that focused three-case pass is claimed here.

## Test doubles and exemption

The metadata and forced-failure cases use fake CLI commands and a synthetic unverified-supervision receipt. The detached-descendant case uses a local child process and inspects its receipt. These unit tests do not call a model provider, live reviewer, browser, or application service.

## Risks

The change covers only these three assertions. It does not establish whole-repository unit-suite health or close the historical Linux failure set whose complete raw test list was not found.
