# Complete Toolchain with Evidence

**Evidence-based tool inventory from 6 months of production usage**

> Analysis of 19,044 commits (Aug 2025 - Feb 2026) at WorldArchitect.AI

---

## 📊 Analysis Methodology

### Data Sources
1. **Git commit analysis** - 19,044 commits over 6 months
2. **MCP diff analysis** - 5,075 `mcp-cli call` or `mcp__` occurrences
3. **Slash command references** - Diff pattern matching
4. **File modification frequency** - Git log timestamps
5. **Binary access times** - `ls -ltu` on `~/.local/bin/`
6. **Active branch patterns** - Agent naming conventions

### Reliability Levels
- 🔥 **Tier 1** - Daily use (1,000+ commits or refs)
- ⭐ **Tier 2** - Heavy use (100-1,000 commits/refs)
- ✅ **Tier 3** - Regular use (10-100 commits/refs)
- ⚠️ **Low evidence** - Git evidence low but confirmed by user

---

## 🔥 Tier 1: Daily Drivers

### Claude Code CLI
- **Evidence:** 6,110 file touches in `.claude/commands/`
- **Usage:** Primary AI assistant
- **Custom config:** 290 lines, 150+ pre-approved permissions
- **Commands:** 80+ custom slash commands
- **Skills:** 40+ skill files
- **Hooks:** 12+ custom hooks (PreToolUse, PostToolUse, UserPromptSubmit)
- **Model:** Sonnet 4.5, 200K context window
- **Cost:** $20/mo (Paid tier)

**Why it's tier 1:**
- Most-modified directory: `.claude/commands/` (6,110 touches)
- Central to entire workflow
- 80+ commands represent years of refinement

---

### pytest
- **Evidence:** 3,308 commits (17.4% of all commits)
- **Usage:** Primary testing framework
- **Pattern:** `TESTING_AUTH_BYPASS=true vpython` for mock mode
- **Directories:** 7,670 file touches in `mvp_site/tests/`

**Why it's tier 1:**
- Single biggest activity category
- Evidence-based testing protocol
- 17.4% of ALL work is testing

---

### gh CLI (GitHub CLI)
- **Evidence:** Binary accessed today (Feb 12, 2026)
- **Commits:** 2,267 PR-related commits
- **Usage:** GitHub automation, PR workflows
- **Location:** `/opt/homebrew/bin/gh`

**Why it's tier 1:**
- Accessed daily (binary timestamps)
- Core to /copilot, /fixpr workflows
- 2,267 PR commits

---

### Gemini (Google)
- **Evidence:** 1,114 commit mentions + 1,440 MCP diff hits
- **Usage:** Primary LLM backend for WorldArchitect.AI
- **MCP:** gemini-cli-mcp server (most-used MCP)
- **Workflow:** Fallback chains (gemini-2.5-flash → 1.5-flash → 2.5-pro)

**Why it's tier 1:**
- Highest MCP usage (1,440 hits)
- 1,114 commit mentions
- Production LLM, not just experimentation

---

### beads (bd)
- **Evidence:** 259 commits + 539 MCP hits + binary accessed yesterday
- **Usage:** MCP-integrated task tracking
- **Location:** `~/.local/bin/bd` (33MB binary)
- **Pattern:** Used MORE than traditional issue trackers

**Why it's tier 1:**
- Binary accessed daily
- 539 MCP hits (6th most-used MCP)
- Real-time AI task interaction

---

## ⭐ Tier 2: Heavy Workflow Tools

### `/copilot` Command
- **Evidence:** 7,950 diff references, 68 file commits, 626 commit mentions
- **Usage:** #1 slash command - autonomous PR processing
- **File:** `.claude/commands/copilot.md` (293 lines)
- **Workflow:** 4 phases (Critical scan → Categorization → Implementation → Verification)

**Why tier 2:**
- Most-referenced command (7,950 hits)
- 68 commits = actively refined
- Handles 100+ comment PRs autonomously

---

### `/fixpr` Command
- **Evidence:** 5,124 diff refs, 1,299 commit mentions, 20 file commits
- **Usage:** PR fix automation
- **File:** `.claude/commands/fixpr.md` (325 lines)

**Why tier 2:**
- 2nd most-referenced command
- 1,299 commit mentions
- Core PR workflow

