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
git diff origin/main...HEAD -- <path/to/important_file_1.py> | sed -n '1,80p'
git diff origin/main...HEAD -- <path/to/important_file_2.py> | sed -n '1,80p'

echo "=== 4. PR STATUS ==="
gh pr view "<PR_NUMBER>" --json number,title,url,state,headRefName

echo "=== 5. LIVE TEST EXECUTION (SANITIZED) ==="
<SCOPED_TEST_COMMAND> 2>&1 \
  | sed -E \
      -e 's#/Users/[^/]+/#/Users/REDACTED/#g' \
      -e 's#/home/[^/]+/#/home/REDACTED/#g' \
      -e 's#/private/var/folders/[^[:space:]]+#/private/var/folders/REDACTED#g' \
      -e 's#/workspace/[^[:space:]]+#/workspace/REDACTED#g' \
      -e 's#/tmp/[^[:space:]]+#/tmp/REDACTED#g'


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

The following GitHub release example applies only when that destination is authorized. Verify the intended PR exists via `gh pr view` before creating any release or upload. Caller must provide non-empty `VIDEO_FILE` and `PREVIEW_FILE` artifacts, an explicit non-empty `RUN_ID`, an explicit non-empty `CAPTURED_SHA` matching the PR head SHA, and declare an explicit caption choice: set `CAPTION_FILE` to the actual .vtt or .srt sidecar path, or set `CAPTION_MODE=burned` when captions are burned into the video. All media and subtitle formats are verified with ffprobe prior to archive creation and publication. Packaging creates a new archive in a private temporary directory so existing user archives are never overwritten or updated with stale entries. Each run publishes to an immutable unique release tag combining the PR number, commit SHA, and run identifier without overwriting or clobbering existing releases.

