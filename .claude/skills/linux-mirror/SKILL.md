---
name: linux-mirror
description: "Mirror the current git dir/worktree/branch onto jeff-ubuntu (Linux) and continue the work session there instead of locally. Pushes the branch, checks it out remotely via SSH, and drops into a tmux session. Falls back to Slack #hermes-pc if SSH is unreachable. Use when asked to move/continue work on the Linux box, hand off to jeff-ubuntu, or mirror this session to Linux."
---

# Linux Mirror — hand this branch off to jeff-ubuntu

Companion to [mac-mirror](../mac-mirror/SKILL.md) (same flow, opposite direction). Unlike `linux-remote` (ad hoc SSH steering), this mirrors the **current repo's committed state** onto jeff-ubuntu and resumes work there in a persistent tmux session.

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
  *) echo "ERROR: repo root ($REPO_ROOT) is not under \$HOME — this skill mirrors by \$HOME-relative path on both machines." >&2; exit 1 ;;
esac
```

If `$BRANCH` is empty (detached HEAD) or `$DIRTY` is non-empty, stop and tell the user — commit/name the branch first.

If `$REMOTE_URL` is an HTTPS URL with an embedded credential (`https://<token>@host/...`), warn the user: that URL gets written verbatim into jeff-ubuntu's clone `.git/config` in step 4. Prefer an SSH remote. (Step 4's base64 encoding is not confidentiality — it only prevents argv re-tokenization/injection; a decodable token is still visible in jeff-ubuntu's `ps` output during the mirror.)

### 2. Push the branch (make it visible to jeff-ubuntu)

```bash
git -C "$REPO_ROOT" push -u origin "$BRANCH"
```

Confirm with the user before pushing if the branch has no upstream yet or diverges from origin (normal push-safety rules apply — see global push-safety policy).

### 3. Pick a connectivity tier

Resolve the connection via the shared [`cross-machine-ssh-tier`](../cross-machine-ssh-tier/SKILL.md) ladder (Tier 1 LAN → Tier 2 Tailscale → Tier 3 Slack `#hermes-pc`). Carry the resolved `$SSH_ARGS`/`$SSH_TARGET` forward into step 4.

```bash
# Peer = jeff-ubuntu (LAN alias `jeff-ubuntu`, Tailscale peer name pattern
# `ubuntu`, per-direction key `id_jeff_ubuntu`). Full ladder, parameter
# rationale, and Tier 3 caveats live in cross-machine-ssh-tier/SKILL.md.
PEER_LAN_ALIAS="jeff-ubuntu"
PEER_TS_PATTERN="ubuntu"
PEER_KEY="$HOME/.ssh/id_jeff_ubuntu"
# shellcheck disable=SC1091
source <(awk '/^```bash$/{flag=!flag;next}/^```$/{flag=!flag;next}flag' \
  "$(dirname "${BASH_SOURCE[0]}")/../cross-machine-ssh-tier/SKILL.md" \
  | sed -n '/^# The ladder$/,/^# Concrete invocations$/p')
# (or just inline-copy the ladder block from cross-machine-ssh-tier for portability)
```

The expected outcomes after the ladder runs:

- `$SSH_TARGET = "jeff-ubuntu"` → Tier 1 succeeded (LAN).
- `${SSH_ARGS[@]} = (-i ~/.ssh/id_jeff_ubuntu)` and `$SSH_TARGET = "jleechan@<tailscale-ip>"` → Tier 2 succeeded (Tailscale).
- `$SSH_TARGET = ""` → both Tier 1 and Tier 2 failed; skip step 4 entirely and post the hand-off context to Slack `#hermes-pc` per the cross-machine-ssh-tier Tier 3 section.

### 4. Remote checkout + tmux (Tier 1/2 only — skip if `$SSH_TARGET` is empty, that means Tier 3 applies instead)

Arguments are base64-encoded before crossing the wire. This isn't just a quoting nicety: `ssh host command args...` does not preserve argv separation — the remote login shell re-joins and re-tokenizes the command line, so an unencoded branch name containing a space silently shifts which value lands in `$1`/`$2`/`$3`, and one containing shell metacharacters (`;`, `` ` ``, `$()`, `&&`, `|` — all valid in a git branch name) executes arbitrary commands on jeff-ubuntu. Base64 output contains none of those characters.

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

Report the session name, target path, and commit SHA from the `READY:` line — cross-check that SHA against your local `git rev-parse HEAD`. This check isn't optional: if jeff-ubuntu's copy already has local commits *ahead* of `origin/$BRANCH` (not diverged, just ahead), `--ff-only` succeeds as a silent no-op and `READY` reports that ahead-of-origin SHA, not the one you just pushed — the SHA cross-check is what actually catches that. Then give the user (or continue as) the attach command:

```bash
ssh -t "${SSH_ARGS[@]}" "$SSH_TARGET" "tmux attach -t <SESSION>"
```

Work now continues inside that tmux session on jeff-ubuntu, on the same branch.

### 6. Push discipline while mirrored

The whole point is that jeff-ubuntu's copy is a live working branch, not a snapshot — so push from there as work lands, same as any other machine:

```bash
git add -A && git commit -m "..." && git push
```

If a PR is already open for `$BRANCH` (`gh pr view "$BRANCH"`), pushes update that PR's head automatically — no extra step. If no PR exists yet, plain `git push` keeps the remote branch current so work isn't stranded on jeff-ubuntu alone.

## Caveats

- Committed-state-only mirror (see "What this carries over" above) — this is the chosen tradeoff over rsyncing the dirty working tree.
- Tier definitions, key naming (`id_jeff_ubuntu` vs `id_macbook`), Tailscale IP re-verification, Slack Tier 3 caveats, and OAuth-scopes-reinstall gotcha all live in [`cross-machine-ssh-tier`](../cross-machine-ssh-tier/SKILL.md) — consult that skill for the rationale behind the ladder.
- The `jeff-ubuntu` SSH alias is LAN-only; off-LAN (traveling) use the Tailscale IP + explicit `-i ~/.ssh/id_jeff_ubuntu` per Tier 2 — and make sure step 4 actually uses the resolved `$SSH_ARGS`/`$SSH_TARGET` from step 3, not a re-hardcoded alias.
- Never pass unencoded user-controlled values (repo path, branch name, remote URL) as literal SSH command arguments — base64-encode first (see step 4).
- Never target a broad/unresolved path for the remote clone — `$REL_PATH` is always derived from the actual local repo root under `$HOME`, never a guess.
- If your remote origin URL embeds a credential (HTTPS + PAT), that credential gets written to jeff-ubuntu's `.git/config` in cleartext the first time this clones there — prefer an SSH remote.
