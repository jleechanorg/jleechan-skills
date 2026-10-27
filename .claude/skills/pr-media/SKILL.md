---
name: pr-media
description: Capture visual evidence that a PR change works and attach it to the PR body
---

# /pr-media — PR Media Proof Capture & Attach

## Purpose

Capture visual evidence that a PR change works and attach it to the PR body. Show the evidence a reviewer needs to assess the change.

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
| Web/UI | `packages/web/`, `.tsx`, `.jsx`, `.css` | Screenshot through the repository's approved browser workflow |
| CLI | `packages/cli/`, command-line output | Terminal output capture |
| Core | `packages/core/src/` | Test output (`pnpm test`) |
| Plugin | `packages/plugins/` | Test output or demo output |
| Docs/Root | `.md`, docs/, roadmap/ | Not applicable — use text evidence only |
| Config | `.yaml`, `.yml`, `.json` (config only) | Not applicable — use test output |

If the change touches multiple types, capture evidence for ALL types affected.

### Step 2: Capture Evidence

#### For Web/UI changes

Use an isolated, approved browser route and save screenshots in the task's
unique `/tmp` evidence directory. Follow the browser owner at
`~/.claude/skills/browser-control/SKILL.md` and the repository evidence owner
for authentication, capture, and artifact handling.

#### For CLI/Core/Plugin changes

Run the relevant check and preserve its actual output in the task's unique
`/tmp` evidence directory, following the evidence owner's capture requirements.

#### For config/refactor-only changes (no visual output possible)

Capture applicable deterministic results in the task's unique `/tmp` evidence
directory. Follow the evidence owner for claim scope and publication.

### Step 3: Build Evidence Section

Construct the evidence markdown to append to the PR body.

For **screenshot evidence**:
```markdown
## Evidence
**Claim class**: unit-test-coverage
**Verdict**: PASS

**Evidence artifact**: <authorized gist or GCS evidence URL>

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
BODY_DIR=$(mktemp -d /tmp/pr-media.XXXXXX)
BODY_FILE="$BODY_DIR/pr-body.md"

# Get current PR body in the task's unique temporary directory
gh pr view <PR_NUMBER> --repo <OWNER>/<REPO> --json body --jq '.body' > "$BODY_FILE"

# Append Evidence section
head -c 65000 "$BODY_FILE" > "$BODY_DIR/pr-body-trimmed.md"  # GitHub limit
printf '\n\n%s' "$EVIDENCE_SECTION" >> "$BODY_DIR/pr-body-trimmed.md"

# Update PR body
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER> \
  --method PATCH \
  --field body="@$BODY_DIR/pr-body-trimmed.md"
```

Note: If GitHub's API rejects the body update (e.g., image path doesn't exist), the Evidence section should be included in the initial PR body at creation time, not patched after.

### Step 5: Publish evidence through the owning workflow

Keep captures in the task's unique `/tmp` evidence directory. When the workflow
requires durable evidence, publish it using the user-scope
`~/.claude/skills/evidence-standards/SKILL.md` procedure and attach its
authorized URL to the PR description. Never add screenshot or video artifacts
to the source repository.

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

- **Large screenshots**: Follow the evidence owner's size and integrity requirements before publication.
- **No display available**: If running headless in CI, use Playwright in headless mode — it works without a physical display
- **PR already created without evidence**: Update the PR body immediately using Step 4 above