```bash
(
  set -euo pipefail
  repo="${REPO:-}"
  url_regex='^https://github\.com/([^/]+/[^/]+)/pull/([1-9][0-9]*)/?$'

  if [[ -n "${PR_NUMBER_OR_URL:-}" ]]; then
    if [[ "$PR_NUMBER_OR_URL" =~ $url_regex ]]; then
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
      PR_NUMBER="$url_pr"
    elif [[ "$PR_NUMBER_OR_URL" =~ ^[1-9][0-9]*$ ]]; then
      if [[ -n "${PR_NUMBER:-}" && "${PR_NUMBER}" != "$PR_NUMBER_OR_URL" ]]; then
        echo "Error: Conflicting PR number '${PR_NUMBER}' vs PR_NUMBER_OR_URL '$PR_NUMBER_OR_URL'" >&2
        exit 1
      fi
      PR_NUMBER="${PR_NUMBER:-$PR_NUMBER_OR_URL}"
    else
      echo "Error: PR_NUMBER_OR_URL must be a valid GitHub PR URL or positive PR number" >&2
      exit 1
    fi
  fi

  if [[ -n "${PR_NUMBER:-}" && "$PR_NUMBER" =~ $url_regex ]]; then
    url_repo="${BASH_REMATCH[1]}"
    url_pr="${BASH_REMATCH[2]}"
    if [[ -n "$repo" && "$repo" != "$url_repo" ]]; then
      echo "Error: Conflicting repository target '$repo' vs PR URL '$url_repo'" >&2
      exit 1
    fi
    repo="${repo:-$url_repo}"
    PR_NUMBER="$url_pr"
  fi

  if ! command -v ffprobe >/dev/null 2>&1; then
    echo "Error: ffprobe is required for media validation but not found in PATH" >&2
    exit 1
  fi

  if [[ -z "${PR_NUMBER:-}" || "$PR_NUMBER" == *"<"* || ! "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: PR_NUMBER must be set to a valid PR number before publication" >&2
    exit 1
  fi
  if [[ -z "${repo:-}" || "$repo" == *"<"* ]]; then
    echo "Error: REPO must be set to a valid owner/repo before publication" >&2
    exit 1
  fi
  if [[ ! "$repo" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]]; then
    echo "Error: REPO must be in the format 'owner/repo'" >&2
    exit 1
  fi
  if [[ -z "${RUN_ID:-}" || "$RUN_ID" == *"<"* ]]; then
    echo "Error: RUN_ID must be set to an explicit nonempty identifier before publication" >&2
    exit 1
  fi
  if [[ -z "${CAPTURED_SHA:-}" || "$CAPTURED_SHA" == *"<"* ]]; then
    echo "Error: CAPTURED_SHA must be set to the explicit commit SHA captured in the evidence" >&2
    exit 1
  fi

  if [[ -z "${VIDEO_FILE:-}" || "$VIDEO_FILE" == *"<"* ]]; then
    echo "Error: VIDEO_FILE must be set to a valid path before publication" >&2
    exit 1
  fi
  if [[ -z "${PREVIEW_FILE:-}" || "$PREVIEW_FILE" == *"<"* ]]; then
    echo "Error: PREVIEW_FILE must be set to a valid path before publication" >&2
    exit 1
  fi

  video_file="$VIDEO_FILE"
  preview_file="$PREVIEW_FILE"

  if [ ! -f "$video_file" ] || [ ! -s "$video_file" ]; then
    echo "Error: Video file '$video_file' not found or is empty" >&2
    exit 1
  fi
  if [ ! -f "$preview_file" ] || [ ! -s "$preview_file" ]; then
    echo "Error: Preview file '$preview_file' not found or is empty" >&2
    exit 1
  fi

  video_codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 "$video_file" 2>/dev/null || true)"
  if [[ "$video_codec" != "video" ]]; then
    echo "Error: Video file '$video_file' does not contain a valid video stream" >&2
    exit 1
  fi

  preview_codec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 "$preview_file" 2>/dev/null || true)"
  if [[ "$preview_codec" != "video" ]]; then
    echo "Error: Preview file '$preview_file' does not contain a valid video/image stream" >&2
    exit 1
  fi

  if [[ -n "${CAPTION_MODE:-}" && "${CAPTION_MODE:-}" != "burned" ]]; then
    echo "Error: Unsupported CAPTION_MODE '${CAPTION_MODE}': only CAPTION_MODE=burned is supported" >&2
    exit 1
  fi

  if [[ -n "${CAPTION_FILE:-}" && "${CAPTION_FILE:-}" != *"<"* && "${CAPTION_MODE:-}" == "burned" ]]; then
    echo "Error: Cannot specify both CAPTION_FILE and CAPTION_MODE=burned: choose exactly one caption option" >&2
    exit 1
  fi

  if [[ "${CAPTION_MODE:-}" == "burned" ]]; then
    caption_file=""
  elif [[ -n "${CAPTION_FILE:-}" && "${CAPTION_FILE:-}" != *"<"* ]]; then
    caption_file="$CAPTION_FILE"
    if [ ! -f "$caption_file" ] || [ ! -s "$caption_file" ]; then
      echo "Error: Caption sidecar '$caption_file' specified but not found or is empty" >&2
      exit 1
    fi
    caption_codec="$(ffprobe -v error -show_entries stream=codec_type -of default=noprint_wrappers=1:nokey=1 "$caption_file" 2>/dev/null || true)"
    if [[ "$caption_codec" != "subtitle" ]]; then
      echo "Error: Caption file '$caption_file' does not contain a valid subtitle stream" >&2
      exit 1
    fi
  else
    echo "Error: Explicit caption choice required: specify CAPTION_FILE (.vtt/.srt) or CAPTION_MODE=burned" >&2
    exit 1
  fi

  # Verify exact intended PR before any release creation or mutation
  pr_view_json="$(gh pr view "$PR_NUMBER" --repo "$repo" --json number,headRefOid,url)"
  pr_head_sha="$(printf '%s' "$pr_view_json" | jq -r '.headRefOid // empty')"
  pr_number_resolved="$(printf '%s' "$pr_view_json" | jq -r '.number // empty')"
  if [[ -n "$pr_number_resolved" && "$pr_number_resolved" != "$PR_NUMBER" ]]; then
    echo "Error: Verified PR number mismatch ($pr_number_resolved vs $PR_NUMBER)" >&2
    exit 1
  fi
  if [[ -z "$pr_head_sha" ]]; then
    echo "Error: Unable to resolve head SHA for PR #$PR_NUMBER in $repo" >&2
    exit 1
  fi

  if [[ "$CAPTURED_SHA" != "$pr_head_sha" ]]; then
    echo "Error: Declared CAPTURED_SHA '$CAPTURED_SHA' does not match verified PR head '$pr_head_sha'" >&2
    exit 1
  fi

  sha_short="${CAPTURED_SHA:0:12}"
  tag="evidence-pr-${PR_NUMBER}-${sha_short}-${RUN_ID}"

  archive_dir="$(mktemp -d "${TMPDIR:-/tmp}/evidence_archive.XXXXXX")"
  trap 'rm -rf "$archive_dir"' EXIT
  zip_file="$archive_dir/$(basename "$video_file").zip"
  zip -j "$zip_file" "$video_file"

  assets=("$zip_file" "$preview_file")
  if [ -n "$caption_file" ]; then
    assets+=("$caption_file")
  fi

  if ! gh release create "$tag" --repo "$repo" --draft --title "PR #${PR_NUMBER} Evidence" --notes ""; then
    echo "Error: Release '$tag' could not be created or already exists; stopping without modifying releases" >&2
    exit 1
  fi
  gh release upload "$tag" --repo "$repo" "${assets[@]}"
  gh release view "$tag" --repo "$repo" --json assets,url
)
```


