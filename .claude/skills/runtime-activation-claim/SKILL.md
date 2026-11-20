---
name: runtime-activation-claim
description: Use when making any "X is enabled" / "feature X works" / "cache works" claim in a running session — requires runtime probe output from the standard harness startup path, NOT a launchd/cron test that explicitly sets the activation env var.
---

# Runtime Activation Claim

## The rule

Before any claim of "feature X is working" / "cache enabled" / "warmup completed" / "feature flag is on":

1. **Read the activation function source** — find `enabled()`, `is_ready()`, `is_active()`, or equivalent property on the relevant class.
2. **Identify every gate** the function checks (env vars, sys.modules probes, config flags, runtime state).
3. **For each gate, state what it requires** — name the env var, expected value, runtime precondition.
4. **Run the active repository's supported probe** under the standard startup
   configuration, with no temporary setting that would force success.
5. **Verify that the observed result supports the specific claim.** An expected
   disabled result proves disabled, not enabled. If the probe contradicts or
   cannot answer the claim, report that directly. A separate functional claim
   needs a probe that exercises the feature.
6. **Quote the probe output verbatim** in the claim.

## Banned patterns

- "Cache works" based on launchd/cron test logs where the launchd env set the activation var.
- "Feature X works" based on a CI run where the env was set via `with mock.patch.dict(...)`.
- "Warmup completed" based on `_init_event.wait()` returning (it is set at init, not at warmup completion).
- "enabled=True" based on reading the source code without running it.

## Example: cache activation

Run the documented probe on the same startup path the user or application
uses, without forcing the cache on. Check an actual cache read or hit if the
claim is that the cache works rather than merely being enabled. A status
flag, an initialization event, or a successful health response alone does
not establish that warmup finished or that requests used the feature.

## Connection to other skills

- `evidence-standards` — for PR-level evidence requirements
- `bypass-claims` — for circular provenance detection
- `verification-before-completion` — for broader verification patterns

## How to apply

If you're about to type "X is working" or "cache enabled" or "warmup completed":
1. Stop. Run the probe.
2. Paste the probe output.
3. Only then write the claim.
