---
name: linux-mirror
description: "Mirror the current git dir/worktree/branch onto a Linux machine and continue the work session there instead of locally. Pushes the branch, checks it out remotely via SSH, and drops into a tmux session. Falls back to Slack if SSH is unreachable. Use when asked to move/continue work on the Linux box, hand off to it, or mirror this session to Linux."
---

# Linux Mirror — hand this branch off to a Linux machine

Companion to [mac-mirror](../mac-mirror/SKILL.md) (same flow, opposite direction). Unlike a plain SSH-steering skill, this mirrors the **current repo's committed state** onto the target machine and resumes work there in a persistent tmux session.

## Setup (once, per pair of machines)

This skill assumes you've already got:
- An SSH host alias for the Linux box in `~/.ssh/config` (LAN), e.g.:
  ```
  Host mylinux
      HostName 192.168.1.50
      User myusername
      IdentityFile ~/.ssh/id_mylinux
  ```
  (`ssh_config` does not expand environment variables — write your actual username literally, not `$USER`.)
- Your repo lives under `$HOME` on **both** machines, at the same relative path (e.g. `~/projects/myrepo` on both). This skill mirrors by `$HOME`-relative path; a repo outside `$HOME`, or at a different relative path on each machine, isn't supported — step 1 below checks for this and stops rather than silently producing a wrong path.
- (Optional, for off-LAN/travel use) Both machines joined to the same Tailscale tailnet. Note: a bare SSH alias like the one above resolves its `HostName` literally — it does NOT fail over to Tailscale automatically. Off-LAN, connect via the Tailscale IP directly with the identity file explicit: `ssh -i ~/.ssh/id_mylinux myusername@<tailscale-ip>` (look it up with `tailscale status | grep <hostname>` — don't hardcode it, Tailscale IPs are stable per-device but you should still re-verify rather than assume).
- (Optional, for SSH-fully-down fallback) A messaging-gateway agent (e.g. a Hermes-style gateway, or anything that runs commands on your behalf) running on the Linux box, watching a Slack channel (or similar) you can post to.

Substitute your own host alias / IP / key path / username everywhere `mylinux` / `myusername` appears below.

## What this carries over

Only **committed and pushed** state — the current branch's HEAD. Uncommitted/staged local edits are NOT transferred (that's an explicit tradeoff for a simple, reliable git-based mirror; commit or stash first if you need them).

## Steps

### 1. Detect local state

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
REMOTE_URL=$(git -C "$REPO_ROOT" remote get-url origin)
DIRTY=$(git -C "$REPO_ROOT" status --porcelain)

