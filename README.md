---
description: Claude Skills & Commands - Modular Agent Skills Library for Claude Code, Antigravity, and Codex
type: llm-orchestration
execution_mode: immediate
---

# 🧠 Claude Skills & Commands

> A battle-tested library of **245 skills** and ergonomic slash commands that supercharge **Claude Code**, **Google Antigravity**, and **OpenAI Codex** with advanced software engineering capabilities.

Instead of generic prompts, this repository equips your AI coding assistant with production-grade engineering disciplines: empirical debugging, multi-model second opinion panels, multi-tier testing harnesses, autonomous PR management, and rigorous verification gates.

---

## ⚡ Quickstart (Install in 30 Seconds)

### Option 1: Claude Code Plugin (Recommended)

In your Claude Code CLI session, add the marketplace and install the package:

```bash
/plugin marketplace add jleechanorg/jleechan-skills
/plugin install jleechan-skills@jleechan-skills
```

Restart your CLI session and run `/help` to see all available commands and skills.

### Option 2: Clone Directly into Your Project

To use these skills and commands in any repository:

```bash
git clone https://github.com/jleechanorg/jleechan-skills.git /tmp/jleechan-skills
mkdir -p .claude/commands .claude/skills
cp -r /tmp/jleechan-skills/.claude/commands/* .claude/commands/
cp -r /tmp/jleechan-skills/.claude/skills/* .claude/skills/
```

### Option 3: Intelligent Self-Setup

Ask Claude Code to inspect this repo and install only what you need:

```text
"Inspect https://github.com/jleechanorg/jleechan-skills and set up the skills most useful for my tech stack."
```

---

## 🏛️ How It Works: Skills First, Thin Slash Pointers

Every workflow in this repository follows a clean, single-source-of-truth architecture:

```
                  ┌──────────────────────────────────────────────┐
                  │                 Developer / AI               │
                  │   types /repro, /es, /wa, /f, etc.           │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │   Slash Command (.claude/commands/*.md)      │
                  │   • Thin invocation pointer & syntax shortcut │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │     Skill Package (.claude/skills/<skill>/)  │
                  │   • Canonical reasoning logic & safety rails │
                  │   • Structured schemas, scripts & tool specs │
                  │   • Portable: Claude Code, Antigravity, Codex│
                  └──────────────────────────────────────────────┘
```

1. **Skills (`.claude/skills/`) are the source of truth**: Complex protocols, schemas, deterministic checklists, and bundled helper scripts live in standard `SKILL.md` folders.
2. **Slash Commands (`.claude/commands/`) are thin pointers**: Slash commands do not contain separate code; they are ergonomic shortcuts that load and run the underlying skill.
3. **Cross-Agent Portability**: Because all skills adhere to the standard `SKILL.md` specification (YAML frontmatter + markdown execution guide), they run natively in **Claude Code**, **Google Antigravity**, and **OpenAI Codex**.

---

## 🚀 The Most Useful Skills (And How to Use Them)

Here are the most impactful skills you can use immediately in your daily development workflow:

---

### 1. 🔍 Root-Cause First Debugging (`root-cause-first`)
> **Slash Pointer**: [`/repro`](.claude/commands/repro.md) | **Skill**: [`.claude/skills/root-cause-first/SKILL.md`](.claude/skills/root-cause-first/SKILL.md)

**The Problem**: AI assistants often rush to modify code based on speculative theories without actually verifying why a bug happens.  
**The Solution**: Enforces a strict empirical debugging protocol:
1. Formulate testable hypotheses.
2. Write a minimal reproduction test or capture runtime traces.
3. Systematically falsify incorrect theories before touching any application code.

```bash
# Example: Tell Claude to find and fix a bug with empirical discipline
/repro "Checkout fails with 500 error when applying coupon code"
```

---

### 2. 📊 Empirical Evidence Standards (`evidence-standards`)
> **Slash Pointer**: [`/es`](.claude/commands/es.md) | **Skill**: [`.claude/skills/evidence-standards/SKILL.md`](.claude/skills/evidence-standards/SKILL.md)

