# /pr-media — PR Media Proof Capture & Attach

## Purpose

Capture visual evidence that a PR change works and attach it to the PR body. Inspired by Ryan's OpenAI Codex talk: "I'm expecting they did the job and that they can prove to me that the code is worth merging."

## Usage

- `/pr-media` — Run the full capture-and-attach workflow for the current PR

## Prerequisites

Before running, confirm:
- The PR exists (created via `gh pr create`)
- You know the PR number
- You have modified/created files in this worktree

## Execution

### Step 1: Detect Change Type

Determine what kind of change was made:

```bash
# List modified files
git diff --name-only origin/main

# Detect change type from file paths
CHANGED_FILES=$(git diff --name-only origin/main)
echo "$CHANGED_FILES"
```

| Change type | Indicators | Capture method |
|---|---|---|
| Web/UI | `packages/web/`, `.tsx`, `.jsx`, `.css` | Screenshot via Playwright or chrome MCP |
| CLI | `packages/cli/`, command-line output | Terminal output capture |
| Core | `packages/core/src/` | Test output (`pnpm test`) |
| Plugin | `packages/plugins/` | Test output or demo output |
| Docs/Root | `.md`, docs/, roadmap/ | Not applicable — use text evidence only |
| Config | `.yaml`, `.yml`, `.json` (config only) | Not applicable — use test output |

If the change touches multiple types, capture evidence for ALL types affected.

### Step 2: Capture Evidence

#### For Web/UI changes

```bash
# Option A: Use Playwright (packages/web/e2e/screenshot.ts)
cd packages/web
pnpm exec playwright screenshot <url> [--full-page] output.png

# Option B: Use chrome MCP navigate + screenshot tools
# mcp__chrome-superpower__navigate_to(url)
# mcp__chrome-superpower__take_screenshot(output_path)
```

#### For CLI/Core/Plugin changes

```bash
# Run the relevant test suite and capture output
pnpm test 2>&1 | tee /tmp/test-output.txt

# Or capture relevant command output
<your-command> 2>&1 | tee /tmp/cmd-output.txt

# For packages/web: capture Playwright screenshot of key UI state
cd packages/web
# Ensure dev server is running, then screenshot
```

#### For config/refactor-only changes (no visual output possible)

```bash
# Capture test results showing nothing broke
pnpm test 2>&1 | tee /tmp/test-output.txt
```

### Step 3: Build Evidence Section

Construct the evidence markdown to append to the PR body.

For **screenshot evidence**:
```markdown
## Evidence
**Claim class**: unit-test-coverage
**Verdict**: PASS

**Media**: https://github.com/<owner>/<repo>/raw/<branch>/path/to/screenshot.png

**Description**: Brief description of what the screenshot proves.
```

For **terminal output evidence**:
```markdown
## Evidence
**Claim class**: unit-test-coverage
**Verdict**: PASS

**Test output**: pnpm test output (see code block below)

```
$ <command>
<actual output showing expected behavior>
```

**Description**: Terminal output proving the change works correctly.
```

### Step 4: Attach to PR

```bash
# Get current PR body
gh pr view <PR_NUMBER> --repo <OWNER>/<REPO> --json body --jq '.body' > /tmp/pr_body.txt

# Append Evidence section
cat /tmp/pr_body.txt | head -c 65000 > /tmp/pr_body_trimmed.txt  # GitHub limit
printf '\n\n%s' "$EVIDENCE_SECTION" >> /tmp/pr_body_trimmed.txt

# Update PR body
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER> \
  --method PATCH \
  --field body="@/tmp/pr_body_trimmed.txt"
```

Note: If GitHub's API rejects the body update (e.g., image path doesn't exist), the Evidence section should be included in the initial PR body at creation time, not patched after.

### Step 5: Commit the screenshot artifact (if any)

```bash
git add path/to/screenshot.png
git commit -m "[agento] chore: add pr-media screenshot for bd-<id>"
git push
```

## Evidence Quality Standards

- **Screenshot must show the change working** — not just the code diff, but the runtime result
- **Terminal output must be actual output**, not fabricated — run the real command
- **Include context**: what command was run, what the expected output is, how it proves the feature works
- **Screenshots must be readable** — ensure adequate resolution and lighting (for UI screenshots)

## Verification

After attaching, verify the PR body contains the Evidence section:

```bash
gh pr view <PR_NUMBER> --repo <OWNER>/<REPO> --json body --jq '.body' | grep -A5 "## Evidence"
```

If the Evidence section is missing, the evidence-gate CI check will fail.

## Edge Cases

- **Large screenshots**: Compress to < 5MB before committing (use `pngquant` or similar)
- **No display available**: If running headless in CI, use Playwright in headless mode — it works without a physical display
- **PR already created without evidence**: Update the PR body immediately using Step 4 above
