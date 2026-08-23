---
name: wa-cloud-run-deploy-failure-debug
description: |
  Diagnose Cloud Run deployment failures for Your Project (and any python-on-Cloud-Run service). Also load for RUNTIME failures when the deployed revision is serving and `/health` returns 200 but the user-facing feature is broken — the proxy may be masquerading the upstream provider (e.g. `Cerebras API error: 402` returning OpenRouter's billing wedge). See `references/2026-07-30-proxy-provider-masquerade-402.md` for the recipe. v2.5.0 (2026-07-24) refines the auth-cookie-TTL sibling class — the original v1.0 hypothesis (cookie TTL is the problem; add `max_age` to the proxy) was wrong for the actual iOS symptom; the real root cause is iOS WebKit localStorage eviction of the Firebase Auth persisted user record. See `references/auth-cookie-ttl-class-2026-07-24.md` v1.1.0 and Pitfall #15.
version: 2.7.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [worldarchitect, deploy, cloud-run, devops, gcp, debugging]
    related_skills: [systematic-debugging, drive-pr-to-green, always-pr-never-local-edit, evidence-standards, advice]
---

# WA Cloud Run Deploy Failure Debug

## When to use this skill

Load first when ANY of these fire in the `$GITHUB_REPOSITORY` repo (or any python-on-Cloud-Run project with a similar shape):

- **Email: "❌ FAILED: dev Deployment - mvp-site-app-dev"** sent via the `send-deploy-notification` action (`dawidd6/action-send-mail`).
- **Auto-Deploy Dev workflow** (or any Cloud Run deploy workflow) shows a red gcloud step with output like:
  ```
  ERROR: (gcloud.run.deploy) The user-provided container failed to start
  and listen on the port defined provided by the PORT=8080 environment variable
  within the allocated timeout.
  ```
- **New Cloud Run revision** shows `Ready=False` and `0% traffic` in `gcloud run services describe <service>`.
- **`gh pr checks` shows the deploy step failed** but earlier steps (build, push) passed.
- **User reports "the deploy says it succeeded but the service is broken"** — the visible green hides the real failure.
- **User reports "I have to log in again after a day or two" / "the cookie expires too soon" / "session doesn't last" on the deployed Cloud Run URL** — auth-cookie-TTL class (sibling to deploy failures; same GCP project, same `client_diag` log surface, different fix surface). **The v1.0 hypothesis (cookie TTL is the failure mode; add `max_age` to the proxy) is WRONG for the actual symptom on iOS** — see `references/auth-cookie-ttl-class-2026-07-24.md` v1.1.0. The real root cause is iOS WebKit localStorage eviction of the Firebase Auth persisted user record; the right fix is server-side session restore from the `__session` cookie + silent client re-bootstrap, NOT a cookie TTL override.
- **User reports "the app shows `<provider-X> API error: 402` but the key should be fine" / "the deploy is green but the chat is broken" / "the spinner just shows `<provider-X> error` for every model"** — proxy-chain provider-masquerade class (the runtime sibling). The deployed revision is serving, `/health` returns 200, but the proxy upstream is denying calls. The displayed provider name in the UI may NOT match the actual upstream the proxy hits. See `references/2026-07-30-proxy-provider-masquerade-402.md` for the recipe (SPA-bundle inspection + `curl` repro + `gcloud run services describe` + secret fingerprint cross-reference).
- **PRECOMPUTE_FAILED in the deploy step BEFORE gcloud is called** — pip install in `setup-precompute-deps` succeeded (log shows `Successfully installed ... fastembed-0.8.0 ...`) but `deploy.sh`'s interpreter probe can't find the interpreter on a self-hosted Mac runner. The deploy step exits 1 at the probe, the failure-email step fires, but `gcloud run deploy` never ran. The fix surface is the composite action's `VPYTHON` env-export, NOT the deploy script's revision log. See Mode 7 below.

## The Iron Law of Cloud Run deploy debugging

```
THE BUILD/IMAGE IS NOT THE DEPLOY.
THE REVISION STARTUP LOGS ARE.
```

`gcloud builds submit` exiting 0 only proves the image built and pushed. Cloud Run then pulls that image, creates a NEW revision, runs its `CMD`, and starts probing TCP port 8080 — ANY of those four steps can fail independently of the build. The `Auto-Deploy` workflow only checks the gcloud exit code; a deployment that quietly rolls back the failed revision still counts as "Auto-Deploy Dev ✅" on the commit. Operators reading PR status see green and stop. The failure ships to production quietly the next time someone redeploys from this base.

## The Iron Law 2 — the script-level probe (added 2026-07-13, PR #8380)

```
THE PIP INSTALL CAN SUCCEED WHILE THE DEPLOY SCRIPT PROBE FAILS.
THE COMPOSITE ACTION'S ENV-EXPORT IS THE BRIDGE.
```

The `setup-precompute-deps` action runs `actions/setup-python@v5.0.0` then `pip install fastembed numpy google-cloud-storage jsonschema pydantic cachetools`. The pip install **succeeds** (`Successfully installed ... fastembed-0.8.0 ...` in the GH Actions log). But on a self-hosted Mac runner, the interpreter lands in the GitHub-Actions-hosted toolcache (`$RUNNER_TOOL_CACHE/python/3.11.x/bin/python`) — NOT on `$PATH` and NOT named `python3` (system Python). `deploy.sh`'s interpreter probe iterates `${VPYTHON:-} ./vpython vpython python3` and finds none of those candidates point at the just-installed interpreter. The probe exits 1 at `deploy.sh:466` BEFORE `gcloud run deploy` is invoked. The failure-email step fires. The deploy job looks like a hard failure but the **image build still succeeded** and **earlier sibling runs may have actually deployed the same commit to dev** — the recurring email is masking the fact that the user's PR likely DID ship.

**The bridge:** composite actions that install runtime dependencies MUST export an env var pointing at the interpreter they just installed (e.g. `echo "VPYTHON=$pythonPath" >> $GITHUB_ENV`) AND prepend the interpreter's bin dir to `$GITHUB_PATH`. `deploy.sh` then reads the env var as an absolute path (`[ -x "${VPYTHON}" ]`, not `command -v`) — the absolute path check is the load-bearing part because the toolcache path may not be on `$PATH` at the point the deploy step runs.

**Diagnosing Iron Law 2 vs Iron Law 1:**

| Question | Iron Law 1 (revision start) | Iron Law 2 (script probe) |
|---|---|---|
| Where does it fail? | `gcloud run deploy` step, Cloud Run revision logs | `deploy.sh` step, before `gcloud run deploy` runs |
| What's the symptom? | `latestCreatedRevisionName != latestReadyRevisionName` OR revision logs show `can't open`, `SIGKILL`, `ModuleNotFoundError` | Deploy step exit code 1 with `PRECOMPUTE_FAILED:` in stdout; no new revision created since the failure |
| Is the old revision still serving? | Yes (old revision serves until new one is Ready) | Yes (no new revision was attempted) |
| Does the user's PR show up on the live service? | Possibly — depends on whether a sibling deploy succeeded | **Probably yes** — sibling deploys in the same push window may have shipped it; verify with `gcloud run services describe` + `commit-sha-full` label |
| First-place fix | Revision-log diagnosis (Modes 1-6 below) | Composite-action env-export contract (Mode 7 below) |

## Six failure modes (ordered by observed frequency)

| # | Failure | Symptom in revision logs | First-place fix |
|---|---------|--------------------------|----------------|
| 1a | **`CMD ["gunicorn", ...]` against ENTRYPOINT=python (e.g. Chainguard)** | `/usr/bin/python: can't open file '/app/$PROJECT_ROOT/gunicorn': [Errno 2]` | `ENTRYPOINT []` + `CMD ["python", "-m", "gunicorn", ...]` |
| 1b | **`CMD ["python", "-m", ...]` against ENTRYPOINT=python (the v1 fix trap)** | `/usr/bin/python: can't open file '/app/$PROJECT_ROOT/python': [Errno 2]` | Same: `ENTRYPOINT []` is mandatory to drop the inherited python prefix |
| 2 | **Container exits fast / uncaught exception in `main:create_app()`** | `Container called exit(2)` followed by repeated STARTUP TCP probe failures | Run `python -c "from main import create_app; create_app()"` locally against the same venv |
| 3 | **Health check timeout** | `Default STARTUP TCP probe failed 1 time consecutively` looping for 4+ minutes | Reduce warmup time or extend Cloud Run `--timeout`/`--startup-probe-timeout` |
| 4 | **OOM during init** | `Worker (pid:NNN) was sent SIGKILL! Perhaps out of memory?` | Reduce `--memory` per-instance, or ship a smaller embed cache |
| 5 | **Missing env var / secret** | Container exits before listening; stderr shows `KeyError: ...` or `Missing required env var` | Diff the env-var contract in `deploy.sh` (`ENV_VARS=...`) against what the app actually reads |
| 6 | **Python 3.14 + protobuf C-extension incompatibility** (Chainguard `:latest-dev` ships 3.14) | `TypeError: Metaclasses with custom tp_new are not supported.` in `google._upb._message` during `firebase_admin` → `google.cloud.firestore` import chain | Pin `protobuf>=5.27.0` in `requirements.txt`, OR use `python:3.11-slim`/`python:3.12-slim` base instead of Chainguard `:latest-dev` |
| 7 | **Script-level probe failure (PRECOMPUTE_FAILED family — pre-gcloud)** — composite action installs deps but never exports the interpreter path; downstream `deploy.sh` probe can't find fastembed/numpy/jsonschema in any of its candidate interpreters; deploy exits 1 BEFORE `gcloud run deploy`. Verified 2026-07-13 PR #8380 v1 | Deploy step stdout shows `PRECOMPUTE_FAILED: no interpreter with fastembed+numpy+google-cloud-storage+mvp_site.agent_prompts found; aborting deploy`; pip install in the action step earlier in the same job succeeded (look for `Successfully installed ... jsonschema-X.X.X ... fastembed-X.X.X ...`) | Composite action MUST write `echo "VPYTHON=$pythonPath" >> $GITHUB_ENV` AND `echo "$binDir" >> $GITHUB_PATH` so `deploy.sh`'s `${VPYTHON:-}` candidate resolves. `deploy.sh` MUST read VPYTHON as an absolute path (`[ -x "${VPYTHON}" ]`, not `command -v`). |
| 8 | **Over-strict probe (PRECOMPUTE_FAILED v2 — post-#8380)** — composite action exports VPYTHON + the install puts fastembed into a clean toolcache Python, but the probe in deploy.sh (and the action's probe-precompute step) checks `import mvp_site.agent_prompts` which transitively pulls in flask/fpdf2/etc. — deps the action does NOT install. Probe always fails even when the install succeeded. Verified 2026-07-13 PR #8381 (run 29292726556) → fixed by PR #8381 | Deploy step stdout shows `WARNING: VPYTHON='/home/runner/_work/_tool/Python/3.11.15/x64/bin/python' set but failed import probe — falling through to PATH lookup` followed by `PRECOMPUTE_FAILED`; pip install in the earlier action step already succeeded. The action's `precompute-ready=false` is emitted but does NOT block the deploy (deploy.sh runs its own probe). | **Three-step diagnostic:** (a) confirm the action's `install-deps` `pip install` completed successfully (look for `Successfully installed ... fastembed-0.8.0 ...`); (b) confirm VPYTHON IS set in the env dump of the deploy step (`VPYTHON: /home/runner/_work/_tool/Python/3.11.x/<arch>/bin/python`); (c) trace the import chain failure: if `VPYTHON -c 'import fastembed, ...'` succeeds but `import mvp_site.X` fails, the chain has a transitive dep the action didn't install. **Fix:** (i) `pip install flask` (or whichever transitive dep the chain needs) in `install-deps`; (ii) reduce the probe to ONLY the deps the install step actually pip-installs (NO `import mvp_site.X` in the probe — let the script surface transitive-dep failures as a clear ModuleNotFoundError at runtime); (iii) verify with a local repro venv: `python3 -m venv /tmp/repro && /tmp/repro/bin/pip install <dep-list> && /tmp/repro/bin/python scripts/precompute_prompt_embeddings.py --help` must exit 0 before merging. See Pitfall #14. |
| 9 | **Silent breaking-major-version bumper on unbounded pip pin** — `requirements.txt` pins e.g. `mcp>=1.0.0`, the upstream package publishes a new major (e.g. `mcp 2.0.0`) that **removes public API surface** still decorated in app code (`@server.list_tools()`, `@server.call_tool()`), the image builds cleanly, the revision is created and reported Ready, BUT every gunicorn worker immediately crashes at module-import time with `AttributeError: 'Server' object has no attribute 'list_tools'`. The revision is "Ready" because gunicorn master binds :8080; it's just serving a worker death-restart loop. Cloud Run's proxy returns 503 to every request. Prod is unaffected because its image predates the upstream major release. Verified 2026-07-28 mcp 2.0.0 release / PR #8657 (pin `mcp>=1.0.0,<2.0.0`). | `curl <service>/health` returns **HTTP 503** with body `Service Unavailable`; `gcloud run services describe` shows `latestReadyRevisionName == latestCreatedRevisionName` (i.e. **the revision IS Ready** — disambiguates from Mode 1-6 startup failures); `gcloud logging read resource.type=cloud_run_revision ... severity>=ERROR` shows a recurring worker-loop: `Booting worker with pid: N` → `Worker (pid:N) exited with code 3` → `Shutting down: Master` → `Reason: Worker failed to boot.` every ~10s; the traceback terminates at the app's first use of the removed API (e.g. `$PROJECT_ROOT/mcp_api.py:69 @server.list_tools()`). | **Five-step fix recipe (the "mcp-style silent-major-bump" recipe):** (a) `python3 -m venv /tmp/probe && /tmp/probe/bin/pip install '<package>==<current-used-version>'` and reproduce the missing-attribute error in 3 lines; (b) `pip index versions <package>` to see the latest; (c) repeat the probe with the latest published version to confirm the API surface was removed/replaced (e.g. `mcp 2.0.0`); (d) check the app's decorators/imports against the broken surface (`grep -rnE '@server\\.(list_tools|call_tool|list_resources|read_resource|list_prompts)' $PROJECT_ROOT/`); (e) **either** pin the upper bound (one-line `mcp>=1.0.0,<2.0.0`) to keep current code working, **or** open a follow-up bead to port the call sites to the new major. The pin is the smallest fix; the port is the durable fix. **Verify with the canonical `/es` recipe (reproduces the prod contract):** `docker build -t wa-debug -f $PROJECT_ROOT/Dockerfile .`, run with `TESTING_AUTH_BYPASS=true`, `curl /health` → 200, `docker run --rm <image> pip show <pkg>` to confirm the pinned version is what's actually installed, `grep -c AttributeError` in the boot log → 0. See `references/2026-07-28-silent-mcp-major-bump.md` for the full verified transcript + the three-leg prevention chain (pin, port, CI gate, weekly audit). |
| 10 | **Runtime proxy-chain provider-masquerade** (sibling class — added 2026-07-30, verified on `consensus-ml.ai` → `ai-universe-consulting-v2` in `worldarchitecture-ai`). The deployed revision is serving, `/health` returns 200, but the user-facing feature is broken with `<UI-label> API error: 402` style messages from the proxy. The displayed provider name in the UI may NOT match the actual upstream the proxy hits. The proxy re-emits the upstream's raw error body to the browser unchanged; the browser wraps it with the UI-side model label. Verified on `consensus-ml.ai`: the SPA bundle contained **zero outbound fetches to any LLM provider** (only `/_log` and `/api/contact`), the Cloud Run revision logs showed clean startup with `POST /v1/chat/completions 200 1700` style access lines, but the response body returned OpenRouter's `{"code":402,"metadata":{"limit_source":"openrouter_credits"}}` payload which the SPA re-rendered as `Cerebras API failed: Cerebras API error: 402`. | Cloud Run revision logs show clean startup + standard access lines for `POST /v1/chat/completions`; NO upstream stack traces in the log stream (the error lives in the response body, not the log stream). The `gcloud run services describe` label `commit-sha-full` matches the latest deploy; `/health` returns 200. The 402 / 5xx only appears when hitting the LLM endpoint with the same body the browser sends. | **Five-step recipe:** (a) `curl -fsS https://<site>/assets/index-*.js \| grep -aoE 'fetch\\([^)]{0,300}\\)' \| sort -u` — if no provider hostname appears inside any `fetch(...)`, the LLM call is server-side; (b) `gcloud run services list --project=<each-project>` to find the backend serving the public URL; (c) `curl -X POST https://<site>/v1/chat/completions -d '{"model":"<displayed-model-name>","messages":[…]}'` to reproduce the upstream's actual error body; (d) probe each candidate key against the *real* upstream with the displayed model name — a 404 on `qwen-3-235b-a22b-instruct-2507` doesn't mean the key is dead, it means that model isn't available on that key. The 4 keys the user provided all worked for `gpt-oss-120b` / `gemma-4-31b` / `zai-glm-4.7` but ALL returned `{"code":"model_not_found"}` for the displayed `qwen-3-235b-a22b-instruct-2507`. **Two fix options:** (A) top up the OpenRouter account that owns the stored `sk-or-v1-…` key (smallest, fastest — `visit https://openrouter.ai/settings/credits` is in the error body itself); (B) repoint the proxy to direct Cerebras / another provider — requires editing the deployed image and shipping a new revision. Full recipe, worked transcript, and the 4-key probe matrix in `references/2026-07-30-proxy-provider-masquerade-402.md`. |

**Mode 1a and 1b are the SAME root cause broken in two distinct ways.** A bare `CMD ["gunicorn", ...]` fails immediately because Docker prepends `python` and tries to open `gunicorn` as a file. The "obvious" fix — `CMD ["python", "-m", "gunicorn", ...]` — ALSO fails because Docker still prepends the inherited `python` entrypoint, giving `python python -m gunicorn ...`, and Python tries to open the first arg `python` as a script file. The only correct fix is `ENTRYPOINT [] + CMD ["python", "-m", ...]`. See `references/2026-07-06-entrypoint-override-mandatory.md`.

## The Phase 1 loop (run these in order; don't skip)

### Step 1 — Find the failing revision name

```bash
gh api "repos/$GITHUB_REPOSITORY/actions/runs/<RUN_ID>/jobs" \
  --jq '.jobs[] | select(.conclusion=="failure") | "\(.name) | \(.id)"'
# Note: <RUN_ID> = the `Auto-Deploy Dev` run from the email body or
#   gh run list --workflow="Auto-Deploy Dev" --limit=1
```

The failing job's log URL is in the email and `gh run view <id> --web`.

### Step 2 — Pull the revision logs (not the build logs)

```bash
gcloud logging read \
  'resource.type=cloud_run_revision
   AND resource.labels.service_name=mvp-site-app-dev
   AND timestamp>="<30 min before failure>Z"
   AND timestamp<="<30 min after failure>Z"' \
  --project=worldarchitecture-ai \
  --limit=100 \
  --format=json
```

The build log (in `deploy / deploy` job output) shows the IMAGE BUILD succeeded. The REVISION LOGS (in Cloud Logging, queried above) show the actual container start failure. **Most operators stop at the build log. Don't.**

Filter the JSON for: `can't open`, `ModuleNotFoundError`, `ImportError`, `KeyError`, `SIGKILL`, `exit(2)`, `Traceback`, `ERROR:`.

### Step 3 — Sanity-check "what does the current prod run?"

```bash
gcloud run services describe mvp-site-app-stable \
  --region=us-central1 --project=worldarchitecture-ai --format=json
```

If prod was last deployed BEFORE the breaking change, prod still runs the old image and is not the regression source — dev failed only because it recently redeployed from the same base. This is what happened 2026-07-05: prod's revision was 2026-06-28, base swap was 2026-07-02, dev failed every push since.

### Step 4 — Find the Dockerfile base + diff the base change

```bash
git log --oneline -10 -- $PROJECT_ROOT/Dockerfile
# Then read the commit that last touched $PROJECT_ROOT/Dockerfile
git show <SHA> --stat
```

Look for `FROM ... python ...` line. Chainguard's `:latest-dev` has `ENTRYPOINT=["python"]` (verified). `python:3.11-slim` does NOT have any ENTRYPOINT.

### Step 5 — Verify the fix locally

```bash
# Reproduce the EXACT CMD the Dockerfile ships:
docker build -t wa-debug -f $PROJECT_ROOT/Dockerfile .
docker run --rm -p 8093:8080 -e PORT=8080 -e TESTING_AUTH_BYPASS=true wa-debug

# OR without docker (works in the repo venv):
cd mvp_site && python -m gunicorn -c gunicorn.conf.py main:create_app() \
  --bind 127.0.0.1:8093 --workers 1 --preload
# Then:
curl http://127.0.0.1:8093/health
# Expected: HTTP 200, body JSON {"status":"healthy","service":"worldarchitect-ai",...}
```

**The macOS fork+objc gotcha:** `--preload` is local-mac-only. Production Linux / Cloud Run doesn't see the `objc[pid]: +[NSMutableString initialize] may have been in progress in another thread when fork()` crash; the production `gunicorn.conf.py` defaults (`gthread`, no `--preload`) are unchanged. Use `--preload` for the smoke test ONLY on macOS; document the reason in the PR.

### Step 5.5 — Sanity-check "is the deploy actually live despite the failure?" (added 2026-07-13)

This step applies whenever the failing job's exit code masks the live deploy state — especially Mode 7 (PRECOMPUTE_FAILED, the deploy step exits 1 BEFORE `gcloud run deploy` is invoked) and any sibling-run-cancellation case (Pitfall 10). The recurring failure email is alarming but the user's PR may have shipped hours ago.

```bash
# 1. What's the latest revision actually serving?
gcloud run services describe mvp-site-app-dev \
  --region=us-central1 --project=worldarchitecture-ai \
  --format='value(status.latestReadyRevisionName, status.latestCreatedRevisionName, metadata.labels.commit-sha-full)'

# Expected interpretation:
#   - latestReadyRevisionName == latestCreatedRevisionName AND
#       commit-sha-full == <PR_HEAD_SHA>: the PR is live and healthy
#   - latestReadyRevisionName != latestCreatedRevisionName: a NEW revision was
#       attempted but isn't ready (Mode 1-6 territory — pull revision logs)
#   - commit-sha-full != <PR_HEAD_SHA>: the live revision is from a PRIOR deploy;
#       the failing run failed before it could deploy anything new

# 2. Is /health returning 200 from the live revision?
URL=$(gcloud run services describe mvp-site-app-dev \
  --region=us-central1 --project=worldarchitecture-ai \
  --format='value(status.url)')
curl -fsS "${URL}/health"
# Expected: HTTP 200, body JSON {"status":"healthy","service":"worldarchitect-ai",...}

# 3. (Optional) What time was the current revision created?
gcloud run revisions describe <latestReadyRevisionName> \
  --region=us-central1 --project=worldarchitecture-ai \
  --format='value(metadata.creationTimestamp)'
```

**Decision matrix:**

| Live state vs PR HEAD | Action |
|---|---|
| Live revision == PR HEAD AND /health returns 200 | **Tell the user "your PR is live and healthy — the failing deploy step is a CI infra issue, not your PR's fault."** Diagnose the CI infra failure separately (Mode 7 territory). |
| Live revision == PR HEAD AND /health returns 5xx | Mode 1-6 territory. Pull the revision logs from the current revision (Step 2, but point at the LIVE revision not the failing one). |
| Live revision != PR HEAD | The failing run actually did try to deploy. Compare timestamps to determine whether the live revision was deployed by an earlier sibling run or by an earlier successful push. |
| No new revision since PR HEAD timestamp | The failing run never reached `gcloud run deploy` (Mode 7 or Pitfall 10). The user's PR code may still be live via an earlier deploy — verify with #1. |

**Verified recipe for PR #8380 / cc7ec0a:** `latestReadyRevisionName == latestCreatedRevisionName == mvp-site-app-dev-03841-ftq`, `commit-sha-full=cc7ec0a06a47ddfa497dc2af1ee1b1677b0efe96`, `/health` returns 200 → the user's PR #8337 shipped via a sibling run at 20:00:18 UTC; the 20:00:20 run failed at Mode 7 (PRECOMPUTE_FAILED) and the failure-email step fired. The right user-facing answer was "your PR is fine, this is a CI infra bug" — NOT "we need to roll back."

## The Phase 2 fix recipe (for ENTRYPOINT/CMD mismatches)

**Container CMD before (broken):**
```dockerfile
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:create_app()"]
```

**Container CMD after (correct, against ENTRYPOINT=python base):**
```dockerfile
ENTRYPOINT []
CMD ["python", "-m", "gunicorn", "-c", "gunicorn.conf.py", "main:create_app()"]
```

**Why `ENTRYPOINT []` AND not just `CMD ["python", "-m", ...]`:**

Docker's exec form runs `<ENTRYPOINT> <CMD-as-args>`. If the parent image sets `ENTRYPOINT=["python"]` (Chainguard `cgr.dev/chainguard/python:latest-dev` does), then:

| Dockerfile | What runs in container | Result |
|---|---|---|
| `CMD ["gunicorn", ...]` | `python /app/$PROJECT_ROOT/gunicorn` | `can't open file '/app/$PROJECT_ROOT/gunicorn'` |
| `CMD ["python", "-m", "gunicorn", ...]` | `python python -m gunicorn ...` | `can't open file '/app/$PROJECT_ROOT/python'` (the first arg is interpreted as a script, not as `-m`'s module) |
| `ENTRYPOINT []` + `CMD ["python", "-m", ...]` | `python -m gunicorn ...` | ✅ gunicorn module found via Python's import system, listens on PORT=8080 |

The "obvious" fix in the row 2 — `CMD ["python", "-m", ...]` without ENTRYPOINT override — DOES NOT WORK. This was the trap that PR #8180 (this session's first attempt) fell into. The advisor who reviewed v1 missed the ENTRYPOINT detail. Only the Phase 1 revision-log inspection AFTER merge revealed the same-family failure with a different `can't open file` path. Always set `ENTRYPOINT []` first, THEN exec-form CMD.

**Why this works in the third row:** `ENTRYPOINT []` clears the inherited entrypoint, so the exec-form CMD runs as written. `python -m gunicorn` resolves the module via Python's import system — no `$PATH` lookup, no `/app/$PROJECT_ROOT/<tool>` file interpretation. Portable across `python:3.11-slim` (no ENTRYPOINT — the `[]` is a no-op there), Chainguard, distroless, and any future base.

**Shell form as alternative (NOT preferred):** `CMD python -m gunicorn ...` (no JSON list) also works because shell-form CMD bypasses the ENTRYPOINT wrap. But shell form loses PID 1 signal handling that some bases rely on. Stick with `ENTRYPOINT [] + CMD ["exec-form", ...]`.

**Generalize:** Any time a Dockerfile `CMD` references a tool, ask "what ENTRYPOINT does the parent image set?" If the answer is "python" (Chainguard, many minimal bases), BOTH `CMD ["tool", ...]` AND `CMD ["python", "-m", ...]` break — only `ENTRYPOINT []` + `CMD ["python", "-m", ...]` survives. The fix surface is one line longer than the obvious fix. Don't stop at the obvious fix; ship the override.

## The Phase 2 fix recipe for Mode 7 v2 (composite-action env-export + install/probe scope match, verified PR #8381)

This is the contract that makes the "install then probe" pattern work. A composite action that installs Python deps in step N must produce an env var pointing at the interpreter it just installed, AND its install list must include every dep the downstream probe will check; the deploy step in step N+1 must consume that env var as an absolute path.

**The scope-match invariant (added 2026-07-14, after PR #8380 v1 shipped an over-strict probe):** the probe MUST import ONLY what the install step actually pip-installs. If the probe adds `import mvp_site.X` and X's transitive chain pulls in flask/fpdf2/etc., the probe ALWAYS fails even on a healthy install — because the toolcache venv will never have those transitive deps. The actual `mvp_site.X` import happens inside the precompute script itself at runtime, where cwd-based path injection finds the source tree and surfaces a clear `ModuleNotFoundError: No module named '<transitive-dep>'` if anything is missing. Verified by PR [#8381](https://github.com/$GITHUB_REPOSITORY/pull/8381) run 29294984874 (success) — the toolcache Python now has flask installed (added to the action's `pip install` list), the probe checks only the 7 deps the action installs, the precompute script imports `mvp_site.agent_prompts` successfully at runtime via cwd-based path injection, no PRECOMPUTE_FAILED anywhere in the log.

**Composite action side (`.github/actions/setup-precompute-deps/action.yml`):**

```yaml
runs:
  using: 'composite'
  steps:
    - name: Set up Python for embedding precompute
      id: setup-python
      uses: actions/setup-python@<pinned-sha>  # v5.0.0
      continue-on-error: true
      with:
        python-version: '3.11'

    # Capture the setup-python interpreter path so the deploy step can
    # hand it to deploy.sh's VPYTHON slot.
    - name: Export precompute interpreter to VPYTHON
      id: set-python-path
      shell: bash
      if: always()
      run: |
        set -u
        python_path="${{ steps.setup-python.outputs.python-path }}"
        if [ -n "$python_path" ] && [ -x "$python_path" ]; then
          echo "VPYTHON=$python_path" >> "$GITHUB_ENV"
          echo "$(dirname "$python_path")" >> "$GITHUB_PATH"
          echo "python-path=$python_path" >> "$GITHUB_OUTPUT"
        fi

    # pip-install ONLY the deps the downstream probe will check (NOT mvp_site
    # — that's the script's job, see Pitfall #14). Add transitive deps the
    # precompute script's mvp_site import chain actually needs (flask was
    # the one missing dep for mvp_site.agent_prompts via
    # mvp_site.llm_providers.provider_gateway → from flask import g).
    - name: Install embedding precompute deps
      id: install-deps
      continue-on-error: true
      shell: bash
      run: |
        python -m pip install --no-cache-dir \
          fastembed numpy google-cloud-storage jsonschema pydantic cachetools flask || true

    # Run the probe AFTER install. Import ONLY the 7 deps the step above just
    # installed — do NOT add `import mvp_site.X` (see Pitfall #14).
    - name: Verify precompute interpreter can import the embed-deps the action just installed
      id: probe-precompute
      shell: bash
      if: always()
      run: |
        set -u
        ready="false"
        python_path="${VPYTHON:-}"
        if [ -z "$python_path" ] || [ ! -x "$python_path" ]; then
          command -v python >/dev/null 2>&1 && python_path="$(command -v python)"
        fi
        if [ -z "$python_path" ] || [ ! -x "$python_path" ]; then
          echo "WARNING: no interpreter available (precompute-ready=false)"
          echo "precompute-ready=false" >> "$GITHUB_OUTPUT"; exit 0
        fi
        if "$python_path" -c 'import fastembed, numpy, google.cloud.storage, jsonschema, pydantic, cachetools, flask' >/dev/null 2>&1; then
          ready="true"
          echo "Precompute interpreter passed import probe ($python_path)"
        else
          echo "WARNING: precompute interpreter failed import probe" >&2
          "$python_path" -c 'import fastembed, numpy, google.cloud.storage, jsonschema, pydantic, cachetools, flask' 2>&1 | head -5 || true
        fi
        echo "precompute-ready=$ready" >> "$GITHUB_OUTPUT"
```

**Deploy script side (`deploy.sh`)** — store the probe target in a single `_EMBED_PROBE` variable so it stays in sync between the VPYTHON branch and the PATH-fallback loop:

```bash
# Probe ONLY the deps the install step actually pip-installs. Do NOT
# add `import mvp_site.X` here — the toolcache venv can't satisfy that
# chain (see Pitfall #14).
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

**The three load-bearing details:**

1. **`[ -x "${VPYTHON}" ]` instead of `command -v "${VPYTHON}"`** — the absolute path check is the contract that makes the toolcache path work. `command -v` only finds executables on `$PATH`; the toolcache path is not on `$PATH` at the point the deploy step runs.
2. **`python` not `python3` in the fallback loop** — system `python3` lacks fastembed; `python` is what `actions/setup-python` prepends to `$PATH` when `$GITHUB_PATH` is honored. On a GitHub-hosted runner both work; on a self-hosted Mac runner only `python` works.
3. **Probe scope == install scope** (Pitfall #14, added 2026-07-14): the probe imports exactly `fastembed numpy google.cloud.storage jsonschema pydantic cachetools flask` (7 deps) — the same list the install step just pip-installed. If the probe is broader than the install (e.g. adds `import mvp_site.agent_prompts`), the probe always fails because `mvp_site.agent_prompts`'s transitive chain includes flask AND other deps the action does not install. The actual `mvp_site` import happens inside the precompute script itself via cwd-based path injection (`scripts/precompute_prompt_embeddings.py:35` adds `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` to `sys.path`, then imports `mvp_site.*` from the source tree at runtime).

**Diagnostic message discipline (the FAIL-LOUD contract):**

When the probe fails, the script's error message MUST list every candidate it tried AND whether `VPYTHON` was set. Without that, the next failure is debuggable only by reading source. The v2 contract (PR #8381) drops `mvp_site.agent_prompts` from both the probe and the message to prevent the operator-facing "no interpreter with ... mvp_site.agent_prompts found" message from masking an otherwise-correct deploy. See `references/2026-07-14-precompute-flask-fix.md` for the verified 6-line diagnostic block + the full session transcript of run 29294984874 (the SUCCESSFUL live verification).

## Pitfalls — DO NOT do these

1. **Don't trust "gcloud builds submit exit 0" as deploy success.** The image built, but the revision may still fail to start. Always pull the Cloud Run revision logs.
2. **Don't compare revisions to a previous deployment's logs** if the Docker base changed between then and now — the ENTRYPOINT may have changed too.
3. **Don't assume "it works locally" means "it works in Cloud Run".** The reverse is also true: a local failure that's macOS-specific (objc fork) does NOT mean Cloud Run will fail. Pin down the actual root cause in the revision logs, then test the FIX not the build.
4. **Don't silently merge the fix.** Per the your-project.com repo rule (`~/.cursor/rules/pr-hyperlink.mdc` + `MERGE APPROVED` gate), always open a PR and wait for explicit `MERGE APPROVED` before merging. The user reviews.
5. **Don't bundle "while I'm here" refactors into the deploy-fix PR.** Per `simplify-code` and `requesting-code-review` skills, the PR must be one logical change — the Dockerfile CMD. No formatting-only edits, no opportunistic test additions, no doc-string rewrites. Pure root-cause fix.
6. **Don't ignore `evidence/gunicorn_es_evidence.log`** if you produce a smoke-test log during Phase 1 — commit it to the PR branch so the failure → fix → proof chain is auditable. Evidence Staleness Tolerance (`~/.claude/skills/evidence-standards`) applies, but a 60-line gunicorn log for a Dockerfile CMD fix is permanent evidence.
7. **Don't ship `CMD ["python", "-m", ...]` as the ENTRYPOINT-mismatch fix.** The "obvious" fix breaks because Docker still prepends the inherited `python` entrypoint, giving `python python -m gunicorn ...` and the same `can't open file` family of errors with `python` instead of `gunicorn` in the path. ONLY `ENTRYPOINT [] + CMD ["python", "-m", ...]` works against an ENTRYPOINT=python base. This is the #1 reason the v1 fix in this session's PR #8180 had to be followed by a v2 fix in PR #8182.
8. **Don't accept an `/advice` approval from the start of a PR as binding once the PR's fix surface has evolved.** When a follow-up commit changes the actual change-set materially (different Dockerfile lines, different config keys, different module), the original review's reasoning may no longer match what's being merged. This session: `/advice` returned "Approve and merge as-is, confidence high" against v1, and v2 turned out to be insufficient for the same root cause — the reviewer's "Verify Chainguard python base has ENTRYPOINT=python" claim was correct but the "use python -m gunicorn instead" recommendation was incomplete. Re-run advisory review on the actual FINAL form of the fix before merging, especially when two+ approaches were considered and one was rejected post-review. See the related `advice` skill.
9. **Don't assume fixing one failure layer exhausts the root cause.** A single base-image swap (e.g. `python:3.11-slim` → `cgr.dev/chainguard/python:latest-dev`) can introduce MULTIPLE independent failure layers that only surface sequentially as you fix each one: (Layer 1) ENTRYPOINT mismatch → `can't open file '/app/.../gunicorn'`, (Layer 2) ENTRYPOINT mismatch with `python -m` → `can't open file '/app/.../python'`, (Layer 3) Python 3.14 + protobuf metaclass → `TypeError: Metaclasses with custom tp_new are not supported.` Each layer masks the next — you can't see Layer 3 until Layers 1+2 are fixed because gunicorn never boots far enough to import `firebase_admin`. After fixing the visible failure, re-pull the revision logs for the NEW revision deployed from your fix and check for the next layer. Don't claim "fixed" until `latestReadyRevisionName == latestCreatedRevisionName` AND `/health` returns 200 from the new revision.
10. **Don't assume `Auto-Deploy Dev` actually deployed just because a run was created.** The workflow uses `concurrency: cancel-in-progress: ${{ github.event_name != 'release' }}` — rapid successive pushes to main cancel earlier deploy runs before the `deploy` job (reusable workflow call) starts. A cancelled run shows only `smoke-tests (skipped)` in its job list and has 0 log lines. To actually deploy after a merge, trigger manually: `gh workflow run deploy-dev.yml --repo $GITHUB_REPOSITORY --ref main`, then watch with `gh run list --workflow=deploy-dev.yml --limit=1`.
11. **Don't ship a composite action that installs runtime deps without exporting the interpreter path (Mode 7 anti-pattern, added 2026-07-13).** The `setup-precompute-deps` action runs `actions/setup-python@v5.0.0` then `pip install fastembed ...` into the GitHub-Actions-hosted toolcache. Without an explicit `echo "VPYTHON=$pythonPath" >> $GITHUB_ENV` step, the interpreter lives at `$RUNNER_TOOL_CACHE/python/3.11.x/bin/python` which is NOT on `$PATH` of subsequent steps AND not named `python3` on self-hosted Mac runners. `deploy.sh`'s probe loop iterated `${VPYTHON:-} ./vpython vpython python3` and silently fell through to system `python3` (no fastembed) every time. The fix is two-pronged: (a) the action MUST `echo "VPYTHON=$pythonPath" >> $GITHUB_ENV` AND `echo "$binDir" >> $GITHUB_PATH` after the install, AND (b) `deploy.sh` MUST trust VPYTHON as an absolute path (`[ -x "${VPYTHON}" ]`) instead of `command -v`. Verified: PR #8380 (action) + deploy.sh probe loop rewrite. **WARNING:** fixing the VPYTHON export is NOT ENOUGH — see Pitfall #14. Without adding the transitive deps the downstream `import mvp_site.X` chain needs (flask was the missing dep for `mvp_site.agent_prompts` via `mvp_site.llm_providers.provider_gateway`) AND reducing the probe to ONLY the deps the install step actually pip-installs, the recurring PRECOMPUTE_FAILED persists. PR [#8381](https://github.com/$GITHUB_REPOSITORY/pull/8381) is the v3 fix that makes the deploy infra actually green; PR #8380 v1 was insufficient on its own.
12. **Don't write a single-line `PRECOMPUTE_FAILED: no interpreter ... found` error message.** The deploy script's failure-email fires every push to main until fixed; the email body is the operator's first debugging surface. A 1-line "set SKIP_PROMPT_EMBEDDINGS_PRECOMPUTE=true to bypass" is the operator's worst-case starting point — they have to read source to know what was tried. The verified diagnostic block (PR #8380) lists the candidates tried in order AND reports `VPYTHON='...' (exists: yes/no)` AND points at the action that should have set `VPYTHON`. Future failures are debuggable from the failure email alone, no source dive.
13. **Don't put the interpreter probe in the same composite-action step as the `setup-python` install (Mode 7 v2 anti-pattern, added 2026-07-13 PR #8380 review).** The v1 fix in PR #8380 inlined the `precompute-ready` probe inside the `set-python` step — which runs BEFORE `install-deps`. That meant `precompute-ready=false` was always emitted even on a perfectly healthy install, because the probe ran against empty site-packages. The fixed action order is 4 separate steps: `setup-python` → `set-python-path` (export `python-path` + `VPYTHON` + `GITHUB_PATH`; NO probe) → `install-deps` → `probe-precompute` (runs AFTER pip install + emits `precompute-ready`). The probe MUST be a separate `id: probe-precompute` step that runs after `install-deps`. **Verified contract test** in `tests/test_precompute_deps_self_hosted.py::TestPrecomputeProbeStepOrder` pins the step-ordering invariant — if a future refactor reintroduces the v1 ordering (probe inside `set-python`), `test_probe_step_runs_after_install_step` fails-fast with the exact diff. **Caveat:** the step-ordering fix alone is NOT sufficient — PR [#8381](https://github.com/$GITHUB_REPOSITORY/pull/8381) further fixed the probe's `import mvp_site.agent_prompts` clause (Pitfall #14), which the action COULD satisfy even with proper step ordering.

**The contract:** in any composite action that follows the "setup-python → install-deps → probe" pattern, the probe step MUST run AFTER the install step. The `precompute-ready` output's value is only meaningful when its step depends on `install-deps.outcome == success` (or `always()` after the install). The reverse order reports `false` for a healthy install — a silent-but-deadly CI infra bug.

**Recipe to verify the order is correct** in any composite action under review:

```bash
# Get the steps in declaration order
python3 -c "
import yaml
action = yaml.safe_load(open('<action.yml>'))
for step in action['runs']['steps']:
    print(step.get('id', '(no-id)'), '|', step.get('name', ''))
"
# Confirm: install step comes BEFORE probe step, not after.
```

Verified correct order (PR #8380 v2):
```
setup-python    | Set up Python for embedding precompute
set-python-path | Export precompute interpreter to VPYTHON  (no probe!)
install-deps    | Install embedding precompute deps  (pip install)
probe-precompute | Verify precompute interpreter can import fastembed+numpy+GCS+mvp_site  (probe AFTER install)
```

Verified WRONG order (PR #8380 v1, caught by CodeRabbit):
```
setup-python    | Set up Python for embedding precompute
set-python      | Export precompute interpreter to VPYTHON + run probe  (probe INLINE, runs BEFORE install)
install-deps    | Install embedding precompute deps
```

If a future refactor puts the probe inline with `set-python`, the regression test fails-fast before the bug ships.

14. **Don't put `import mvp_site.X` in a probe that runs against a Python the install step doesn't actually pre-install (added 2026-07-14, post-#8380).** PR #8380 v1's deploy.sh probe checked `import mvp_site.agent_prompts` even though the `setup-precompute-deps` action only `pip install`s `fastembed numpy google-cloud-storage jsonschema pydantic cachetools`. `mvp_site.agent_prompts`'s import chain transitively pulls in `flask` via `mvp_site.llm_providers.provider_gateway → from flask import g`, and the action does NOT pip-install `flask`. Result: the probe ALWAYS fails on self-hosted Mac runners even on a healthy install. Verified by deploy run [29292726556](https://github.com/$GITHUB_REPOSITORY/actions/runs/29292726556) — `WARNING: precompute interpreter failed import probe (fastembed+numpy+google-cloud-storage+mvp_site.agent_prompts)` immediately followed by deploy.sh's `WARNING: VPYTHON='...' set but failed import probe — falling through to PATH lookup`. The fix in PR #8381 has two halves:

    **a. Make the install list match the probe list** — add any transitive dep the probe actually needs to the action's `pip install`. For PR #8381 that was just `flask`. To find which transitive deps you need: `python3 -m venv /tmp/repro && /tmp/repro/bin/pip install <installed-deps> && /tmp/repro/bin/python -c "import mvp_site.X"` — the failing `ModuleNotFoundError` tells you which dep the action needs to add. Repeat until the import succeeds. The probe and the install must stay in lockstep forever — `tests/test_precompute_deps_self_hosted.py`'s `TestInstallDepsPinsFlaskForToolcacheUsability.test_install_deps_pip_installs_flask` pins the install list.

    **b. Remove the over-strict probe imports** — the probe should import ONLY what the install step just pip-installed (i.e. exactly `fastembed numpy google.cloud.storage jsonschema pydantic cachetools flask` post-#8381). Do NOT add `import mvp_site.X`. The precompute script (`scripts/precompute_prompt_embeddings.py:35`) injects the repo root onto `sys.path` via `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`, then imports `mvp_site.X` at runtime. If a transitive dep is genuinely missing, the script surfaces a `ModuleNotFoundError: No module named '<X>'` at the actual import site — which is a far clearer debug signal than the probe gate's silent `false`.

    **Generalize:** any time a deploy-time probe tries to validate "the script can run", check what the install step ACTUALLY pip-installs, then probe only that. Script-side imports (which may pull in transitive deps not in any install list) belong at script-runtime, not probe-time. If the probe is more permissive than the install (e.g. checks mvp_site.chain when only mvp_site itself isn't installed), the probe becomes a useless gate that always reports failure — the deploy infra is wired correctly, the probe is over-strict. `tests/test_precompute_deps_self_hosted.py::TestDeployShProbeNoMvpSiteAgentPrompts::test_deploy_sh_probe_does_not_check_mvp_site.agent_prompts` pins the contract via `_EMBED_PROBE='...'` regex.

15. **Don't propose fix options before proving the root cause (added 2026-07-24, verified on iOS auth-cookie symptom).** The session that produced this v2.5.0 revision had the user push back on a 4-option fix menu (A/B/C/D) for "the cookie expires after 1-2 days" with *"Let's first root cause why it's expired versus all these speculative fixes. It has not been 30 days."* The pushback was correct — the proposed fixes (server-side `max_age` override, etc.) were a no-op for the actual symptom on iOS. The diagnostic order is: (1) confirm user-agent, (2) compute sign-in interval, (3) check Firebase project config for any cookie TTL config, (4) read the JS persistence code path, (5) only then propose fixes. Phase 1 takes 2 minutes; the fixes are wrong if Phase 1 is skipped. **The v1.0 reference for `references/auth-cookie-ttl-class-2026-07-24.md` is the canonical example of this pitfall** — it shipped 4 fix options before proving the cause, and the v1.1.0 reference revision documents why the v1.0 fixes would not have worked. Future investigators of "I have to log in again after a day or two" must read the v1.1.0 reference and run Phase 1 before proposing any fix.

## Verification before claiming "fixed"

| Gate | How to verify | Block if red |
|------|---------------|--------------|
| Local smoke test | `curl http://127.0.0.1:8093/health` returns 200 with the JSON body | Don't push |
| Docker build (if you have docker) | `docker build -t wa-debug -f $PROJECT_ROOT/Dockerfile .` finishes successfully | Fix Dockerfile before pushing |
| PR CI passes | `gh pr checks <N>` all green (or at least no relevant-to-this-PR failures) | Don't merge |
| **Cloud Run revision actually serving** | `gcloud run revisions list --service=<name>` shows the new SHA as `latestReadyRevisionName` (not just `latestCreatedRevisionName`); `gcloud run services describe <name>` shows 100% traffic on it | Don't close the bead — re-investigate (see Pitfall 7) |
| **Live deploy matches PR HEAD (Mode 7 sanity check)** | `gcloud run services describe <name> --format='value(metadata.labels.commit-sha-full)'` returns the PR's head SHA AND `curl <service-url>/health` returns 200 | Don't claim "fixed" — see Step 5.5 above |
| Post-merge: next dev deploy succeeds | Watch `gh run list --workflow="Auto-Deploy Dev" --limit=1` after the next push | Don't close the bead |

The fourth row is new and is the one that caught this skill's first version. `latestCreatedRevisionName` ≠ `latestReadyRevisionName`. The created-but-not-ready state is exactly what happens when the v1 fix shipped but the v1-only change still failed the startup probe.

The fifth row (added 2026-07-13) catches the opposite failure mode: the deploy step fails BEFORE `gcloud run deploy` is invoked (Mode 7), but a sibling run in the same push window may have shipped the PR. The live service IS the source of truth — verify before claiming "fixed."

## Cross-references

- `references/2026-07-05-chainguard-entrypoint.md` — full session evidence: failing revision `mvp-site-app-dev-03646-k8w`, gcloud logging query, PR #8180, the silent 4-day outage pattern. **(Note: this reference documents the v1 fix. The v1 fix was incomplete — see the addendum below. Read both files together for the complete story.)**
- `references/2026-07-06-entrypoint-override-mandatory.md` — the v1→v2 patch lesson: `CMD ["python", "-m", ...]` is NOT sufficient when the base image sets `ENTRYPOINT=["python"]`. Documents the failing revision from PR #8180's merge (`mvp-site-app-dev-03647-68m`), the second-stage `can't open file '/app/$PROJECT_ROOT/python'` error, and the canonical fix `ENTRYPOINT [] + CMD ["python", "-m", ...]`. **MUST READ** before advising anyone on a Chainguard ENTRYPOINT/CMD fix.
- `references/2026-07-13-precompute-deps-self-hosted-mac.md` — Mode 7 evidence: failing GHA run 29280658965, the `setup-precompute-deps` toolcache architecture, the `deploy.sh` probe loop's `python3` blind spot, the PR #8380 fix (action exports `VPYTHON` + `deploy.sh` reads it as absolute path), and the "your PR is fine, only the deploy CI is broken" diagnostic that landed via Step 5.5. **MUST READ** before assuming the user's PR is broken when a deploy failure email lands — the failure may be at the script probe, NOT at the deployed revision.
- `references/2026-07-14-precompute-flask-fix.md` — Mode 8 (v2 PR #8381) evidence: the post-#8380 deploy run 29292726556 that kept failing despite #8380 v2's step-ordering fix; the transitive-dep trace (mvp_site.agent_prompts → mvp_site.dice_strategy → mvp_site.llm_providers.provider_gateway → `from flask import g` → `ModuleNotFoundError`); the PR #8381 fix (action now `pip install flask`; probe reduced to the 7 deps the install step actually installs; deploy.sh stores the probe target in a single `_EMBED_PROBE` variable); the live verification by dev-deploy run 29294984874 (success + revision `mvp-site-app-dev-03844-8t2` serving PR HEAD + `/health` HTTP 200); and the local repro recipe that proves the red-state-then-green pattern (simulated toolcache venv with the install list; probe exits 0; `scripts/precompute_prompt_embeddings.py --help` exits 0; the full `mvp_site` chain imports successfully). **MUST READ** before diagnosing any "PRECOMPUTE_FAILED but install log shows Successfully installed ..." scenario.
- `references/2026-07-30-proxy-provider-masquerade-402.md` — **the runtime sibling class** (verified 2026-07-30 on `consensus-ml.ai` → `ai-universe-consulting-v2` in `worldarchitecture-ai`): when the deployed revision is serving and `/health` returns 200 but the user-facing feature is broken with a `Cerebras API error: 402` / `OpenRouter 402` style message, the proxy is masquerading the upstream. Recipes: SPA-bundle-inspection (`grep -aoE 'fetch\([^)]{0,300}\)' <bundle>`), `gcloud run services list` cross-reference to find the serving backend, `curl -X POST` to reproduce the upstream's actual error body, and the 4-key probe matrix showing all 4 keys worked for `gpt-oss-120b` / `gemma-4-31b` / `zai-glm-4.7` but ALL returned `{"code":"model_not_found"}` for the displayed `qwen-3-235b-a22b-instruct-2507`. Two fix options: top up OpenRouter credits (smallest, fastest) or repoint the proxy to direct Cerebras (durable, requires a new revision). **MUST READ** before diagnosing any "the app shows <provider-X> error 402 but <provider-X> says the key is fine" symptom.
- `references/auth-cookie-ttl-class-2026-07-24.md` — **v1.1.0 (REFINED 2026-07-24):** the original v1.0 hypothesis (cookie TTL is the failure mode, fix is server-side `max_age` override on the proxy at `$PROJECT_ROOT/main.py:1692`) was **WRONG** for the actual iOS user-visible symptom. The real root cause is iOS WebKit ITP evicting the Firebase Auth client's persisted user record (forced to localStorage by `auth.js:75-99` iOS WebKit IndexedDB neutralization); the right fix is server-side session restore from `__session` cookie + silent client re-bootstrap, NOT a cookie TTL override. Verified symptom: campaign `wc2BBcSgOljiU3vJ160A` on `mvp-site-app-dev-03980-l7l` from iPhone iOS 26.5.2 / Chrome mobile, sign-in interval 2d 18h. **MUST READ** before treating "the cookie expired / I have to log in again" as either a deploy failure (it's not), a client-side bug (it's not), or a cookie-TTL issue (it's not — the cookie survives fine; the persisted user record is what gets evicted).
- `~/.claude/skills/systematic-debugging/SKILL.md` — the umbrella Phase 1 protocol this skill is a domain-specific instance of.
- `~/.hermes/skills/skills/workflow/drive-pr-to-green/SKILL.md` — for driving the resulting PR through to merge.
- `~/.claude/skills/evidence-standards/SKILL.md` — for `/es` evidence requirements and Staleness Tolerance.
- `~/.claude/skills/advice/SKILL.md` — the `/advice` second-opinion slash skill; relevant here because advisor approval was scoped to the v1 fix surface, not to the eventual v2 (Pitfall 8 captures the lesson).
- `~/.cursor/rules/pr-hyperlink.mdc` — for the PR-hyperlink rule when reporting status to the user.
- The repo's `CLAUDE.md` "Merge safety" section — for the `MERGE APPROVED` gate on your-project.com PRs.

## One-line summary

**Three Iron Laws:** (1) the build log lies; the revision log tells the truth — pull the Cloud Run `cloud_run_revision` resource logs for the failing revision, find the actual container-startup error, fix that, smoke-test locally, then open a PR — don't merge without `MERGE APPROVED`. (2) the pip install can succeed while the script probe fails — when the deploy step exits 1 BEFORE `gcloud run deploy` is invoked, the user's PR may already be live via a sibling run; verify with `gcloud run services describe` before claiming "your PR is broken." (3) **the auth-cookie-TTL class's v1.0 hypothesis was wrong** — for "I have to log in again after a day or two" on iPhone, the failure is iOS WebKit localStorage eviction of the Firebase Auth persisted user record, NOT a cookie TTL issue. See `references/auth-cookie-ttl-class-2026-07-24.md` v1.1.0. (4) **the proxy-chain provider-masquerade class** — for "<provider-X> API error: 402" on a Cloud Run app, the displayed provider name and the actual upstream are often different; the proxy re-emits the upstream's raw error body wrapped with the UI label. `grep -aoE 'fetch\([^)]{0,300}\)' <spa-bundle-url>` + `curl -X POST` to reproduce + `gcloud run services describe` to find the backend is the recipe. See `references/2026-07-30-proxy-provider-masquerade-402.md`.
