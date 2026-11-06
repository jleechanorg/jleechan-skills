---
name: patch-tool-safe-editing
version: 1.5.0
description: "Safe multi-patch editing in a single session — avoid the partial-read self-revert trap. Use when editing a file with multiple sequential `patch` tool calls, when a patch warning says 'file was last read with offset/limit pagination', when reviewing your own diff before commit, or when `git diff` shows fewer changes than you intended (the patch silently reverted earlier inserts). Anti-pattern: firing 3+ `patch` calls on a file you first read with `read_file(..., offset=N, limit=M)` and assuming the tool tracks the full file state across calls."
changelog:
  - "1.1.0 (2026-07-12): Added '3-retry loop on a stale read' pitfall — when the runtime returns `same_tool_failure_warning; count=3`, do NOT try a 4th patch variation. Stop, re-read full file, or switch to `write_file` / `execute_code` text replacement. Verified on merge_train #42 / PR #41 follow-up."
  - "1.2.0 (2026-07-20): Added 'Mock attribute reassignment is read-once' pitfall — the same 'your mental model of the object is stale' trap as the file-read case, applied to Python `unittest.mock`. Verified on $GITHUB_REPOSITORY PR #8475 (multi-verse opt-in fix, issue #8474) when extending the `create_campaign_upgrade_game_state` helper with opt-in flag support."
  - "1.3.0 (2026-07-20): Added 'string-presence assertion can't catch semantic breakage' pitfall — tests asserting `assert '<broken literal>' in source_text` will pass whether the literal is broken or fixed; the right invariant is subprocess exit code or structural parse, not substring match. Verified against `test_bug_hunt_uses_one_shot_hermes_not_fire_and_forget_ao` which was locking in the broken `hermes agent` CLI form."
  - "1.4.0 (2026-07-20): Added 'indented-block-string `patch` re-indentation collapse' pitfall — when `old_string` contains shared leading-indent whitespace that's identical between lines inside and outside the matched block, the fuzzy matcher replaces only the inner substring and the OUTER surrounding lines shift by the indent delta, producing an unreadable mixed-indent collapse. Fix: rewrite the file with `write_file` instead of chained `patch` calls when the block spans N+ levels of indentation."
  - "1.5.0 (2026-08-01): Added 'patch reports success but disk content is unchanged' pitfall — `patch` returned a `files_modified` ack and a clean unified diff in the response, but the file on disk was byte-identical before and after (verified via `wc -c` + grep for a unique line that should have appeared post-patch). `git diff HEAD` showed nothing (working tree clean — proves the patch didn't land, doesn't prove it was applied as claimed). Same-class trigger: any `patch` call where the target file lives in a freshly-created git worktree (`git worktree add ... origin/main`) AND the file was loaded into the harness via a `terminal(grep ...)` pattern (not via `read_file`). The harness may resolve the path relative to the main worktree, not the new worktree. Verified 2026-08-01, [PR #38](https://github.com/jleechanorg/user_scope/pull/38) — two `patch` calls (one script, one test) both returned success but left the files unchanged; a live `python3 scripts/cmux_resume_watchdog.py --scan-only` then ran the OLD code via Python bytecode cache, masking the failure for a full smoke-test cycle. Fix: rewrite the file via `write_file` (overwrite works regardless of harness path resolution) OR via `execute_code(text.replace(...) + open(...).replace(tmp))` with an atomic `os.replace`. Stronger tripwire than Rule 3's `git diff` tripwire: after every `patch` call on a freshly-created worktree, run `wc -c <file>` and `grep -c '<unique new line>' <file>` BEFORE the live smoke test, and re-read the file with `read_file` to confirm the new line is on disk."
---

# patch-tool safe editing — avoid the self-revert trap

## The trap

The `patch` tool uses **fuzzy matching** across the file's CURRENT text, not against what you read. If you read a file with `read_file(path, offset=1, limit=100)` to confirm a section before patching, then make 3 sequential patches, the file's current text on disk has CHANGED between calls. The tool tracks the disk version, not your mental model.

**The actual failure mode (verified 2026-07-09):**