**The Problem**: Code changes claim performance gains, bug fixes, or UI fixes without verifiable runtime proof.  
**The Solution**: Anti-speculation guardrails:
- Requires real telemetry queries (Cloud Run logs, database traces, profiling metrics) before concluding root cause.
- Mandates headless browser DOM measurements across mobile (375x812) and desktop (1440x900) viewports for UI changes.
- Prohibits fabricated, mocked, or paraphrased test outputs.

```bash
# Example: Generate verified evidence for a completed feature or bugfix
/es "Verify API response latency reduction under 200 concurrent requests"
```

---

### 3. 🤖 Multi-Model Consensus & Advice Panel (`web-advice`)
> **Slash Pointer**: [`/web-advice`](.claude/commands/web-advice.md), [`/advice`](.claude/commands/advice.md) | **Skill**: [`.claude/skills/web-advice/SKILL.md`](.claude/skills/web-advice/SKILL.md)

**The Problem**: Single-model blind spots when designing complex architectures or reviewing critical pull requests.  
**The Solution**: Queries a council of frontier LLMs (**Claude**, **Grok**, **Gemini**, **GPT**) in parallel to critique your design, identify edge cases, and provide second opinions before code is written or merged.

```bash
# Example: Run an architectural critique before implementing a major refactor
/web-advice "Should we migrate auth session storage from Redis to DynamoDB with TTL?"
```

---

### 4. 🏭 Autonomous Dark Factory Loops (`dark-factory`)
> **Slash Pointer**: [`/f`](.claude/commands/f.md), [`/factory`](.claude/commands/extended-library/factory.md) | **Skill**: [`.claude/skills/dark-factory/SKILL.md`](.claude/skills/dark-factory/SKILL.md)

**The Problem**: Unstructured, multi-turn AI coding workflows easily drift off-course, lack rigorous validation gates, or produce code that passes only because tests were loosely written by the same model.  
**The Solution**: An end-to-end autonomous factory loop:
- Executes structured DOT workflow graphs via the `dark-factory` binary runner.
- Grades implementation changes against **sealed holdout tests** that the coding agent cannot inspect or game.
- Calibrates code review findings across a multi-model reviewer panel (Codex, Claude, MiniMax, Antigravity) with bounded repair loops before declaring victory.

```bash
# Example: Run an autonomous factory pipeline with holdout evaluation
/f "Implement idempotent webhook signature validation with HMAC-SHA256"
```

---

### 5. 🔬 Deep Technical Research (`research`)
> **Slash Pointer**: [`/research`](.claude/commands/research.md) | **Skill**: [`.claude/skills/research/SKILL.md`](.claude/skills/research/SKILL.md)

**The Problem**: Shallow web searches return outdated or inaccurate developer documentation.  
**The Solution**: Multi-engine research pipeline that combines ultra-depth reasoning with multi-source queries (Perplexity, DuckDuckGo, Grok, Gemini, Claude) with mandatory primary source verification.

```bash
# Example: Conduct thorough technical investigation with cited sources
/research "PostgreSQL 17 logical replication improvements and zero-downtime schema upgrades"
```

---

### 6. 🧪 Multi-Tier Harness Engineering (`harness-engineering`)
> **Slash Pointer**: [`/harness`](.claude/commands/harness.md), `/4layer` | **Skill**: [`.claude/skills/harness-engineering/SKILL.md`](.claude/skills/harness-engineering/SKILL.md)

**The Problem**: Fragile unit tests mock everything, while slow end-to-end tests are flaky.  
**The Solution**: Systematic 3-tier testing discipline:
- **Layer 1**: Deterministic unit tests for pure logic.
- **Layer 2**: Real-service callstacks (unmocked local dependencies, real sqlite/in-memory DBs).
- **Layer 3**: Headless browser validation with live DOM assertions across responsive viewports.

```bash
# Example: Build an automated verification harness for an endpoint
/harness "Test stripe webhook idempotency under concurrent retries"
```

---

### 7. 🚦 Deterministic Green PR Gate (`pr-green-definition`)
> **Slash Pointer**: [`/green`](.claude/commands/green.md) | **Skill**: [`.claude/skills/pr-green-definition/SKILL.md`](.claude/skills/pr-green-definition/SKILL.md)

**The Problem**: PRs are merged while CI checks are still pending or merge conflicts exist.  
**The Solution**: Defines an unambiguous 2-gate standard verified at the exact PR HEAD commit SHA:
1. **CI Green**: All GitHub Actions / check runs pass cleanly.
2. **Mergeable**: Zero merge conflicts with the base branch.

