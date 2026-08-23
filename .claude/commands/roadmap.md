---
description: Roadmap Command
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: Survey Current Situation

**Action Steps:**
1. **Read Claude auto-memories** for roadmap-relevant context:
   ```python
   import subprocess, glob, os, re
   # Derive current project's memory dir from git root
   try:
       git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
       project_key = git_root.replace('/', '-')  # preserve leading dash: /Users/... → -Users-...
       memory_dir = os.path.expanduser(f'~/.claude/projects/{project_key}/memory/')
       memory_files = glob.glob(os.path.join(memory_dir, '*.md'))
   except Exception:
       memory_files = []
   # Keyword filter: roadmap, planning, architecture, decision, goals
   keywords = ['roadmap', 'planning', 'architecture', 'decision', 'goal']
   relevant = []
   for f in memory_files:
       with open(f, encoding='utf-8') as handle:
           memory_text = handle.read().lower()
       if any(k in memory_text for k in keywords):
           relevant.append(f)
   ```
   Display any matches as "📍 From Memory" before proceeding.

2. **Scan roadmap/ directory** for existing docs:
   ```python
   import subprocess, os, glob
   git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
   roadmap_files = glob.glob(os.path.join(git_root, 'roadmap', '*.md'))
   ```
   - Show titles (first H1 or filename) and modification dates
   - If a doc matches the current task topic (keyword match against filenames + first 5 lines), flag it as "EXISTING — consider updating"

3. **Scan beads** for related open items:
   - Run: `br list --status open`, and abort the bead-match step if the command returns a non-zero exit code
   - Keyword-match against current task input
   - If matches found, show them as "EXISTING BEADS — consider updating these instead of creating new ones"

4. **Report situation summary** before asking for input or proceeding:
   - N existing roadmap docs found (list titles)
   - N related open beads found (list IDs + titles)
   - N memory entries found
   - Recommendation: UPDATE existing vs CREATE new

### Phase 1: Integrated Workflow Execution

**Action Steps:**
For each task, execute in sequence:
1. **`/think light`** - Quick analysis to understand task scope
2. **`/planexec`** - Create detailed execution plan with optimal strategy
3. **`/handoff`** - Generate handoff branches and coordinate parallel work

## 📋 REFERENCE DOCUMENTATION

# Roadmap Command

**Purpose**: Update roadmap files with enhanced multi-task parallel processing and integrated agent workflow