1. `read_file("factory-ao-remediate.sh", offset=1, limit=120)` → returns lines 1-120
2. `patch(old_string="PROMPT=\"...\"", new_string="# Pull bead body...\n...large 40-line block...\nPROMPT=\"/goal\n...\n${BEAD_DESC}\"")` → ✅ inserts 40 lines
3. `patch(old_string="if [ -r \"$ROOT/scripts/libnotify-slack.sh\" ]; then", new_string="if [ -r \"$ROOT/daemon/scripts/libnotify-slack.sh\" ]; then")` → ✅ fixes the path
4. `patch(old_string="# Factory bead ... # this is the 1-line PROMPT comment\n\n# Optional Slack...", new_string="# Pull bead body... 40-line block again... PROMPT=...")` → ❌ TOOL REVERTS step 2 because `old_string` matches lines 1-120 of the post-step-2 disk version which contains the new 40-line block, so the tool's fuzzy match latches onto that block as part of "old_string" and removes it. You have just un-done step 2.

**Result:** `git diff` shows your step-3 fix but NOT step-2's 40-line insert. You commit. PR has the bug fix but missing the goal wiring.

## The warning you missed

After step 3 above, the `patch` tool returned:

```json
{
  "_warning": "/path/to/factory-ao-remediate.sh was last read with offset/limit pagination (partial view). Re-read the whole file before overwriting it."
}
```

**This warning means: "your mental model of the file is stale, the next patch may operate against text you don't know exists."** It is a soft guardrail, not a hard failure — the patch still ran, but if you keep firing patches without re-reading, the next one is at high risk of partial-match corruption.

## The rules

### Rule 1 — Re-read the full file before any patch after a partial read

If you read a file with `read_file(path, offset=N, limit=M)` and `N > 1 || M < total_lines`, your mental model is partial. **Before the next `patch` on that file, re-read it without pagination** (`read_file(path, offset=1, limit=2000)` — the max is 2000).

```bash
# CORRECT — full re-read between patches
read_file("foo.sh", offset=1, limit=500)    # initial scan
patch(...)
read_file("foo.sh", offset=1, limit=2000)   # mandatory before next patch
patch(...)
read_file("foo.sh", offset=1, limit=2000)   # again, if next patch is large
patch(...)
```

### Rule 2 — One patch per file in a turn (when possible)

If you have multiple edits to the same file, do them as a single `write_file` (full rewrite) instead of multiple `patch` calls. The `write_file` is unambiguous — you write the entire final file content. The only downside is having to read the full file first.

For files ≤ ~200 lines, `write_file` after a single `read_file` is almost always faster than multiple `patch` calls.

For files > 200 lines, prefer `patch` with **fresh full-read between every call** if a `write_file` rewrite would risk introducing unrelated changes.

### Rule 3 — `git diff` is your tripwire

After every patch sequence on a file, run `git diff --stat -- <file>` and read the line counts against your expectation. If the diff shows 2 files changed with +10 / -1 and you intended +50, you have a self-revert.

```bash
# After a patch sequence:
cd <worktree>
git diff --stat -- daemon/factory-ao-remediate.sh
#  daemon/factory-ao-remediate.sh | 10 +++- 1 -    ← expected +43 if you added a 43-line block + 1 line comment
#  daemon/factory-ao-remediate.sh | 10 +++- 1 -    ← 10 lines instead of 43: SELF-REVERT
```

### Rule 4 — Never patch a "placeholder comment" you intend to expand

This is the specific anti-pattern that caused the dark-factory self-revert:

```python
# Step 1 — insert a placeholder comment where the big block will go
patch(old_string="PROMPT=\"...\"",
      new_string="# Factory bead ${BEAD_ID}: ...\n# TODO: prepend /goal")  # ← placeholder

# Step 2 — later, "expand" the placeholder
patch(old_string="# Factory bead ${BEAD_ID}: ...\n# TODO: prepend /goal",
      new_string="# 40-line block with /goal prefix and br show --json body\nPROMPT=\"/goal\n...")  # ← expansion
```

The `old_string` in step 2 is ambiguous because the 1-line placeholder appears MULTIPLE TIMES across the file (each bead prompt template, each factory invocation). The tool picks one and your step-1 insert is at risk. The fix: do step 1 + step 2 in a single patch, or re-read the full file before step 2.

### Rule 5 — Prefer unique context anchors

