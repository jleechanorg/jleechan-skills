---
name: automation-run
description: Run selected scheduled PR automation jobs using the current package and scheduler owners.
---

# Scheduled Automation Runner

Use the current schedule and the installed automation package's owner
documentation to identify and run the requested jobs. This entry does not
hardcode package, repository, or command names.

## Execution workflow

### Phase 1: Identify the requested jobs

- Resolve the current repository from the invocation or `gh repo view`.
- Inspect the schedule without printing raw crontab lines or credential values.
- Report only the schedule, job identifier, executable, and non-secret
  arguments; preserve all existing entries, including `GITHUB_TOKEN` lines.
- Use the scheduler's current configuration as the source of truth; do not use
  historical examples as a job inventory.

### Phase 2: Run the selected jobs

- Follow the installed package's supported invocation for each selected job.
- Keep credentials in the existing process environment and out of command
  arguments, logs, and terminal output.
- Capture the actual command result and exit status. Do not kill, restart, or
  duplicate unrelated scheduled processes.

### Phase 3: Verify the requested result

- Check the selected job's concrete output or artifact using its owning
  workflow.
- A process start, exit code alone, or generic success message does not prove
  the requested result.
- Report the verified result and any unresolved part as `UNVERIFIED`.
