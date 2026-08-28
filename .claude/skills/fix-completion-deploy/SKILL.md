---
name: fix-completion-deploy
description: "Use when fixing broken automation (CI, gates, hooks). A commit is NOT a fix; verify the fix is active post-deploy; restart gateway after config.yaml changes."
---

# Fix completion — infrastructure fixes require deployment


When fixing broken automation (skeptic gate, CI workflows, lifecycle workers, hooks):
- A commit is NOT a fix. The system is still broken until the fix is deployed (pushed + running).
- "Fix X" from the user is push authorization for the fix branch/PR. Do not stop at commit and ask "want me to push?"
- After pushing, verify the fix is active: check that the next cron/workflow run produces a different result.
- After every successful `git push`, report the exact pushed HEAD SHA and the remote commit URL, preferably `https://github.com/<owner>/<repo>/commit/<sha>`.
- If the fix is in a PR-required repo: create the PR immediately, don't wait to be asked.

**Config changes also require deployment** — a config file write with no process restart is a silent no-op:
- After changing model/provider/fallback keys in `config.yaml`, restart the gateway immediately (see `~/.hermes/CLAUDE.md` post-mutation section for the exact sequence)
- Verify with a new "Cron ticker started" log line — not just `curl /health` (liveness ≠ config loaded)
- Both `~/.hermes/config.yaml` (staging) and `~/.hermes_prod/config.yaml` (prod) must be updated; they don't sync automatically

**Why**: 2026-06-02 — M3 model switch wrote config files correctly but skipped gateway restart. Process ran with M2.7 in memory for 4 days. Skeptic bug precedent: fix was in commits but not deployed for hours.
