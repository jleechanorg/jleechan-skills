---
description: Use Oracle CLI in browser mode (no API key) for context bundling and analysis
type: usage
scope: oracle
---

# Oracle Browser Usage

## When to activate
- Need AI analysis with project files but prefer browser ChatGPT instead of API keys.
- Tasks: architecture review, debug triage, diff review, frontend/backend issue analysis.

## Quick start (browser)
1. Ensure you are logged into chatgpt.com in your default Chrome/Chromium profile.
2. Source helper bundles: `source scripts/oracle_helpers.sh` (exports globs and helper commands).
3. Run helpers (browser auto-selected when no API key):
   - `oracle_arch_preview` (dry-run bundle preview).
   - `oracle_arch` (architecture review).
   - `oracle_ai_debug [tmp/bug-report.md]` (AI pipeline bug).
   - `oracle_diff_review` (reviews current git diff).
   - `oracle_ui_debug [tmp/ui-bug.md]` (frontend triage).

## Core flags
- `--engine browser` (implicit when no API key), `--wait` to stay attached.
- `--dry-run summary` to preview bundle before sending.
- `--files-report` to see token spend per file.

## Prompts (adapt as needed)
- Architecture: “Fast architecture review of Your Project; describe components, how MCP/Flask/Gemini/Firestore fit; top 5 cleanup opportunities.”
- AI bug: “We have a bug in the AI story pipeline… walk HTTP→MCP→Gemini→parsing→state/validators; propose minimal patch + tests.”
- Diff review: “Senior review of this diff for Your Project (correctness, perf, security, architecture alignment).”
- Frontend: “Frontend bug described in note; find likely causes in campaign wizard; propose JS/CSS fixes and a minimal regression test.”

## Troubleshooting
- If Oracle says “ChatGPT session not detected”: sign into chatgpt.com in Chrome or pass cookies (`--browser-inline-cookies` or `--browser-cookie-path`).
- If bundle is too big: trim globs in `scripts/oracle_helpers.sh` or add excludes (`!pattern`).
