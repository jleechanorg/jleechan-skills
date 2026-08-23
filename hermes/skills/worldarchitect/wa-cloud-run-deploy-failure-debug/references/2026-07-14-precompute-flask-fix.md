# Mode 8 (PRECOMPUTE_FAILED v2) — post-#8380 evidence & fix recipe

**Authored 2026-07-14.** Complements `references/2026-07-13-precompute-deps-self-hosted-mac.md` (Mode 7 / PR #8380) with the post-merge evidence that PR #8380 v1 was INSUFFICIENT, and the v2 fix landed as [PR #8381](https://github.com/$GITHUB_REPOSITORY/pull/8381).

## The recurring failure (post-#8380 merge, 2026-07-13 ~23:20 UTC)

PR #8380 v1 (the v2 with step-ordering fix) merged at commit `50dff1e4285fcea17ec3de42f930425035e7662f`. The very next push to `main` triggered a fresh dev auto-deploy that ALSO failed at the precompute probe.

Dev auto-deploy run [29292726556](https://github.com/$GITHUB_REPOSITORY/actions/runs/29292726556) (2026-07-13 23:20:07Z):

```
2026-07-13T23:21:00.080Z   Successfully installed annotated-types-0.7.0 anyio-4.14.2 … fastembed-0.8.0 …
2026-07-13T23:21:00.137Z   Successfully installed cachetools-7.1.4 … flask-3.1.3 …
2026-07-13T23:21:08.417Z Successfully installed annotated-types-0.7.0 anyio-4.14.2 attrs-26.1.0 … google-cloud-storage-3.13.0 … jsonschema-4.26.0 … pydantic-2.13.4 … cachetools-7.1.4
…
2026-07-13T23:21:09.116Z WARNING: precompute interpreter failed import probe (fastembed+numpy+google-cloud-storage+mvp_site.agent_prompts)
2026-07-13T23:21:09.586Z ##[error]Process completed with exit code 1.
…
2026-07-13T23:24:35.914Z WARNING: VPYTHON='/home/runner/_work/_tool/Python/3.11.15/arm64/bin/python' set but failed import probe — falling through to PATH lookup
2026-07-13T23:24:36.818Z PRECOMPUTE_FAILED: no interpreter with fastembed+numpy+google-cloud-storage+mvp_site.agent_prompts found; aborting deploy
```

**Two distinct failure points, same root cause:**
1. **Action's `probe-precompute` step:** "WARNING: precompute interpreter failed import probe" — emitted because the probe checked `import mvp_site.agent_prompts` and that import fails in the toolcache Python.
2. **deploy.sh's own probe:** "WARNING: VPYTHON='...' set but failed import probe — falling through to PATH lookup" — same failure mode when the deploy.sh probe runs the same over-strict import against the same toolcache Python.

## The transitive-dep trace (the missed dep)

Local repro confirmed the trace (run from a clean venv with the v1 action's install list — fastembed + numpy + GCS + jsonschema + pydantic + cachetools, NO flask):

```
$ /tmp/repro_precompute/venv/bin/python -c 'import fastembed, numpy, google.cloud.storage'
OK
$ /tmp/repro_precompute/venv/bin/python -c 'import mvp_site.agent_prompts'
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import mvp_site.agent_prompts
  File "$HOME/.worktrees/wa-precompute-deps/$PROJECT_ROOT/agent_prompts.py", line 24, in <module>
    from mvp_site import (
    …<5 lines>…
    )
  File "$HOME/.worktrees/wa-precompute-deps/$PROJECT_ROOT/dice_strategy.py", line 14, in <module>
    from mvp_site.llm_providers import provider_gateway
  File "$HOME/.worktrees/wa-precompute-deps/$PROJECT_ROOT/llm_providers/provider_gateway.py", line 12, in <module>
    from flask import g as flask_g, has_app_context
ModuleNotFoundError: No module named 'flask'
```

**The chain:** `mvp_site.agent_prompts` → `from mvp_site import (...)` (lazy proxies via `$PROJECT_ROOT/__init__.py:_LazyModule`) → eventually triggers import of `mvp_site.dice_strategy` → `from mvp_site.llm_providers import provider_gateway` → `from flask import g, has_app_context` → FAIL.

**Why PR #8380 v1 missed this:** the action's install-deps step lists 6 deps, all of which are the ones the precompute EMBEDDING work needs. The probe was added as an "extra confidence check" that `mvp_site` was importable — but `mvp_site`'s chain has heavy transitive deps (flask, fpdf2, etc.) that nobody noticed were missing because the SCRIPT uses cwd-based path injection (line 35) and lazy imports to avoid loading the heavy chain at import time. The probe was asking for more than the action could ever guarantee.

## The fix (PR #8381) — two-surface

### 1. `setup-precompute-deps` action — add flask to install-deps

```diff
- python -m pip install --no-cache-dir fastembed numpy google-cloud-storage jsonschema pydantic cachetools || true
+ python -m pip install --no-cache-dir fastembed numpy google-cloud-storage jsonschema pydantic cachetools flask || true
```

Why `flask` and not the full `$PROJECT_ROOT/requirements.txt`: `$PROJECT_ROOT/__init__.py` uses lazy-import proxies (`_LazyModule` class) — `from mvp_site import (...)` doesn't actually execute the imports until first attribute access. Only the modules touched during the precompute's import chain are needed at runtime, and the chain transitively touches `flask` via `mvp_site.llm_providers.provider_gateway`. The precompute script does `from mvp_site import intent_classifier, prompt_rag` (line 37) — both are lazy proxies and don't trigger the chain until accessed. But `from mvp_site.agent_prompts import _load_instruction_file` (line 38) DOES trigger the chain.

Tradeoff considered: install `pip install -r $PROJECT_ROOT/requirements.txt` would balloon the action from ~30s to ~3+ minutes (Flask-Cors, Flask-Limiter, selenium, playwright, firebase_admin, google-cloud-firestore, fpdf2, etc.). The targeted `flask` install is ~5-10s on cold cache, ~1-2s on warm.

### 2. Reduce the probe to scope-match the install

The action's `probe-precompute` step + `deploy.sh`'s probe both imported `import mvp_site.agent_prompts`. That import can NEVER succeed in the toolcache venv as long as the install list is a focused subset of mvp_site's transitive deps — the action is being asked to validate a script-level import that belongs at script-runtime, not probe-time. Fix: strip `mvp_site` from the probe entirely.

**probe target (post-#8381):** `import fastembed, numpy, google.cloud.storage, jsonschema, pydantic, cachetools, flask`

**deploy.sh change:** store the probe target in a single `_EMBED_PROBE` variable so the VPYTHON branch and the PATH-fallback loop can't drift:

```bash
_EMBED_PROBE='import fastembed, numpy, google.cloud.storage, jsonschema, pydantic, cachetools, flask'
if [ -n "${VPYTHON:-}" ] && [ -x "${VPYTHON}" ]; then
    if "${VPYTHON}" -c "${_EMBED_PROBE}" >/dev/null 2>&1; then
        _EMBED_PY="${VPYTHON}"
    else
        echo "WARNING: VPYTHON='${VPYTHON}' set but failed import probe — falling through to PATH lookup" >&2
    fi
fi
if [ -z "$_EMBED_PY" ]; then
    for _cand in ./vpython vpython python; do
        command -v "$_cand" >/dev/null 2>&1 || continue
        if "$_cand" -c "${_EMBED_PROBE}" >/dev/null 2>&1; then
            _EMBED_PY="$_cand"; break
        fi
    done
fi
```

The `PRECOMPUTE_FAILED:` diagnostic message was updated to match: `fastembed+numpy+google-cloud-storage+jsonschema+pydantic+cachetools` (the 7 deps the probe actually checks).

### 3. Regression tests (5 new, total 20)

`tests/test_precompute_deps_self_hosted.py` got 5 new tests:

| Class | Test | Pins |
|---|---|---|
| `TestInstallDepsPinsFlaskForToolcacheUsability` | `test_install_deps_pip_installs_flask` | action's install-deps now includes flask |
| `TestInstallDepsPinsFlaskForToolcacheUsability` | `test_probe_target_includes_flask` | action's probe checks all 7 deps |
| `TestInstallDepsPinsFlaskForToolcacheUsability` | `test_probe_target_excludes_mvp_site_agent_prompts` | action's probe does NOT check `mvp_site.agent_prompts` |
| `TestDeployShProbeNoMvpSiteAgentPrompts` | `test_deploy_sh_probe_does_not_check_mvp_site_agent_prompts` | deploy.sh's `_EMBED_PROBE` var excludes mvp_site.* |
| `TestDeployShProbeNoMvpSiteAgentPrompts` | `test_deploy_sh_precompute_failed_message_matches_v2_probe` | PRECOMPUTE_FAILED message matches new probe target |

## Live verification (dev auto-deploy run 29294984874, PR #8381 branch)

Triggered manually on the PR branch (`gh workflow run auto-deploy-dev.yml --ref fix/precompute-deploy-sh-pyhonpath-toolcache`). Polled for ~12 min until completion.

**Outcome: success**

Deploy log key signals:
```
2026-07-14T00:07:27.170Z Successfully installed annotated-types-0.7.0 anyio-4.14.2 attrs-26.1.0 blinker-1.9.0 cachetools-7.1.4 … flask-3.1.3 … fastembed-0.8.0 … jsonschema-4.26.0 …
                                                                              ↑ NEW DEP — flask is now in the install list
2026-07-14T00:07:27.921Z Precompute interpreter passed import probe (/home/runner/_work/_tool/Python/3.11.15/x64/bin/python)
2026-07-14T00:09:58.767Z Build completed successfully!
2026-07-14T00:10:03.080Z --- Precomputing prompt embeddings (asset_version idempotent) via /home/runner/_work/_tool/Python/3.11.15/x64/bin/python (batch_size=8) ---
                                                                              ↑ VPYTHON used as the embedding interpreter
2026-07-14T00:10:03.775Z 🧠 CLASSIFIER: Loading embedding model BAAI/bge-small-en-v1.5...
                                                                              ↑ FastEmbed actually loaded + HuggingFace model fetching
```

No `PRECOMPUTE_FAILED` anywhere in the deploy log. No `WARNING: VPYTHON ... failed import probe`.

Post-deploy ground-truth check:
```
$ gcloud run services describe mvp-site-app-dev --region=us-central1 --project=worldarchitecture-ai \
    --format='value(status.latestReadyRevisionName, status.latestCreatedRevisionName, metadata.labels.commit-sha-full)'
mvp-site-app-dev-03844-8t2  mvp-site-app-dev-03844-8t2  5e84d19e9a56690ea6cc798fc72b3feb3d062038
                                                                                ↑ matches PR HEAD SHA

$ curl -fsS https://mvp-site-app-dev-i6xf2p72ka-uc.a.run.app/health
{"concurrency":{"max_concurrent_requests":16,"threads":16,"workers":1},"mcp_client":{"initialized":false},"service":"worldarchitect-ai","status":"healthy","timestamp":"2026-07-14T00:22:13.916309+00:00"}
```

## Local repro recipe (the "prove the red state" pattern)

Before pushing any fix to a deploy-probe bug, prove the failure mode locally with this recipe — saved for future sessions:

```bash
# 1. Simulate the toolcache venv with the proposed install list
REPRO=/tmp/repro_precompute
rm -rf $REPRO && mkdir -p $REPRO && cd $REPRO
python3 -m venv venv
# pip-install the SAME list the action installs
venv/bin/pip install --quiet fastembed numpy google-cloud-storage jsonschema pydantic cachetools flask

# 2. Verify the NEW probe exits 0
REPO=$HOME/.worktrees/wa-precompute-deps   # or wherever the actual repo checkout is
$REPRO/venv/bin/python -c 'import fastembed, numpy, google.cloud.storage, jsonschema, pydantic, cachetools, flask' >/dev/null
echo "probe exit: $?  (0 = pass)"

# 3. Verify the SCRIPT can run via the toolcache Python (cwd-based path injection)
cd $REPO
$REPRO/venv/bin/python scripts/precompute_prompt_embeddings.py --help >/dev/null 2>/tmp/script.err
echo "script exit: $?  (0 = script imports work)"
tail -3 /tmp/script.err

# 4. Verify the mvp_site chain imports work
$REPRO/venv/bin/python -c "
import sys; sys.path.insert(0, '.')
import mvp_site.agent_prompts
import mvp_site.intent_classifier
import mvp_site.prompt_rag
import mvp_site.prompt_embedding_store
print('all 4 critical mvp_site modules import OK')
" 2>&1 | tail -2
```

If step 2 exits non-zero, the install list is wrong (a dep is missing — add it). If step 3 exits non-zero or step 4 hits `ModuleNotFoundError`, your install list doesn't cover the mvp_site chain — re-check `mvp_site.llm_providers`, `mvp_site.game_state`, `mvp_site.memory_utils`, `mvp_site.narrative_response_schema`, etc. (whatever the script's import chain transitively loads).

## The general lesson (Pitfall #14)

> **Probe scope MUST match install scope.** Any time a deploy-time probe tries to validate "the script can run", check what the install step ACTUALLY pip-installs, then probe ONLY that. Script-side imports (which transitively pull in heavy deps not in any install list) belong at script-runtime, not probe-time.

Captured as Pitfall #14 in the umbrella SKILL.md.

## Timeline summary (one-line per artifact)

- 2026-07-13 ~20:00 UTC: PR #8337 merged → first PRECOMPUTE_FAILED (`cc7ec0a06`, run 29280658965). Issue #8379 opened.
- 2026-07-13 ~20:00-22:24 UTC: PR #8380 authored (5 commits including the CodeRabbit step-ordering fix). Merged at `50dff1e4285fcea17ec3de42f930425035e7662f`.
- 2026-07-13 23:20:07 UTC: First deploy post-#8380 still fails (run 29292726556). The v1 fix was insufficient.
- 2026-07-14 00:05 UTC: PR [#8381](https://github.com/$GITHUB_REPOSITORY/pull/8381) opened (5e84d19e9a) with the v2 fix.
- 2026-07-14 00:06 UTC: Manual dev-deploy triggered on PR branch (run 29294984874).
- 2026-07-14 00:18:16 UTC: Deploy completes SUCCESS. Revision `mvp-site-app-dev-03844-8t2` serving PR HEAD.
- 2026-07-14 ~00:23 UTC: `/health` returns HTTP 200. The fix is verified end-to-end.

— written from session 20260713_222600_dev_deploy_failure_repro_8381
