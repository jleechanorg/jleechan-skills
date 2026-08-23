---
description: Execute Ralph orchestration system for autonomous task execution
type: orchestration
---

# Ralph Orchestration Command

**Purpose**: Launch Ralph task agent to autonomously execute complex multi-step goals with continuous iteration until completion.

## ⚠️ Important: Ralph vs Genesis

**Ralph** = Standalone ralph-orchestrator fork at `$RALPH_REPO` (default: `$HOME/projects/ralph-orchestrator`)
- Uses Codex CLI by default (200K context via OpenRouter)
- Separate codebase from your project
- Command: `python -m ralph_orchestrator`

**Genesis** = Your project's orchestration system (different from Ralph!)
- Located at: `$PROJECT_ROOT/genesis/` (or your project's genesis path)
- **Uses Codex CLI by default** (can override with `--claude` flag)
- Command: `python genesis/genesis.py`
- See `/gene` command for Genesis execution

## Ralph Repository Location

**Required**: `$RALPH_REPO` (default: `$HOME/projects/ralph-orchestrator`)

This command will verify the Ralph repo exists before executing. If you want to use a different Ralph installation, specify the repo path as the first argument.

## Usage

```bash
/ralph_custom <goal-file-path> [max-iterations] [ralph-repo-path]
```

**Parameters**:
- `goal-file-path`: Path to markdown goal file defining the autonomous task
- `max-iterations`: (Optional) Maximum iterations before stopping (default: 20)
- `ralph-repo-path`: (Optional) Path to Ralph repo (default: `$HOME/projects/ralph-orchestrator`)

## How Ralph Works

Ralph is an autonomous task agent that:
1. **Uses Codex CLI by default** - larger context windows (200K tokens) via OpenRouter
2. **Reads goal files** in markdown format with clear success criteria
3. **Creates ta[REDACTED_OPENAI_KEY] agents** in tmux sessions for parallel work
4. **Iterates continuously** until goal completion or max iterations reached
5. **Self-corrects errors** by analyzing failures and adjusting approach
6. **Commits progress** regularly to track incremental changes
7. **Reports completion** with evidence of success criteria met

**Default Agent**: `--agent codex` (can override with `--agent claude`, `--agent gemini`, or `--agent auto`)
**Fallback Mode**: Use `--agent auto` to try Codex → Claude → Gemini automatically

## Goal File Format

Ralph goal files must follow this structure:

```markdown
# Goal: [Clear one-sentence goal statement]

## Current Status
[Document starting state]

## Tasks
1. **Task Name**: Clear, actionable task description
2. **Task Name**: Next sequential task

## Success Criteria
✅ Criterion 1 (measurable outcome)
✅ Criterion 2 (verification method)
✅ Criterion 3 (deliverable exists)

## Autonomous Execution
Ralph should:
1. Read this goal file
2. Execute all tasks sequentially
3. Test after each step
4. Document results
5. Commit and push when complete
```

## Best Practices for Ralph Goals

### ✅ DO: Write Autonomous-Ready Goals
- **Clear success criteria**: Ralph must know when it's done
- **Measurable outcomes**: "Tests pass" not "Code works"
- **Specific paths**: Provide exact file locations and repo paths
- **Sequential tasks**: Order matters - dependencies first
- **Test validation**: Include test commands Ralph can run
- **Commit protocol**: Specify when to commit (after each file, after task, etc.)

### ❌ DON'T: Create Vague Goals
- "Make it better" - No measurable outcome
- "Fix bugs" - Which bugs? Where?
- "Improve performance" - By how much?
- "Update documentation" - Which files? What content?

## Example: Production Deployment Goal

```markdown
# Goal: Complete Production MCP Server Deployment

## Current Status
✅ Mock server working (15/15 tests passing)
❌ Production server crashes (Firebase initialization error)

## Tasks

### Task 1: Fix Firebase Authentication
**Location**: `/path/to/project/src/config/firebase.ts`

**Issue**: Server crashes with "Service account object must contain 'private_key'"

**Fix**: Implement Application Default Credentials (ADC) support
```typescript
// Add ADC fallback path
else if (process.env.FIREBASE_PROJECT_ID) {
  console.log('🔑 Using Application Default Credentials (ADC)');
  firebaseApp = initializeApp({ projectId: process.env.FIREBASE_PROJECT_ID });
}
```

**Validation**:
```bash
cd /path/to/project
npm run build
npm start
curl http://localhost:3001/health  # Should return 200 OK
```

### Task 2: Test Production Functionality
After server starts successfully:

1. **Test campaign creation**:
```bash
curl -X POST http://localhost:3001/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","title":"Test Campaign","setting":"fantasy"}'
```

2. **Test interaction** (use campaign_id from step 1):
```bash
curl -X POST http://localhost:3001/api/campaigns/{id}/interaction \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","user_input":"I explore the dungeon"}'
```

3. **Verify in Firebase Console**: Campaign and interaction documents exist

### Task 3: Document Production Deployment

Create `PRODUCTION_DEPLOYMENT.md` with:
- Prerequisites (Node.js, Firebase, credentials)
- Environment variables required
- Deployment steps
- Validation tests
- Known issues

### Task 4: Commit and Push

```bash
git add -A
git commit -m "feat: add production deployment support with ADC authentication

- Implement Application Default Credentials fallback
- Add production deployment documentation
- Validate with real Firebase/Gemini credentials

Tested with campaign creation and interaction endpoints."
git push origin HEAD:production-deployment-work
```

## Success Criteria

✅ Production server starts without errors (health endpoint responds)
✅ Campaign creation works with real Firebase (document exists in Firestore)
✅ Interaction endpoint works with real Gemini (response generated)
✅ PRODUCTION_DEPLOYMENT.md exists with complete deployment guide
✅ All changes committed and pushed to remote branch
✅ Final validation report created with test results

## Autonomous Execution

Ralph should:
1. Read this goal file
2. Execute all 4 tasks sequentially
3. Test after each fix
4. Document results in validation report
5. Commit and push when complete
6. Report final status with evidence
```

## Ralph Orchestration Workflow

When you execute `/ralph_custom`:

1. **Verify Ralph Repository**
   ```bash
   # Default location (set RALPH_REPO or pass as parameter)
   RALPH_REPO="${RALPH_REPO:-$HOME/projects/ralph-orchestrator}"

   # Or use custom location from parameter
   if [ $# -ge 3 ]; then
       RALPH_REPO="$3"
   fi

   # Verify repo exists
   if [ ! -d "$RALPH_REPO" ]; then
       echo "❌ ERROR: Ralph repository not found at: $RALPH_REPO"
       echo "Please ensure ralph-orchestrator is cloned to the expected location"
       echo "Or specify custom path: /ralph_custom <goal-file> <iterations> <ralph-repo-path>"
       exit 1
   fi

   echo "✅ Found Ralph repository at: $RALPH_REPO"
   ```

2. **Goal File Validation**
   - Verify goal file exists and is readable
   - Check for required sections (Goal, Tasks, Success Criteria)
   - Confirm autonomous execution instructions present

3. **Launch Ralph Orchestrator**
   ```bash
   cd "$RALPH_REPO"

   # Activate virtual environment if it exists
   if [ -d ".venv" ]; then
       source .venv/bin/activate
   fi

   # Run Ralph with Codex agent (explicit default)
   python -m ralph_orchestrator "$GOAL_FILE" \
       --agent codex \
       --max-iterations "$MAX_ITERATIONS" \
       --verbose
   ```

4. **Monitor Ralph Progress**
   - Ralph creates tmux sessions for work
   - Agent logs to Ralph's log directory
   - Check Ralph output for progress updates

5. **Verify Completion**
   - Check Ralph's completion report
   - Verify all success criteria met
   - Review git commits for evidence of work

## Common Ralph Patterns

### Security-Sensitive Tasks
Ralph may refuse tasks that appear to violate security policies (credential harvesting, malicious code). If this happens:

1. **Clarify intent**: Update goal file to explain credentials already exist
2. **Change framing**: "TEST the server" not "FIND credentials"
3. **Provide context**: Explain this is legitimate development work

### Production vs Mock Mode
For testing with real services:

1. **Document credential location**: Tell Ralph where `.env` file is
2. **Specify test validation**: How Ralph verifies real service integration
3. **Expected errors**: Document known limitations (e.g., Firestore indexes)

### Commit Protocol
To avoid infinite loops, always specify commit frequency:

```markdown
## 🚨 MANDATORY COMMIT PROTOCOL

After creating or modifying ANY file, immediately commit:
```bash
git add <filename>
git commit -m "feat: add <filename>"
```

**Progress Validation (every 5 files)**:
1. Run: `git log --oneline | head -10`
2. Verify: `git status` shows clean
3. If untracked files exist, commit them before proceeding
```

## Troubleshooting

### Ralph Gets Stuck in Analysis Paralysis
**Symptom**: Ralph runs for hours but generates minimal code

**Solutions**:
1. Kill Ralph process: `pkill -f "orchestrate_unified.py.*<goal-file-name>"`
2. Review goal file - may be too vague or lack measurable success criteria
3. Add explicit commit protocol to force progress tracking
4. Reduce max iterations to force completion

### Ralph Refuses Security-Sensitive Tasks
**Symptom**: Ralph stops with "violates security policy" message

**Solutions**:
1. Update goal file to clarify legitimate intent
2. Change task framing from "search for" to "use existing"
3. Document that credentials/resources already exist
4. Provide exact file paths to eliminate search behavior

### Ralph Claims Success Without Changes
**Symptom**: Ralph reports task complete but `git status` shows no changes

**Solutions**:
1. Add verification checklist to goal file:
   - File existence check
   - Git diff validation
   - Commit verification
   - Work evidence (file paths + line numbers)
2. Require Ralph to provide specific evidence of changes
3. Mandate git commit after each task

## Integration with Other Commands

- **`/orch`**: Launch generic orchestration (use Ralph for autonomous task execution)
- **`/converge`**: Similar autonomous execution with different iteration strategy
- **`/cons`**: Review Ralph's code quality after completion
- **`/checkpoint`**: Save Ralph's progress before major changes

## Real-World Ralph Usage Example

From a TypeScript migration benchmark:

```bash
# Ralph command (uses Codex by default)
/ralph_custom $PROJECT_ROOT/goals/complete-production-deployment.md 30

# Explicit execution (what Ralph does internally)
cd "$RALPH_REPO"
python -m ralph_orchestrator \
    "$PROJECT_ROOT/goals/complete-production-deployment.md" \
    --agent codex \
    --max-iterations 30 \
    --verbose
```

**Goal**: Fix undefined field bug, document Firestore index requirement, validate production functionality

**Ralph's Autonomous Execution**:
1. ✅ Applied conditional spread operator fix (line 39 CampaignService.ts)
2. ✅ Created PRODUCTION_DEPLOYMENT.md with deployment guide
3. ✅ Rebuilt server (`npm run build`)
4. ✅ Tested campaign creation (campaign ID: vG64GU7JppVOdFJP2QqL)
5. ✅ Tested interaction endpoint (documented expected index error)
6. ✅ Committed changes and pushed to remote branch

**Evidence**: All success criteria met, working production server, complete documentation

## When to Use Ralph vs Genesis

**Use Ralph (`/ralph_custom`)** for:
- Tasks requiring **large context windows** (200K tokens via Codex)
- Autonomous execution with Codex's stronger reasoning
- Complex multi-file refactoring
- When you want fallback to Claude → Gemini automatically
- Standalone projects outside your main codebase

**Use Genesis (`/gene`)** for:
- Tasks within your project context
- When you want fast-gen mode with Cerebras speed
- Integrated with your project's codebase and tools
- Also uses Codex by default (same model as Ralph)
- When you need project-specific context

## When to Use Ralph vs Manual Work

**Use Ralph** for:
- Multi-step tasks with clear success criteria (5+ steps)
- Production deployments requiring validation
- Bug fixes with specific test cases
- Autonomous execution while you work on other tasks
- Benchmark comparisons

**Manual work** for:
- Exploratory coding without clear endpoint
- Architectural decisions requiring human judgment
- Creative feature design
- Complex debugging requiring hypothesis testing
- Tasks requiring frequent user input

---

**Ralph** = Standalone ralph-orchestrator, Codex by default, large context (200K)
**Genesis** = Project-integrated, Codex by default, fast-gen mode with Cerebras
