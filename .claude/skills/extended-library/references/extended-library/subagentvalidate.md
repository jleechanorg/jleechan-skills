---
description: /subagentvalidate Command - Dual Consultant Validation Sweep
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: Establish Validation Target

**Action Steps:**
1. Scan the last **10 messages** in the conversation context for either:
   - The latest reported automated test results (look for markers such as "Test Results:", "Test Output:", or "Pass/Fail:"), or
   - The latest claims/conclusions produced by the main coding agent (look for markers such as "Claim:", "Conclusion:", or "Summary:").
2. If neither is present, request the coding agent (or operator) to supply the relevant test output or claim before proceeding.
3. Summarize the target to validate (what was claimed, key files/behaviors involved, reported pass/fail state).

### Phase 1: Select Consultant Pair

**Action Steps:**
1. Choose exactly **two** distinct consultant subagents from:
   - `codex-consultant` (architecture & scalability)
   - `gemini-consultant` (best practices & performance)
   - `cursor-consultant` (pragmatic implementation & deployment)
   - `code-centralization-consultant` (duplication & cohesion)
   - `code-review` (generalist code reviewer)
2. Prioritize consultants whose specialties best match the validation target. Example heuristics:
   - Architecture or design claims → include `codex-consultant`.
   - Performance, quality, or "best practice" claims → include `gemini-consultant`.
   - Implementation practicality or deployment readiness → include `cursor-consultant`.
   - Refactoring, deduplication, or shared utility claims → include `code-centralization-consultant`.
   - Broad correctness assertions → include `code-review`.
3. Record the selected pair in TodoWrite before launching the tasks.

### Phase 2: Parallel Consultant Execution

**Action Steps:**
1. Launch both consultants **in the same message** using the `Task` tool for true parallel execution.
2. Each task must include:
   - `subagent_type` set to the chosen consultant (e.g., `"codex-consultant"`).
   - A concise `description` (≤90 chars) stating the validation focus.
   - A detailed `prompt` containing:
     - Summary of the validation target from Phase 0.
     - Relevant code diffs, file paths, or test outputs (copy/paste snippets, not just references).
     - Explicit questions: "Do the provided results substantiate the claim?", "What contradicts the claim?", "What follow-up actions are required?"
3. Example structure:
   ```
   Task(
     subagent_type="codex-consultant",
     description="Validate architecture claim for auth refactor",
     prompt="""
     Context: Latest claim from main agent states ...
     Evidence: <summarized test output / diff>
     Questions:
       1. Do these results fully support the claim?
       2. Identify any missing checks or risks.
       3. List concrete follow-up tasks if validation fails.
     """
   )

   Task(
     subagent_type="gemini-consultant",
     description="Cross-check performance assurance",
     prompt="""
     <same context block tailored to consultant>
     """
   )
   ```
4. If any required evidence is unavailable, immediately halt execution and prompt the coding agent or operator for the missing information using TodoWrite. Do not run the subagents until the requested evidence arrives.

### Phase 3: Consolidate Findings

**Action Steps:**
1. Wait for both consultant responses and summarize their conclusions side-by-side (agreement, divergence, and key evidence).
2. Provide a final validation verdict:
   - ✅ Confirmed (both consultants agree the claim/test result stands), or
   - ⚠️ Needs follow-up (disagreement or missing evidence), or
   - ❌ Rejected (both consultants flag substantive issues).
3. List concrete next steps for the main coding agent (additional tests, code changes, documentation updates).
4. Update TodoWrite with completion status and major outcomes.

## 📋 REFERENCE DOCUMENTATION

# /subagentvalidate Command - Dual Consultant Validation Sweep

**Purpose**: Rapidly confirm whether the latest automated test results or coding-agent claims are trustworthy using two independent consultant subagents.

**Usage**:
```
/subagentvalidate [optional context]
```
- Optional argument can specify the claim or test suite to focus on.

**Key Behaviors**:
- Always operate on the **latest** relevant claim or test results in the conversation unless an explicit target is provided.
- Never run fewer or more than two consultants.
- Always run the two consultant tasks in parallel.
- Always return a clear verdict with actionable next steps.

**Troubleshooting**:
- If consultants give conflicting answers, surface both views and recommend additional validation work (rerun tests, request logs, etc.).
- If context is insufficient, request more info instead of guessing.
- Respect repository security guidance: never leak secrets, keep focus on current branch/PR.
