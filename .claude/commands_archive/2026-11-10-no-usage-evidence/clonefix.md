---
description: Clone PR, add TDD tests, and push to correct remote branch
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: Extract PR Information (⚠️ MANDATORY FIRST STEP)

**Action Steps:**
1. **Parse PR URL or number** from user input
2. **Extract repository owner and name** from PR URL (e.g., `jleechanorg/ai_universe_frontend`)
3. **Extract PR number** (e.g., `244` from `https://github.com/jleechanorg/ai_universe_frontend/pull/244`)
4. **Fetch PR head branch name** (CRITICAL - prevents wrong branch push):
   - **Preferred**: Use `gh pr view {pr_number} --json headRefName -q .headRefName` (handles auth automatically)
   - **Alternative**: Use GitHub API: `curl -H "Authorization: Bearer $GITHUB_TOKEN" -s https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number} | jq -r .head.ref`
   - **Store result** as `{verified_branch_name}` variable for use in subsequent phases
5. **Fetch PR base branch name**: Use `gh pr view {pr_number} --json baseRefName -q .baseRefName` OR GitHub API: `curl -H "Authorization: Bearer $GITHUB_TOKEN" -s https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number} | jq -r .base.ref`
6. **Store base branch** as `{base_branch}` variable for use in subsequent phases
7. **Verify branch names** before proceeding: Confirm both `{verified_branch_name}` and `{base_branch}` are set

**CRITICAL VERIFICATION STEPS:**
- Use GitHub API or `gh pr view` to get actual branch name
- NEVER assume branch name from PR number
- ALWAYS verify: `git branch -r | grep <branch-name>` or `gh pr view <number> --json headRefName`
- Store verified branch name for later push

### Phase 1: Clone Repository to /tmp

**Action Steps:**
1. **Create unique clone directory**: `/tmp/{repo_name}_clonefix_{timestamp}`
2. **Clone repository**: `git clone https://github.com/{owner}/{repo}.git {clone_dir}`
3. **Navigate to clone directory**: `cd {clone_dir}`
4. **Check if branch exists locally** (MUST check BEFORE fetch to avoid errors):
   - **Check if exists**: `git show-ref --verify --quiet refs/heads/{verified_branch_name}`
   - **If branch exists locally**: Create a backup copy before proceeding
     - Backup existing branch: `git branch {verified_branch_name}_backup_{timestamp} {verified_branch_name}`
     - Delete local branch to allow fetch: `git branch -D {verified_branch_name}` (safe since we have backup)
5. **Fetch the verified remote branch** from Phase 0:
   - **Fetch remote branch**: `git fetch origin {verified_branch_name}:{verified_branch_name}`
   - **Note**: This will create the local branch from the remote if it doesn't exist, or update it if it was deleted in step 4
6. **Checkout the verified remote branch locally**: `git checkout {verified_branch_name}`
   - **CRITICAL**: Use the actual remote branch name (`{verified_branch_name}`) from Phase 0, NOT `pr-{pr_number}`
   - This ensures the local branch matches the remote PR branch exactly
7. **Set upstream tracking**: `git branch --set-upstream-to=origin/{verified_branch_name} {verified_branch_name}`
   - **Explicit requirement**: The local branch must track the same upstream remote branch as the PR

**Verification:**
- Confirm clone successful
- Confirm on correct PR branch (should be `{verified_branch_name}`)
- Verify upstream tracking: `git branch -vv` should show `{verified_branch_name}` tracking `origin/{verified_branch_name}`
- List changed files: `git diff {base_branch}...HEAD --stat`

### Phase 1.5: Detect and Resolve Merge Conflicts (⚠️ NEW - CRITICAL)

**Action Steps:**
1. **Create proof directory** (CRITICAL - must exist before file writes):
   - **Create directory**: `mkdir -p /tmp/{repo_name}_clonefix_proof/`
   - **Note**: This directory is used throughout Phase 1.5 and later phases
