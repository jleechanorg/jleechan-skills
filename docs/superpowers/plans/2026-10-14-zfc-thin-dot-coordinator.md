# ZFC Thin Dot Coordinator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace regex/substring/marker-counting reply classification in `.claude/skills/agy-dot-coordinator/scripts/ping-dots.py` with a thin Zero-Framework Cognition (`/zfc`) LLM classifier using the existing provider ladder, then reinstall and verify on both macOS and Linux (`<linux-host>`).

**Architecture:** `.claude/skills/agy-dot-coordinator/scripts/ping-dots.py` retains only deterministic OS/transport mechanics (slot selection, `flock`, `STOP`/`delivery_unverified` holds, bounded process-group execution, `DOT_SENT_VERIFIED` checks, and JSON state writes) and delegates semantic reply evaluation (`compliant`, `working`, `reaction_only`, `unstructured_text`, `idle_refusal`) to the existing LLM provider ladder (`generate(provider, prompt)`). Empty, pre-reminder, or unattributed tails deterministically return `'no_response'` without an LLM call; provider failures during classification fail closed as `'classification_unavailable'` (incrementing `consecutive_classification_failures` in state JSON) without heuristic fallback or spurious escalation.

**Tech Stack:** Python 3 standard library (`argparse`, `fcntl`, `json`, `os`, `pathlib`, `platform`, `shutil`, `signal`, `subprocess`, `sys`, `tempfile`, `time`, `urllib.request`), `unittest`, `launchd` (macOS), `systemd` (Linux).

---

### Task 1: Parameterize Provider Generation (`generate(provider, prompt=PROMPT)`) and Add Structural Extractor & JSON Verdict Parser

**Files:**
- Modify: `.claude/skills/agy-dot-coordinator/scripts/ping-dots.py`
- Modify: `.claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py`
- Test: `.claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py`

**Step 1: Write the failing test**

Add hermetic unit checks in `.claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py` verifying:
1. `m.generate(provider, prompt="custom prompt")` passes the custom prompt (rather than the module-global `PROMPT`) to each provider using hermetic fakes:
   - Monkeypatch `m.bounded_run` for `luna`, `minimax`, `haiku`, `codex`, and `agy` to record the command/`stdin_text` and return canned stdout.
   - Monkeypatch `urllib.request.urlopen` for `gemini` to record the request payload and return a canned JSON candidate response.
