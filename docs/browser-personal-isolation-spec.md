# Personal browser isolation

## Outcome

Browser skills direct automation to an agent-owned browser and leave the user's
personal Chrome window, tabs, profile, cookies, and login state untouched.

## Non-goals

No browser launcher, service, credential, profile, or executable changes. These
instructions do not establish the cause of a past Chrome exit or enforce isolation
mechanically in browser tools.

## Acceptance

- All seven changed browser skill entry points apply the canonical isolation rule.
- Attachments require browser/profile and task-tab ownership verification.
- Personal cookie sources, automatic GUI recovery, continuous relaunch, and broad
  shared-browser cleanup are excluded.
- Headless remains the default. An explicit current-thread request may use a
  separate, verified task-owned headed browser/profile. Retire conflicting
  instructions that permit personal/default-browser use, spontaneous desktop-app
  launch or recovery, manual login or credential capture, cookie copying outside the one
  explicitly authorized agent-owned-source transfer, and direct API requests
  using copied browser credentials.
- Linux updates preserve unrelated host guidance and verify file hashes after transfer.

## User stories

Before: browser routing and recovery recipes could select personal profiles or
shared windows. After: an agent chooses an owned background tab or isolated
headless Chromium and cleans up only resources created by its task.

## Proof plan

Run existing browser contract tests, check whitespace and added-line portability,
review the complete diff, and read back Linux file hashes. Record static checks
separately from runtime focus behavior. Do not launch a browser to validate this
documentation change; a later authorized runtime experiment is separate proof.

## Mock exemption

No product UI changes; a visual mock does not apply.

## Risk

Instructions depend on agents and tools honoring ownership checks. Aside is a GUI
browser, so background behavior must be established before use. Linux-specific
guidance can drift; patch application must reject a changed source hash.