2. **Check PR merge state** from GitHub (authoritative source):
   - **Get merge state**: `gh pr view {pr_number} --json mergeStateStatus -q .mergeStateStatus`
   - **Store result** as `{merge_state}` variable
   - **Save proof**: `echo "{merge_state}" > /tmp/{repo_name}_clonefix_proof/merge_state_before.txt`
3. **Evaluate merge state**:
   - **CLEAN** or **UNSTABLE**: No conflicts, proceed to Phase 2
   - **DIRTY**, **CONFLICTING**, **BLOCKED**, or **UNKNOWN**: Potential conflicts, continue to step 4
4. **Attempt merge with base branch** (for DIRTY, CONFLICTING, BLOCKED, or UNKNOWN states only - NOT UNSTABLE):
   - **Fetch latest base branch**: `git fetch origin {base_branch}`
   - **Attempt merge**: `git merge origin/{base_branch} --no-edit`
   - **If merge succeeds cleanly (no conflicts)**: Skip to step 7 (verification)
   - **If merge fails with conflicts**: Continue to step 5
5. **Auto-resolve common conflict patterns**:
   - **List conflicted files**: `git diff --name-only --diff-filter=U`
   - **For each conflicted file**:
     - **learnings.md pattern**: Keep both sides, remove markers
       ```bash
       # Remove conflict markers (use generic pattern to match any branch name)
       # CRITICAL: Use double quotes for variable expansion, escape properly
       sed -i '/^<<<<<<< HEAD$/d' "$file"
       sed -i '/^=======$/d' "$file"
       sed -i '/^>>>>>>> [^[:space:]]*$/d' "$file"
       # Deduplicate lines
       awk '!seen[$0]++' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
       git add "$file"
       ```
     - **CLAUDE.md pattern**: Prefer our version (PR branch)
       ```bash
       git checkout --ours "$file"
       git add "$file"
       ```
     - **Other patterns**: Apply intelligent resolution based on file type
   - **Check if all conflicts resolved**: `git diff --name-only --diff-filter=U`
   - **If unresolved conflicts remain**:
     - **Report to user**: List remaining conflicted files
     - **Request manual intervention**: "Cannot auto-resolve conflicts in: {files}"
     - **HALT workflow**: Do NOT proceed to Phase 2 until resolved
   - **Save proof of resolved files**: `git diff --name-only --cached > /tmp/{repo_name}_clonefix_proof/conflicts_resolved.txt`
6. **Commit conflict resolution** (only if conflicts were auto-resolved in step 5):
   ```bash
   git commit -m "resolve: Auto-resolve merge conflicts with {base_branch}

🤖 Generated by /clonefix command

Co-Authored-By: Claude <noreply@anthropic.com>"
   ```
7. **Verify resolution**:
   - **Push changes** (if any were made): `git push origin {verified_branch_name}`
   - **Check new merge state**: `gh pr view {pr_number} --json mergeStateStatus -q .mergeStateStatus`
   - **Save proof**: `echo "{new_merge_state}" > /tmp/{repo_name}_clonefix_proof/merge_state_after.txt`
   - **Verify CLEAN**: Confirm merge state is now "CLEAN" or "UNSTABLE"
   - **If still in failure state** (DIRTY, CONFLICTING, BLOCKED, or UNKNOWN): Report failure and halt workflow

**CRITICAL SAFETY CHECKS:**
- ❌ NEVER proceed to Phase 2 with unresolved conflicts
- ❌ NEVER skip conflict resolution if merge state is DIRTY
- ✅ ALWAYS verify merge state before and after resolution
- ✅ ALWAYS push resolution before adding tests
- ✅ ALWAYS commit resolution with descriptive message

**Conflict Resolution Verification:**
- Confirm merge state checked
- Confirm conflicts detected (if any)
- Confirm resolution attempted
- Confirm all conflicts resolved
- Confirm resolution pushed successfully
- Confirm new merge state is CLEAN

### Phase 2: Identify New Logic Requiring Tests

**Action Steps:**
1. **Review PR changes**: `git diff {base_branch}...HEAD`
2. **Identify new functionality** added in PR
3. **List files modified** with new logic
4. **Document what needs testing**:
   - New functions/methods
   - Changed behavior
   - Edge cases
   - Integration points