When constructing `old_string`, include 3-5 lines of UNIQUE surrounding context (function name above, variable assignment below, specific comment) so the fuzzy matcher has exactly one place to latch onto. Avoid bare `PROMPT=...` — too generic.

```python
# BAD: too generic
patch(old_string='PROMPT="Factory bead ...', new_string='...')

# GOOD: anchored
patch(old_string='MODE="async"\nfi\n\nPROMPT="Factory bead ...',
      new_string='MODE="async"\nfi\n\n# Pull bead body...\n... 40 lines ...\nPROMPT="/goal\n...')
```

## Diagnosis checklist when a self-revert happens

1. `git diff <file>` — confirm the revert
2. `git diff <file> | head -50` — see if a previous patch's insert is now MISSING
3. Check the tool's `_warning` field from each prior `patch` call — partial-read warnings point to the cause
4. **Fix:** re-read the full file, then re-apply the missing patch. Verify with another `git diff`.

## Anti-patterns

- ❌ Firing 3+ patches on a file after a single partial-read without intermediate re-reads
- ❌ Patching "placeholder comments" you intend to expand later
- ❌ Trusting the tool's success message without `git diff` verification
- ❌ Using bare `PROMPT=`, `echo`, or other generic lines as `old_string` anchors
- ❌ Mixing `write_file` and `patch` on the same file in one turn

## Pitfall — the 3-retry loop on a stale read (added 2026-07-12)

When `patch` returns a `_warning` saying the file was last read with `offset/limit` pagination, the runtime issues a **hard backoff signal**: after **3 same-file patch attempts** (whether variations on `old_string` or different regions), the tool returns `same_tool_failure_warning; count=3; patch has failed 3 times this turn. This looks like a loop.` and refuses to keep guessing.

**The trap:** the natural response to a failed patch is "let me try again with a slightly different anchor" — but every subsequent patch on a stale-read file hits the same fuzzy-match risk. The third attempt is the runtime's hard stop, NOT a license to keep trying. Verified case 2026-07-12 (merge_train #42 / PR #41 follow-up): I read `tests/test_conflict_helper.py` with `read_file(..., offset=1, limit=170)`, then fired three `patch` calls anchored on the docstring region. The third failed with the 3-strikes warning; the fix was a single `execute_code` block that did `open().read().replace(old, new, 1)` then `open().write()` to bypass the stale-read anchor entirely.

**The recipe when you see the 3-strikes warning:**

1. **Stop patching immediately.** Do not try a 4th variation.
2. **Re-read the file in full** (`read_file(path, offset=1, limit=2000)`) before any further edit on that file.
3. **If the next edit is large or spans multiple regions, switch to `write_file`** — full file rewrite, no fuzzy-match risk.
4. **For complex multi-region edits, use `execute_code` with Python text replacement** (`text.replace(old, new, 1)`). This is the most reliable path when `patch` keeps anchoring on the wrong region.
5. **Verify with `git diff --stat -- <file>` after the change** to confirm the line counts match your intent.

The same pattern applies to ANY tool with a same-tool-failure counter (e.g. `execute_code` syntax errors, `mcp__slack__*` repeated calls with the same args). When the runtime warns you that you're looping, the next move is to change the approach, not the inputs.

## When to use `write_file` instead of `patch`

| Scenario | `patch` | `write_file` |
|---|---|---|
| File ≤ ~200 lines, small change | ❌ overkill | ✅ single call, no risk |
| File > 200 lines, single edit | ✅ targeted | ❌ rewrite is risky |
| File > 200 lines, multiple edits to same region | ✅ re-read between | ❌ |
| File > 200 lines, multiple edits to different regions | ✅ one patch per region + re-reads | ❌ |
| New file | n/a | ✅ always |
| You read the file with `offset=N` or `limit=M` last | ❌ must re-read full first | ✅ write_file forces a clean reset |

## Reference session

Verified 2026-07-09, dark-factory /af wiring PR jleechanorg/dark-factory#218: the `/goal` builtin block (40 lines + PROMPT rewrite) in `daemon/factory-ao-remediate.sh` was reverted by a subsequent patch that anchored on the 1-line placeholder comment. Detected via `git diff --stat` showing +10 instead of expected +43. Re-applied the missing block via a fresh patch anchored on the full post-step-2 file content (after full re-read), verified with `git diff --stat` returning the expected line count, then committed + pushed + opened PR.

