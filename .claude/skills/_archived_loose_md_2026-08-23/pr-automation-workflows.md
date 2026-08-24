# PR Automation Workflows

**CRITICAL**: There are FOUR distinct workflows, each running on separate cron schedules. They are NOT conditional branches - they are separate execution modes.

## 1. Comment-Only Mode (Default)
**Cron**: Every hour (`0 * * * *`)
**Command**: `jleechanorg-pr-monitor --max-prs 10`

**What it does**:
- Posts "Codex support" comments on ALL non-draft PRs (regardless of branch name)
- Comment format: Asks Codex to provide coding assistance
- Target: Up to 10 PRs per run
- Marker: `<!-- codex-automation-commit:SHA -->`

**Scope**: ALL open, non-draft PRs in the organization

## 2. Comment-Validation Mode
**Cron**: Every 30 minutes (`*/30 * * * *`)
**Command**: `jleechanorg-pr-monitor --comment-validation --max-prs 10`

**What it does**:
- Posts comment validation requests on ALL non-draft PRs (regardless of branch name)
- Comment format: `@coderabbit-ai @greptileai @bugbot @copilot` - asks bots to review
- Target: Up to 10 PRs per run
- Marker: `<!-- comment-validation-request:SHA -->`

**Scope**: ALL open, non-draft PRs in the organization

## 3. Fixpr Mode
**Cron**: Every 30 minutes (`*/30 * * * *`)
**Command**: `jleechanorg-pr-monitor --fixpr --max-prs 10 --cli-agent gemini,cursor`

**What it does**:
- Fixes merge conflicts and failing CI checks
- Uses orchestrated PR runner with Gemini/Cursor agents
- Target: Up to 10 PRs with conflicts or failing checks
- Only processes PRs that have actual issues (conflicts/failing checks)

**Scope**: PRs with merge conflicts OR failing CI checks

## 4. Fix-Comment Mode (Currently Disabled)
**Cron**: Commented out
**Command**: `jleechanorg-pr-monitor --fix-comment --cli-agent gemini,cursor --max-prs 3`

**What it does**:
- Resolves PR review comments
- Uses Gemini/Cursor to address bot feedback
- Target: Up to 3 PRs per run

**Scope**: PRs with unaddressed review comments

## Additional Workflows

### Codex Update Mode
**Cron**: Every hour at :15 (`15 * * * *`)
**Command**: `jleechanorg-pr-monitor --codex-update`
**What**: Runs Codex automation tasks (browser-based)

### Codex API Mode
**Cron**: Every hour at :30 (`30 * * * *`)
**Command**: `jleechanorg-pr-monitor --codex-api --codex-apply-and-push`
**What**: Runs Codex automation via API (not browser)

## Key Distinctions

| Workflow | Posts Comments? | Branch Filter? | Target PRs |
|----------|----------------|----------------|------------|
| Comment-only | Yes (Codex support) | **NO** - ALL PRs | All non-draft |
| Comment-validation | Yes (bot review) | **NO** - ALL PRs | All non-draft |
| Fixpr | No (fixes issues) | **NO** | PRs with conflicts/failing checks |
| Fix-comment | No (addresses comments) | **NO** | PRs with review comments |

## Common Mistakes

❌ **WRONG**: "Comment-only mode should only post on Codex branches"
✅ **RIGHT**: "Comment-only mode posts on ALL non-draft PRs"

❌ **WRONG**: "Comment-validation is for non-Codex branches only"
✅ **RIGHT**: "Comment-validation is a separate cron job that runs on ALL non-draft PRs"

❌ **WRONG**: "Use branch name to decide which comment type to post"
✅ **RIGHT**: "The cron job determines the comment type (--comment-validation flag)"

## Implementation

The monitoring cycle code path (line 4003 in jleechanorg_pr_monitor.py):

```python
if comment_validation:
    # Post comment validation request (asks AI bots to review)
    comment_result = self.post_comment_validation_request(repo_full_name, pr_number, pr)
else:
    # Post codex instruction comment (asks Codex to code)
    comment_result = self.post_codex_instruction_simple(repo_full_name, pr_number, pr)
```

**The flag determines the comment type, NOT the branch name.**


## Copilot and Codex Tracking Requirements

When automation (Codex) or the `/copilot` tool fixes PR comments, require URL tracking artifacts:
- `responses.json` entries should include `html_url` for each processed comment.
- Tracking commits should include the appropriate marker:
  - `[codex-automation-commit]` for automation system tasks.
  - `[copilot-commit]` for `/copilot` tool executions.
- Commits should use separate URL buckets for:
  - `FIXED`
  - `CONSIDERED` (`ACKNOWLEDGED`/`DEFERRED`/`NOT_DONE`)
- If `responses.json` is missing URLs, backfill from `comments.json` by matching comment IDs in a type-safe way (`(.id|tostring) == $id`).

This keeps both fix-comment/codex automation and manual `/copilot` workflows auditable and consistent with expectations.

