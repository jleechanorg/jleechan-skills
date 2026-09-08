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

## Mandatory Frames

| # | Frame | Must show |
|---|-------|-----------|
| 1 | URL + Page Load | Full browser URL bar with route under test |
| 2 | Before State | Initial state before action |
| 3 | Action | Click/input/navigation action |
| 4 | After State | Resulting state after action |
| 5 | Git Linkage | Terminal split, devtools log, or on-page SHA marker |

## Recording Options

### Option 1: Claude-in-Chrome GIF/Video workflow
Use browser automation and record the full flow while keeping URL visible.

### Option 2: Kap (manual desktop capture)
```bash
brew install --cask kap
```
Record browser window including address bar.

### Option 3: ffmpeg (headless/CI)
```bash
ffmpeg -video_size 1280x720 -framerate 10 -f x11grab -i :99 -t 30 /tmp/<work_name>.mp4
```

## Caption Requirements (MANDATORY)

Both tmux and UI videos must always have captions.

Accepted forms:
1. Burned-in captions in the video (preferred)
2. Sidecar caption file (`.vtt`/`.srt`) linked alongside the reviewed media artifacts

Use `~/.claude/skills/video-caption/SKILL.md` for reliable burned-in captions.

## Evidence access and authorized publication

Follow `~/.claude/skills/evidence-standards/SKILL.md` for publication authority, audience, and destination. A PR, checked-in document, access-controlled receipt/store, or authorized gist may link the evidence. A gist or GitHub upload is not an independent acceptance requirement. Preserve real media, captions, exact source provenance, and reviewer access; publish only within the current authorization.

The following GitHub release example applies only when that destination is authorized. This example uses a sidecar: set `caption_file` to the actual generated `.vtt` or `.srt` path. For captions already burned into the video, omit the sidecar argument.

```bash
caption_file="/abs/path/to/ui_flow.vtt"
zip -j /tmp/ui_flow.mp4.zip /abs/path/to/ui_flow.mp4
gh release create evidence-pr-<PR_NUMBER> --draft --title "PR #<PR_NUMBER> Evidence" --notes "" 2>/dev/null || true
gh release upload evidence-pr-<PR_NUMBER> /tmp/ui_flow.mp4.zip /abs/path/to/ui_flow.gif "$caption_file" --clobber
gh release view evidence-pr-<PR_NUMBER> --json assets,url
gh pr edit <PR_NUMBER_OR_URL> --body-file /tmp/pr_body.md
```

For this authorized GitHub example, build `/tmp/pr_body.md` from the asset URLs returned by `gh release view --json assets,url`. Do not guess the final download URL for draft releases. Other authorized destinations use their own verified artifact locations.

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
