---
name: cmux-cloud
description: Use cmux Cloud to inspect or run work on an existing remote machine, monitor durable jobs, transfer task files, or balance work across available compute.
---

# cmux Cloud machines

Use the installed cmux CLI and its current vendor guidance (`cmux cloud --skill`)
for exact syntax. Commands and limits can change; check the relevant
`cmux cloud <verb> --help` whenever a flag, limit, or exit behavior matters.

## Inspect before routing

Start with read-only machine inventory, authentication status, and routing
information. Use the vendor's inventory command as the authority for which
machines exist and their current capacity. Prefer an already-running suitable
machine and pin its identifier on remote execution. A router may provision a
machine for an unrecognized path, so inspect its plan before running it.

Do not provision machines, increase a paid plan, or trigger other billable
resources unless the user authorized that action. Pause or resume a machine only
when the user authorized it and its owner and task impact are clear. Deleting a
machine is destructive and always requires explicit user approval, even when the
task created it. Never delete a machine that the task did not create. Pausing may
stop compute charges while retaining its disk; confirm current semantics with
vendor help.

## Run and observe work

Use a short remote-exec command for a bounded probe. For scripts whose next
steps depend on their exit status, use the command that propagates the remote
exit code; some versions of a probe command report only a generic local failure.
Verify these behaviors in the installed CLI before relying on them.

For long work, start a durable remote terminal or job. Record its identifier,
wait for completion, and read its output before reporting a result. A finished
wait means the process ended; it does not mean the command passed. Keep the
remote work directory and transferred files scoped to the task.

Before transferring files, check current size limits and default excludes. Avoid
copying credentials, browser profiles, or unrelated repository state. Pulling a
directory may require archiving it on the remote machine first; use the
documented transfer mechanism and verify the resulting file.

## Browser and credentials

Use only the task-authorized isolated browser and authentication route. Keep
personal browser profiles separate from automation profiles. Some provider
consent or multi-factor steps require a human gesture; report that exact
dependency rather than automating around it.

Never export, copy, print, or place credentials in task files or command-line
arguments. Use an existing authorized credential store or supported identity
flow. Creating or rotating credentials and granting new access require the
appropriate authorization.

## Balance work across machines

Compare current available CPU and memory on the candidate hosts, then route the
next independent heavy job to the host with more capacity. Re-measure before
starting another heavy batch. Keep shared-resource and simulator exclusivity
separate from host scheduling: a capacity note does not reserve an account,
service, campaign, or device. Do not start competing builds on the same
simulator device and app bundle without coordinating its active operator.

Prefer fewer active machines when the current work fits, because provisioned
machines may continue consuming resources while idle. Check live pool limits
before starting work and pause task-owned idle machines when authorized and
safe.

## Verify before reporting

- Bind each result to the machine, command, and process/job identifier used.
- Read both the completion status and captured output.
- Report the actual remote exit status and any missing verification layer.
- Recheck inventory before claiming a machine was paused, removed, or available.

## Portable skill contract

This seven-element specification covers the three skill packages in this
change.

- **Outcome:** The catalog gains reusable design-comparison,
  interface-exploration, and cmux Cloud skills.
- **Non-goals:** No application runtime, live machine, account, profile, or
  credential is changed; no scripts or unrelated packages are added.
- **Acceptance:** All three packages have valid frontmatter, are discoverable,
  omit personal host data, and retain bounded delegation and resource rules.
- **User story:** As a catalog user, I can find these skills when their tasks
  apply and use them without inheriting private host configuration.
- **Proof plan:** Record source hashes and dependencies, validate each package,
  verify read-only installer discovery, scan for personal data, and inspect the
  complete base-to-head diff.
- **Mock exemption:** This instruction-only change does not alter product UI,
  so screenshots and runtime video do not apply. The design-fidelity skill
  still requires the approved mock when used for UI implementation.
- **Risks:** Vendor command behavior can drift, and local discovery checks do
  not prove installation or runtime success on another host.