**Output:**
- Create summary of changes requiring tests
- Identify test framework (Jest, Vitest, pytest, etc.)
- Note existing test patterns in repo

### Phase 3: Execute TDD Workflow (/tdd)

**Action Steps:**
1. **Call `/tdd` command** with context about new logic
2. **Follow TDD methodology**:
   - Phase 0: Create test matrix
   - Phase 1 (RED): Write failing tests
   - Phase 2 (GREEN): Implement code to make tests pass
   - Phase 3 (REFACTOR): Refactor implementation code while keeping tests passing
3. **Ensure comprehensive coverage**:
   - Unit tests for new functions
   - Integration tests for workflows
   - Edge case coverage
   - Error handling tests

**Error Handling:**
- If `/tdd` command fails: Report error, show failed test file, ask user to review and retry
- If `/tdd` times out: Consider repo complexity; may need manual test creation
- If tests are incomplete: Use /tdd output as base and manually add missing test coverage

**Test Requirements:**
- All tests must follow existing test patterns in repo
- Tests must be properly organized (same structure as existing tests)
- Tests must use correct testing framework
- Tests must have proper mocking/setup

**Phase 3 Success Criteria (Gate to Phase 4):**
- ✅ All newly created tests pass locally
- ✅ Test framework correctly configured
- ✅ Test files organized in expected location
- ✅ Coverage target met (typically 80%+)
- If any criteria fails: Remain in Phase 3, fix issues, re-run /tdd or manually supplement tests

### Phase 4: Verify Tests Pass Locally

**Action Steps:**
1. **Run test suite**: Execute appropriate test command for repo
   - **If unknown**: Check `package.json` (npm/yarn), `Makefile`, `tox.ini`, `pyproject.toml`, `.github/workflows`, or ask /tdd output
   - **Common commands**: `npm test`, `yarn test`, `pytest`, `cargo test`, `go test ./...`
2. **Fix any issues**: Address linting errors, type errors, test failures
3. **Verify all tests pass**: Confirm 100% pass rate for new tests
4. **Save proof**: Create `/tmp/{repo_name}_clonefix_proof/` directory with:
   - Test output showing all tests passing
   - List of test files created
   - Test summary/coverage report

**Proof Files:**
- `test_results.txt` - Full test output
- `test_files_list.txt` - List of created test files
- `test_summary.json` - JSON summary with coverage
- `README.md` - Documentation of test suite

**Phase 4 Success Criteria (Gate to Phase 5):**
- ✅ All new tests pass with 0 failures
- ✅ Proof directory created with all required files
- ✅ test_results.txt shows "PASS" or equivalent success marker
- If any test fails: Fix the test code, re-run suite, confirm all pass before proceeding

### Phase 5: Verify Correct Remote Branch (⚠️ CRITICAL - PREVENTS WRONG BRANCH PUSH)

**Action Steps:**
1. **Get actual PR branch name** (re-verify from GitHub):
   - **Preferred**: Use `gh pr view {pr_number} --json headRefName -q .headRefName` (handles auth automatically)
   - **Alternative**: Use GitHub API with auth: `curl -H "Authorization: Bearer $GITHUB_TOKEN" -s https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number} | jq -r .head.ref`
   - **Note**: Authenticated requests get 5,000 requests/hour vs 60/hour unauthenticated. Required for private repos.
   - **Store result** as `{verified_branch_name}` variable (overwrites Phase 0 value if different)
2. **Verify branch exists remotely**: `git ls-remote --heads origin {verified_branch_name}`
3. **Confirm branch name matches**: Compare with Phase 0 verification (should match unless branch was renamed)
4. **Verify upstream tracking is correct**: `git branch -vv` should show `{verified_branch_name}` tracking `origin/{verified_branch_name}`
   - **Note**: Upstream tracking was already set in Phase 1, but verify it's still correct

**CRITICAL SAFETY CHECKS:**
- ❌ NEVER push without verifying branch name
- ❌ NEVER assume branch name from PR number
- ✅ ALWAYS verify with GitHub API or `gh` CLI
- ✅ ALWAYS confirm branch exists before push
- ✅ ALWAYS show user the branch name before pushing

