# Dot Existing-Profile Lock Specification

## Outcome

An existing-profile-only probe ignores only the exact profile-lock helper owned by its ancestor Dot wrapper, so the wrapper does not block its own probe while other profile owners remain blocking.

## Non-goals

- Do not change profile selection, authentication, browser launch policy, or Chrome singleton-lock cleanup.
- Do not claim behavior for a real Dot profile, Chrome session, browser, or authenticated account.
- Do not change player-facing UI or game behavior.

## Acceptance

- The exact ancestor-owned Python lock-holder command is accepted by the fake-profile probe.
- Extra-argument lookalikes, malformed Python command prefixes, non-ancestor lock holders, other processes mentioning the profile, and an existing Chrome SingletonLock remain blocking.
- The launcher tests use temporary fake profiles, a controlled process-table fixture, and a fake Playwright module; they never launch a real browser.

## User story

When the Dot wrapper probes its existing profile while holding its own profile lock, the operator receives an availability result instead of a false busy result. Other profile owners remain blocked. This is an operator CLI behavior; players see no UI change.

## Proof plan

- Tested implementation SHA: `5eab865d60bd2a5cf9cd3d4c589f17c70c681e9a`.
- Command: `env -u BASH_ENV PATH=/usr/bin:/bin:/usr/sbin:/sbin python3 -m unittest tests.test_dot_transport_existing_profile_launch`.
- Result: `Ran 27 tests in 41.607s (OK)`.
- The evidence supports only deterministic fake-profile launcher behavior. It does not support claims about real Dot, Chrome, authentication, or browser sessions.

## Mock or exemption

A real Chrome or Dot profile would introduce account and browser state unrelated to this lock-classification contract. Temporary fake profiles, fake process-table output, and fake Playwright are sufficient to exercise the acceptance cases without real profile or browser access.

## Risk

The process-table recognition is security-sensitive: accepting an unrelated owner could permit an unsafe launch, so ambiguous and malformed entries must continue to block. The shell-wrapper test removes inherited BASH_ENV/ENV and fixes PATH; it does not establish how a real Dot invocation behaves under ambient Bash startup files. Track that separate scope question in Bead bd-co9.