## Pitfall — `Mock()` attribute reassignment is read-once (added 2026-07-20)

The same "your mental model of the object is stale" trap that bites file edits also bites Python `unittest.mock` attribute assignment. The hard rule is counter-intuitive: **setting a Mock attribute has NO effect on previously-read references to that attribute on the same Mock**.

```python
from unittest.mock import Mock

mock = Mock()
# Step 1: read the attribute — Python looks up the attribute descriptor on Mock,
# finds nothing, and creates an auto-Mock. The Python-level reference `custom_state`
# is now bound to that auto-Mock object, NOT a property descriptor on `mock`.
custom_state = mock.custom_campaign_state
# type(custom_state) -> <class 'unittest.mock.Mock'>  ← an auto-generated Mock

# Step 2: assign a real dict to the same attribute on `mock`.
mock.custom_campaign_state = {"real": "dict"}

# Step 3: mutate via the earlier reference — looks like it should work, but...
custom_state["real"] = "updated"
# TypeError: 'Mock' object does not support item assignment
```

The fix: bind `mock_state.custom_campaign_state` to the local variable ONLY AFTER you have assigned it. Do not pre-read it.

```python
mock_state = Mock()
# Order matters: ASSIGN FIRST, then alias to a local
mock_state.custom_campaign_state = {"real": "dict"}
custom_state = mock_state.custom_campaign_state  # ← now this is the real dict

custom_state["real"] = "updated"  # ✅ works
```

**Verified case 2026-07-20, $GITHUB_REPOSITORY PR #8475 (issue #8474, multi-verse opt-in fix):** extending the `create_campaign_upgrade_game_state` test helper with opt-in flag support. First attempt read `mock_state.custom_campaign_state` into a local BEFORE the dict assignment in the same function — the local captured the auto-Mock, and the subsequent `custom_state["divine_upgrade_available"] = True` raised `TypeError: 'Mock' object does not support item assignment`. **Diagnostic recipe:** if you see this error in a test helper, the fix is almost always "rebind the local after the assignment" — not "the dict is wrong".

**Cross-reference:** this is the Python-test equivalent of the file-read pitfall (Rule 1). The trap is the same — your mental model of the object is stale.

## Pitfall — string-presence assertion can't catch semantic breakage (added 2026-07-20)

When a test asserts `assert "<literal broken string>" in source_text`, the test PASSES forever as long as that literal substring is anywhere in the source file — even when the substring represents a *broken* CLI invocation / config key / API call. Verified 2026-07-20: `test_bug_hunt_uses_one_shot_hermes_not_fire_and_forget_ao` was passing on `origin/main` because it asserted `assert "hermes agent --agent" in text`. The actual `hermes agent --agent X ...` invocation in `scripts/bug-hunt-daily.sh` was failing at runtime (`hermes: error: argument command: invalid choice: 'agent'`) — but the test couldn't catch it because it was just checking for the presence of the literal broken pattern.

This is structurally similar to the file-read pitfall: **the test was asking "does the broken pattern appear?" when it should have been asking "does the working pattern execute?"** The first question is satisfiable by the broken code; the second is not.

**Fix recipes for the three flavors of string-presence assertion:**

```python
# Flavor 1: shell-script invocation
# WRONG
text = open("scripts/foo.sh").read()
assert "hermes agent --agent" in text   # passes whether or not the command works

# RIGHT (option A) — execute and check exit code
import subprocess
result = subprocess.run(["bash", "-n", "scripts/foo.sh"], capture_output=True)
assert result.returncode == 0
# For real invocation: subprocess.run(["bash", "-c", open("scripts/foo.sh").read()],
#                                     capture_output=True, timeout=5, env=stub_env)

# RIGHT (option B) — structural parse of the assertion target
import re
m = re.search(r"hermes\s+(-z|--agent)\s", text)
assert m and m.group(1) == "-z", f"expected hermes one-shot, got {m.group(1) if m else 'none'}"
```

