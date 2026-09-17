---
name: mac-mirror
description: "Mirror the current git dir/worktree/branch onto a Mac and continue the work session there instead of locally. Pushes the branch, checks it out remotely via SSH, and drops into a tmux session. Falls back to Slack if SSH is unreachable. Use when asked to move/continue work on a Mac, hand off to it, or mirror this session to Mac from Linux or elsewhere."
---

# Mac Mirror — hand this branch off to a Mac

Companion to [linux-mirror](../linux-mirror/SKILL.md) (same flow, opposite direction). Unlike a plain SSH-steering skill, this mirrors the **current repo's committed state** onto the target Mac and resumes work there in a persistent tmux session.

If you're already running locally on the target Mac, there's nothing to mirror — say so and stop.

## Setup (once, per pair of machines)

This skill assumes you've already got:
- An SSH host alias for the Mac in `~/.ssh/config` (LAN), e.g.:
  ```
  Host mymac
      HostName 192.168.1.60
      User myusername
      IdentityFile ~/.ssh/id_mymac
  ```
  (`ssh_config` does not expand environment variables — write your actual username literally, not `$USER`.)
- SSH enabled on the Mac (System Settings → General → Sharing → Remote Login), with the other machine's public key added.
- Your repo lives under `$HOME` on **both** machines, at the same relative path (e.g. `~/projects/myrepo` on both). This skill mirrors by `$HOME`-relative path; a repo outside `$HOME`, or at a different relative path on each machine, isn't supported — step 1 below checks for this and stops rather than silently producing a wrong path.
- (Optional, for off-LAN/travel use) Both machines joined to the same Tailscale tailnet — same caveat as linux-mirror: the bare alias won't fail over to Tailscale automatically, target the Tailscale IP + explicit `-i` when off-LAN.
- (Optional, for SSH-fully-down fallback) A messaging-gateway agent running on the Mac, watching a Slack channel (or similar) you can post to.

Substitute your own host alias / IP / key path / username everywhere `mymac` / `myusername` appears below.

## What this carries over

Only **committed and pushed** state — the current branch's HEAD. Uncommitted/staged local edits are NOT transferred; commit or stash first if you need them.

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

If `$REMOTE_URL` is an HTTPS URL with an embedded credential (`https://<token>@host/...`), warn the user before continuing: that URL gets written verbatim into the remote clone's `.git/config` in step 4, so the credential ends up live on the target Mac too. Prefer an SSH remote, or a credential helper that doesn't embed the token in the URL. (Step 4's base64 encoding is not a confidentiality measure for this value — it only prevents argv re-tokenization/injection. A trivially-decodable token is still visible in the remote host's `ps` output during the mirror.)

### 2. Push the branch

```bash
git -C "$REPO_ROOT" push -u origin "$BRANCH"
```

Confirm with the user first if the branch has no upstream yet or diverges from origin.

### 3. Pick a connectivity tier — try in order, stop at first success. Carry the resolved connection forward into `SSH_ARGS`/`SSH_TARGET` for step 4 — don't just check reachability and then reconnect a different way.

```bash
SSH_ARGS=()
SSH_TARGET="mymac"   # Tier 1 default: the LAN alias

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
  echo "SSH_OK via Tier 1 (LAN alias)"
else
  # Tier 2 — Tailscale SSH (off-LAN). The alias above won't fail over here —
  # target the Tailscale IP directly with the identity file explicit.
  TS_IP=$(tailscale status | awk '/<mac-hostname>/{print $1}')
  SSH_ARGS=(-i ~/.ssh/id_mymac)
  SSH_TARGET="myusername@$TS_IP"
  if ssh "${SSH_ARGS[@]}" -o ConnectTimeout=5 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
    echo "SSH_OK via Tier 2 (Tailscale)"
  else
    SSH_TARGET=""   # neither tier reached — fall through to Tier 3 below
  fi
fi
```

**Tier 3 — Messaging-gateway handoff (SSH AND Tailscale both down, `$SSH_TARGET` empty):** post the exact repo/branch/commit and the steps from §4 to a channel a reactive gateway agent on the Mac is watching, asking it to execute them locally and reply when the tmux session is ready. It has no shared context with this session — give complete, explicit instructions.

