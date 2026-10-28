# Current-host-first routing for `/parallel`

## Outcome and goal
Agents use the current host's measured, task-specific capacity first. They use another already available host only when the current host cannot safely admit more work or another measured constraint makes it ineligible.

## Modification
Update the `/parallel` skill and its host-load-balancing reference so the core rule, decision steps, resource table, examples, quick diagnostic, and config one-liner state current-host-first routing. Keep Mac's existing CPU admission tiers, use workload-specific Linux measurements, and preserve the no-provision/no-VM-wake boundary. Link the installed `lm` and `cc` aliases and identify their canonical Linux-mirror and cmux-Cloud targets.

## Necessity
The current source says to shard across every available machine and choose the host with the most headroom. That can move work from a suitable current host based only on comparative idle CPU, while CPU limits and user-owned machine settings are host-specific.

## Integration proof
The skill points to its adjacent host-load-balancing reference, which owns host measurement and transfer rules. The reference names the installed `~/.claude/skills/lm/SKILL.md` and `~/.claude/skills/cc/SKILL.md` aliases, which dispatch to the canonical Linux-mirror and cmux-Cloud skills; the shared policy adapter retains Mac-specific admission and requires Linux-local measurements. No installer, runtime, credentials, or machine configuration is changed by this source PR.

## Non-goals
No runtime code, automated scheduler, new thresholds for Linux, VM provisioning or wake, paid capacity, mount or service changes, credential transfer, or installation changes. This PR does not change the separate shared home adapters or install skills on either host.

## Acceptance
- When current-host capacity fits the independent work, instructions direct agents to use that host even if a remote host has more idle CPU.
- Remote hosts are eligible only after current-host capacity is full under its measured rules or another measured constraint excludes it.
- At 20% Mac CPU idle with one active heavy lane and no test-suite conflict, another permitted heavy lane stays local; below 10% idle, no new heavy lane starts and another host is considered only after its own capacity is measured.
- CPU-bound transfer occurs only when the current host's workload-specific admission rule refuses the next lane; Linux uses the same measured-bound rule without adding a new fixed threshold.
- Mac retains the `<25%` and `<10%` CPU tiers; Linux retains its own workload-specific measurements.
- The current-host preference appears in the core law, decision procedure, one-line configuration form, capacity table, quick diagnostic, and pytest guidance.
- Existing no-provision/no-resume and task-ownership rules remain effective.

## User story
An agent starting a task continues on a suitable, already-authorized current machine. If that host cannot safely admit more work, it measures an alternative, transfers only when the alternative is eligible, and preserves one writer. No player-facing behavior or product UI changes.

## Proof plan
Inspect the full source diff, run structural and semantic text canaries for a 20%-idle Mac with a permitted lane, a below-10%-idle Mac refusing new heavy work, Linux's measured admission decision, cloud restrictions, and reference resolution; run `git diff --check` and the source skill-inventory scan. Portable-manifest verification is separate and does not prove the edited canonical files.

## Mock exemption
This PR changes Markdown agent instructions only. Application runtime behavior and product mocks are inapplicable.

## Risk
Overly broad wording could reduce safe parallelism or move work prematurely. Keep the per-machine concurrency ceiling, route independent work remotely only when the current host's measured rule refuses the next lane or another measured constraint makes it ineligible, and remeasure before heavy batches.