case "$REPO_ROOT" in
  "$HOME"/*) REL_PATH=${REPO_ROOT#"$HOME/"} ;;
  *) echo "ERROR: repo root ($REPO_ROOT) is not under \$HOME ($HOME) — this skill mirrors by \$HOME-relative path on both machines. Move or symlink the repo under \$HOME first." >&2; exit 1 ;;
esac
```

If `$BRANCH` is empty (detached HEAD) or `$DIRTY` is non-empty, stop and tell the user — commit/name the branch first.

If `$REMOTE_URL` is an HTTPS URL with an embedded credential (`https://<token>@host/...`), warn the user before continuing: that URL gets written verbatim into the remote clone's `.git/config` in step 4, so the credential ends up live on the target machine too. Prefer an SSH remote, or a credential helper that doesn't embed the token in the URL. (Step 4's base64 encoding is not a confidentiality measure for this value — it only prevents argv re-tokenization/injection. A trivially-decodable token is still visible in the remote host's `ps` output during the mirror.)

### 2. Push the branch (make it visible to the Linux machine)

```bash
git -C "$REPO_ROOT" push -u origin "$BRANCH"
```

Confirm with the user before pushing if the branch has no upstream yet or diverges from origin (normal push-safety rules apply).

### 3. Pick a connectivity tier — try in order, stop at first success. Carry the resolved connection forward into `SSH_ARGS`/`SSH_TARGET` for step 4 — don't just check reachability and then reconnect a different way.

```bash
SSH_ARGS=()
SSH_TARGET="mylinux"   # Tier 1 default: the LAN alias

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
  echo "SSH_OK via Tier 1 (LAN alias)"
else
  # Tier 2 — Tailscale SSH (off-LAN fallback, e.g. traveling with a laptop
  # while the Linux box stays home). The alias above won't fail over here —
  # target the Tailscale IP directly with the identity file explicit.
  TS_IP=$(tailscale status | awk '/<linux-hostname>/{print $1}')
  SSH_ARGS=(-i ~/.ssh/id_mylinux)
  SSH_TARGET="myusername@$TS_IP"
  if ssh "${SSH_ARGS[@]}" -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
    echo "SSH_OK via Tier 2 (Tailscale)"
  else
    SSH_TARGET=""   # neither tier reached — fall through to Tier 3 below
  fi
fi
```

**Tier 3 — Messaging-gateway handoff (SSH AND Tailscale both down, `$SSH_TARGET` empty):** if the Linux box runs a reactive gateway agent watching a Slack channel (or similar), post the exact repo/branch/commit and the steps from §4 below, asking it to execute them locally and reply when the tmux session is ready. This is a real handoff to a different agent process with no shared context — give it complete, explicit instructions.

If this tier ever seems dead, don't assume it needs a restart — two things are much likelier culprits, in order of how much time they'll save you:
1. **A missing OAuth-style scope grant on the gateway's own credential, not a connection problem.** A connection can report fully healthy — process alive, socket/session established, ping/pong succeeding — while a specific required permission was declared in the integration's config/manifest but never actually granted to the live credential (e.g. added to a Slack app's manifest after the app was already installed — the scope isn't live until the app is reinstalled/reauthorized). **Discriminating check:** call the platform's own auth-introspection endpoint with the gateway's actual live credential (for Slack: `auth.test`, or attempt the specific scoped call you need and read the error — `missing_scope` names the gap directly) rather than trusting the integration's own settings UI, which can show a scope as "configured" when it was never granted. **Remedy:** reinstall/reauthorize the app so the currently-declared scopes actually take effect — a bare process restart does not do this.
2. **A message-filtering rule you're tripping as a test artifact, not a real failure.** Many gateways correctly drop messages attributed to a bot/app identity by default (including messages posted via some *other* app's OAuth-issued token, which platforms often tag with that app's identity even when the underlying account is a real human). Verify with a message you know is genuinely human-originated — typed directly in the client, not posted via any API token — before concluding the gateway itself is broken.

Only after ruling both of these out is it worth suspecting the connection layer itself (e.g. enabling debug-level logging on the gateway process — check its actual log destination, which for a systemd-managed service is the journal, e.g. `journalctl --user -u <service>`, not necessarily its own app log file).

### 4. Remote checkout + tmux (Tier 1/2 only — skip if `$SSH_TARGET` is empty, that means Tier 3 applies instead)

Arguments are base64-encoded before crossing the wire. This isn't just a quoting nicety: `ssh host command args...` does not preserve argv separation — the remote login shell re-joins and re-tokenizes the command line, so an unencoded branch name containing a space silently shifts which value lands in `$1`/`$2`/`$3`, and one containing shell metacharacters (`;`, `` ` ``, `$()`, `&&`, `|` — all valid in a git branch name) executes arbitrary commands on the remote host. Base64 output contains none of those characters, so encoding closes both problems regardless of what the original value contains.

```bash
REL_PATH_B64=$(printf '%s' "$REL_PATH" | base64 | tr -d '\n')
BRANCH_B64=$(printf '%s' "$BRANCH" | base64 | tr -d '\n')
REMOTE_URL_B64=$(printf '%s' "$REMOTE_URL" | base64 | tr -d '\n')

ssh "${SSH_ARGS[@]}" "$SSH_TARGET" bash -s -- "$REL_PATH_B64" "$BRANCH_B64" "$REMOTE_URL_B64" << 'EOF'
set -e
REL_PATH=$(printf '%s' "$1" | base64 -d)
BRANCH=$(printf '%s' "$2" | base64 -d)
REMOTE_URL=$(printf '%s' "$3" | base64 -d)
TARGET="$HOME/$REL_PATH"

if [ ! -e "$TARGET/.git" ]; then
  mkdir -p "$(dirname "$TARGET")"
  git clone "$REMOTE_URL" "$TARGET"
fi

cd "$TARGET"

ORIGIN_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -n "$ORIGIN_URL" ] && [ "$ORIGIN_URL" != "$REMOTE_URL" ]; then
  echo "ERROR:$TARGET already has a different origin ($ORIGIN_URL) — not touching it, resolve manually" >&2
  exit 1
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "ERROR:$TARGET has uncommitted changes on the remote side — not overwriting them, resolve manually" >&2
  exit 1
fi

git fetch origin "$BRANCH"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" "origin/$BRANCH"
fi

if ! git pull --ff-only origin "$BRANCH"; then
  echo "DIVERGED:$TARGET — local $BRANCH has diverged from origin/$BRANCH, resolve manually before continuing" >&2
  exit 1
fi

SESSION=$(printf '%s' "mirror-$BRANCH" | tr -c 'a-zA-Z0-9_-' '-')
# tmux has-session prefix-matches by default (checking for "mirror-feat"
# would incorrectly succeed against an existing "mirror-feature-x") — the
# leading "=" forces an exact match.
tmux has-session -t "=$SESSION" 2>/dev/null || tmux new-session -d -s "$SESSION" -c "$TARGET"
echo "READY:$SESSION:$TARGET:$(git rev-parse HEAD)"
EOF
```

Note: `printf` (not `echo`) for the session-name sanitizing is deliberate — piping `echo`'s output through `tr -c '...' '-'` turns the trailing newline into a literal `-`, corrupting the session name.

### 5. Hand off

Report the session name, target path, and commit SHA from the `READY:` line — cross-check that SHA against your local `git rev-parse HEAD` before trusting the mirror is on the commit you think it is. This check isn't optional: `--ff-only` only guards against a genuinely diverged remote branch — if the remote already has local commits sitting *ahead* of `origin/$BRANCH` (not diverged, just ahead), the pull succeeds as a silent no-op and `READY` reports that ahead-of-origin SHA, not the one you just pushed. The SHA cross-check is what actually catches that case. Then give the user (or continue as) the attach command:

```bash
ssh -t "${SSH_ARGS[@]}" "$SSH_TARGET" "tmux attach -t <SESSION>"
```

Work now continues inside that tmux session on the Linux machine, on the same branch.

### 6. Push discipline while mirrored

The whole point is that the remote copy is a live working branch, not a snapshot — so push from there as work lands, same as any other machine:

```bash
git add -A && git commit -m "..." && git push
```

If a PR is already open for `$BRANCH`, pushes update that PR's head automatically — no extra step. If no PR exists yet, plain `git push` keeps the remote branch current so work isn't stranded on the Linux machine alone.

## Caveats

- Committed-state-only mirror (see "What this carries over" above) — this is the chosen tradeoff over rsyncing the dirty working tree.
- Repo must live under `$HOME` at the same relative path on both machines (see Setup) — step 1 fails loudly rather than silently mirroring to the wrong place.
- A bare host alias is typically LAN-only; off-LAN (traveling), target the Tailscale IP + explicit `-i` per Tier 2 — and make sure step 4 actually uses the resolved `$SSH_ARGS`/`$SSH_TARGET` from step 3, not a re-hardcoded alias, or the whole point of the fallback is lost.
- Never pass unencoded user-controlled values (repo path, branch name, remote URL) as literal SSH command arguments — a branch name is attacker-controllable shell input the moment someone else can push to your fork, and SSH doesn't preserve argv separation across the wire. Base64-encode first (see step 4).
- Tier 3 (messaging-gateway handoff) hands off to a *different* agent/process with no shared context — give it complete, explicit instructions, don't assume it can infer intent from this conversation. Also verify it's genuinely reactive before relying on it (see Tier 3 caveats above) — a live-looking connection isn't proof it's actually processing events, and a missing permission grant is a much likelier culprit than the connection itself.
- If your remote origin URL embeds a credential (HTTPS + PAT), that credential gets written to the target machine's `.git/config` in cleartext the first time this clones there — prefer an SSH remote or an external credential helper.
