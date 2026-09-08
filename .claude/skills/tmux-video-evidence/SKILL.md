---
name: tmux-video-evidence
description: Record captioned terminal evidence videos with portable, sanitized outputs for authorized review
---

# Tmux Video Evidence for Agent Work Verification

## Purpose

Prove terminal execution against a specific commit and publish reviewable evidence that both humans and agents can consume directly from the PR.

## Required Outputs

Every terminal evidence package must include:
- A terminal video (`.mp4` preferred)
- A browser-friendly preview artifact (`.gif` recommended)
- Captions for that video (burned-in preferred; `.vtt`/`.srt` acceptable)
- Sanitized terminal/test output (no machine-specific absolute paths)
- Media links accessible to the intended reviewer at an authorized destination
- A downloadable high-fidelity artifact (`.mp4` or `.mp4.zip`)

## Mandatory Video Sections

Record these sections in order:

| # | Section | Must show |
|---|---------|-----------|
| 1 | Git Provenance | `git rev-parse HEAD`, branch, merge-base |
| 2 | Commit Log | `git log --oneline origin/main..HEAD` |
| 3 | Code Diffs | `git diff origin/main...HEAD` (not just `--stat`) |
| 4 | PR Status | `gh pr view <N>` |
| 5 | Live Work | Real test/deploy/command output |
| 6 | Post-run SHA | Same `git rev-parse HEAD` as section 1 |

## Evidence Script Template

Create `/tmp/<work_name>_evidence.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="<absolute path to repo>"
cd "$REPO_ROOT"

HEAD_SHA="$(git rev-parse HEAD)"

echo "=== 1. GIT PROVENANCE ==="
echo "HEAD: $HEAD_SHA"
git branch --show-current
git merge-base HEAD origin/main

echo "=== 2. COMMIT LOG ==="
git log --oneline origin/main..HEAD

echo "=== 3. CODE DIFFS ==="
git diff origin/main...HEAD -- <important file 1> | head -80
git diff origin/main...HEAD -- <important file 2> | head -80

echo "=== 4. PR STATUS ==="
gh pr view <PR_NUMBER> --json number,title,url,state,headRefName

echo "=== 5. LIVE TEST EXECUTION (SANITIZED) ==="
<test command> 2>&1 \
  | sed -E \
      -e 's#/Users/[^/]+/#/Users/REDACTED/#g' \
      -e 's#/private/var/folders/[^[:space:]]+#/private/var/folders/REDACTED#g'

echo "=== 6. POST-RUN SHA ==="
POST_SHA="$(git rev-parse HEAD)"
echo "PRE=$HEAD_SHA"
echo "POST=$POST_SHA"
[ "$HEAD_SHA" = "$POST_SHA" ] && echo "SHA MATCH"
```

## Recording

```bash
chmod +x /tmp/<work_name>_evidence.sh

# Option A: direct screen recording (mp4)
# (Use Kap or equivalent and run /tmp/<work_name>_evidence.sh in the visible terminal)

# Option B: asciinema capture, then convert to mp4
timeout 120 asciinema rec /tmp/<work_name>.cast --command "/tmp/<work_name>_evidence.sh" --idle-time-limit 5 --overwrite
agg --cols 120 --rows 50 /tmp/<work_name>.cast /tmp/<work_name>.gif
ffmpeg -y -i /tmp/<work_name>.gif -movflags +faststart -pix_fmt yuv420p /tmp/<work_name>.mp4
```

## Captions (MANDATORY)

For every tmux video, provide captions by either:
1. Burning captions into the video (preferred), or
2. Producing `/tmp/<work_name>.vtt` and linking it alongside the reviewed media artifacts.

Use `~/.claude/skills/video-caption/SKILL.md` when you need to generate burned-in captions reliably.

## Evidence access and authorized publication

Follow `~/.claude/skills/evidence-standards/SKILL.md` for publication authority, audience, and destination. A PR, checked-in document, access-controlled receipt/store, or authorized gist may link the evidence. A gist or GitHub upload is not an independent acceptance requirement. Preserve real media, captions, exact source provenance, and reviewer access; publish only within the current authorization.

The following GitHub release example applies only when that destination is authorized:

```bash
zip -j /tmp/terminal.mp4.zip /abs/path/to/terminal.mp4
gh release create evidence-pr-<PR_NUMBER> --draft --title "PR #<PR_NUMBER> Evidence" --notes "" 2>/dev/null || true
gh release upload evidence-pr-<PR_NUMBER> /tmp/terminal.mp4.zip /abs/path/to/terminal.gif /abs/path/to/terminal.srt --clobber
gh release view evidence-pr-<PR_NUMBER> --json assets,url
gh pr comment <PR_NUMBER_OR_URL> --body-file /tmp/evidence_comment.md
```

Behavior:
- Keeps publication fully zero-touch via `gh`
- Publishes durable GitHub-hosted release URLs for the `.gif`, `.mp4.zip`, and captions
- Avoids dependence on a browser session cookie

Optional path:
- `$HOME/.claude/scripts/github_pr_media_upload.py` can still be used when native `user-attachments` URLs are explicitly desired and browser auth is available

## Compression Guidance

GitHub free plans often cap video uploads at 10 MB. Compress when needed:

```bash
ffmpeg -y -i /tmp/<work_name>.mp4 -vcodec h264 -crf 23 -preset medium /tmp/<work_name>.compressed.mp4
```

## Reviewer Checklist

A reviewer should reject evidence if any are missing:
1. Pre/post SHA match
2. Real command output (not echo-only)
3. Captions present
4. Sanitized logs (no machine-specific absolute paths)
5. Media links accessible to the intended reviewer at an authorized destination
6. Automated `gh` release/comment workflow or optional native-attachment helper used instead of manual drag-drop
7. Matching metadata and captions in the reviewed evidence receipt
