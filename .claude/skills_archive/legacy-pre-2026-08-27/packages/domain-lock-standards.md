# Domain Lock Standards

This skill defines the standard operating procedure (SOP) for all AI coding agents (Claude Code, Codex, Antigravity, OpenCode, wafer/agy) when encountering spawn-time or real-time domain lock collisions.

---

## 1. What are Domain Locks?
Domain locks (`merge_train`) prevent parallel AI agents from co-editing the same files or logical domains concurrently. When an agent attempts to edit or write a file, a global `PreToolUse` hook verifies if the file's domain is held by another PR. 

If the domain is held, the hook blocks the tool call by returning a `deny` decision, displaying a block message to the agent:
`merge_train: REFUSED — domain is held: HELD: <domain> by PR#<PR> agent=<agent> branch=<branch>`

---

## 2. Mandatory SOP when Blocked
When you receive a `deny` block from the `PreToolUse` hook, **do not retry the tool call blindly, do not modify settings, and do not attempt to force the write.** Follow this step-by-step procedure:

### Step 1: Diagnose the Collision
Identify the holding PR and agent name from the block message. 
Run the following audit command in the terminal to inspect all active locks in the repository:
```bash
domain_lock list --status active --registry file_domains.yaml
```

### Step 2: Determine Path Forward
Evaluate which of the three standard mitigation pathways is appropriate:

#### A. Symbol-Exclusive Rescoping (Preferred)
If the holding PR is co-editing the same file but you are editing **disjoint functions or classes**, you can co-tenant the domain by registering symbol-exclusive locks.
1. Check the functions you need to edit.
2. Run symbol-level reservation for your specific symbols:
   ```bash
   domain_lock reserve --domain <domain-name> --symbols func1,func2 --pr <your-PR> --agent $(whoami) --branch $(git branch --show-current)
   ```
3. Retry your `Edit`/`Write` tool. As long as your symbol sets do not intersect with the other PR's symbols, the lock check will succeed!

#### B. Sibling Ticket Switch
If you cannot rescope to symbol-level locks (e.g. you both need to edit the exact same functions), pivot to a sibling ticket or a task that touches a completely different, unheld domain.
1. Release any locks you hold for the current task: `domain_lock release --pr <your-PR>`
2. Select another open issue/bead that affects a free domain.
3. Start the new task.

#### C. Fail-Fast
If the task is highly critical and cannot be rescoped or pivoted, **halt immediately**. Present the conflict to the human user with a clear summary:
- The domain in conflict.
- The competing PR and branch.
- Ask the human if you should wait or coordinate a manual resolution.

---

## 3. Semaphore Locks (Co-tenancy Limits)
Some large domains are configured with `concurrency_limit: N` (e.g. `2`). 
- These domains allow up to $N$ distinct PRs to co-tenant the domain concurrently (either as whole-domain or symbol-level locks).
- The lock system will only block a new PR if the number of distinct active holding PRs has reached $N$, OR if there is a direct symbol-level overlap on the exact same function or class.
- Always check the `concurrency_limit` field under `file_domains.yaml` when analyzing locks.