### Phase 6: Commit and Push to Correct Branch

**Action Steps:**
1. **Stage test files**: `git add tests/**/*.test.* tests/**/*.spec.*`
2. **Stage test matrix/docs**: `git add tests/**/*matrix*.md`
3. **Commit with descriptive message**:
   ```
   test: add comprehensive TDD tests for {feature}

   - Add {N} tests covering {feature} functionality from PR #{pr_number}
   - Test files: {list}
   - All {N} tests passing locally
   - Follows TDD methodology with matrix-driven test coverage
   ```
4. **Verify remote branch again** (double-check before push)
5. **Push to verified branch**: `git push origin {verified_branch_name}`
   - **CRITICAL**: Since we're already on `{verified_branch_name}` (checked out in Phase 1), we can push directly
   - **Alternative explicit syntax**: `git push origin HEAD:{verified_branch_name}` (explicitly push current HEAD to remote branch)
   - **Note**: The local branch name matches the remote branch name, so `git push` will work correctly
6. **If push fails due to hooks**: Investigate the failure, fix the underlying issue, and re-run tests. Do NOT use `--no-verify` unless explicitly approved by repo maintainers and documented in the commit message.

**Pre-Push Verification:**
- Confirm branch name is correct
- Confirm commit message is descriptive
- Confirm all tests pass
- Confirm proof saved in /tmp

**Cleanup and Retention:**
- Proof directories in `/tmp` should be retained for at least 7 days for verification
- **Cleanup Safety**: Always run with `--dry-run` / `-print` first to preview what will be deleted
  - Example: `find /tmp -name "*_clonefix_*" -type d -mtime +30 -print` (preview only)
  - After confirming, run the destructive command: `find /tmp -name "*_clonefix_*" -type d -mtime +30 -exec rm -rf {} \;`
  - Alternative: Use `-delete` instead of `-exec rm` for atomic operation
- Note: `/tmp` is typically world-readable; avoid storing sensitive credentials in proof artifacts

### Phase 7: Create Summary Report

**Action Steps:**
1. **Document what was done**:
   - PR URL and number
   - Repository cloned to
   - **🆕 Merge conflicts detected** (if any)
   - **🆕 Conflicts auto-resolved** (list of files)
   - **🆕 Final merge state** (CLEAN/UNSTABLE)
   - Tests added (count and files)
   - Branch pushed to
   - Test results summary
2. **Save to proof directory**: `/tmp/{repo_name}_clonefix_proof/`
   - **🆕 Save merge_state_before.txt**: Initial PR merge state
   - **🆕 Save merge_state_after.txt**: Post-resolution merge state
   - **🆕 Save conflicts_resolved.txt**: List of auto-resolved files
3. **Report to user**:
   - Success confirmation
   - **🆕 Conflict resolution summary** (if applicable)
   - Branch name verified and pushed to
   - Test count and coverage
   - Proof location

## 📋 REFERENCE DOCUMENTATION

# CloneFix Command - Automated PR Test Addition

**Purpose**: Clone a PR, add comprehensive TDD tests, and push to the correct remote branch

**Usage**: `/clonefix <PR_URL>` or `/clonefix <owner>/<repo>#<pr_number>`

**Examples**:
- `/clonefix https://github.com/jleechanorg/ai_universe_frontend/pull/244`
- `/clonefix jleechanorg/ai_universe_frontend#244`

## Workflow Summary

1. **Extract PR Info** → Get repo, PR number, verify branch name
2. **Clone to /tmp** → Create unique directory, checkout PR branch
3. **🆕 Resolve Conflicts** → Detect and auto-resolve merge conflicts (NEW!)
4. **Identify Logic** → Review changes, determine what needs tests
5. **Execute /tdd** → Use TDD workflow to add comprehensive tests
6. **Verify Tests** → Run tests, fix issues, save proof
7. **Verify Branch** → CRITICAL: Get actual branch name from GitHub
8. **Commit & Push** → Push to verified correct branch
9. **Report** → Summary with proof location

## Critical Safety Rules

