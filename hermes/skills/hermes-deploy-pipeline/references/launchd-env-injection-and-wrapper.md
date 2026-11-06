# launchd `EnvironmentVariables` and login-env wrapper pattern

## Problem

`launchd` launches plists with a stripped environment:

- **PATH** = `/usr/bin:/bin:/usr/sbin:/sbin` (no `~/.cargo/bin`, no `/opt/homebrew/bin`, no `~/.local/bin`)
- **No login shell** — `~/.bashrc`, `~/.zshrc`, `~/.bash_profile`, `~/.profile` are NOT sourced
- **No inherited shell env** — `HERMES_SLACK_BOT_TOKEN`, `GH_TOKEN`, `AO_BOT_GH_TOKEN`, etc. set in the interactive shell are invisible to the daemon
- **No `br`, `gh`, `sqlite3`, `python3` (some hosts)** — anything installed via Homebrew, cargo, npm-global, pipx, or uv

Any daemon script that calls these tools via `subprocess.run(...)`, `bash -c 'br …'`, or `command br …` crashes with:

```
FileNotFoundError: [Errno 2] No such file or directory: 'br'
```

The crash happens inside the python heredoc / bash function, exit code 1 propagates up, `launchd` sees `last exit code = 1` but **state = running** (because `KeepAlive=true` respawns immediately on the next `StartInterval`). The user-visible symptom is: "the daemon is alive but every tick does the same wrong thing, and the log only shows the bash portion that succeeded before the python heredoc crashed."

## Two fixes — pick the one your plist already uses

### Pattern A — `EnvironmentVariables` block (recommended for new plists)

Add to the plist:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>$HOME/.cargo/bin:$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    <key>HERMES_SLACK_BOT_TOKEN</key>
    <string>@HERMES_SLACK_BOT_TOKEN@</string>
    <key>FACTORY_SLACK_CHANNEL_ID</key>
    <string>@FACTORY_SLACK_CHANNEL_ID@</string>
