---
name: eval-vendor-tooling
description: "Evaluate a third-party AI/ML repo, vendor claim, or article headline — clone, run inference, contract-verify the README vs source vs shipped checkpoint, and publish a self-contained reproducible eval to jleechanorg/evals. Trigger when a user message pairs a URL/repo reference with an action verb like 'evaluate', 'replay', 'does X actually work', or 'publish findings to evals'."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [eval, vendor, third-party, reproducibility, claim-verification, ml-model, public-publish]
    related_skills: [browser-headless-default, github-repo-management, github-pr-workflow, evidence-attach-not-path-cite, outbout-secret-publication-gate]
---

# Evaluate third-party vendor tooling (class-level)

When the user gives you a URL, repo link, or vendor claim ("X cuts cost by 60%") and asks you to evaluate, this is the workflow. The session-proven lesson: **just do the work** — clone, fetch, infer, capture raw outputs. Don't ask permission menus before the first tool call. After a tool call fails, don't fall back to asking the user — pivot to the next reasonable tool.

## Phase 0 — Pick the right first tool. Don't ask.

When the user's first message contains a URL or repo reference AND an action verb ("clone", "evaluate", "replay", "test"), your first turn must contain a real tool call. Pick the cheapest correct tool:

| Source type | First tool |
|---|---|
| GitHub repo (`github.com/<owner>/<repo>`) | `terminal: git clone <url>` (into a clean workspace like `~/projects/<slug>/`) |
| Plain-text endpoint (`.md`, `.yaml`, `raw.githubusercontent.com`, docs JSON) | `web_extract` or `terminal: curl` |
| Paywalled / JS-rendered (Medium, vendor blog, dynamic docs) | `browser_navigate` (headless) |
| Any other URL | `browser_navigate` headless (per `browser-headless-default`) |

Do NOT post a clarifying menu first. Do NOT ask "paste vs I try harder". Just pick and go.

After a tool fails:
- `web_extract` returns "ddgs is search-only" → pivot to `browser_navigate` headless
- `curl` to a known bot-wall (Medium, Cloudflare-protected) returns 5-10 KB of HTML → pivot to `browser_navigate`
- `browser_navigate` gets the "Just a moment…" Cloudflare interstitial → say so, don't fake content from there
- `gh repo view` returns 404 → `gh repo create ...` if user wants to publish; otherwise ask once

Only if the **pivot path itself fails** should you surface a blocker to the user.

## Phase 1 — Capture raw inputs as you go

Don't re-fetch the article, README, or paper more than once. Save everything that you'll need later:

- The HTML/MD response → `/tmp/<slug>.html` for later grep
- Downloaded source files (`*.py`, `*.yaml`, `*.json`) → keep them in their cloned locations
- Mine `session_search` for related past work in the user's projects if relevant — the user's real prompts are usually the best eval inputs

## Phase 2 — Read source, not just README

README is a marketing claim. Source is the contract. Always read:

- The model definition file (architecture, head shape, layer config) — for ML repos this is the inference entrypoint
- The download-model.sh or equivalent — confirms what was actually shipped
- The model-loading call — `strict=True` (will raise on mismatch) vs `strict=False` (will silently ignore)
- The version-pinning files (`requirements.txt`, `pyproject.toml`, `Dockerfile`)

For ML repos specifically, run a contract verification step before any inference:

```python
import torch
sd = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
for k, v in sd.items():
    if "classifier" in k or "head" in k or "output" in k:
        print(f"{k}: {tuple(v.shape)}")
# If README says Linear(768-4) but shape is [6, 768], the repo lies.
```

Also check class counts: `NUM_LABELS` constants in code, label dictionaries, class head width in `state_dict`, sample labels in tests.

## Phase 3 — Run inference in-process, not via HTTP

If the eval involves running a model, **don't spin up the vendor's full FastAPI / agent / router stack first**. Transport is not the question. Model behavior is.

