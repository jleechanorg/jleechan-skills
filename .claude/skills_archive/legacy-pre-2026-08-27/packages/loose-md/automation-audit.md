# Automation Audit Skill

**Usage**: `/automation-audit [hours]`

**Purpose**: Comprehensive audit of all automation job runs - analyze logs, check PR processing metrics, and verify remote commits with attribution.

## Audit Metrics

### Primary Metrics to Collect

1. **PRs Discovered**: Total PRs found in scan (from `discovering open PRs` or `Total recent PRs discovered`)
2. **PRs Skipped**: PRs not processed (from `Skipping PR` or `already processed` messages)
3. **PRs Actioned**: PRs where work was attempted (from `Processing PR` messages)
4. **PRs with Commits**: PRs that resulted in remote commits with proper attribution

### Secondary Metrics

- **CLI Validation Results**: Which CLIs passed/failed preflight
- **Cycle Results**: From `Monitoring cycle complete: X actionable, Y skipped`
- **Errors/Warnings**: Any errors in the logs

## Execution Steps

### Step 1: Gather Log Files

```bash
# Primary job logs (in /tmp or $HOME/Library/Logs/)
FIXPR_LOG="/tmp/fixpr.log"
FIXCOMMENT_LOG="/tmp/fix-comment.log"
COMMENT_VAL_LOG="/tmp/comment-validation.log"

# Or from home directory
HOME_LOGS="$HOME/Library/Logs/${PROJECT_NAME:-your-project}-automation/"
```

### Step 2: Parse PR Metrics

Extract key metrics from each log:

```bash
# Count PRs discovered
grep -c "Total recent PRs discovered" "$LOG" || echo "0"

# Count PRs skipped
grep -c "Skipping PR" "$LOG" || echo "0"

# Count PRs processed (actioned)
grep -c "Processing PR" "$LOG" || echo "0"

# Count actionable results
grep -oE "Monitoring cycle complete: [0-9]+ actionable" "$LOG"
```

### Step 3: Check for Remote Commits

Query GitHub API for automation-authored commits:

```bash
# Time range (default: last 6 hours)
SINCE="${1:-6}"
SINCE_DATE=$(date -v-${SINCE}H +%Y-%m-%dT%H:%M:%SZ)

# Search for automation-authored commits
gh api repos/$GITHUB_REPOSITORY/commits \
  --since "$SINCE_DATE" \
  --jq '.[] | select(.commit.author.name |
    contains("claude") or
    contains("Claude") or
    contains("MiniMax") or
    contains("codex") or
    contains("Codex") or
    contains("automation") or
    contains("Copilot")
  ) | {sha: .sha[0:8], author: .commit.author.name, date: .commit.author.date}'
```

### Step 4: Verify Commit Attribution

For each commit found:
- Verify author name includes AI identifier
- Verify commit message follows conventions
- Verify Co-Authored-By attribution

```bash
# Check commit details
gh api repos/$GITHUB_REPOSITORY/commits/{sha} \
  --jq '.commit.message, .commit.author.name, .authors'
```

## Example Output

```
=== Automation Audit Report (Last 6 hours) ===

| Job          | PRs Discovered | PRs Skipped | PRs Actioned | Commits Made |
|--------------|---------------|-------------|--------------|--------------|
| fix-comment  | 12            | 10          | 2            | 1            |
| fixpr        | 12            | 12          | 0            | 0            |
| comment-val  | 8             | 8           | 0            | 0            |

=== CLI Preflight Results ===
- MiniMax: ✅ PASSED
- Gemini: ❌ FAILED (quota)
- Cursor: ❌ FAILED (auth)

=== Skip Decision Verification ===
⚠️ CRITICAL: 7 PRs incorrectly skipped - NEW COMMITS found!

| PR  | Processed Commit | Current HEAD | Status |
|-----|-----------------|---------------|--------|
| #5642 | c9270a4c | e815d36a | ❌ NEW COMMIT |
| #5641 | 88d4163d | 0609ae09 | ❌ NEW COMMIT |

=== Commits Made ===
- SHA abc1234: [copilot] fix: ... (PR #5584)
- Attribution: Claude Opus 4.6 <noreply@anthropic.com>
```

## Log File Locations

- `/tmp/fixpr.log` - fixpr job runs
- `/tmp/fix-comment.log` - fix-comment job runs
- `/tmp/comment-validation.log` - comment-validation job runs
- `$HOME/Library/Logs/${PROJECT_NAME:-your-project}-automation/` - persistent logs

## Key Log Patterns

| Pattern | Meaning |
|---------|---------|
| `Skipping PR ... - already processed` | PR already handled, no action needed |
| `Processing PR` | Work was attempted on this PR |
| `Monitoring cycle complete: X actionable, Y skipped` | Summary of cycle |
| `✅ Preflight: X passed` | CLI validation passed |
| `❌ Preflight: X failed` | CLI validation failed |

## Skeptical Review Checklist

- [ ] Are all "skipped" PRs legitimately already processed? (Check commit hash)
- [ ] Are any "actioned" PRs showing failures?
- [ ] Are commits properly attributed (Co-Authored-By)?
- [ ] Are there any errors in the logs that were missed?
- [ ] Did any PRs fail to get processed due to errors?

### Step 5: Verify Skip Decisions (CRITICAL)

For each skipped PR, verify the "already processed" commit matches current HEAD:

```bash
# Extract PR numbers and processed commits from logs
grep "Skipping PR" "$LOG" | grep -oE "#[0-9]+" | tr -d '#' | head -10

# For each PR, compare processed commit to current HEAD
# Processed: look for "already processed commit XXXXXXX"
# Current: gh api repos/owner/repo/pulls/{number} --jq '.head.sha'

# If they differ, this is a BUG - PR should have been reprocessed!
```

**Known Issues**:
- Commit hash may be truncated (7 chars) causing false positives
- History storage may be stale/out of sync

### Why Only N PRs?

The automation filters by `cutoff_hours` (default 24):
- Only PRs updated within the cutoff are discovered
- Total open PRs may be much larger (e.g., 2612) but only recent ones are scanned
- Verify with: `gh api "search/issues?q=repo:owner/repo+is:pr+is:open+updated:>YYYY-MM-DD"`