### Branch Verification Protocol

**MANDATORY STEPS BEFORE PUSH:**
1. Extract PR number from input
2. Query GitHub API or `gh` CLI for actual branch name
3. Verify branch exists remotely
4. Confirm branch name matches before push
5. Show user branch name for confirmation

**NEVER:**
- ❌ Assume branch name from PR number
- ❌ Push without verifying branch name
- ❌ Use the local branch name `pr-{num}` directly for push (always use `{verified_branch_name}` from GitHub)
- ❌ Skip branch verification step

**Note**: Phase 1 explicitly checks out the verified remote branch name (`{verified_branch_name}`) locally in the /tmp clone location. If the branch already exists locally, a backup copy is created before proceeding. The local branch is set to track the same upstream remote branch as the PR, ensuring consistency throughout the workflow.

**ALWAYS:**
- ✅ Use GitHub API or `gh pr view` to get branch name
- ✅ Verify branch exists before push
- ✅ Show user the branch name before pushing
- ✅ Double-check branch name in Phase 5 and Phase 6

## Error Handling

**If branch verification fails:**
- Report error to user
- Show available branches
- Ask user to confirm correct branch name
- Do NOT proceed without verification

**🆕 If merge conflicts detected:**
- Check PR merge state from GitHub
- Attempt auto-resolution using common patterns
- If auto-resolution fails, list conflicted files
- Request manual intervention for complex conflicts
- HALT workflow until conflicts fully resolved
- Verify merge state is CLEAN before proceeding

**If tests fail:**
- Fix linting/type errors
- Address test failures
- Re-run tests until all pass
- Do NOT push failing tests

**If push fails:**
- Check branch name again
- Verify remote exists
- Check permissions
- Report error with details

**Additional Edge Cases:**
- PR branch deleted from remote before Phase 1 completes: Abort workflow, report error
- PR branch force-pushed (local tracking stale): Re-fetch and verify branch name again
- Repo too large for `/tmp` storage: Use alternative temp location or check disk space first
- Network failures during long clone operations: Implement retry logic with exponential backoff
- Multiple simultaneous `clonefix` runs causing /tmp collision: Use unique timestamp in directory name (already implemented)
- **🆕 Merge conflicts that cannot be auto-resolved**: Report to user, provide conflicted file list, request manual resolution before proceeding

## Integration with /tdd

This command integrates with `/tdd` command:
- Calls `/tdd` internally for test creation
- Follows TDD methodology (RED → GREEN → REFACTOR)
- Uses matrix-driven test coverage
- Ensures comprehensive test suite

## Proof Directory Structure

```
/tmp/{repo_name}_clonefix_proof/
├── README.md                 # Summary documentation
├── merge_state_before.txt    # 🆕 PR merge state before conflict resolution
├── merge_state_after.txt     # 🆕 PR merge state after conflict resolution
├── conflicts_resolved.txt    # 🆕 List of auto-resolved conflicts (if any)
├── test_results.txt          # Full test output
├── test_files_list.txt       # List of test files
├── test_summary.json         # JSON summary
└── final_verification.txt    # Final test run proof
```

## 🆕 Merge Conflict Resolution Features

**Automatic Conflict Detection:**
- Queries GitHub PR merge state (authoritative source)
- Detects DIRTY, CONFLICTING, or BLOCKED states
- Halts workflow if conflicts present until resolved

**Intelligent Auto-Resolution:**
- **learnings.md**: Keeps both sides, removes markers, deduplicates
- **CLAUDE.md**: Prefers PR branch version (--ours strategy)
- **Future patterns**: Extensible for additional file-specific resolution strategies

**Safety Guarantees:**
- ✅ Never proceeds with unresolved conflicts
- ✅ Verifies merge state before and after resolution
- ✅ Pushes resolution before adding tests
- ✅ Saves proof of conflict resolution process
- ✅ Reports unresolvable conflicts to user for manual intervention

**Workflow Integration:**
- Runs after clone (Phase 1.5)
- Runs before test addition (Phase 2)
- Ensures clean merge state before TDD workflow
- Maintains full audit trail in proof directory
