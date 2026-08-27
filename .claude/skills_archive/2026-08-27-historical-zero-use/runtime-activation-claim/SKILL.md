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
4. **Run a probe in a CLEAN subprocess** with NO env override:
   ```bash
   python3 -c "from <module> import <Class>; print(<Class>().enabled)"
   ```
5. **The probe output MUST be `True`** before claiming the feature works.
6. **Quote the probe output verbatim** in the claim.

## Banned patterns

- "Cache works" based on launchd/cron test logs where the launchd env set the activation var.
- "Feature X works" based on a CI run where the env was set via `with mock.patch.dict(...)`.
- "Warmup completed" based on `_init_event.wait()` returning (it is set at init, not at warmup completion).
- "enabled=True" based on reading the source code without running it.

## Common multi-gate features in this repo

| Feature | Activation function | Standard harness probe |
|---------|---------------------|------------------------|
| `WORLDAI_TEST_CACHE` (ServerCacheManager) | `ServerCacheManager().enabled` | `python3 -c "from testing_mcp.lib.llm_response_cache.server_cache import ServerCacheManager; print(ServerCacheManager().enabled)"` |
| FastEmbed classifier warmup | (instance attribute) | check `instance.ready` after init |
| Embed LRU warmup | `embed_cache_warmup.warm_in_background()` | probe with retry until `len(embed_cache) > 0` |
| BQ cache probes | BigQuery query result | `bq query` against live table |

## Worked example — cache activation

**Claim:** "The local cache is working."

**Wrong evidence:** "I ran the launchd test which sets `WORLDAI_TEST_CACHE=read_write` and it passed."

**Correct evidence:**
```
$ python3 -c "from testing_mcp.lib.llm_response_cache.server_cache import ServerCacheManager; print(ServerCacheManager().enabled)"
True
```

In the standard harness startup path (NOT launchd env, NOT pytest). Quote the output.

## Counter-example — false claim

**Claim:** "Cache works."

**Wrong test:** `test_cache_cross_run_savings.py` run with `WORLDAI_TEST_CACHE=read_write` explicitly set in the test harness env. Test PASSED → "cache works."

**Why it's wrong:** The test harness sets the activation var, so `enabled()` returns `True` only inside that test run. In the standard `testing_mcp/` startup path (no env override), `enabled()` returns `False` because `start_local_mcp_server()` never ran (or the env wasn't propagated). The launchd test passes but the standard path is broken — exactly the PR #7810 / #7901 root cause.

**How to fix the wrong test:** Remove the explicit env override from the test. Run with the standard harness env. If the test then FAILS, the cache is NOT working in the standard path.

## Failure class

This skill addresses the **"mislabeled artifact" + "repeated manual fix"** failure class. Same pattern has recurred across:
- PR #7810 (cache-integrity launchd → assumed testing_mcp/ also works)
- PR #7892 (mock Gemini response shape → claimed stripping verified)
- PR #7901 (one-line fix → agent claimed "all good")
- FastEmbed warmup (init_event set at init, /health 200 doesn't expose classifier state)

## Connection to other skills

- `evidence-standards` — for PR-level evidence requirements
- `bypass-claims` — for circular provenance detection
- `verification-before-completion` — for broader verification patterns

## How to apply

If you're about to type "X is working" or "cache enabled" or "warmup completed":
1. Stop. Run the probe.
2. Paste the probe output.
3. Only then write the claim.
