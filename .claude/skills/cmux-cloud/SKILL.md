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

This contract governs exporting reusable skill packages into this shared
catalog. It applies to this package and sibling packages exported in the same
change.

### Outcome

The catalog contains three discoverable, self-contained skills for visual
design comparison, interface exploration, and safe cmux Cloud work on existing
machines. An export changes agent instructions only; it does not install or
activate the skill on another host.

### Non-goals

- Do not change application code, runtime behavior, services, or user data.
- Do not add scripts, tests, CI, installer changes, dependencies, or packages
  beyond the explicitly selected skills.
- Do not export every home skill by default. Catalog publication is opt-in:
  export only the candidates the user explicitly selected for the current
  request.
- Do not make skill invocation explicit-only as a side effect of publication;
  preserve the target catalog's normal discovery behavior.
- Do not copy private machine identifiers, personal paths, account details,
  browser profiles, secrets, or credential-transfer procedures.

### Acceptance

- Each exported package is a directory named for its skill and has one
  `SKILL.md` with matching `name` and a concise, discriminating `description`.
- The package can be discovered through the catalog installer without adding
  a machine-specific configuration or host-only dependency.
- Instructions remain useful across supported runtimes; name a required tool
  only when its current availability can be checked and provide a bounded
  fallback when appropriate.
- Delegation is optional and bounded by task independence, authorization, and
  available resources; it is never a fixed agent-count requirement.
- Cloud examples use existing authorized machines. Provisioning, paid-plan
  changes, resuming billable resources, and destructive operations retain their
  separate user-authorization boundaries.
- Keep the full change limited to the explicitly selected Markdown skill
  files; place this contract within one of those files.

### User story

As a maintainer of the shared skill catalog, when I explicitly select reusable
skills for export, I want concise, portable instructions that preserve their
useful methods and current safety boundaries, so another supported agent can
discover and apply them without inheriting private host configuration.

### Proof plan

Before editing, record each canonical source path, source hash, dependency, and
planned adaptation. After editing, validate frontmatter and skill names, run
the catalog's package-shape checks, verify installer discovery without
installing into a live home, and inspect the complete base-to-head diff.
Search changed content for personal identifiers, machine paths, credentials,
and unreviewed host-specific assumptions. Recompute hashes and report the
exact commit and check results. Do not infer successful publication or live
activation from a local package check.

### Mock exemption

The exported artifacts are Markdown instructions and do not change a rendered
product interface. A product UI mock, browser capture, or visual comparison is
therefore not acceptance evidence for this package change. When the
design-fidelity skill is used for a UI implementation, its own approved mock
and rendered implementation are required inputs to that separate task.

### Risks

Vendor command syntax and resource limits can drift; verify them with installed
help before relying on them. A source skill may contain private settings or
runtime assumptions that look reusable but are not. Review those dependencies
before export, remove personal or credential-bearing recipes, and keep
catalog publication explicitly selected. Package validation proves structure
and discovery only; it does not prove a particular runtime installed the
skill or that a future task's service, browser, or visual behavior works.