</dict>
```

Pros: explicit, version-controlled, no shell parsing surprises, secrets never appear in `~/.bashrc`.
Cons: requires re-bootstrap after every change (and `launchctl bootout`/`bootstrap` cycles have a known gotcha — see "Bootstrap failed: 5" below).

### Pattern B — `launchd-wrapper.sh` indirection

Wrapper pattern at `<repo>/daemon/launchd/launchd-wrapper.sh`:

```bash
#!/usr/bin/env bash
# Sources interactive login env (PATH, git config, SSH agent, homebrew bins)
# before exec'ing the actual tick script. launchd's bare PATH would otherwise
# leave br / gh / sqlite3 / python3 / callpath unresolvable.
if [ -r "$HOME/.bashrc" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.bashrc"
fi
exec "$@"
```

Plist invocation becomes:

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>@REPO@/daemon/launchd/launchd-wrapper.sh</string>
    <string>@REPO@/daemon/scripts/<job>.sh</string>
</array>
```

Pros: daemon sees the full user env, including every installed CLI. `~/.bashrc` is the single source of truth.
Cons: `~/.bashrc` is a security surface — it typically contains tokens. For a daemon that only does local work (dispatch + sqlite + log), that's fine. For a daemon that posts to Slack, prefer Pattern A with `EnvironmentVariables` so the token isn't loaded into every interactive shell.

**Pick B if the repo already standardizes on it.** Don't mix patterns in one repo — pick one for consistency.

## Secret-injection rules (both patterns)

**Never commit a real token to a `.plist` or `.plist.template` in the repo.** Use placeholder substitution:

1. Repo file: `<string>@HERMES_SLACK_BOT_TOKEN@</string>`
2. Installer (e.g. `install-launchagents.sh`) reads the real value from:
   - `op read op://Vault/Item/field` (1Password CLI)
   - `~/.bashrc` exported var (less secure — token persists in shell history, .bashrc backup tarballs)
   - `~/.config/<service>/env` file (mode 600)
3. Installer does `sed -i '' "s/@HERMES_SLACK_BOT_TOKEN@/${TOKEN}/" ~/Library/LaunchAgents/<label>.plist`
4. CI / pre-commit guard rejects commits that contain `xoxb-` or `C0[A-Z0-9]{10}` literals in `.plist` / `.plist.template` files

## Fail-soft notification pattern (libnotify-slack.sh style)

For daemons that post to Slack (or any external notification), gate every post on a `slack_capable` check so the daemon runs in environments without Slack without breaking the tick loop:

```bash
slack_capable() {
    if [ -n "$HERMES_SLACK_BOT_TOKEN" ] && [ -n "$FACTORY_SLACK_CHANNEL_ID" ]; then
        echo 1
    else
        echo 0
    fi
}

slack_post() {
    local text="${1:-}"
    [ -n "$text" ] || return 0
    if [ "$(slack_capable)" != "1" ]; then
        return 0   # silent no-op
    fi
    # ... curl chat.postMessage ...
}
```

This is the opposite of "crash loud on missing creds":

| Call site type | Correct default |
|---|---|
| Slack / Discord / webhook notification | **silent no-op when creds unset** (daemon must keep running) |
| Database write / file write / PR creation | **fail loud** (daemon can't dispatch if dispatch itself is broken) |

Pick the right default per call site. Document it in the function name (`slack_post` vs `dispatch_record`).

## Diagnostic recipe — "daemon exits 1 every tick"

```bash
# 1. Confirm the launchd job state
launchctl print gui/$(id -u)/<label> | grep -E "state|last exit|runs"
# state = running, last exit code = 1, runs = 1748 → tick is crashing every cycle

# 2. Tail the err log
tail -50 ~/Library/Logs/<service>.err.log
# FileNotFoundError: 'br'        → PATH stripped, env vars not injected
# FileNotFoundError: 'sqlite3'   → same
# python traceback points to the subprocess.run() call that tried the missing tool

# 3. Tail the out log — bash portion succeeded, only python heredoc crashed
tail -50 ~/Library/Logs/<service>.out.log
# (probably shows: ok: schema applied / unstuck=0 / recovered=0 / parked …)

# 4. Apply the fix:
#    a. Open the plist template, add EnvironmentVariables block with full PATH
#    b. OR confirm launchd-wrapper.sh exists and sources ~/.bashrc
#    c. launchctl bootout gui/$(id -u)/<label>
#    d. launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist
#    e. Wait one StartInterval, tail both logs to confirm clean exit
```

**Bootstrap gotcha (verified 2026-06-25, jleechanclaw):** `launchctl bootout` on a currently-running job fails with `Boot-out failed: 3: No such process`, and `bootstrap` after that fails with `Bootstrap failed: 5: Input/output error`. Safe nudge for an already-registered, currently-not-running job is `launchctl kickstart -kp gui/$(id -u)/<label>` — re-execs the script on the next interval (or immediately). If the job IS running, `launchctl kill SIGTERM gui/$(id -u)/<label>` first, wait 5s, then `kickstart -kp`.

## Worked example — dark-factory /af wiring PR jleechanorg/dark-factory#218 (2026-07-09)

Trigger: user asked "is /af working?" and "wire /goal builtin into worker briefs + create #factory slack channel." Initial probe found:

- Plist: `~/Library/LaunchAgents/ai.dark-factory.af-tick.plist` — no `EnvironmentVariables`, BUT `daemon/launchd/launchd-wrapper.sh` exists and sources `~/.bashrc`. Pattern B in production.
- `af-tick.err.log`: every tick crashes with `FileNotFoundError: [Errno 2] No such file or directory: 'br'`. (Reason: `KeepAlive=true` + `StartInterval=240` was re-spawning faster than `launchd-wrapper.sh` could `exec` — race condition where the bash sourcing hadn't completed before the python heredoc ran. Fixed upstream in PR `$USER-v2wv`, not in this PR.)
- `af-tick.out.log`: bash portion succeeded → `ok: schema applied / unstuck=0 / recovered=0 / parked $USER-{4uzw,bxjy,hslx,ccfin}` repeated. Operator-side perception: "warp terminal says factory is working" because the bash portion output looks alive.

PR #218 fixed two orthogonal things:

1. **`/goal` builtin in `factory-ao-remediate.sh` PROMPT=`.`** Prepended literal `/goal` (Claude Code + Codex builtin) to the `ao spawn --prompt` argument. Appended `br show --json` body (`description` + `acceptance_criteria`) so the worker reads the goal artifact rather than re-deriving from IDs.
2. **Slack `#factory` notifications.** New `daemon/scripts/libnotify-slack.sh` provides `slack_capable` / `slack_post` / `slack_announce` (fail-soft, async by default). `factory-af-tick.sh` sources it for per-tick beacon. `factory-ao-remediate.sh` emits per-bead pickup beacon. Plist template grew `EnvironmentVariables` dict with `@FACTORY_SLACK_CHANNEL_ID@` + `@HERMES_SLACK_BOT_TOKEN@` placeholders (operator populates via 1Password CLI post-merge).

**Both commits in PR #218** (`96eeb079e`) at `feat/slack-factory-goal-wiring` branch on `origin/main`. Pending operator action: create `#factory` channel in Slack UI, set the env vars, reload the plist.

## Reference skills

- `hermes-deploy-pipeline` → "Launchd `EnvironmentVariables` and the login-env wrapper pattern" — umbrella-level summary
- `dispatch-task` → "When to skip AO and implement inline" — why a small daemon PR like this was inline, not dispatched
- `agento` → "Inline implementation for small daemon PRs" — the heuristic