# Fake-home subprocess PATH portability

**Related PR:** [PR #611](https://github.com/jleechanorg/jleechan-skills/pull/611)

## Outcome

Subprocess tests that replace `HOME` can keep system tools reachable while placing the host's `~/.local/bin` wrappers after preferred commands. Relative, empty, symlinked, and absolute PATH entries are classified using the child working directory. An absent PATH remains absent for callers that do not need to add command directories; test fixtures that invoke system tools use the platform default search path.

## Non-goals

- Change application runtime behavior or production PATH handling.
- Repair every test that replaces `HOME`; this change covers the shared helper and its three current callers.
- Diagnose all failures in the Linux repository-wide unit suite.
- Use a real browser, account, model provider, or application service.

## Acceptance

- The shared helper reorders host `.local/bin` entries correctly for absolute, relative, empty, and symlinked entries resolved from the child cwd.
- The helper preserves an absent PATH; the coordinator installer caller omits missing variables, and the integration fixture adds `os.defpath` when its Git operations require a command path.
- The Dot probe's default Node fallback is selected from the sanitized child PATH when neither an explicit `DOT_NODE` nor the host's pinned Node 22 executable is available.
- The four focused unittest modules pass in a Linux environment, and GitHub `contract-tests` passes at the PR head.

## User story

No user-facing change — this PR changes only subprocess test setup and its regression coverage.

## Proof plan

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_subprocess_environment tests.test_coordinator_naming tests.test_dot_transport_session_probe tests.test_integrate_cleanup` in a Linux environment. Record the exact head and base, runtime versions, test names and result, ordered PATH with home prefixes redacted, and `command -v rm` with its home prefix redacted. Verify the published bundle's raw downloadable bytes against its manifest and record the GitHub `contract-tests` run at the same head.

## Test doubles and exemption

The target is deterministic test-harness behavior. The tests use temporary repositories, fake `gh` and `node` executables, and a fake Playwright module; these fixtures are the controlled environment needed to test PATH selection. They do not stand in for application services or support any application-runtime claim.

## Risks

The changed tests exercise the named helper and its three callers only. Other fake-home tests and remaining Linux suite failures are outside this PR. The result is limited to the focused unit suite and the GitHub workflow; it does not establish whole-suite health or live application behavior.