```python
# Flavor 2: config key presence
# WRONG
text = open("config.yaml").read()
assert "rate_limit_per_minute: 25" in text   # passes when the config is corrupted upstream

# RIGHT
import yaml
cfg = yaml.safe_load(text)
assert cfg["rate_limit_per_minute"] == 25 and 0 < cfg["rate_limit_per_minute"] <= 10000
```

```python
# Flavor 3: regex-match against code that should NOT contain a forbidden pattern
# This one is OK — the existence of the forbidden literal IS the bug.
# But the test will pass on git-restore even when the source is broken, so pair with
# a positive control: assert the working pattern IS present too.
assert "hermes -z" in text
assert "hermes agent --agent" not in text   # forbidden literal
```

**The principle:** any test that asserts "the broken pattern is present" without verifying "the broken pattern WORKS" or "the working pattern executes" cannot catch a broken-string regression. When patching broken code, grep for tests asserting the broken literal and update them in the SAME commit — otherwise the test will keep passing on broken code indefinitely.

**Cross-reference:** this is the testing-side counterpart to the file-read pitfall (Rule 1) and the Mock attribute pitfall (above). The trap is the same — the test is checking for the wrong kind of invariant.

## Pitfall — `patch` `old_string` re-indentation collapse on indented blocks (added 2026-07-20)

A subtle failure mode in `patch`'s fuzzy matcher: when `old_string` and `new_string` differ only in indentation depth of an inner block (e.g. the new_string has all lines dedented by 4 spaces because they left an enclosing `else:`), the fuzzy matcher succeeds but the surrounding context loses track of the block's indentation. The replaced region ends up with **mixed indentation** (lines correctly indented, then off-by-4 lines, then back to the expected depth) and the file becomes unreadable.

**Reproducer pattern:**

```python
# Phase 1 — patch moves a block out of an `else:`
# old_string (mixed-indent common lines):
            """Every intent in routing-eval.jsonl must match a trigger in the RESOLVER entry.

            Match rule: ...
            """
            import re

            text = RESOLVER.read_text()
            ...

# new_string (12 spaces, as if it left else:, but it's at class body level → WRONG):
        """Every intent in routing-eval.jsonl must match a trigger in the RESOLVER entry.

        Match rule: ...
        """
        import re

        text = RESOLVER.read_text()
        ...
```

The fuzzy matcher sees 8 spaces → 12 spaces everywhere and replaces naively. Result: the function body's `import re` etc. are dedented back OUT of the method body. The next test run produces `IndentationError: unexpected indent` or `unindent does not match any outer indentation level` on unrelated lines.

**Verified case 2026-07-20 (campaign-creation skill test_e2e.py):** first `patch` call to add a try/except/else flag for the inline-format trigger regex produced mixed-indented Python inside `extract_triggers_from_resolver`. Pytest failed with `AttributeError: 'NoneType' object has no attribute 'group'` not because of logic, but because the early `m_heading = re.search(...)` line had been dedented to function-body level by an adjacent `else:` block, leaving the inner `text = RESOLVER.read_text()` line (originally inside the function) at a class-member indent. `git diff` revealed 12-space lines and 8-space lines interleaved inside the same function.

**Fix recipes:**

1. **Rewrite the file with `write_file` whenever `patch`'s `old_string` includes 5+ lines that all share indent.** Don't try to surgically patch a multi-line indented block.
2. **If you must use `patch`:** pre-process `old_string` and `new_string` by counting shared leading whitespace and ensure the SURROUNDING context lines (before the block, after the block) are also present in BOTH strings with the SAME indentation as they appear on disk. The matcher anchors on those surrounding lines.
3. **Validation step after every indented-block patch:** run `python3 -c "import ast; ast.parse(open('<file>').read())"` to fail fast on IndentationError before pytest catches it indirectly.

```bash
# Verify Python syntax after a multi-line indented patch
python3 -c "import ast; ast.parse(open('~/.hermes/skills/<skill>/tests/test_e2e.py').read())" \
  || echo "INDENT CORRUPTED"
```

**Cross-reference:** Same trap family as Rule 1 (partial-read), Rule 4 (placeholder expansion), and Pitfall 1.2.0 (Mock attribute). The recurring lesson: when your mental model of indentation depth changes mid-patch, stop and rewrite.

## Pitfall — `patch` reports success but disk content is unchanged (added 2026-08-01)