From the JSON output returned by `gh release view`, extract the uploaded asset URLs and construct `/tmp/evidence_comment.md`. Do not guess draft asset download URLs or invent placeholder URLs.

Once `/tmp/evidence_comment.md` is constructed, post the comment to the authorized PR:

```bash
(
  set -euo pipefail
  repo="${REPO:-}"
  url_regex='^https://github\.com/([^/]+/[^/]+)/pull/([1-9][0-9]*)/?$'

  if [[ -n "${PR_NUMBER_OR_URL:-}" ]]; then
    if [[ "$PR_NUMBER_OR_URL" =~ $url_regex ]]; then
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
      PR_NUMBER="$url_pr"
    elif [[ "$PR_NUMBER_OR_URL" =~ ^[1-9][0-9]*$ ]]; then
      if [[ -n "${PR_NUMBER:-}" && "${PR_NUMBER}" != "$PR_NUMBER_OR_URL" ]]; then
        echo "Error: Conflicting PR number '${PR_NUMBER}' vs PR_NUMBER_OR_URL '$PR_NUMBER_OR_URL'" >&2
        exit 1
      fi
      PR_NUMBER="${PR_NUMBER:-$PR_NUMBER_OR_URL}"
    else
      echo "Error: PR_NUMBER_OR_URL must be a valid GitHub PR URL or positive PR number" >&2
      exit 1
    fi
  fi

  if [[ -n "${PR_NUMBER:-}" && "$PR_NUMBER" =~ $url_regex ]]; then
    url_repo="${BASH_REMATCH[1]}"
    url_pr="${BASH_REMATCH[2]}"
    if [[ -n "$repo" && "$repo" != "$url_repo" ]]; then
      echo "Error: Conflicting repository target '$repo' vs PR URL '$url_repo'" >&2
      exit 1
    fi
    repo="${repo:-$url_repo}"
    PR_NUMBER="$url_pr"
  fi

  if [[ -z "${PR_NUMBER:-}" || "$PR_NUMBER" == *"<"* || ! "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: PR_NUMBER must be set to a valid PR number before publication" >&2
    exit 1
  fi
  if [[ -z "${repo:-}" || "$repo" == *"<"* ]]; then
    echo "Error: REPO must be set to a valid owner/repo before publication" >&2
    exit 1
  fi
  if [[ ! "$repo" =~ ^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$ ]]; then
    echo "Error: REPO must be in the format 'owner/repo'" >&2
    exit 1
  fi

  comment_file="${COMMENT_FILE:-/tmp/evidence_comment.md}"
  if [ ! -s "$comment_file" ]; then
    echo "Error: Comment body file '$comment_file' does not exist or is empty" >&2
    exit 1
  fi

  # Verify exact intended PR before posting comment
  pr_view_json="$(gh pr view "$PR_NUMBER" --repo "$repo" --json number,headRefOid,url)"
  pr_number_resolved="$(printf '%s' "$pr_view_json" | jq -r '.number // empty')"
  if [[ -n "$pr_number_resolved" && "$pr_number_resolved" != "$PR_NUMBER" ]]; then
    echo "Error: Verified PR number mismatch ($pr_number_resolved vs $PR_NUMBER)" >&2
    exit 1
  fi

  target_pr="$PR_NUMBER"
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