Same debugging priority as linux-mirror's Tier 3 if this seems dead — don't assume it needs a restart:
1. **A missing OAuth-style scope grant on the gateway's own credential, not a connection problem.** A connection can report fully healthy while a permission declared in the integration's config was never actually granted to the live credential. Discriminating check: call the platform's own auth-introspection endpoint with the gateway's live credential (e.g. Slack's `auth.test`, or attempt the scoped call and read the error). Remedy: reinstall/reauthorize the integration — a bare restart doesn't do this.
2. **A message-filtering rule tripping on a test artifact**, not a real failure — many gateways drop messages attributed to a bot/app identity by default, including ones posted via some other app's OAuth token. Verify with a message typed directly by a human, not posted via any API token.

Only after ruling both out is it worth suspecting the connection layer itself (debug-level logging on the gateway process — check its actual log destination, e.g. `journalctl` for a systemd-managed service, or the equivalent launchd log for a macOS service).

### 4. Remote checkout + tmux (Tier 1/2 only — skip if `$SSH_TARGET` is empty, that means Tier 3 applies instead)

Arguments are base64-encoded before crossing the wire — `ssh host command args...` does not preserve argv separation, the remote shell re-tokenizes the command line, so an unencoded branch name with a space or shell metacharacter (`;`, `` ` ``, `$()`, `&&`, `|` — all valid in a git branch name) can misdirect arguments or execute commands on the remote host. Base64 output contains none of those characters.

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
# tmux has-session prefix-matches by default — the leading "=" forces an
# exact match so a shorter branch name doesn't false-match a longer one.
tmux has-session -t "=$SESSION" 2>/dev/null || tmux new-session -d -s "$SESSION" -c "$TARGET"
echo "READY:$SESSION:$TARGET:$(git rev-parse HEAD)"
EOF
```

Note: `printf` (not `echo`) for the session-name sanitizing is deliberate — piping `echo`'s output through `tr -c '...' '-'` turns the trailing newline into a literal `-`, corrupting the session name.

### 5. Hand off

Report the session name, target path, and commit SHA from the `READY:` line — cross-check that SHA against your local `git rev-parse HEAD`. This check isn't optional: `--ff-only` only guards against a genuinely diverged remote branch — if the remote already has local commits sitting *ahead* of `origin/$BRANCH` (not diverged, just ahead), the pull succeeds as a silent no-op and `READY` reports that ahead-of-origin SHA, not the one you just pushed. The SHA cross-check is what actually catches that case. Then give the attach command:

```bash
ssh -t "${SSH_ARGS[@]}" "$SSH_TARGET" "tmux attach -t <SESSION>"
```

### 6. Push discipline while mirrored

```bash
git add -A && git commit -m "..." && git push
```

If a PR is open for `$BRANCH`, pushes update its head automatically. Otherwise plain `git push` keeps the remote branch current so work isn't stranded on the Mac alone.

## Caveats

- Committed-state-only mirror — see "What this carries over" above.
- Repo must live under `$HOME` at the same relative path on both machines (see Setup) — step 1 fails loudly rather than silently mirroring to the wrong place.
- macOS SSH keychain may prompt on first connection; `ssh-add --apple-use-keychain ~/.ssh/id_mymac` caches it.
- A bare host alias is typically LAN-only; off-LAN, target the Tailscale IP + explicit `-i` per Tier 2 — and make sure step 4 actually uses the resolved `$SSH_ARGS`/`$SSH_TARGET`, not a re-hardcoded alias.
- Never pass unencoded user-controlled values (repo path, branch name, remote URL) as literal SSH command arguments — base64-encode first (see step 4).
- Tier 3 hands off to a *different* agent/process with no shared context — see the debugging priority above before assuming it's broken vs. just needing a genuinely human-originated test or a missing permission grant.
- If your remote origin URL embeds a credential (HTTPS + PAT), that credential gets written to the target machine's `.git/config` in cleartext the first time this clones there — prefer an SSH remote or an external credential helper.
