---
name: ui-video-evidence
description: Record captioned browser/UI evidence videos and link sanitized artifacts for authorized review
---

# UI Video Evidence for Visual Verification

## Purpose

Prove user-visible behavior in a way reviewers and agents can verify quickly from the PR conversation.

Before producing or reviewing any video, apply the canonical [`evidence-standards` continuous-video rule](../evidence-standards/SKILL.md#continuous-video-only--slideshows-are-forbidden). Screenshot sequences and slideshow MP4s never satisfy video evidence.

## When UI Video Is Required

Use the [lifecycle proof rules](../pr-lifecycle/exceptions.md#proportional-exceptions-and-fast-paths). Those rules select whether rendered proof is required. Use captioned before/after video for claims that depend on a sequence, including:
- Layout or styling during a transition, animation, or scroll
- Click flows, form submissions, navigation, or opening and closing a modal
- Streaming, loading, and other claims about the order or timing of frames

Missing video withholds a sequence claim. No static proof format waives explicitly requested video or applicable platform coverage.

## Required Outputs

Use this checklist for video runs. For static-only claims, use the [canonical evidence standard](../evidence-standards/SKILL.md#ui-changes-require-a-genuine-implementation-beforeafter-comparison):
- UI video (`.mp4` preferred)
- UI fallback media (`.gif` recommended when player embed is not required)
- Captions (burned-in preferred; `.vtt`/`.srt` acceptable)
- Git linkage (`git rev-parse HEAD` visible in recording context)
- Media links accessible to the intended reviewer at an authorized destination
- A browser-viewable artifact (`.gif`, commit-pinned raw asset, release asset, or native attachment)
- A downloadable high-fidelity artifact (`.mp4`, `.mp4.zip`, or release asset)
- Matching metadata and caption artifacts in the reviewed evidence receipt

## Scoped Browser Ownership (resolve FIRST, before picking a capture method)

Before choosing how to capture evidence, check whether the target repo has its
own browser-execution owner (e.g. `testing_ui/CLAUDE.md`,
`../browser-testing/SKILL.md`). If a scoped owner exists and
forbids headed/manual capture or Claude-in-Chrome, its policy wins — use its
designated headless tool (Aside CLI/`aside-mcp`, or headless Playwright). Do
not escalate to a native-chrome/manual-capture requirement, and do not ask for
Screen Recording permission, when a scoped headless path is available and not
documented as blocked.

## Mandatory Frames

Capture both implementations under the [canonical BEFORE/AFTER rule](../evidence-standards/SKILL.md#ui-changes-require-a-genuine-implementation-beforeafter-comparison). The
pre-action frame is not by itself a pre-change-code baseline. Apply the action
rows only on revisions where the action exists; otherwise show the actual prior
experience or the action's absence in the matching state.

| # | Frame | Must show |
|---|-------|-----------|
| 1 | URL + Page Load | Full native browser URL bar with route under test, OR — when the scoped owner mandates headless capture — a genuine route/URL provenance marker (printed navigation URL/log line, on-page route text, or window title) captured from the same automated session and tied to the frame timestamp |
| 2 | Pre-action State | Initial state before an available action |
| 3 | Action | Click/input/navigation action, where available |
| 4 | Post-action State | Result of an available action |
| 5 | Git Linkage | Terminal split, devtools log, or on-page SHA marker |

## Recording Options

### Option 1: Scoped headless driver (Aside / Playwright) — DEFAULT
Follow `../browser-testing/SKILL.md`: drive the browser headlessly
via Aside CLI/`aside-mcp` or headless Playwright, log the navigated URL/route to
the terminal or an overlay, and record with the scoped repo's own recorder
(e.g. `testing_ui/streaming/base.py` `UIVideoRecorder`) or `ffmpeg` (Option 3).
Never use `mcp__claude-in-chrome__*` or any headed browser for this path.

### Option 2: Manual desktop capture (Kap) — LAST RESORT ONLY
Only when the current thread explicitly requests visible capture, the browser
is independently verified as task-owned, and the repo permits it. Absence of a
repo prohibition is not authorization. Follow the shared browser-control owner;
never use personal/default Chrome, its profiles or its cookies.
```bash
brew install --cask kap
```
Record browser window including address bar.

### Option 3: ffmpeg (headless/CI)
```bash
ffmpeg -video_size 1280x720 -framerate 10 -f x11grab -i :99 -t 30 "/tmp/${WORK_NAME:-work}.mp4"
```

## Caption Requirements (MANDATORY)

Both tmux and UI videos must always have captions.

Accepted forms:
1. Burned-in captions in the video (preferred)
2. Sidecar caption file (`.vtt`/`.srt`) linked alongside the reviewed media artifacts

Use `../video-caption/SKILL.md` for reliable burned-in captions.

## Evidence access and authorized publication

Follow `../evidence-standards/SKILL.md` for publication authority, audience, and destination. A PR, checked-in document, access-controlled receipt/store, or authorized gist may link the evidence. For PRs governed by pr-lifecycle, its review receipts belong in the PR description; opted-in repositories also link every stage-exit receipt through its required sanitized gist URL (except a pr-lifecycle one-liner fast-path receipt, which lives in the PR body). Applicable inline viewable media and original media URLs are required there. Other authorized artifact storage does not remove that description/publication requirement. Preserve real media, captions, exact source provenance, and reviewer access; publish only within the current authorization.

The following GitHub release example applies only when that destination is authorized. Verify the intended PR exists via `gh pr view` before creating any release or upload. Caller must provide non-empty `VIDEO_FILE` and `PREVIEW_FILE` artifacts, an explicit non-empty `RUN_ID`, an explicit non-empty `CAPTURED_SHA` matching the PR head SHA, and declare an explicit caption choice: set `CAPTION_FILE` to the actual .vtt or .srt sidecar path, or set `CAPTION_MODE=burned` when captions are burned into the video. All media and subtitle formats are verified with ffprobe prior to archive creation and publication. Packaging creates a new archive in a private temporary directory so existing user archives are never overwritten or updated with stale entries. Each run publishes to an immutable unique release tag combining the PR number, commit SHA, and run identifier without overwriting or clobbering existing releases.

This example publishes a current-candidate capture only. Retain baseline media at
its actual source SHA through an authorized artifact route; never relabel it as
the PR head to satisfy this example's head-equality guard.

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

  if [[ -n "${CAPTION_FILE:-}" && "${CAPTION_MODE:-}" == "burned" ]]; then
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

  archive_scratch="$("${CLAUDE_HOME:-$HOME/.claude}/skills/scratch-space/scripts/scratch-dir.sh" tmp)"
  if [ -z "$archive_scratch" ]; then
    echo "Scratch resolver returned an empty path; refusing archive allocation" >&2
    exit 75
  fi
  archive_dir="$(mktemp -d "$archive_scratch/evidence_archive.XXXXXX")"
  zip_file="$archive_dir/$(basename "$video_file").zip"
  trap 'rm -f -- "$zip_file"; rmdir -- "$archive_dir"' EXIT
  zip -j "$zip_file" "$video_file"

  assets=("$zip_file" "$preview_file")
  if [ -n "$caption_file" ]; then
    assets+=("$caption_file")
  fi

  if ! gh release create "$tag" --repo "$repo" --target "$CAPTURED_SHA" --draft --title "PR #${PR_NUMBER} Evidence" --notes ""; then
    echo "Error: Release '$tag' could not be created or already exists; stopping without modifying releases" >&2
    exit 1
  fi
  release_json="$(gh release view "$tag" --repo "$repo" --json assets,targetCommitish,url)"
  release_target="$(printf '%s' "$release_json" | jq -r '.targetCommitish // empty')"
  if [[ -z "$release_target" || ! "$release_target" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "Error: Unable to resolve valid target commit for release '$tag' in $repo" >&2
    exit 1
  fi
  if [[ "$release_target" != "$CAPTURED_SHA" ]]; then
    echo "Error: Verified release target commit '$release_target' does not match CAPTURED_SHA '$CAPTURED_SHA'" >&2
    exit 1
  fi
  gh release upload "$tag" --repo "$repo" "${assets[@]}"
  release_json="$(gh release view "$tag" --repo "$repo" --json assets,targetCommitish,url)"
  release_target="$(printf '%s' "$release_json" | jq -r '.targetCommitish // empty')"
  if [[ -z "$release_target" || ! "$release_target" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "Error: Unable to resolve valid target commit for release '$tag' in $repo" >&2
    exit 1
  fi
  if [[ "$release_target" != "$CAPTURED_SHA" ]]; then
    echo "Error: Verified release target commit '$release_target' does not match CAPTURED_SHA '$CAPTURED_SHA'" >&2
    exit 1
  fi
  for expected_asset in "${assets[@]}"; do
    name="$(basename "$expected_asset")"
    matches="$(printf '%s' "$release_json" | jq --arg n "$name" '[.assets[] | select(.name == $n)]')"
    count="$(printf '%s' "$matches" | jq 'length')"
    if [[ "$count" -ne 1 ]]; then
      echo "Error: Expected asset '$name' present $count time(s) in release readback (must be exactly 1)" >&2
      exit 1
    fi
    if [[ -z "$(printf '%s' "$matches" | jq -r '.[0].url // empty')" ]]; then
      echo "Error: Expected asset '$name' has no usable URL in release readback" >&2
      exit 1
    fi
  done
  printf '%s\n' "$release_json"
)
```

From the JSON output returned by `gh release view`, extract the uploaded asset URLs and construct `the canonical Scratch comment body`. Do not guess draft asset download URLs or invent placeholder URLs.

Once `the canonical Scratch comment body` is constructed, post the comment to the authorized PR:

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
  if [[ -z "${CAPTURED_SHA:-}" || "$CAPTURED_SHA" == *"<"* || ! "$CAPTURED_SHA" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "Error: CAPTURED_SHA must be set to a valid 40-character commit SHA" >&2
    exit 1
  fi

  comment_scratch="$("${CLAUDE_HOME:-$HOME/.claude}/skills/scratch-space/scripts/scratch-dir.sh" tmp)"
  comment_file="${COMMENT_FILE:-$comment_scratch/evidence_comment.md}"
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
  pr_head_sha="$(printf '%s' "$pr_view_json" | jq -r '.headRefOid // empty')"
  if [[ -z "$pr_head_sha" || ! "$pr_head_sha" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "Error: Unable to resolve valid head SHA for PR #$PR_NUMBER in $repo" >&2
    exit 1
  fi
  if [[ "$CAPTURED_SHA" != "$pr_head_sha" ]]; then
    echo "Error: Declared CAPTURED_SHA '$CAPTURED_SHA' does not match verified PR head '$pr_head_sha'" >&2
    exit 1
  fi

  target_pr="$PR_NUMBER"
  gh pr comment "$target_pr" --repo "$repo" --body-file "$comment_file"
)
```

Optional path:
- `$HOME/.claude/scripts/github_pr_media_upload.py` may still be used when native `user-attachments` URLs are specifically desired and a valid GitHub web session cookie is available

Behavior:
- Keeps publication fully zero-touch via `gh`
- Produces durable GitHub-hosted URLs that can be pasted into the PR description or comment
- Avoids dependence on a browser session cookie

## PR Snippet Template

```markdown
## UI Evidence

- GIF: `<reviewer-accessible location at the authorized destination>`
- MP4 ZIP: `<reviewer-accessible location at the authorized destination>`
- Captions: burned-in (or link to the matching caption artifact)
- Route: `/path/under/test`
- Commit: `<sha>`
- Claim: <what this proves>
```

## Anti-Patterns

Reject these:
- URL bar cropped out
- Success-only clip with no applicable before→after transition or, when a user action exists, no before/action flow
- No git SHA linkage
- Missing captions
- Screenshot-only evidence for flow claims
- Manual drag-drop as the only publication path
- Media inaccessible to the intended reviewer

## Authorization vs Capability (MANDATORY)

Before choosing a capture method, distinguish three separate things:
1. **Task authorization** — you already have authorization to do routine,
   in-scope evidence capture; a failed OS-level capture probe does NOT mean
   the user withheld authorization.
2. **OS capability** — whether one process/tool can capture the screen
   natively (e.g. a CoreGraphics/Screen Recording permission check).
3. **Evidence sufficiency** — whether the required frames and provenance can
   be produced through an authorized, already-available alternative (e.g. a
   scoped headless browser driver, see "Scoped Browser Ownership" above).

Rules:
- **Never run a TCC/permission reset as a diagnostic probe** (e.g. `tccutil
  reset ScreenCapture`, or any command that mutates OS privacy grants) to test
  whether capture works. This destroys unrelated apps' existing grants and is
  not reversible from inside the agent.
- Exhaust all authorized, scoped, headless capture alternatives (Option 1 and
  Option 3 above) before concluding that human/OS-level consent is required.
- If genuine OS consent is required after alternatives are exhausted, report
  the exact capability gap and the alternatives you tried —
  do not claim the user withheld authorization and do not declare the whole goal blocked.
- Do not fabricate a browser address bar or native chrome to satisfy the
  Mandatory Frames table when actual capture is headless.

## Reviewer Checklist

1. Video is linked from the review receipt at an authorized, reviewer-accessible destination
2. Any publication follows the authorized destination and applicable automation workflow
3. Captions are present
4. Each clip meets the [action-window rule](#action-must-be-in-the-window-mandatory), including proof of absence where applicable
5. URL and route match claim
6. Actual baseline and candidate source linkage is verified, not inferred from captions
7. The reviewed evidence receipt includes matching metadata/caption artifacts
8. mpdecimate retained-frame count reported as kept/nominal (see Frozen-frame detection); a low count triggers provenance/timeline review, while a constructed slideshow always fails under the canonical rule
9. Before/after provenance is fresh runs of each build, or labeled `derived` with source
10. `/er` and second-opinion (`advice` skill) verdicts come from a different agent/lane than the evidence producer, and name that lane
11. An independent AI reviewer (not the author or orchestrator) judged frames extracted from the
    published video against each acceptance step, with PASS/FAIL and timestamps;
    privacy, playback, and upload checks are separate and do not substitute
    (`evidence-review` check 4)

## Frozen-frame and slideshow detection (MANDATORY)

The canonical continuous-video prohibition is in [`evidence-standards`](../evidence-standards/SKILL.md#continuous-video-only--slideshows-are-forbidden). It is absolute: the motion probe below is diagnostic evidence, never permission to accept a screenshot sequence, and captions or named action frames never waive the prohibition.

Report the mpdecimate **retained-frame count** (kept) and the nominal frame
count for every clip. The probe must fail closed: a failed decode or empty count
is an error, never "zero frames".

```bash
set -o pipefail
kept=$(ffmpeg -nostdin -v error -i v.mp4 -vf mpdecimate -f null -progress pipe:1 - \
  | grep -o '^frame=[0-9]*' | tail -1 | cut -d= -f2) || { echo "probe FAILED"; exit 1; }
nominal=$(ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames -of csv=p=0 v.mp4) || { echo "ffprobe FAILED"; exit 1; }
[ -n "$kept" ] && [ -n "$nominal" ] || { echo "count unavailable: FAILED"; exit 1; }
echo "kept=$kept nominal=$nominal"
```

A low retained-frame count triggers provenance and timeline review; it is not
standalone proof of a slideshow and is not an automatic rejection of legitimate
continuous footage with an idle interval. A constructed still-image sequence
always fails under the canonical rule regardless of its retained-frame count,
caption, or successful decode.

## Action must be in the window (MANDATORY)

On each revision where the action exists, show the starting state, the actual
action, and the result continuously. A result-only clip fails. If the action
does not exist on one revision, show the actual prior experience or its absence
in the matching state on that side. Do not substitute a no-op for the action.

When there is no in-app action, mark it N/A and record the observable transition
through its result. For load or mount claims, start recording before navigation
or the triggering event, and keep the ordinary loading sequence in the clip.

## Provenance of before/after clips (MANDATORY)

Before and after clips must come from fresh runs of each build (baseline and
candidate). Any re-cut, trimmed, or reused baseline clip must be labeled
`derived` in its caption and receipt, with its source (original artifact URL,
build SHA, and run). Unlabeled derived clips are INSUFFICIENT.

## Reviewer independence

`/er` and second-opinion (`advice` skill) verdicts on UI video evidence must come from an agent other
than the one that produced the evidence. Self-review does not satisfy either
gate.

## First-frame verification (MANDATORY)

1. **Match the start to the claim.** For a journey starting on a ready page,
   use the expected visible UI state, not a fixed sleep, as the recording
   boundary. For load or mount claims, readiness is a check during recording,
   not a prerequisite to start.
2. **Verify the first frame visually before pushing.** Extract frame 1 and
   confirm the expected starting boundary. A genuine blank or loading frame
   before the page appears is valid for a load claim only if the trigger,
   relevant frames, and resulting state are visible in the same continuous clip:

   ```bash
   ffmpeg -i video.mp4 -vf "select=eq(n\,0)" -vframes 1 frame1.png
   ```

3. **Evidence Gate caveat:** the `evidence-gate` CI check validates `metadata.json` freshness, NOT visual content. Visual verification is the responsibility of the agent presenting the evidence — a green evidence-gate says nothing about whether the video shows anything.

### Project capture helpers

Use the project's shared capture helpers for ready-page recordings where
available. For a load or mount claim, use readiness helpers after starting the
recorder and verify the starting boundary visually; do not apply a blanket
nonblank-first-frame check.

## Slack Distribution — Native Attachments Only

When distributing video or visual evidence to Slack (channels, incident threads, or DMs):
- **NEVER** use text-only Slack MCP tools (`conversations_add_message`) to send bare paths or GitHub URLs. Text-only message tools do not render media inline.
- **ALWAYS** use the dedicated uploader script:
  ```text
  python3 ../slack-media-upload/scripts/slack_upload.py [--dm | --channel <id>] --file <path> [--title <title>...] [--thread-ts <ts>] [--comment <text>]
  ```
- This wraps Slack's two-step `files.getUploadURLExternal` → `files.completeUploadExternal` API so videos and GIFs render directly inline in Slack.
