---
name: minimax-401-diagnostic
description: Diagnose MiniMax 401 auth errors in AO workers. A redacted or invalid MINIMAX_API_KEY is one possible cause; verify current provider errors and configuration before identifying the cause or changing settings.
when_to_use: "Use when: (1) an AO worker tmux pane shows 'Please run /login · API Error: 401' or 'login fail: carry the API secret key', (2) worker is stuck waiting for input despite having 'minimax' model config, (3) /ms surfaces another 401 incident. Do NOT use for general auth issues — this skill is specifically for the MiniMax proxy 401 + /login prompt stall pattern."
allowed-tools: ["Bash", "Read", "Write", "Edit"]
context: "A redacted or invalid MINIMAX_API_KEY in the launchd configuration is one known cause of 401 errors. A /login prompt may follow a provider 401, but verify the current response and configuration before concluding that credentials or model routing caused it. Do not swap models as a substitute for diagnosis."
---

# MiniMax 401 Diagnostic

## Common symptom pattern

This sequence is one possible failure pattern; verify each step from current
provider output and worker configuration.

1. AO worker starts → hits MiniMax proxy → proxy returns `401 Unauthorized`
2. Claude Code intercepts 401 → shows `/login` prompt in tmux pane
3. Worker appears to hang ("waiting for input") but is actually blocked on `/login`
4. `tmux capture-pane` shows: `Please run /login · API Error: 401` or `login fail: carry the API secret key in the 'Authorization' field`
5. Config shows `agent: minimax` or `model: MiniMax-M2.7` — this alone does not establish the cause

## Quick Diagnosis

### Step 0 — Plist template check (do this FIRST)

```bash
# Check for unsubstituted @VAR@ tokens in the installed plist
# If any exist, bash expands them to empty → 401 on every API call
python3 - "$HOME/Library/LaunchAgents/ai.agento.lifecycle-all.plist" <<'EOF'
import plistlib, re, sys
content = open(sys.argv[1]).read()
vars = re.findall(r'@[A-Z_][A-Z0-9_]*@', content)
if vars:
    print(f'BAD: Unsubstituted tokens: {sorted(set(vars))}')
else:
    print('OK: No unsubstituted @VAR@ tokens')
EOF

# If BAD: re-run setup to regenerate plist with real env vars:
bash scripts/setup-launchd.sh lifecycle
# Then verify:
bash scripts/test-launchd-env.sh
```

Unsubstituted `@VAR@` tokens establish that the plist template was not rendered.
Use the repository's launchd setup workflow, then continue diagnosis if the
401 persists.

```bash
python3 - "$HOME/Library/LaunchAgents/ai.agento.lifecycle-all.plist" <<'EOF'
import plistlib, re, sys

with open(sys.argv[1], "rb") as source:
    data = plistlib.load(source)
variables = re.findall(r"@[A-Z_][A-Z0-9_]*@", str(data))
key = data.get("EnvironmentVariables", {}).get("MINIMAX_API_KEY", "")
print("BAD: unsubstituted plist template tokens" if variables else "OK: no template tokens")
if key == "__OPENCLAW_REDACTED__":
    print("BAD: MINIMAX_API_KEY is the redacted sentinel")
elif key:
    print("OK: MINIMAX_API_KEY is configured; value not displayed")
else:
    print("BAD: MINIMAX_API_KEY is missing")
EOF
```

Do not print the plist or retrieve the keychain item's value. For safe
credential handling, follow [cloud-ops-credential-guard](../cloud-ops-credential-guard/SKILL.md)
and the repository's launchd setup workflow.

## Full Diagnostic Steps

### Step 1: Capture the worker's tmux pane

```bash
# Find the tmux session for the stuck worker
tmux list-sessions | grep <worker-name>

# Capture the stuck state
tmux capture-pane -pt <session>:0.0 -S -100
```

Look for: `Please run /login`, `API Error: 401`, `login fail`, `MINIMAX_API_KEY`

### Step 2: Check the plist's MINIMAX_API_KEY without displaying it

```bash
python3 - "$HOME/Library/LaunchAgents/ai.agento.lifecycle-all.plist" <<'EOF'
import plistlib, sys
with open(sys.argv[1], "rb") as source:
    data = plistlib.load(source)
key = data.get("EnvironmentVariables", {}).get("MINIMAX_API_KEY", "")
if key == "__OPENCLAW_REDACTED__":
    print("BAD: redacted sentinel")
elif key:
    print("OK: configured; value not displayed")
else:
    print("BAD: missing")
EOF
```

### Step 3: Check keychain for the real key

```bash
# Check presence without leaking credential to terminal
security find-generic-password -s MINIMAX_API_KEY >/dev/null 2>&1 && echo "Keychain: MINIMAX_API_KEY present" || echo "Keychain: MINIMAX_API_KEY missing"
```

This check reports presence only. Never retrieve or print the keychain value.

### Step 4: Fix — use the repository's launchd setup workflow

```bash
# Use the repository's launchd setup to repair the service configuration
bash scripts/setup-launchd.sh lifecycle
```

Do not copy a credential into a plist or shell variable manually. Follow the
repository's launchd setup workflow and the credential-handling rules in
[cloud-ops-credential-guard](../cloud-ops-credential-guard/SKILL.md).

### Step 5: Reload the launchd service

```bash
launchctl bootout gui/$(id -u)/ai.agento.lifecycle-all
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.agento.lifecycle-all.plist
launchctl kickstart -k gui/$(id -u)/ai.agento.lifecycle-all
```

### Step 6: Verify workers recover

```bash
sleep 5
pgrep -f "lifecycle-worker" | wc -l  # Should show 12+ workers
tmux list-sessions | grep ao-        # Should show active sessions, not stuck on /login
```

## Verify Before Changing the Model

You might see `model: MiniMax-M2.7` in the config and think "just switch to Claude Opus." A model change does not establish or repair the cause of an authentication error. First:

1. Verify that the current provider response is a 401 and identify which route returned it.
2. Confirm the active worker configuration and credential-presence status without displaying credential values.
3. Change model routing only when the current configuration and provider evidence show it is the cause.

## Anti-Patterns

- **WRONG**: `ao spawn --agent codex` to "fix" the 401 — masks the symptom, wrong model for the task
- **WRONG**: `export MINIMAX_API_KEY=...` in a running shell — doesn't fix the launchd service's env
- **WRONG**: Changing `model` in agent-orchestrator.yaml without evidence that routing is the cause
- **WRONG**: Killing and respawning the worker without fixing the plist — it will hit the same 401 immediately

## Recurring Incident History

| Date | Worker | Manifestation | Root Cause |
|------|--------|---------------|------------|
| 2026-04-15 | PRs #454, #453, #452, #450, #444 | 5 PRs stuck with 401 | `__OPENCLAW_REDACTED__` in plist |
| 2026-05-01 | ao-4449 (PR #511) | `/login` + 401, stuck at "Brewed for 3m 13s" | `__OPENCLAW_REDACTED__` in plist |

## Files to Check

- `~/Library/LaunchAgents/ai.agento.lifecycle-all.plist` — MINIMAX_API_KEY value
- `scripts/setup-launchd.sh` — how MINIMAX_API_KEY is substituted into the plist
- `~/.hermes_prod/config.yaml` — MiniMax credential source

## Claim Class

This skill covers a recurring credential-related failure pattern. Verify the
current error and active configuration before applying its remediation.