---

### `/execute` (`/e`) Command
- **Evidence:** 6,332 diff references
- **Usage:** General task execution
- **Pattern:** Auto-approval workflow

**Why tier 2:**
- 2nd highest diff refs
- General-purpose execution
- Used across all task types

---

### `/cerebras` (`/cereb`) Commands
- **Evidence:** 2,889 + 2,012 diff refs = 4,901 combined, 246 commits
- **Usage:** Fast code generation via Cerebras API
- **Modes:** Default (structured) vs Light (--light flag)
- **Script:** `cerebras_direct.sh`

**Why tier 2:**
- 4,901 combined references
- 246 commit mentions
- Active code generation tool

---

### Comment Automation Suite
- **`/commentreply`:** 4,007 refs, 19 file commits
- **`/commentfetch`:** 2,440 refs, 18 file commits
- **`/commentcheck`:** 1,269 refs, 22 file commits

**Why tier 2:**
- Combined 7,716 references
- Core to /copilot workflow
- Autonomous comment handling

---

### `/redgreen` (TDD) Command
- **Evidence:** 2,262 diff refs + 1,555 `/tdd` refs = 3,817 combined, 162 commits
- **Usage:** Red-green TDD workflow
- **Pattern:** Write failing test → Confirm fail → Minimal code → Pass → Refactor

**Why tier 2:**
- 3,817 combined references
- 162 commit mentions
- Evidence-based testing culture

---

### orchestration + tmux
- **Evidence:** 1,397 `/orch` refs, 287 commits, 4 agent branch prefixes
- **Usage:** Multi-agent coordination
- **Agents:** copilot/, cursor/, codex/, claude/ branches
- **Tool:** tmux for session management

**Why tier 2:**
- Proven multi-agent orchestration (branch evidence)
- 287 commits
- Real production usage (not aspirational)

---

### Cursor IDE
- **Evidence:** Binary accessed Feb 7, active `cursor/*` branches
- **Usage:** AI pair programming IDE
- **Location:** `~/.local/bin/cursor`, `/Applications/Cursor.app/`
- **Branches:** Multiple `cursor/` prefixed branches

**Why tier 2:** ⚠️
- Low git evidence BUT user-confirmed
- Active agent branches
- Recent binary access

---

### MCP Servers (Tier 2)

#### sequential-thinking
- **Evidence:** 649 MCP diff hits
- **Usage:** Enhanced reasoning for complex problems

#### grok
- **Evidence:** 670 MCP hits (vs 59 commit mentions)
- **Usage:** X.ai real-time intelligence
- **Pattern:** Used more than commits suggest (via MCP calls)

#### perplexity-ask
- **Evidence:** 661 MCP hits, 943 `/perp` refs (vs 43 commit mentions)
- **Usage:** Research and web search
- **Pattern:** Heavy MCP usage not reflected in commits

#### chrome-superpower + claude-in-chrome
- **Evidence:** 407 combined MCP hits
- **Usage:** Browser automation (not `/browser` command)
- **Pattern:** Direct MCP calls, not slash command

#### context7
- **Evidence:** 341 MCP hits
- **Usage:** Library documentation queries

---

## ✅ Tier 3: Regular Use

### Research & Planning Commands
- **`/research`:** 2,213 refs
- **`/think`:** 1,743 refs
- **`/plan`:** 1,753 refs
- **`/pr`:** 1,821 refs

---

### Test Generation Commands
- **`/testllm`:** 2,172 refs, 14 file commits
- **`/generatetest`:** 82 file commits (most-modified command!)
- **`/adde2e`:** 18 file commits

**Pattern:** Active test automation development

---

### Multi-Model Validation
- **`/secondo` (`/second_opinion`):** 106 commits, 49 file commits
- **Usage:** Get second opinions from multiple AI models

---

### Branch Management
- **`/sync`:** 26 file commits
- **Usage:** Synchronize branches with main

---

### Docker + Docker Compose ⚠️
- **Evidence:** 17 commits (0.1%)
- **Usage:** Containerization and local development
- **Status:** Low git evidence BUT user-confirmed usage
- **Explanation:** Docker usage often doesn't generate commits (running containers)

---