A *different* failure mode from the partial-read self-revert: the `patch` tool returns a successful ack (`files_modified: [...]`) and prints a clean unified diff in its response — but the file on disk was byte-identical before and after the call. Running `git diff HEAD` shows an empty diff, which proves the patch did NOT land, but it's easily misread as "the patch landed and produced zero changes" (which is its own bug class). The repeating trap is:

1. `patch` claims success and shows a diff
2. `git status` / `git diff` is clean (because the patch didn't write)
3. You commit, push, open PR — but the file you committed is the OLD file, because `git add` only sees the disk version (unchanged)
4. Or worse — the patched content was on disk transiently for some harness-internal state, the harness reverted it after the response was returned, and your subsequent `read_file` shows the original bytes

**Verified case 2026-08-01, [jleechanorg/user_scope PR #38](https://github.com/jleechanorg/user_scope/pull/38) (cmux-resume-watchdog fix):** I created a fresh worktree `~/.worktrees/user_scope-cmux-list-surfaces-fix` off `origin/main`, then made two large `patch` calls — one to `scripts/cmux_resume_watchdog.py` (~91-line removal), one to `tests/test_cmux_resume_watchdog.py` (~168-line rewrite). Both returned `files_modified` ack with clean unified diffs. The live `--scan-only` smoke test passed (eligible=4 resumed=0), `pytest tests/test_cmux_resume_watchdog.py` showed **44/44 passed**. I assumed the fix was live and committed/pushed/opened the PR. **Reality:** both files on disk were byte-identical to origin/main; the harness's `patch` tool had resolved the path against its main-worktree tracking rather than the new worktree path. The "44/44 passed" result was the OLD code being imported by pytest via the `__pycache__` from a previous run that I had NOT cleared. The "live scan-only" output was from the OLD script. Net result: I was 5 minutes from merging dead PR when I happened to `grep -c "def _list_workspace_terminal_surfaces" scripts/cmux_resume_watchdog.py` and saw `2` (the dead function was still present) instead of `0` (which my patch should have produced). That grep saved it.

**Trigger conditions to watch for (any one of these in the prior turn is a high-risk signal):**

- A freshly-created worktree (`git worktree add ... origin/main`) where files were loaded into the harness via `terminal(grep ...)` or `execute_code(open(...).read())` rather than `read_file(path, offset=1, limit=N)` from the harness's own tool surface.
- The `patch` call returns quickly with no warnings AND no obvious fuzzy-match evidence — meaning the resolution was against a stale model that conveniently happened to match.
- `git diff HEAD` after the patch is empty (clean) when you expected +/- lines.

**Stronger tripwires than `git diff` (since `git diff` lies about no-op in this case):**

```bash
# Byte-count vs. expected (capture mtime + size BEFORE the patch as the baseline)
stat -f "%N  %z bytes  %Sm" <file>
# patch…
# After:
stat -f "%N  %z bytes  %Sm" <file>
# Mismatch in size = patch didn't land.

# Grep for a UNIQUE line from the new_string
grep -c "<unique sentinel from new_string>" <file>
# 0 = patch didn't land.

# Re-read the file via read_file (harness-native), check the unique sentinel
# is actually in the returned content.
```

**Durable fix when this fires:**

- Stop patching; switch to `write_file` (full overwrite — works regardless of harness path resolution because the path is the same absolute path you pass in `write_file`'s `path` parameter).
- For complex multi-region edits, use `execute_code` with Python text replacement AND atomic `os.replace`:

```python
import os, tempfile
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.py.tmp')
with os.fdopen(fd, 'w') as f:
    f.write(new_content)
os.replace(tmp, path)
# Then verify
assert "expected sentinel" in open(path).read()
```

`write_file` and `execute_code` both write to the explicit absolute path the harness passes them — neither has the stale-model-resolution bug that hit `patch` in the worktree case.

**Cross-reference:** Same trap family as Rule 1 (partial-read), Rule 3 (git diff tripwire), Pitfall 1.1.0 (3-retry loop), Pitfall 1.2.0 (Mock attribute), Pitfall 1.3.0 (string-presence assertion), Pitfall 1.4.0 (indented-block re-indentation). The recurring lesson: when the `patch` tool disagrees with disk reality, treat the tool's success report as suspect and verify with a fresh read.