```bash
# Example: Verify PR merge readiness at HEAD
/green
```

---

### 8. 🪄 Convert Any Procedure into a Reusable Skill (`skillify`)
> **Slash Pointer**: [`/skillify`](.claude/commands/skillify.md) | **Skill**: [`.claude/skills/skillify/SKILL.md`](.claude/skills/skillify/SKILL.md)

**The Problem**: Useful scripts and team runbooks remain buried in READMEs and ad-hoc shell files.  
**The Solution**: Takes any bash script, runbook, or prompt and turns it into a structured, discoverable `SKILL.md` package with YAML frontmatter, execution rules, and automated validation tests.

```bash
# Example: Package an existing deployment script into a cross-agent skill
/skillify scripts/deploy-staging.sh
```

---

## 🗂️ Command Layout & Catalog

The repository includes **28 Active Core commands** and **211 extended library commands**:

### Active Core Commands (Flat `/<name>`)
Ranked by empirical usage mined from real development sessions (`/command-research`):
- **Core Engineering**: [`/execute`](.claude/commands/execute.md), [`/green`](.claude/commands/green.md), [`/repro`](.claude/commands/repro.md), [`/es`](.claude/commands/es.md), [`/er`](.claude/commands/er.md), [`/smoke`](.claude/commands/smoke.md), [`/harness`](.claude/commands/harness.md), [`/end2end-testing`](.claude/commands/end2end-testing.md)
- **Review & Consensus**: [`/advice`](.claude/commands/advice.md), [`/web-advice`](.claude/commands/web-advice.md), [`/copilot`](.claude/commands/copilot.md), [`/fixpr`](.claude/commands/fixpr.md)
- **Research & Discovery**: [`/research`](.claude/commands/research.md), [`/ms`](.claude/commands/ms.md), [`/wiki-search`](.claude/commands/wiki-search.md), [`/history`](.claude/commands/history.md), [`/learn`](.claude/commands/learn.md)
- **Automation & Tools**: [`/f`](.claude/commands/f.md), [`/auto`](.claude/commands/auto.md), [`/browser`](.claude/commands/browser.md), [`/browserclaw`](.claude/commands/browserclaw.md), [`/claw`](.claude/commands/claw.md), [`/skillify`](.claude/commands/skillify.md), [`/roadmap`](.claude/commands/roadmap.md), [`/levelup`](.claude/commands/levelup.md), [`/nextsteps`](.claude/commands/nextsteps.md), [`/linux`](.claude/commands/linux.md), [`/innov`](.claude/commands/innov.md)

### Extended Command Library (`/extended-library:<name>`)
All other **211 specialized commands** live in [`.claude/commands/extended-library/`](.claude/commands/extended-library/) and remain fully invocable with the `extended-library:` prefix:
```bash
/extended-library:cerebras     # High-speed code generation
/extended-library:scaffold     # Scaffolds 17 development scripts for your tech stack
/extended-library:ao           # Agent Orchestrator fleet control
```

Browse [`.claude/skills/`](.claude/skills/) for the complete library of **245 skill directories** and [`.claude/commands/`](.claude/commands/) for all slash shortcuts.

---

## 🔗 Chaining & Composition

Commands and skills are designed to compose naturally in single prompts:

```bash
# Plan, review, and execute
"/research OAuth2 PKCE flows then /advice on the approach then /execute the implementation"

# Test and autonomous repair
"/smoke and if any test fails /repro the failure then /execute the fix"

# Full feature lifecycle
"/think about user notifications /design the schema /execute with tests /green"
```

---

## 📚 References & Contributing

- [INSTALL.md](INSTALL.md) — Comprehensive installation guide and troubleshooting.
- [archive/ARCHIVE-DECISION-2026-08-23.md](archive/ARCHIVE-DECISION-2026-08-23.md) — Command ranking and two-tier architecture decision record.
- [archive/extended-library-README.md](archive/extended-library-README.md) — Guide for extended library commands and promotion mechanics.
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — Version history and release notes.

---

🚀 **Built for modern AI-assisted engineering with [Claude Code](https://claude.ai/code)**