### Warp Terminal ⚠️
- **Evidence:** No git evidence (it's just a terminal)
- **Usage:** Primary terminal application
- **Location:** `/Applications/Warp.app/`
- **Status:** User-confirmed daily driver

---

### Antigravity IDE ⚠️
- **Evidence:** 0 commit mentions, 0 branch prefixes
- **Usage:** Experimental AI IDE
- **Location:** `/Applications/Antigravity.app/`
- **Status:** Low git evidence BUT user-confirmed usage
- **Explanation:** GUI usage doesn't generate commits

---

### Codex (App + CLI) ⚠️
- **Evidence:** Some `codex/*` branch prefixes
- **Usage:** Alternative AI assistant
- **Location:** `/Applications/Codex.app/`, `/opt/homebrew/bin/codex`
- **Status:** Active agent branches

---

### mcp_mail ⚠️
- **Evidence:** 28 MCP diff hits
- **Usage:** Agent-to-agent messaging
- **Status:** Low git evidence BUT user-confirmed usage
- **Explanation:** Inter-agent communication doesn't always generate commits

---

### Playwright
- **Evidence:** 69 commits
- **Usage:** Browser testing framework
- **Pattern:** Direct usage, not via `/browser` command

---

### Cloud & Deployment
- **Firebase:** 136 commits - Backend services
- **Cloud Run:** 192 deploy commits - Serverless deployment
- **Google Cloud Platform:** gcloud CLI for operations

---

### httpie
- **Evidence:** Present in codebase
- **Usage:** API testing (better than curl)

---

## ❌ Explicitly NOT Used (Despite Being Installed)

### `/browser` Command
- **Last commit:** Nov 22, 2025 (3 months ago)
- **Status:** Command exists but UNUSED
- **Reality:** Uses Chrome MCP directly instead

### PaddleOCR
- **Last access:** Nov 2024
- **Status:** Dead/stale tool

---

## 🎯 Summary by Tier

### Tier 1 (Daily - 1,000+ commits/refs)
1. Claude Code CLI (6,110 touches)
2. pytest (3,308 commits)
3. gh CLI (daily access)
4. Gemini (1,114 commits + 1,440 MCP)
5. beads (259 commits + daily access)

### Tier 2 (Heavy - 100-1,000 commits/refs)
6. /copilot (7,950 refs)
7. /fixpr (5,124 refs)
8. /execute (6,332 refs)
9. /cerebras (4,901 refs)
10. Comment automation (7,716 combined)
11. /redgreen + /tdd (3,817 combined)
12. orchestration + tmux (287 commits)
13. Cursor IDE ⚠️ (user-confirmed)
14. MCP servers: sequential-thinking, grok, perplexity, chrome, context7

### Tier 3 (Regular - 10-100 commits/refs)
15. Research/planning commands (/research, /think, /plan, /pr)
16. Test generation (/testllm, /generatetest, /adde2e)
17. /secondo (multi-model validation)
18. /sync (branch management)
19. Docker + Docker Compose ⚠️ (user-confirmed)
20. Warp Terminal ⚠️ (user-confirmed)
21. Antigravity IDE ⚠️ (user-confirmed)
22. Codex ⚠️ (user-confirmed)
23. mcp_mail ⚠️ (user-confirmed)
24. Playwright (69 commits)
25. Cloud services (Firebase, Cloud Run, GCP)
26. httpie

---

## 📝 Notes on Evidence

**⚠️ Low evidence, user-confirmed tools:**
Some tools show low git evidence but are confirmed in actual use:
- **Docker** - Container usage doesn't generate commits
- **Antigravity** - GUI usage doesn't generate commits
- **Warp Terminal** - It's just a terminal (no git traces)
- **mcp_mail** - Inter-agent messaging doesn't always commit
- **Cursor** - Some usage via GUI doesn't create git traces

**High-signal patterns:**
- File modification frequency (`.claude/commands/` churn)
- MCP diff hits (real API calls)
- Binary access timestamps (proves recent usage)
- Branch naming patterns (proves multi-agent usage)
- Commit mentions + diff refs (combined signal)

---

**Last Updated:** 2026-02-12
**Analysis Period:** Aug 2025 - Feb 2026 (6 months)
**Total Commits:** 19,044
**MCP Diff Hits:** 5,075
