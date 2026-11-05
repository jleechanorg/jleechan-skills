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
| UI claim | User-visible behavior | Follow the repository's browser and visual-evidence owners |
| CLI or service claim | Command or service behavior | Follow the repository's test and evidence owners |
| Documentation claim | Instruction or documentation behavior | Use text evidence scoped to the claim |
| Configuration claim | Configuration behavior | Follow the repository's validation owner |

Choose evidence by the claim and the target repository's owners, not by file
extension or directory name alone.

### Step 2: Capture Evidence

#### For Web/UI changes

Use an isolated, approved browser route and save screenshots under the task's
unique `/tmp/<repo>/evidence/...` directory, as specified by
`~/.codex/AGENTS.md` § Workspace and method fidelity. Follow the browser owner at
`~/.claude/skills/browser-control/SKILL.md` and the repository evidence owner
for authentication, capture, and artifact handling.

### Step 3: Prepare the evidence record

Follow `~/.claude/skills/evidence-standards/SKILL.md` to classify the claim,
assess what the artifact proves, and publish durable evidence when required.
Store captures under the task's unique `/tmp/<repo>/evidence/...` directory;
do not write artifacts into the repository. Do not assign a claim class or
`PASS` verdict solely because a screenshot or command output exists.

### Step 4: Update the PR description

Use the target repository's PR-description owner to add or update `## Evidence`
in its owned location before review-gate records. Preserve the complete existing
body and all review history. Never truncate or reconstruct the body, and never
append evidence after the final `## Advice Approval` section. Include only the
authorized evidence URL and claim supported by the artifact.

### Step 5: Verify the readback

Read the updated PR body and confirm the evidence record is present in the
correct section, prior gate records remain intact, and `## Advice Approval`
remains last. Verify the evidence URL through its owning workflow.

## Evidence Quality Standards

- **Screenshots establish only the visual claim they show.** They do not establish test coverage or a passing test run.
- **Terminal output must be actual output** from the target repository's supported check.
- **Include context**: what claim the artifact supports, what it proves, and what remains unproven.
- **Screenshots must be readable** — ensure adequate resolution and lighting (for UI screenshots)

## Edge Cases

- **Large screenshots**: Follow the evidence owner's size and integrity requirements before publication.
- **No display available**: Use the browser and capture route approved by the target repository's owner.
- **PR already created without evidence**: Update `## Evidence` in its owned location while preserving the complete description and final gate section.
