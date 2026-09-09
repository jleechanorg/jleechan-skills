---
name: ui-video-evidence
description: Record captioned browser/UI evidence videos and link sanitized artifacts for authorized review
---

# UI Video Evidence for Visual Verification

## Purpose

Prove user-visible behavior in a way reviewers and agents can verify quickly from the PR conversation.

## When UI Video Is Mandatory

UI/browser video is mandatory whenever work is user-facing, including:
- Visual/UI layout or styling changes
- Click flows, form submit flows, navigation, or modal behavior
- New/changed browser interactions
- Any claim of visual correctness or lack of visual regression

If a PR touches user-facing behavior, missing UI video is an evidence failure.

## Required Outputs

Each UI evidence run must provide:
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
`~/.claude/skills/browser-testing/SKILL.md`). If a scoped owner exists and
forbids headed/manual capture or Claude-in-Chrome, its policy wins — use its
designated headless tool (Aside CLI/`aside-mcp`, or headless Playwright). Do
not escalate to a native-chrome/manual-capture requirement, and do not ask for
Screen Recording permission, when a scoped headless path is available and not
documented as blocked.

## Mandatory Frames

| # | Frame | Must show |
|---|-------|-----------|
| 1 | URL + Page Load | Full native browser URL bar with route under test, OR — when the scoped owner mandates headless capture — a genuine route/URL provenance marker (printed navigation URL/log line, on-page route text, or window title) captured from the same automated session and tied to the frame timestamp |
| 2 | Before State | Initial state before action |
| 3 | Action | Click/input/navigation action |
| 4 | After State | Resulting state after action |
| 5 | Git Linkage | Terminal split, devtools log, or on-page SHA marker |

## Recording Options

### Option 1: Scoped headless driver (Aside / Playwright) — DEFAULT when a repo forbids headed capture
Follow `~/.claude/skills/browser-testing/SKILL.md`: drive the browser headlessly
via Aside CLI/`aside-mcp` or headless Playwright, log the navigated URL/route to
the terminal or an overlay, and record with the scoped repo's own recorder
(e.g. `testing_ui/streaming/base.py` `UIVideoRecorder`) or `ffmpeg` (Option 3).
Never use `mcp__claude-in-chrome__*` or any headed browser for this path.

### Option 2: Manual desktop capture (Kap) — LAST RESORT ONLY
Only when no repo-scoped headless policy exists AND native browser chrome is
required. Do not use this when the repo forbids headed/manual capture.
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

Use `~/.claude/skills/video-caption/SKILL.md` for reliable burned-in captions.

## Evidence access and authorized publication

Follow `~/.claude/skills/evidence-standards/SKILL.md` for publication authority, audience, and destination. A PR, checked-in document, access-controlled receipt/store, or authorized gist may link the evidence. A gist or GitHub upload is not an independent acceptance requirement. Preserve real media, captions, exact source provenance, and reviewer access; publish only within the current authorization.

The following GitHub release example applies only when that destination is authorized. Verify all declared media and caption inputs exist before creating the release; do not invent fallback PR targets. Set `caption_file` to the actual generated `.vtt` or `.srt` path when using a sidecar; leave it empty only when captions are already burned into the video. The asset list includes the sidecar only when set.

```bash
(
  set -euo pipefail
  if [[ -z "${PR_NUMBER:-}" || "$PR_NUMBER" == *"<"* ]]; then
    echo "Error: PR_NUMBER must be set to a valid PR number before publication" >&2
    exit 1
  fi

  video_file="${VIDEO_FILE:-/tmp/ui_flow.mp4}"
  preview_file="${PREVIEW_FILE:-/tmp/ui_flow.gif}"
  caption_file="${CAPTION_FILE:-}"  # Set to the actual .vtt or .srt path unless captions are burned in.
  zip_file="${ZIP_FILE:-/tmp/ui_flow.mp4.zip}"

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
  gh release create "$tag" --draft --title "PR #${PR_NUMBER} Evidence" --notes ""
  gh release upload "$tag" "${assets[@]}" --clobber
  gh release view "$tag" --json assets,url
)
```

From the JSON output returned by `gh release view`, extract the uploaded asset URLs and construct `/tmp/pr_body.md`. Do not guess draft asset download URLs or invent placeholder URLs.

Once `/tmp/pr_body.md` is constructed, update the authorized PR:

```bash
(
  set -euo pipefail
  if [[ -z "${PR_NUMBER:-}" || "$PR_NUMBER" == *"<"* ]]; then
    echo "Error: PR_NUMBER must be set to a valid PR number before publication" >&2
    exit 1
  fi
  target_pr="${PR_NUMBER_OR_URL:-$PR_NUMBER}"
  body_file="${BODY_FILE:-/tmp/pr_body.md}"
  if [ ! -s "$body_file" ]; then
    echo "Error: PR body file '$body_file' does not exist or is empty" >&2
    exit 1
  fi
  gh pr edit "$target_pr" --body-file "$body_file"
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
- Success-only clip (no before/action)
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
4. Before/action/after flow is visible
5. URL and route match claim
6. Git SHA linkage is visible
7. The reviewed evidence receipt includes matching metadata/caption artifacts

## First-frame verification (MANDATORY)

Moved here from `~/.claude/CLAUDE.md` on 2026-07-25. Applies to AGY CLI and any browser-capture pipeline.

1. **Wait for page readiness before capture.** Replace fixed-delay sleeps with `page.wait_for_load_state("networkidle")` AND `page.wait_for_selector(<expected-ui-element>, state="visible")`. A blank/white first frame is invalid evidence — it means the page had not rendered.
2. **Verify the first frame visually before pushing.** Extract frame 1 from the MP4 and confirm it shows the expected starting state (dashboard, modal opener, etc.), not a loading screen:

   ```bash
   ffmpeg -i video.mp4 -vf "select=eq(n\,0)" -vframes 1 frame1.png
   ```

3. **Reject evidence with a white/blank first frame.** Re-capture with stronger wait conditions. Do not publish a blank capture and label it as evidence.
4. **Evidence Gate caveat:** the `evidence-gate` CI check validates `metadata.json` freshness, NOT visual content. Visual verification is the responsibility of the agent presenting the evidence — a green evidence-gate says nothing about whether the video shows anything.

### Capture script standard *(your-project.com-specific)*

Every `testing_ui/capture_*.py` script must use the shared `browser_test_helpers.py` helpers — `wait_for_page_ready()` and `verify_first_frame_not_blank()`. New scripts that re-implement waits inline are a regression.

## Slack Distribution — Native Attachments Only

When distributing video or visual evidence to Slack (channels, incident threads, or DMs):
- **NEVER** use text-only Slack MCP tools (`conversations_add_message`) to send bare paths or GitHub URLs. Text-only message tools do not render media inline.
- **ALWAYS** use the dedicated uploader script:
  ```text
  python3 ~/.claude/skills/slack-media-upload/scripts/slack_upload.py [--dm | --channel <id>] --file <path> [--title <title>...] [--thread-ts <ts>] [--comment <text>]
  ```
- This wraps Slack's two-step `files.getUploadURLExternal` → `files.completeUploadExternal` API so videos and GIFs render directly inline in Slack.