2. `m.parse_verdict('{"verdict": "compliant"}') == "compliant"` and fenced ````json\n{"verdict": "idle_refusal"}\n```` returns `"idle_refusal"`.
3. `m.parse_verdict` raises `ValueError` on malformed JSON, non-object JSON, or unknown verdict strings.
4. `m.extract_reply_after_reminder`:
   - Extracts trimmed text appearing after `REMINDER_OPENING` + `ATTRIBUTION_SUFFIX`.
   - Returns `""` when `page_text` is empty, lacks `REMINDER_OPENING`, lacks `ATTRIBUTION_SUFFIX` (preventing an unattributed reminder's own contract body from being extracted as a reply), or has only whitespace after `ATTRIBUTION_SUFFIX`.

**Step 2: Run test to verify it fails**

Run:
```bash
python3 .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py
```
Expected: FAIL with `AttributeError: module 'ping_dots' has no attribute 'parse_verdict'`.

**Step 3: Write minimal implementation**

In `.claude/skills/agy-dot-coordinator/scripts/ping-dots.py`:
- Update `claude_json(model, env=None, prompt=PROMPT)`, `generate_gemini(prompt=PROMPT)`, and `generate(provider, prompt=PROMPT)` to accept `prompt=PROMPT`.
- Add `ATTRIBUTION_SUFFIX`, `MAX_CLASSIFY_REPLY_CHARS`, `VALID_VERDICTS`, `extract_reply_after_reminder(page_text)`, and `parse_verdict(raw_text)`.

**Step 4: Run test to verify it passes**

Run:
```bash
python3 .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py
```
Expected: New `generate(..., prompt=...)`, `parse_verdict`, and `extract_reply_after_reminder` checks pass.

**Step 5: Commit**

```bash
git add .claude/skills/agy-dot-coordinator/scripts/ping-dots.py .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py
git commit -m "gemini/gemini-4-argon: feat(coordinator): parameterize provider prompt and add verdict parser [gemini][gemini-4-argon]"
```

---

### Task 2: Replace Heuristic `classify_response` with ZFC LLM Semantic Classifier and Update `verify_and_escalate`

**Files:**
- Modify: `.claude/skills/agy-dot-coordinator/scripts/ping-dots.py`
- Modify: `.claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py`
- Modify: `.claude/skills/agy-dot-coordinator/SKILL.md`

**Step 1: Write the failing test**

In `.claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py`, replace the heuristic-era un-stubbed classification calls (`lines 92-104`) and add hermetic `m.generate`-stubbed tests:
1. Assert that `STATUS_MARKERS` is removed from `m` (`not hasattr(m, 'STATUS_MARKERS')`).
2. Test that `m.classify_response` returns `'no_response'` with **zero** calls to `m.generate` when the tail is empty, lacks `REMINDER_OPENING`, lacks `ATTRIBUTION_SUFFIX`, or has no text after `ATTRIBUTION_SUFFIX`.
3. Test with a hermetic `m.generate` stub that `m.classify_response`:
   - Wraps the head-truncated (`[:6000]`) reply inside `<dot_reply>...</dot_reply>` and escapes any literal `</dot_reply>`.
   - Calls `m.generate(provider, prompt)` and returns the model's verdict (`'idle_refusal'`, `'compliant'`, `'working'`, `'reaction_only'`, `'unstructured_text'`), proving that a reply containing all four `STATUS:` / `ACTIONS + PROOF:` / `BLOCKERS:` / `NEXT:` headers is classified by the model stub (`'idle_refusal'`) rather than by marker counting.
4. Test that `m.classify_response` falls back across `providers` when an earlier provider raises `ValueError` or returns malformed/unknown JSON, and returns `'classification_unavailable'` when all providers fail.
5. Update all `m.verify_and_escalate` test scenarios in `test_reminder_compliance.py` to stub `m.generate` hermetically (so no real LLM processes are spawned in unit tests) and verify:
   - `provider='luna'` builds the full fallback tuple `('luna', 'minimax', 'codex', 'gemini')` so classification falls back to `'minimax'` if `'luna'` fails during `verify_and_escalate`, and `provider='agy'` uses `PROVIDERS` without calling quota-quarantined `'agy'`.
   - Escalates and increments `consecutive_noncompliance` on `'idle_refusal'`, `'reaction_only'`, `'unstructured_text'`, and `'no_response'`.
   - Does NOT escalate on `'compliant'` (resets `consecutive_noncompliance = 0` and `consecutive_classification_failures = 0`).
   - Does NOT escalate on `'working'` after recheck, and preserves prior `consecutive_noncompliance` without resetting it to `0`.
   - Does NOT escalate on `'classification_unavailable'`, preserves prior `consecutive_noncompliance`, and increments `consecutive_classification_failures`.
6. Move the final `FAILURES` check and `sys.exit(1)` to the bottom of `test_reminder_compliance.py` so every check in the file is enforced by the process exit code.

**Step 2: Run test to verify it fails**

Run:
```bash
python3 .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py
```
Expected: FAIL because `STATUS_MARKERS` still exists and `classify_response` still uses heuristic marker counting instead of `m.generate`.

**Step 3: Write minimal implementation**

In `.claude/skills/agy-dot-coordinator/scripts/ping-dots.py`:
- Remove `STATUS_MARKERS` and all substring/length heuristics from `classify_response`.
- Implement `CLASSIFY_PROMPT_TEMPLATE` (with `<dot_reply>...</dot_reply>` fencing and tie-break rules), `classify_response(page_text, providers=PROVIDERS)`, `read_and_classify(dot, account, env, windows=None, providers=PROVIDERS)`, and updated `verify_and_escalate(dot, account, env, provider, state_file, wait_secs=180, recheck_secs=120, providers=None)`.
- Update `ESCALATION_BODY` to explicitly cover `idle_refusal` of authorized/relayed work while preserving all required contract labels.
- Update `.claude/skills/agy-dot-coordinator/SKILL.md` to document the ZFC LLM classification flow, `<dot_reply>` fencing, fallback ladder, and `VALID_VERDICTS`.

**Step 4: Run all 6 test suites to verify they pass**

Run:
```bash
python3 .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py && \
python3 .claude/skills/agy-dot-coordinator/tests/test_ping_dots_timeout.py && \
python3 -m unittest tests/test_simple_dot_ping.py tests/test_dot_recovery_prompt.py tests/test_agy_dot_coordinator.py tests/test_dot_coordinator_checkback_contract.py
```
Expected: All 6 test suites PASS with 0 failures and zero live LLM calls.

**Step 5: Commit**

```bash
git add .claude/skills/agy-dot-coordinator/SKILL.md .claude/skills/agy-dot-coordinator/scripts/ping-dots.py .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py
git commit -m "gemini/gemini-4-argon: feat(coordinator): replace regex/marker heuristics with ZFC LLM reply classifier [gemini][gemini-4-argon]"
```

---

### Task 3: Sync, Reinstall, and Rerun on macOS and Linux (`<linux-host>`)

**Files:**
- Modify (runtime install on macOS): `~/.claude/skills/agy-dot-coordinator/`
- Modify (runtime install on Linux `<linux-host>`): `<linux-host>:~/.claude/skills/agy-dot-coordinator/`

**Step 1: Diff-check, sync, and run installed unit tests on both macOS and `<linux-host>`**

- Inspect `diff -ru ~/.claude/skills/agy-dot-coordinator/ .claude/skills/agy-dot-coordinator/` on macOS and via SSH on `<linux-host>` to confirm no unmerged local runtime edits are overwritten.
- Sync `.claude/skills/agy-dot-coordinator/` to `~/.claude/skills/agy-dot-coordinator/` on macOS and to `<linux-host>:~/.claude/skills/agy-dot-coordinator/`.
- Run `test_reminder_compliance.py` and `test_ping_dots_timeout.py` on both macOS and `<linux-host>`.

**Step 2: Reinstall native scheduler services on macOS and Linux**

- On macOS:
  ```bash
  /bin/bash ~/.claude/skills/agy-dot-coordinator/scripts/install-service.sh
  ```
  Expected: `SUCCESS: ai.gemini.agy-dot-coordinator is registered.`
- On Linux (`<linux-host>`):
  ```bash
  ssh <linux-host> '/bin/bash ~/.claude/skills/agy-dot-coordinator/scripts/install-service.sh'
  ```
  Expected: `ai.gemini.agy-dot-coordinator.timer` enabled and listed in `systemctl --user list-timers`.

**Step 3: Rerun live coordinator generation, classification, and due-slot execution on macOS and Linux**

- On macOS:
  1. Run `~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-wrapper.sh --account test --generate-only` to verify live provider generation.
  2. Run a live LLM classification check invoking `classify_response()` from `~/.claude/skills/agy-dot-coordinator/scripts/ping-dots.py` against the real `dot.sh --account test read 12000` conversation tail (verifying live LLM classification returns `'idle_refusal'` on the 2026-10-13 refusal tail rather than `'compliant'`).
  3. Run `~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-wrapper.sh --account test` with `COORDINATOR_RESPONSE_WAIT_SECS=30 COORDINATOR_RESPONSE_RECHECK_SECS=30` to execute a full live ping + ZFC LLM response verification cycle on macOS.
- On Linux (`<linux-host>`):
  1. Run `ssh <linux-host> '~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-wrapper.sh --account <account-b> --generate-only'` to verify live provider generation on Linux.
  2. Run a live LLM classification check on `<linux-host>` invoking `classify_response()` via the installed `~/.claude/skills/agy-dot-coordinator/scripts/ping-dots.py` against a real reminder + reply payload to verify live LLM classification over the Linux provider ladder.
  3. Run `ssh <linux-host> '~/.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-wrapper.sh'` to verify live scheduled wrapper execution on Linux.

---

## TDD Plan Check

| Task | Behavior Change? | TDD Sequence Verified | Verification Command |
|---|---|---|---|
| Task 1: Parameterize `generate` + `parse_verdict` + `extract_reply_after_reminder` | Yes | Write failing tests in `test_reminder_compliance.py` → verify FAIL (`AttributeError: parse_verdict`) → implement in `ping-dots.py` → verify PASS → commit | `python3 .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py` |
| Task 2: ZFC LLM `classify_response` + `idle_refusal` escalation | Yes | Write failing hermetic tests asserting `STATUS_MARKERS` removal, `<dot_reply>` fencing, fallback ladder, and LLM `idle_refusal` detection → verify FAIL → implement in `ping-dots.py` and `SKILL.md` → verify PASS across all 6 test suites → commit | `python3 .claude/skills/agy-dot-coordinator/tests/test_reminder_compliance.py && python3 .claude/skills/agy-dot-coordinator/tests/test_ping_dots_timeout.py && python3 -m unittest tests/test_simple_dot_ping.py tests/test_dot_recovery_prompt.py tests/test_agy_dot_coordinator.py tests/test_dot_coordinator_checkback_contract.py` |
| Task 3: Cross-host reinstall & live rerun (macOS + `<linux-host>`) | Operational deployment (`TDD: N/A` — deploys code already TDD-verified in Tasks 1–2 to local/remote runtime dirs and reloads `launchd`/`systemd`) | Verified by running installed unit tests on both hosts, checking `launchctl list` / `systemctl --user list-timers`, and executing live `ping-dots.py` generation and classification runs on macOS and `<linux-host>` | `/bin/bash ~/.claude/skills/agy-dot-coordinator/scripts/install-service.sh` and `ssh <linux-host> '/bin/bash ~/.claude/skills/agy-dot-coordinator/scripts/install-service.sh'` |

## Implementation Preconditions

- Local macOS `launchd` user domain (`gui/$UID`) and `~/.claude/skills/agy-dot-coordinator/` exist.
- SSH access to `<linux-host>` (`<linux-host>`) and remote `~/.claude/skills/agy-dot-coordinator/` exist (verified via `ssh -o ConnectTimeout=5 <linux-host> 'hostname && ls -la ~/.claude/skills/agy-dot-coordinator/scripts/'`).
- LLM provider credentials (`lunaroute key` / `LUNAROUTE_API_KEY`, `MINIMAX_API_KEY`, `codex`, `GEMINI_API_KEY` / `WORLDAI_DEV_GEMINI_API_KEY`) are sourced by `agy-dot-coordinator-wrapper.sh` from `~/.bashrc`.
