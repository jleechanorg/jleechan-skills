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

This template contains placeholders. Do not execute it directly or invent fallback defaults. Before creating `/tmp/${WORK_NAME:-work}_evidence.sh`, complete all placeholder fields with the user's actual PR number, scoped test command, and relevant modified files:

```text
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$REPO_ROOT"

echo "=== 1. PRE-RUN SHA ==="
HEAD_SHA="$(git rev-parse HEAD)"
echo "$HEAD_SHA"
git branch --show-current
git merge-base HEAD origin/main

echo "=== 2. COMMIT LOG ==="
git log --oneline origin/main..HEAD

echo "=== 3. CODE DIFFS ==="
git diff origin/main...HEAD -- <path/to/important_file_1.py> | head -80
git diff origin/main...HEAD -- <path/to/important_file_2.py> | head -80

echo "=== 4. PR STATUS ==="
gh pr view "<PR_NUMBER>" --json number,title,url,state,headRefName

echo "=== 5. LIVE TEST EXECUTION (SANITIZED) ==="
<SCOPED_TEST_COMMAND> 2>&1 \
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
chmod +x "/tmp/${WORK_NAME:-work}_evidence.sh"

# Option A: direct screen recording (mp4)
# (Use Kap or equivalent and run "/tmp/${WORK_NAME:-work}_evidence.sh" in the visible terminal)

# Option B: asciinema capture, then convert to mp4
timeout 120 asciinema rec "/tmp/${WORK_NAME:-work}.cast" --command "/tmp/${WORK_NAME:-work}_evidence.sh" --idle-time-limit 5 --overwrite
agg --cols 120 --rows 50 "/tmp/${WORK_NAME:-work}.cast" "/tmp/${WORK_NAME:-work}.gif"
ffmpeg -y -i "/tmp/${WORK_NAME:-work}.gif" -movflags +faststart -pix_fmt yuv420p "/tmp/${WORK_NAME:-work}.mp4"
```

## Captions (MANDATORY)

For every tmux video, provide captions by either:
1. Burning captions into the video (preferred), or
2. Producing `/tmp/<work_name>.vtt` or `.srt` and linking that actual file alongside the reviewed media artifacts.

Use `~/.claude/skills/video-caption/SKILL.md` when you need to generate burned-in captions reliably.

## Evidence access and authorized publication

Follow `~/.claude/skills/evidence-standards/SKILL.md` for publication authority, audience, and destination. A PR, checked-in document, access-controlled receipt/store, or authorized gist may link the evidence. A gist or GitHub upload is not an independent acceptance requirement. Preserve real media, captions, exact source provenance, and reviewer access; publish only within the current authorization.

The following GitHub release example applies only when that destination is authorized. Verify all declared media and caption inputs exist before creating the release; do not invent fallback PR targets. Set `caption_file` to the actual generated `.vtt` or `.srt` path when using a sidecar; leave it empty only when captions are already burned into the video. The asset list includes the sidecar only when set.

