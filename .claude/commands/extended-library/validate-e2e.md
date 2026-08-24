# /validate-e2e — Audit test files for honest E2E classification

## Instructions for Claude

When this command is invoked, scan the specified test file (or all test files with "e2e" in the name) and check each against the 5 mandatory E2E criteria. Report violations honestly.

## Input

`/validate-e2e [file_path or directory]`

- If a file path is given, validate that single file.
- If a directory is given, find all files matching `*e2e*` and validate each.
- If no argument, search the current repo for all `*e2e*` test files.

## Validation Criteria

For each file with "e2e" in its name, check ALL 5:

### 1. Spawns real external work
- PASS: Contains `subprocess.run(["ao", "spawn"`, `gh pr create`, or similar real process spawning where the process is expected to DO WORK (not just return status)
- FAIL: Only imports modules, constructs objects in-memory, or calls functions directly

### 2. Waits for work to complete
- PASS: Contains `time.sleep`, polling loops, `subprocess.run` with timeout >30s waiting for external process output, or `ao status` polling
- FAIL: Spawns then immediately kills. No wait between spawn and verification. Process never does real work.

### 3. Verifies pipeline outcome
- PASS: Asserts on something that COULD ONLY EXIST if the pipeline ran — a new PR number, a new commit SHA, a CI status change, a merged PR, a Slack message
- FAIL: Asserts on return values of Python functions called in-process. Checks pre-existing resources. Verifies file writes to tmp_path.

### 4. Creates its own test data
- PASS: The test creates the PR/issue/session/branch it's testing. No hardcoded PR numbers pointing to pre-existing resources.
- FAIL: Uses `REAL_PR_NUMBER = 300` or similar constants pointing to resources that existed before the test ran.

### 5. Takes >60 seconds
- PASS: Test log shows wall clock >60s, OR test has explicit waits/polling that would take >60s
- FAIL: Completes in <60s. Real pipelines can't finish that fast.

## Output Format

For each file:

```
FILE: path/to/test_e2e_something.py
  [PASS/FAIL] 1. Spawns real external work: <evidence>
  [PASS/FAIL] 2. Waits for work to complete: <evidence>
  [PASS/FAIL] 3. Verifies pipeline outcome: <evidence>
  [PASS/FAIL] 4. Creates its own test data: <evidence>
  [PASS/FAIL] 5. Takes >60 seconds: <evidence>

  VERDICT: [GENUINE E2E / MISLABELED — rename to test_integration_* or test_smoke_*]
  RECOMMENDED NAME: <suggested rename if mislabeled>
```

## Action

After reporting, if any files are mislabeled:
1. List the `git mv` commands to rename them honestly
2. Ask the user if they want the renames executed
3. Do NOT auto-rename without confirmation