**Action**: Commit local changes, switch to main, update roadmap/*.md, push to origin, switch back

**Usage**:
- `/roadmap` or `/r` - Single task (traditional mode)
- `/roadmap task1, task2, task3` - **Multi-task parallel processing** (comma-separated)
- `/roadmap "complex task 1" "simple task 2"` - **Multiple quoted tasks** for complex descriptions
- `/roadmap task1 task2 task3` - **Space-separated multiple tasks** (alternative format)

**Multi-Task Support**: The `/roadmap` command can process **multiple tasks simultaneously**. This is especially useful for:
- Breaking down large analysis work into focused individual tasks
- Creating parallel development streams
- Organizing related work items with proper task IDs and tracking

**MANDATORY**: When using `/roadmap` command, follow this exact sequence:

1. **Autonomy-Focused Task Clarification**: Ask detailed clarifying questions with the explicit goal of making tasks as autonomous as possible. Gather all necessary context, constraints, and requirements upfront.

2. **Task Classification**: Suggest classifications prioritizing autonomy:
   - **Small & LLM Autonomous**: LLM can complete independently with minimal guidance (PREFERRED)
   - **Small & Human-Guided**: Needs human oversight but straightforward
   - **Medium**: Requires detailed planning
   - **Large**: Requires comprehensive scratchpad

3. **Comprehensive Requirements Definition**: Based on classification:
   - **Small & LLM Autonomous**: Add complete 1-2 sentence requirements with all context needed
   - **Small & Human-Guided**: Add detailed 3-5 sentence requirements covering edge cases
   - **Medium**: ALWAYS create detailed `roadmap/scratchpad_task[NUMBER]_[brief-description].md` with implementation plan
   - **Large**: ALWAYS create comprehensive `roadmap/scratchpad_task[NUMBER]_[brief-description].md` with architecture and phases
   - **Any Detailed Task**: If defining tasks to a detailed degree during planning, ALWAYS create scratchpad files regardless of classification

   **Find-or-Create Logic** (apply after Phase 0 situation survey):
   - **For beads**: If Phase 0 found a matching open bead → update it with `br update <id> --status in_progress` + add notes. Do NOT create a duplicate. If no matching bead → create with `br create "<title>" --type task --priority 2`
   - **For roadmap docs**: If Phase 0 found a matching roadmap/*.md file → open and UPDATE it (add a dated section at the bottom: `## Update YYYY-MM-DD\n<new content>`). If no matching doc → create new: `roadmap/TOPIC_SLUG_YYYY-MM-DD.md`

4. **Autonomy Validation**: Before finalizing, verify each task has sufficient detail for independent execution

5. Record current branch name

6. Check for uncommitted changes regardless of current branch:
   - Run `git status --porcelain`
   - If changes exist, stage only roadmap-related files before any branch switch
   - If unrelated changes are present, do not auto-commit them; ask for confirmation before including them

7. Switch to main branch: `git checkout main`

8. Pull latest changes: `git pull origin main`

9. Create clean roadmap update branch: `git checkout -b roadmap-update-[timestamp]`

10. Make requested changes to roadmap files (create if missing):
   - `roadmap/roadmap.md` (main roadmap file — create with `# Roadmap\n` header if absent)
   - `roadmap/sprint_current.md` (current sprint status — create with `# Current Sprint\n` header if absent)
   - `roadmap/scratchpad_task[NUMBER]_[description].md` (if applicable)

11. Commit changes with format: `docs(roadmap): [description]`

12. Push branch: `git push -u origin roadmap-update-[timestamp]`

13. Create PR: `gh pr create --title "docs(roadmap): [description]" --body "Roadmap update via /roadmap command"`

14. Switch back to original branch: `git checkout [original-branch]`

15. **MANDATORY**: Explicitly report merge status: "✅ PR CREATED" with PR link for user to merge

16. **Claude Memory Write** (only if session produced real decisions/plans, skip for read-only invocations):
   - Derive memory dir from git root (same method as Phase 0 step 1)
   - Fill in `<topic>`, `<one_liner>`, `<what>`, `<why>`, `<how_to_apply>` from the session's actual content
   ```python
   import subprocess, os, datetime, textwrap
   git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
   project_key = git_root.replace('/', '-')  # preserve leading dash: /Users/... → -Users-...
   memory_dir = os.path.expanduser(f'~/.claude/projects/{project_key}/memory/')
   today = datetime.date.today().isoformat()
   slug = '<topic>'.lower().replace(' ', '_')[:40]
   filename = f'project_roadmap_{today}_{slug}.md'
   content = textwrap.dedent(f"""\
       ---
       name: roadmap_{today}_{slug}
       description: Roadmap decision: <one_liner>
       type: project
       ---

       **What**: <what_was_decided_or_planned>
       **Why**: <motivation>
       **How to apply**: When working on <topic_keywords>, check this first.
   """)
   os.makedirs(memory_dir, exist_ok=True)
   with open(os.path.join(memory_dir, filename), 'w') as f:
       f.write(content)
   with open(os.path.join(memory_dir, 'MEMORY.md'), 'a') as f:
       f.write(f'\n- [roadmap_{today}_{slug}]({filename}) — <one_liner>')
   ```

**Files Updated**: `roadmap/roadmap.md`, `roadmap/sprint_current.md`, and task scratchpads as needed

**Workflow**: All roadmap changes now follow standard PR workflow - no exceptions to main push policy

## Enhanced Multi-Task Parallel Processing

**When multiple tasks are provided**, the command automatically:

### 1. **Task Parsing & Analysis**

- Parse comma-separated tasks or multiple arguments
- Identify task complexity and dependencies
- Group related tasks for efficient processing

### 3. **Parallel Task Coordination**

- Spawn dedicated tasks for each work item using `/orchestrate`
- Create isolated worktrees for conflict-free parallel work
- Each task works on its own feature branch
- Tasks execute autonomously with progress tracking

### 4. **Progress Tracking**

- Update `roadmap/roadmap.md` with parallel task status:
  ```
  ## Active Parallel Tasks (Auto-Generated)
  - **TASK-1234-AUTH** 🟡 [Agent: task-agent-1234] - Implementing authentication
  - **TASK-1235-API** 🟡 [Agent: task-agent-1235] - Building REST endpoints
  - **TASK-1236-UI** 🟢 [Agent: task-agent-1236] - Creating UI components
  ```
- Status indicators:
  - 🟢 Ready/Completed
  - 🟡 In Progress
  - 🔴 Blocked/Failed
  - ⚪ Pending

### 5. **Branch Management**

- Each task gets its own feature branch: `feature/task-[id]-[name]`
- Handoff branches for documentation: `handoff-[task-name]`
- Clean separation prevents merge conflicts

### 6. **Automatic PR Creation**

- Each completed task creates its own PR
- PRs reference the parent roadmap task
- Cross-references between related PRs

## Example Multi-Task Usage

```
User: /roadmap implement auth system, create API docs, add unit tests
Assistant: I'll process these 3 tasks in parallel. Let me analyze each one:

[Executes /think light for each task]

Task 1: Implement auth system - Complex, needs design
Task 2: Create API docs - Medium, documentation task
Task 3: Add unit tests - Small, testing task

[Executes /planexec for each task with optimal strategies]

[Executes /handoff for each task, creating branches]

Now spawning parallel tasks:
- Task task-1234 → Implementing auth system
- Task task-1235 → Creating API docs
- Task task-1236 → Adding unit tests

[Updates roadmap.md with parallel task tracking]

You can monitor progress with:
- `tmux attach -t task-agent-1234` (auth)
- `tmux attach -t task-agent-1235` (docs)
- `tmux attach -t task-agent-1236` (tests)
```

## Implementation Flow

1. **Parse Tasks**: Split by commas or process multiple args
2. **For Each Task**:
   - Execute `/think light` to analyze
   - Execute `/planexec` to create strategy
   - Execute `/handoff` to create work branch
   - Spawn agent via `/orchestrate`
3. **Update Roadmap**: Add parallel task section
4. **Monitor Progress**: Track agent status
5. **Merge Results**: As agents complete tasks

## Implementation Approach

**LLM-Native Design**: This enhanced roadmap command works through Claude's natural interpretation of the above specifications, similar to other slash commands like `/think`, `/planexec`, and `/handoff`.

When you use `/roadmap` with multiple tasks, Claude will:
1. Parse the input according to the specifications above
2. Execute the integrated workflow sequence naturally
3. Spawn agents via `/orchestrate` for parallel processing
4. Update roadmap.md with progress tracking

This LLM-native approach provides flexibility while maintaining consistency through clear documentation.
