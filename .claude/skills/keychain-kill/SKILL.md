---
name: keychain-kill
description: "Diagnose and clear macOS SecurityAgent keychain prompts caused by a headless/background process (launchd, cron, isolated tmux agents). Scoped: terminates only prompts whose parent chain descends from the current session, never a machine-wide pattern kill. Slash command: /keychain_kill."
scope: user
---

# macOS Keychain Kill & Headless Keyring Troubleshooting

Diagnose why macOS `SecurityAgent` prompts are appearing for a headless process, terminate only the prompts this session caused, and fix the underlying keyring-access cause with a credential the worker owns.

## 1. Scoped Dismissal (diagnose, then kill only your own)

When a headless process triggers keychain lookups, macOS launches `SecurityAgent` to request password entry from the user. If the process is backgrounded, it hangs recursively.

### Scope the kill to the prompts THIS session caused

`SecurityAgent` is a shared system agent. A blind `pkill -9 -f SecurityAgent` (the previous
instruction here) kills **every** pending authentication request on the machine, including
another agent's, another user process's, or the operator's own password prompt mid-typing.
That is why this step is no longer "run it first".

Diagnose before killing, then terminate only what this session caused:

```bash
# 1. Who is asking? List candidate authentication agents; Step 2 checks lineage.
ps -Ao pid,ppid,stat,etime,args | grep -Ei '[S]ecurityAgent|[U]niversalAccessAuthWarn'

# 2. Only proceed if an authentication agent's parent chain descends from THIS
#    session (the tmux/launchd/agent process you are working on). Replace
#    <session-pid>. This prints only matching executable names, with PID, PPID,
#    and the full command line from the same process snapshot.
ps -Ao pid=,ppid=,args= | awk -v root="<session-pid>" '
  { ppid[$1]=$2; executable[$1]=$3; line[$1]=$0 }
  END { for (p in ppid) { q=p; n=0
          while (q!="" && q!=0 && n<40) {
            if (q==root) {
              name=executable[p]
              sub(/^.*\//, "", name)
              sub(/^\[/, "", name); sub(/\]$/, "", name)
              if (p!=root && (name=="SecurityAgent" || name=="universalAccessAuthWarn")) {
                print line[p]
              }
              break
            }
            q=ppid[q]; n++
          }
        }
  }'

# 3. For a candidate PID, record its start time, PPID, executable, and full
#    command line. Immediately before signaling, re-read those fields and
#    re-trace its current parent chain to this session. If any identity field
#    differs from the recorded candidate, or its lineage no longer reaches this
#    session, stop. Send TERM only to that confirmed PID.
ps -p <pid> -o pid= -o ppid= -o lstart= -o comm= -o args=
kill -TERM <pid>

# 4. Wait briefly, then read the same identity fields again. If that exact
#    process has exited, stop. If the PID is absent or now identifies another
#    process, stop. A successful TERM command only means the signal was sent.
sleep 1
ps -p <pid> -o pid= -o ppid= -o lstart= -o comm= -o args=

# 5. Only if the same process still exists, revalidate its identity and current
#    parent chain immediately before signaling. Then use KILL on that PID.
ps -p <pid> -o pid= -o ppid= -o lstart= -o comm= -o args=
kill -KILL <pid>
```

`universalAccessAuthWarn` follows the same rule: identify, confirm, then kill the specific PIDs.

If you cannot establish that the agent descends from this session, **do not kill it** — report
the prompt and let the operator dismiss it. Killing an unrelated auth dialog loses whatever
they were authenticating.

Record in your response which PIDs you terminated and how you established the lineage.

## 2. Root Cause & Architectural Permanent Fix

Headless background agents (e.g. running under tmux or `ai.hermes.prod` launchd daemons) operate in separate security sessions where the user's main login keychain (`$HOME/Library/Keychains/login.keychain-db`) is locked. When SCM tools (`gh`, `git`, or `claude` authentication modules) attempt to check credentials, they query the locked login keychain, triggering the OS prompt.

### Bypassing Keychain Lookups inside Background Workers

The permanent solution requires isolating background SCM operations from the locked GUI login keychain:

1. **Give the worker its own credentials instead of the operator's keychain.**
   The durable fix is for the background process to authenticate with a credential it owns:
   a service account, a token in the process environment, or
   `git config credential.helper` pointing at a store that is not the GUI login keychain.
   For `gh`, use an already-provisioned `GH_TOKEN` or `GITHUB_TOKEN` in the worker's
   process environment for headless use. Do not use `gh auth login --with-token` as a
   workaround: `gh auth login` stores tokens in the system credential store by default,
   which can trigger the same prompt. See the
   [GitHub CLI authentication guidance](https://cli.github.com/manual/gh_auth_login).
   Then no `SecurityAgent` prompt is generated in the first place.

   > **Do not** create a password-less keychain and make it the default
   > (`security create-keychain -p ""` + `security default-keychain -s`). That recipe was
   > previously recommended here and has been **removed**: a keychain with an empty
   > password whose contents are unlocked on demand is not a credential boundary. It
   > weakens every later lookup on the machine, persists after this task ends, and is
   > invisible to the operator. A per-session keychain is only acceptable when it is
   > created with a real secret supplied out-of-band and is scoped to the worker's own
   > config, never set as the system default.

2. **CLI Storage Bypasses (`--bare`)**:
   Pass `--bare` to processes that support it, so they do not write or read secure local
   storage they do not need. This is a per-invocation choice; do not make it a global default
   that hides a credential problem from the next run.

3. **Workspace trust is a decision, not a config line.**
   Do not pre-populate `trustedFolders.json` to silence trust prompts. That removes a
   security confirmation the operator is meant to see, and it applies to every future
   worktree — including untrusted ones. Report the prompt and let the operator trust the
   folder. If a workflow clones many worktrees unattended, propose an explicit, reviewed
   allowlist of paths instead of blanket trust.

## 3. Diagnostic Procedures

If keychain prompts continue to appear, perform the following checks:

1. **Find Active Security Agents**:
   Verify if a lingering SecurityAgent process is currently active:
   ```bash
   ps aux | grep -i SecurityAgent | grep -v "grep"
   ```
2. **Verify CLI Health & Non-Canonical Processes**:
   Run `ao doctor` to ensure all active background workers inherit the canonical compiled environment. Terminate outdated processes carrying old environment configurations:
   ```bash
   ao doctor --fix
   ```

## Output

Report which PIDs you terminated and the lineage evidence for each. If you could not establish lineage, say so and leave the prompt alone. If prompts recur, walk the diagnostics above, then propose a worker-owned credential — never a password-less keychain and never blanket workspace trust.
