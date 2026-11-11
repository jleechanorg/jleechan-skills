---
name: goalexec-define
description: Define goal criteria without executing — just parse and save
---

# /goalexec_define Skill

Define a goal with measurable success criteria and save it, without starting any execution loop. Use when you want to define a goal and hand off execution separately.

## Usage

```
/goalexec_define "Fix the rewards latency issue"
```

## Behavior

1. **Parse goal statement** from arguments
2. **Extract success criteria** — derive measurable, testable criteria:
   - "Create X" → "X exists with correct content"
   - "Fix Y" → "Y no longer fails"
   - "PR merged" → "PR state = MERGED"
   - "All tests pass" → "Test exit code = 0"
3. **Save goal to `goals/.current-goal`** (flat file, single active goal):
   ```
   # Goal
   <original statement>

   ## Success Criteria
   1. <criterion>
   2. <criterion>
   ...
   ```
4. **Announce criteria** — display them clearly

Does NOT start any loop or cron. Use `/goalexec` to define AND execute.

## Criteria Extraction Patterns

| Goal phrase | Criterion |
|-------------|-----------|
| "Create X" | X exists with correct content |
| "Fix Y" | Y no longer fails |
| "PR merged" | PR state = MERGED |
| "All tests pass" | Test exit code = 0 |
| "Implement Z" | Z works as specified |