```bash
(
  set -euo pipefail
  repo="${REPO:-}"
  target_pr="${PR_NUMBER_OR_URL:-${PR_NUMBER:-}}"
  if [[ "$target_pr" =~ github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
    url_repo="${BASH_REMATCH[1]}"
    url_pr="${BASH_REMATCH[2]}"
    if [[ -n "$repo" && "$repo" != "$url_repo" ]]; then
      echo "Error: Conflicting repository target '$repo' vs PR URL '$url_repo'" >&2
      exit 1
    fi
    repo="${repo:-$url_repo}"
    if [[ -n "${PR_NUMBER:-}" && "${PR_NUMBER}" != "$url_pr" ]]; then
      echo "Error: Conflicting PR number '${PR_NUMBER}' vs PR URL '$url_pr'" >&2
      exit 1
    fi
    PR_NUMBER="${PR_NUMBER:-$url_pr}"
  fi

  if [[ -z "${PR_NUMBER:-}" || "$PR_NUMBER" == *"<"* ]]; then
    echo "Error: PR_NUMBER must be set to a valid PR number before publication" >&2
    exit 1
  fi
  if [[ -z "${repo:-}" || "$repo" == *"<"* ]]; then
    echo "Error: REPO must be set to a valid owner/repo before publication" >&2
    exit 1
  fi
  if [[ "$repo" != */* ]]; then
    echo "Error: REPO must be in the format 'owner/repo'" >&2
    exit 1
  fi

  video_file="${VIDEO_FILE:-/tmp/terminal.mp4}"
  preview_file="${PREVIEW_FILE:-/tmp/terminal.gif}"
  caption_file="${CAPTION_FILE:-}"  # Set to the actual .vtt or .srt path unless captions are burned in.
  zip_file="${ZIP_FILE:-/tmp/terminal.mp4.zip}"

  if [ ! -f "$video_file" ]; then
    echo "Error: Video file '$video_file' not found" >&2
    exit 1
  fi
  if [ ! -f "$preview_file" ]; then
    echo "Error: Preview file '$preview_file' not found" >&2
    exit 1
  fi
  if [ -n "$caption_file" ] && [ ! -f "$caption_file" ]; then
    echo "Error: Caption sidecar '$caption_file' specified but not found" >&2
    exit 1
  fi

  zip -j "$zip_file" "$video_file"

  assets=("$zip_file" "$preview_file")
  if [ -n "$caption_file" ]; then
    assets+=("$caption_file")
  fi

  tag="evidence-pr-${PR_NUMBER}"
  if ! gh release create "$tag" --repo "$repo" --draft --title "PR #${PR_NUMBER} Evidence" --notes ""; then
    is_draft="$(gh release view "$tag" --repo "$repo" --json isDraft --jq '.isDraft')"
    if [ "$is_draft" != "true" ]; then
      echo "Error: Release '$tag' could not be created and is not a draft release" >&2
      exit 1
    fi
  fi
  gh release upload "$tag" --repo "$repo" "${assets[@]}" --clobber
  gh release view "$tag" --repo "$repo" --json assets,url
)
```

From the JSON output returned by `gh release view`, extract the uploaded asset URLs and construct `/tmp/evidence_comment.md`. Do not guess draft asset download URLs or invent placeholder URLs.

Once `/tmp/evidence_comment.md` is constructed, post the comment to the authorized PR:

```bash
(
  set -euo pipefail
  repo="${REPO:-}"
  target_pr="${PR_NUMBER_OR_URL:-${PR_NUMBER:-}}"
  if [[ "$target_pr" =~ github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
    url_repo="${BASH_REMATCH[1]}"
    url_pr="${BASH_REMATCH[2]}"
    if [[ -n "$repo" && "$repo" != "$url_repo" ]]; then
      echo "Error: Conflicting repository target '$repo' vs PR URL '$url_repo'" >&2
      exit 1
    fi
    repo="${repo:-$url_repo}"
    if [[ -n "${PR_NUMBER:-}" && "${PR_NUMBER}" != "$url_pr" ]]; then
      echo "Error: Conflicting PR number '${PR_NUMBER}' vs PR URL '$url_pr'" >&2
      exit 1
    fi
    target_pr="$url_pr"
  fi

  if [[ -z "${target_pr:-}" || "$target_pr" == *"<"* ]]; then
    echo "Error: PR_NUMBER must be set to a valid PR number before publication" >&2
    exit 1
  fi
  if [[ -z "${repo:-}" || "$repo" == *"<"* ]]; then
    echo "Error: REPO must be set to a valid owner/repo before publication" >&2
    exit 1
  fi
  if [[ "$repo" != */* ]]; then
    echo "Error: REPO must be in the format 'owner/repo'" >&2
    exit 1
  fi

  comment_file="${COMMENT_FILE:-/tmp/evidence_comment.md}"
  if [ ! -s "$comment_file" ]; then
    echo "Error: Comment body file '$comment_file' does not exist or is empty" >&2
    exit 1
  fi
  gh pr comment "$target_pr" --repo "$repo" --body-file "$comment_file"
)
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
ffmpeg -y -i "/tmp/${WORK_NAME:-work}.mp4" -vcodec h264 -crf 23 -preset medium "/tmp/${WORK_NAME:-work}.compressed.mp4"
```

## Reviewer Checklist

A reviewer should reject evidence if any are missing:
1. Pre/post SHA match
2. Real command output (not echo-only)
3. Captions present
4. Sanitized logs (no machine-specific absolute paths)
5. Media links accessible to the intended reviewer at an authorized destination
6. Any publication uses the authorized destination and applicable automation workflow
7. Matching metadata and captions in the reviewed evidence receipt
