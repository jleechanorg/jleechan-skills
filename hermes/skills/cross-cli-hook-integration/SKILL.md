---
name: cross-cli-hook-integration
version: 1.0.0
description: |
  Ship a CLI lifecycle hook (Stop, PreToolUse, PostToolUse, SessionStart,
  UserPromptSubmit) that runs correctly across Claude Code, Codex, Cursor
  Agent, Antigravity (Gemini CLI's antigravity branding), and agy. The four
  CLIs disagree on (a) where they discover hook scripts, (b) what payload
  shape they send on stdin, (c) which JSON fields they honor in the
  response, and (d) which event names they emit. Vendor docs are load-bearing
  for shape but silently omit the discovery indirection; only running real
  CLI sessions reveals the ground truth. Verified 2026-07-30 against Claude
  v2.1.220, Codex 0.144.5, Cursor 3.11.13, Antigravity, agy 1.1.8.
triggers:
  - "cross cli hook"
  - "hook for claude codex cursor antigravity agy"
  - "port hook across CLIs"
  - "normalize hook payload"
  - "stop hook all CLIs"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
context: inline
---

# Cross-CLI Hook Integration

A class-level recipe for any hook that must run on more than one of:
**Claude Code / Codex / Cursor / Antigravity / agy**. Covers discovery
indirection (where each CLI looks for hook files), payload shape (what
each CLI writes to stdin), response schema (what JSON each CLI honors),
and the post-deploy verification protocol.

The hard-won lesson: **vendor docs are necessary but not sufficient.**
Every cross-CLI hook bug class in this repo (2026-07-17 Codex apply_patch
case-sensitivity, 2026-07-30 Claude/Codex Stop schema divergence) had a
fixture-tested unit suite that passed against fixtures the agent wrote
from the docs. The bugs only surfaced when a real CLI session drove the
hook with a real payload. Treat the live-payload capture protocol in §4
as mandatory, not optional.

## 1. Discovery indirection — where each CLI looks for hooks

This is the #1 source of "I shipped a hook but nothing fires" bugs.
Vendor docs list a flat `~/.claude/settings.json` / `~/.codex/hooks.json`
path but omit the *indirection* layers (wrapper scripts, fallback
chains, dispatch routers). Get this wrong and the hook silently never
runs.

### 1.1 Claude Code v2.1.220+

`~/.claude/settings.json` → `hooks.<EventName>[].hooks[]` is the
authoritative location. Events: `PreToolUse`, `PostToolUse`,
`UserPromptSubmit`, `Stop`, `SessionStart`, `SubagentStart`,
`SubagentStop`, `PreCompact`, `PostCompact`, `Notification`.

There is **no `stop-hook-dispatch.sh` indirection** — whatever you put
in the `Stop` array fires directly. Claude runs every hook in the array
in order, with the JSON response from one hook becoming the input to the
next (chain semantics). If you want the cross-cli hook to always run,
append it as the FIRST entry in `Stop`.

Project-local hooks live in `<repo>/.claude/settings.json` and are
honored for Claude sessions launched from inside that repo.

### 1.2 Codex 0.144.5+ (verified 2026-07-30)

Codex has TWO indirection layers most agents miss:

**Layer A — `~/.codex/hooks.json` `Stop` array is NOT executed
directly.** It dispatches to `~/.codex/stop-hook-dispatch.sh` (verified
on this machine, 49 lines). The dispatch script:

1. reads the cwd from the payload,
2. checks for `<cwd>/.codex/hooks.json` Stop config,
3. **sets `local_stop_configured=true` to suppress the legacy fallback
   — but does NOT actually run the project's Stop hooks.**

So your project-local `codex_hooks.json` (or even `.codex/hooks.json`)
Stop entries will be observed (the dispatch sets a flag) but never
executed. The actual hook that fires is whatever
`stop-hook-dispatch.sh` decides to invoke.

**Layer B — `codex_hooks.json` at the repo root (no dot prefix) is
NEVER read.** Codex only reads `<cwd>/.codex/hooks.json` and
`~/.codex/hooks.json`. Files named `codex_hooks.json` (which is the
historical name in `jleechanorg/claude-commands`) are decoration.

**To make a new hook actually run in Codex:**

```bash
# 1. Drop the hook script in a discoverable location.
cp .codex/hooks/cross_cli_status.py ~/.codex/hooks/cross_cli_status.py

# 2. Replace the dispatch script with one that runs your hook.
cp .codex/stop-hook-dispatch.sh ~/.codex/stop-hook-dispatch.sh

# 3. The dispatch script must explicitly invoke your hook; don't rely
#    on <repo>/.codex/hooks.json being read.
```

The new dispatch script's shape (verified pattern, 2026-07-30):

```bash
#!/usr/bin/env bash
set -euo pipefail
input="$(cat)"

# Primary: cross-CLI status hook (always run)
for cand in \
  "${cwd:-.}/.claude/hooks/cross_cli_status.py" \
  "${cwd:-.}/.codex/hooks/cross_cli_status.py" \
  "$HOME/.claude/hooks/cross_cli_status.py" \
  "$HOME/.codex/hooks/cross_cli_status.py"; do
  if [ -x "$cand" ]; then
    HERMES_HOOK_CLI=codex HERMES_HOOK_EVENT=Stop \
      printf '%s' "$input" | python3 "$cand" --no-header || true
    break
  fi
done

# Secondary: mem0 save (preserve legacy behavior)
# Tertiary: legacy stop-git-header-json.sh fallback (only if cross-cli absent)
echo '{"continue":true}'
```

### 1.3 Cursor 3.11.13+ (cursor agent)

`~/.cursor/hooks.json` (or `<repo>/.cursor/hooks.json`). Events: `stop`,
`beforeSubmitPrompt`, `beforeReadFile`, `afterFileEdit`,
`beforeMCPExecution`, `afterMCPExecution`, `preCompact`. Schema is
unstable; pin to the exact Cursor version in your fixtures.

### 1.4 Antigravity (Gemini CLI variant)

`~/.gemini/hooks.toml` (TOML, not JSON) for `BeforeTool` / `BeforeModel`
/ `AfterModel` / `AfterAgent`. The Gemini event names are lowercase;
Claude uses `PreToolUse` / `PostToolUse`. **There is no documented
"Stop" event in Antigravity** — the closest analogue is `AfterAgent`,
which fires once per turn.

### 1.5 agy 1.1.8+

agy wraps an OpenAI-compatible envelope around Claude/Codex payloads.
It does not have its own hook system — install the cross-cli hook in
`~/.claude/hooks/` (Claude's location) and agy will fire it. Mark the
record with `HERMES_HOOK_CLI=agy` so the extractor picks the right
shape.

## 2. Payload shape — what each CLI writes to stdin

Verified 2026-07-30 against real `claude --print` and `codex exec`
sessions. See `references/live-payload-capture-2026-07-30.md` for the
raw transcript + the schema registry.

### 2.1 Claude v2.1.220 `Stop` payload

```json
{
  "cwd": "/private/tmp/cc-hooks-ratelimit",
  "session_id": "c726962e-3185-4681-aec2-313689a33360",
  "transcript_path": "...transcript.jsonl",
  "prompt_id": "550e8400-...",
  "last_assistant_message": "ping",
  "stop_hook_active": false,
  "session_crons": [],
  "effort": {"level": "medium"},
  "background_tasks": [],
  "permission_mode": "bypassPermissions",
  "hook_event_name": "Stop"
}
```

**Notable:** the Stop payload does **NOT** carry `model`,
`context_window`, or `cost` — those appear only in the **statusline**
payload, which is a different code path. Hooks that need those fields
must subscribe to the statusline, not Stop.

### 2.2 Codex 0.144.5 `Stop` payload

```json
{
  "cwd": "/private/tmp/cc-hooks-ratelimit",
  "hook_event_name": "stop",                       // ← lowercase
  "last_assistant_message": "pong",
  "model": "gpt-6-sol",                            // ← top-level STRING
  "permission_mode": "bypassPermissions",
  "session_id": "019fb560-...",
  "stop_hook_active": false,
  "transcript_path": "...transcript.jsonl",
  "turn_id": "019fb560-..."
}
```

**Notable:** Codex's Stop payload also lacks `usage` (tokens + cost).
The "tokens used N" line in Codex's CLI output is rendered from a
separate, non-hook channel. The `model` field is a top-level STRING
(not a dict) in Stop, contrasting with the `model.{id,display_name}`
dict in the statusline.

### 2.3 The casing disambiguator

Both CLIs share `stop_hook_active`, `session_id`, and
`transcript_path`. The reliable disambiguator is the *casing* of
`hook_event_name`:

| CLI | `hook_event_name` value |
|---|---|
| Claude | `"Stop"` (capital S) |
| Codex | `"stop"` (lowercase) |
| Cursor | event name not in payload (separate field) |
| Antigravity | `"AfterAgent"` (CamelCase) |

Add a fallback: Claude also publishes `session_crons` and `effort`
that Codex never does. So the detector reads:

```python
if "stop_hook_active" in payload and (
    payload.get("hook_event_name") == "Stop"
    or "session_crons" in payload
    or "effort" in payload
):
    return "claude"
```

## 3. Response schema — what JSON each CLI honors

### 3.1 Claude `Stop`

- `continue: false` + `stopReason: "..."` blocks the turn and surfaces
  the reason.
- `additionalContext: "..."` is appended to the next prompt.
- Any other fields are ignored.

### 3.2 Codex `Stop`

- `{ "continue": true }` is the **only** supported response shape.
- `{ "continue": false, "stopReason": "..." }` is parsed but **not
  supported** — Codex marks the hook as failed and continues anyway.
  Verified on learn.chatgpt.com/docs/hooks.md, 2026-07-17.
- Always exit 0 with `{ "continue": true }` on success. Exit non-zero
  is treated as a failure; the tool / turn continues.

### 3.3 Cursor `stop`

- `StopHookOutput = { followup_message?: string }`.
- Empty `{}` is treated as "no followup"; the agent stays stopped.
- Returning a `followup_message` re-prompts the agent with that text
  appended to its context.

### 3.4 Antigravity `AfterAgent`

- `decision: "allow" | "deny" | "block"` controls the next turn.
- `reason: "..."` is surfaced to the UI when blocked.
- There is no documented "followup_message" or "additionalContext"
  field; the only meaningful output is the decision.

## 4. The live-payload capture protocol (mandatory)

**Rule: never trust fixture tests against docs alone. Always run real
CLI sessions before the /er PASS verdict.**

Three concrete steps:

### 4.1 Capture the actual payload

For each CLI you support:

```bash
# Claude
timeout 60 claude --print --dangerously-skip-permissions \
  'Reply with the single word: ping' >/dev/null
jq '.' "$HOME/.claude/var/cross_cli_status/last.json"

# Codex
timeout 60 codex exec --dangerously-bypass-approvals-and-sandbox \
  'Reply with the single word: pong' >/dev/null
jq '.' "$HOME/.claude/var/cross_cli_status/last.json"
```

If the JSON file is missing or empty, the hook did not fire — go back
to §1 and re-verify discovery indirection before debugging anything
else.

### 4.2 Bake the captured payloads into unit-test fixtures

The fixtures in `tests/test_cross_cli_status.py::CLAUDE_LIVE_PAYLOAD`
and `tests/test_cross_cli_status.py::CODEX_LIVE_PAYLOAD` are the
**regression-test ground truth** — they assert "this is what the hook
actually receives from a real CLI session." If a future vendor update
changes the payload shape, the unit tests fail FIRST and the agent
updates both the extractor and the fixture in lockstep.

### 4.3 Add a regression test for every schema drift you find

Every bug class found in §3 (Codex `continue:false` ignored, Claude
Stop missing `model`/`context_window`, Cursor no `rate_limit_pct`
field, Antigravity no public Stop event) is now a regression test:

```python
def test_claude_stop_payload_lacks_model(self) -> None:
    """Claude v2.1.220 Stop payload does NOT carry `model` or
    `context_window` (those only appear in the statusline payload)."""
    rec = parse(json.dumps(CLAUDE_LIVE_PAYLOAD))
    self.assertIsNone(rec["model"])
    self.assertIsNone(rec["context_pct"])

def test_codex_stop_payload_model_is_string(self) -> None:
    """Codex 0.144.5 Stop payload has `model` as a top-level STRING,
    not a dict."""
    rec = parse(json.dumps(CODEX_LIVE_PAYLOAD))
    self.assertIsInstance(rec["model"], str)
```

## 5. Recipe — shipping a new cross-CLI hook

1. **Pick the event** — Stop is the lowest-risk (purely informational,
   never blocks the turn). PreToolUse is the highest-stakes (controls
   tool execution; needs the full response-schema discipline in §3).

2. **Audit the existing hook** — read the current `codex_hooks/*.sh`
   (or equivalent) to find which fields are read, which are silently
   dropped, and which assumptions break under a real payload.

3. **Write the cross-CLI hook** as a single Python module that:
   - reads JSON from stdin (no other CLI),
   - detects the CLI from `HERMES_HOOK_CLI` env + payload shape
     (per §2.3),
   - normalizes fields into a single schema,
   - is fail-soft by default (writes an `unknown_cli` record rather
     than blocking the turn),
   - emits the **lowest-common-denominator response** — for Stop,
     that's `{ "continue": true }` (Codex's only supported shape).

4. **Wire it into Claude** — add to `~/.claude/settings.json` `Stop`
   array as the first entry. Copy the script to `~/.claude/hooks/`
   (or `<repo>/.claude/hooks/` for project-local).

5. **Wire it into Codex** — replace `~/.codex/stop-hook-dispatch.sh`
   with one that explicitly invokes your hook (per §1.2). Do NOT
   rely on `<repo>/codex_hooks.json` or even `<repo>/.codex/hooks.json`
   Stop entries being executed.

6. **Wire it into Cursor + Antigravity + agy** — see §1.3-1.5.

7. **Run live capture** — §4.1.

8. **Bake fixtures + regression tests** — §4.2 + §4.3.

9. **Document the schema drift** — append to the SKILL.md's
   `references/live-payload-capture-<date>.md` so future agents know
   which fields are documented-but-absent in each CLI's payload.

10. **Verify in `/er` + `/advice`** — load `advice` skill; use the
    cross-CLI schema verification recipe (now codified in
    `references/cross-cli-hook-schema-verification.md` of the advice
    skill). The 3-reviewer fan-out catches: schema-deviation bugs the
    unit tests miss (Reviewer B), implementation bugs the docs didn't
    cover (Reviewer A), bypass / loop-storm edge cases (Reviewer C).

## 6. Known limitations (don't promise more than the hooks deliver)

| Limitation | Why | Mitigation |
|---|---|---|
| Claude v2.1.220 Stop has no `model` / `context_window` / `cost` | Those are statusline-only | Subscribe to the statusline event for those fields; record `null` in the Stop record |
| Codex 0.144.5 Stop has no `usage` (tokens/cost) | Codex renders "tokens used" outside the hook channel | Parse the Codex CLI stdout separately if you need tokens/cost; don't expect them in the hook payload |
| Cursor `stop` exposes no rate-limit % fields | Cursor app surfaces RL% in the UI badge, not the hook payload | Heuristic: `status="error" + loop_count >= 4` → `rate_limit_pct=100, window="loop_storm"` (signals a Cursor loop storm) |
| Antigravity `AfterAgent` schema is undocumented | Gemini CLI variant has no published Stop payload | Surface whatever Gemini-shape fields are present; `decision` is the only reliable signal |
| Codex's `unified_exec` skips PreToolUse | Codex 0.144+ has a second shell-call path that bypasses the hook chain (verified 2026-07-17) | Hook is a guardrail not a boundary; pair with sandbox + approval policy + audit log |

## 7. References

- Companion skill: `~/.claude/skills/cross-cli-status-hook/SKILL.md` —
  the worked example: a single Python Stop hook that handles all five
  CLIs, with 20 unit tests + a live-tmux integration suite.
- Cross-reference: `~/.hermes/skills/advice/SKILL.md` →
  "Cross-CLI hook schema verification recipe (added 2026-07-15)" —
  the `/advice` recipe for verifying vendor-docs claims before
  shipping a cross-CLI hook.
- Cross-reference: `~/.hermes/skills/codex-path-deletion-guard/SKILL.md`
  → "Pitfall #0" — Codex 0.144+ has a `unified_exec` shell path that
  skips PreToolUse hooks entirely. Verified regression on 2026-07-17.