Load the model in-process via `torch.load` + a re-implemented architecture (or a faithful copy of the vendor's `nn.Module` classes), and run inference directly. Capture per-input:

- The prompt as sent
- Tokens used (and whether it was truncated)
- Per-class probabilities (not just argmax — the distribution tells you what the model is actually uncertain about)
- Latency per inference

For latency: GPU latencies vendor cites are usually `g4dn.xlarge` at batch=1; CPU is ~10× slower. Don't trust vendor latency claims without reading the test setup.

## Phase 4 — Catch the contract mismatch (the most common failure)

The single most common failure pattern in third-party ML repos:

> README claims N classes. Code says N classes. **Checkpoint has M ≠ N classes.**

If `model.load_state_dict(sd)` raises `size mismatch … copying a param with shape torch.Size([M, …]) from checkpoint, the shape in current model is torch.Size([N, …])`:

- The repo does not run end-to-end out of the box. Document this as a **Failure** in the report.
- Don't try to fix it silently. Either:
  1. Patch the code to `NUM_LABELS=M` (and document), or
  2. Run with `load_state_dict(strict=False)` and a matching head shape, but flag the divergence in the report.
- Either way, the **published interpretation of the model's output is unverified** when there's a class-count mismatch. Index 0..M-1 from the checkpoint is the only ground truth.

Other common contract violations to look for:
- Head shape ↔ labels dict mismatch
- Tokenizer vocabulary size ↔ embedding matrix rows mismatch
- Max-seq-len in code ↔ positional embeddings
- "`strict=True`" load that will raise on the user's machine
- Pre-claimed accuracy metrics without a test set in the repo

## Phase 5 — Capture outputs in a real shell, not a sandbox

The agent's `execute_code` runs in a sandboxed Python process that **does not persist files to `/tmp` across calls reliably**. To keep raw outputs:

```bash
# Write the inference script to a real .sh file
write_file(path="/tmp/run_<slug>.sh", content="<<SCRIPT>>...<<PYEOF>>...PYEOF")

# Run it via real bash so /tmp output survives
bash /tmp/run_<slug>.sh
```

Why: `execute_code` outputs vanish after the call returns. Anything you want to ship in the eval (raw logits, per-prompt timings, prompts themselves) must be written via a real shell script and survive into the next tool call.

## Phase 6 — Publish to `jleechanorg/evals`

Self-contained eval repo structure (matches the canonical layout landed in this repo's own session):

```
jleechanorg/evals/
├── README.md                      # top-level index + conventions
├── LICENSE                        # MIT, with note that vendored code keeps its own license
├── .gitignore                     # never commit model weights or upstream clones
└── docs/<eval-slug>/
    ├── README.md                  # folder-level entry, TL;DR, link map
    ├── report.md                  # full narrative (what we tested, what we found, verdict)
    ├── repro.sh                   # one-command reproduction (one real shell script)
    └── raw/
        ├── prompts.json
        └── results.json
```

Per-eval folder naming: `docs/<eval-type>-<subject>/` where `<eval-type>` is one of:
- `cli-eval-<tool-name>` for CLI tools
- `router-eval-<vendor-repo>` for LLM routers
- `model-eval-<model-name>` for raw model evaluations
- `tool-eval-<tool-name>` for SaaS / hosted tools

Commit message convention: `[agento] feat: <eval-name> — <one-line summary>`. The `[agento]` prefix matches the convention from worldarchitect/agent-orchestrator work.

**Before `git push`**, per `pr-ci-fix-autopush` and `push-pr-donot-stop-halfway`:
- `git rev-parse origin/main` must equal `HEAD` after push
- `gh repo view jleechanorg/evals` shows the new description and default branch
- The README renders correctly on github.com (visit it once via `web_extract` against the raw URL if you want to verify)
- No model weights, venvs, or `upstream-clone/` directories in the diff (`.gitignore` MUST cover them)

## Pitfalls

### P1. Don't ask permission menus when the user gave a directive

Bad first turn after curl fails:
> "Do you want me to (A) try harder on the article, (B) wait for you to paste, or (C) try a different approach?"

Good first turn:
> `browser_navigate(url)` (the call itself, with a 1-line summary)

The `task-ack-and-execute` SOUL.md COMMIT already requires the first turn to contain a tool call. This pitfall reinforces: **after a tool fails, don't pivot to asking — pivot to the next tool.**

### P2. README ≠ contract

Always run a contract verification step (Phase 2) before trusting any headline numbers. Common violations: claimed parameter count is loose, claimed accuracy has no test set, claimed latency is GPU-only at batch=1.

### P3. Sandbox outputs don't survive

`execute_code` outputs vanish after the call. Use a real `bash` subprocess via `write_file` → `terminal bash` if you need raw outputs to persist.

### P4. Class-count mismatches are the #1 contract violation in ML repos

Always print the checkpoint head shape BEFORE running inference. Save it to the eval's `raw/results.json` so future readers can verify your setup.

### P5. Latency claims are scope-dependent

"10ms router" might be GPU-only, batch=1, on a specific instance type. Don't trust without reading the test setup. Always re-measure on the eval's own machine.

### P6. Paywalled content is a real obstacle

Medium and similar sites have aggressive bot-walls. If `browser_navigate` headless + `BROWSERBASE_ADVANCED_STEALTH` can't get past it, the article itself is unreadable. **Say so** in the report rather than fabricating a summary.

### P7. Don't leak credentials in eval artifacts

Per the `outbound-secret-publication-gate` SOUL.md COMMIT, before pushing anything to `jleechanorg/evals`, scan all `.md` and `.sh` files for `ghp_`, `xoxp-`, `sk-`, `AKIA` patterns. Never commit tokens, no matter how "obvious" they seem in a private context.

## Verification

After publishing:

1. `git -C ~/projects/evals log --oneline -1` — commit exists
2. `git -C ~/projects/evals rev-parse origin/main` equals `HEAD` (no local commits behind)
3. `gh repo view jleechanorg/evals --json description,defaultBranchRef` — description + main branch set
4. Web-fetch the raw README URL on github.com to verify markdown renders
5. `bash docs/<slug>/repro.sh` from a clean checkout — runs end-to-end and reproduces `raw/results.json`

## Related references

- `references/router-eval-deycoding-2026-07-22.md` — first worked example, in this repo's own session: a ~140M encoder BFSI router that doesn't load out of the box, can't do whole-convo classification, and has a contract mismatch.

## Related skills

- `browser-headless-default` — for the headless browser pivot path
- `github-repo-management` — for `gh repo create`, `git push`, etc.
- `evidence-attach-not-path-cite` — for embedding screenshots / evidence in reports
- `outbound-secret-publication-gate` (SOUL.md COMMIT) — for the pre-publish credential scan
- `pr-clean-branch-from-main-no-history-bloat` (SOUL.md COMMIT) — if the eval repo itself needs branch discipline