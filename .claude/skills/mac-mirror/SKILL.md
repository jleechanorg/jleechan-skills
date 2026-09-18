---
name: mac-mirror
description: "Mirror the current git dir/worktree/branch onto the MacBook and continue the work session there instead of locally. Pushes the branch, checks it out remotely via SSH, and drops into a tmux session. Falls back to Slack #hermes-pc if SSH is unreachable. Use when asked to move/continue work on the MacBook, hand off to the Mac, or mirror this session to Mac from jeff-ubuntu or elsewhere."
---

# Mac Mirror — hand this branch off to the MacBook

Companion to [linux-mirror](../linux-mirror/SKILL.md) (same flow, opposite direction). Unlike `mac-remote` (ad hoc SSH steering), this mirrors the **current repo's committed state** onto the MacBook and resumes work there in a persistent tmux session.

If you're already running locally on the MacBook (`uname -s` = `Darwin` and `hostname -s` matches the MacBook), there's nothing to mirror — say so and stop.

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
  *) echo "ERROR: repo root ($REPO_ROOT) is not under \$HOME — this skill mirrors by \$HOME-relative path on both machines." >&2; exit 1 ;;
esac
```

If `$BRANCH` is empty (detached HEAD) or `$DIRTY` is non-empty, stop and tell the user — commit/name the branch first.

If `$REMOTE_URL` is an HTTPS URL with an embedded credential (`https://<token>@host/...`), warn the user: that URL gets written verbatim into the MacBook's clone `.git/config` in step 4. Prefer an SSH remote. (Step 4's base64 encoding is not confidentiality — it only prevents argv re-tokenization/injection; a decodable token is still visible in the MacBook's `ps` output during the mirror.)

### 2. Push the branch

```bash
git -C "$REPO_ROOT" push -u origin "$BRANCH"
```

Confirm with the user first if the branch has no upstream yet or diverges from origin.

### 3. Pick a connectivity tier

Resolve the connection via the shared [`cross-machine-ssh-tier`](../cross-machine-ssh-tier/SKILL.md) ladder (Tier 1 LAN → Tier 2 Tailscale → Tier 3 Slack `#hermes-pc`). Carry the resolved `$SSH_ARGS`/`$SSH_TARGET` forward into step 4.

```bash
# Peer = macbook (LAN alias `macbook`, Tailscale peer name pattern `macbook`,
# per-direction key `id_macbook`). Full ladder, parameter rationale, and Tier 3
# caveats live in cross-machine-ssh-tier/SKILL.md.
PEER_LAN_ALIAS="macbook"
PEER_TS_PATTERN="macbook"
PEER_KEY="$HOME/.ssh/id_macbook"
# shellcheck disable=SC1091
source <(awk '/^```bash$/{flag=!flag;next}/^```$/{flag=!flag;next}flag' \
  "$(dirname "${BASH_SOURCE[0]}")/../cross-machine-ssh-tier/SKILL.md" \
  | sed -n '/^# The ladder$/,/^# Concrete invocations$/p')
# (or just inline-copy the ladder block from cross-machine-ssh-tier for portability)
```

The expected outcomes after the ladder runs:

- `$SSH_TARGET = "macbook"` → Tier 1 succeeded (LAN).
- `${SSH_ARGS[@]} = (-i ~/.ssh/id_macbook)` and `$SSH_TARGET = "jleechan@<tailscale-ip>"` → Tier 2 succeeded (Tailscale).
- `$SSH_TARGET = ""` → both Tier 1 and Tier 2 failed; skip step 4 entirely and post the hand-off context to Slack `#hermes-pc` per the cross-machine-ssh-tier Tier 3 section.

### 4. Remote checkout + tmux (Tier 1/2 only — skip if `$SSH_TARGET` is empty, that means Tier 3 applies instead)

Arguments are base64-encoded before crossing the wire — `ssh host command args...` does not preserve argv separation, the remote shell re-tokenizes the command line, so an unencoded branch name with a space or shell metacharacter (`;`, `` ` ``, `$()`, `&&`, `|` — all valid in a git branch name) can misdirect arguments or execute commands on the Mac. Base64 output contains none of those characters.

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
