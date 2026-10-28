# Merge resolution: codex/advice-runtime-deadline-20261026 (PR #580) — 2026-10-28
Merged origin/main `20a45ad5378dc880b9f79d9ba629784876596899` into the PR branch.

## `.claude/skills/advice/SKILL.md`
- Workflow structure: **Combined** — kept the current main structure, then carried forward the PR branch additions requiring same-host queue timestamps and requiring zero exit, a parseable receipt, and a nonempty verdict before counting the primary-pair runner. Main had replaced the longer duplicated workflow, so the superseded duplicate prose was not restored.

## `.claude/skills/advice/scripts/run_primary_pair.py`
- Scratch and output setup: **Combined** — kept main’s canonical Scratch resolver and fresh output-directory reservation; made Scratch resolver timeout respect the PR’s remaining work deadline, reporting deadline exhaustion as attempt timeout.
- Deadline-aware subprocesses: **Combined** — kept the PR’s absolute attempt/work deadlines on Git preflight, fingerprinting, clone setup and reviewer dispatch while preserving main’s Scratch-root selection and setup error handling.
- Duplicate `git()` return: **Dropped side** — removed the unreachable duplicate `subprocess.run` left by the automatic hunk combination; the live return already applies the deadline-bounded timeout.

## Tests
- Before: `python3 -m unittest tests.test_advice_primary_pair` at PR head `220f003e332dba27bcaa902995d72a20a7a3c3a2` → 49 tests; 1 failure and 1 error from short wall-clock assertions (barrier completion within 0.5s and receipt expectation with a 0.2s attempt budget).
- After: `python3 -m unittest tests.test_advice_primary_pair` → PASS, 51 tests; `python3 .claude/skills/advice/scripts/test_run_primary_pair.py` → PASS, 12 tests; `python3 -m py_compile .claude/skills/advice/scripts/run_primary_pair.py .claude/skills/advice/scripts/test_run_primary_pair.py tests/test_advice_primary_pair.py` and `git diff --check` → PASS.
