# Linux scheduling for the PR workflow usage collector

## Outcome

Stage a systemd user service and timer with the pinned collector release on Linux. Enable the hourly job only when the operator passes `--activate`.

## Non-goals

This change covers installer behavior. Live service activation and changes to the dashboard, collector logic, or publishing destinations are outside its scope.

## Acceptance

- A default install stages both units under the pinned release and makes zero calls to `systemctl`.
- Explicit activation installs both units in the user's systemd directory, reloads the user manager, and enables the timer for :37 past each hour.
- An active or enabled timer requires `--replace`. Replacement stops and disables the old timer before enabling the new one.
- Existing macOS launchd and manual cron output continue to work. Linux unit arguments use the existing systemd escaping.

## User story

A Linux operator can prepare the same usage collector release before deciding when it should begin running. Previously the installer printed the systemd unit text for manual setup.

## Proof plan

Run the new Linux cases with the candidate tests against the base installer and the candidate installer. Capture the expected failures on the base and the passing results on the candidate. Run the installer regression suite with temporary home directories and stubbed service commands.

## Visual evidence

This change affects a shell installer and systemd unit files. There is no graphical surface.

## Risk

Activation changes the user's timer state. Stubbed tests verify destinations, arguments, and command order. Actual scheduling by a live systemd user manager remains outside this verification.
