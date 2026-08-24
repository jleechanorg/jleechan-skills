---
description: e
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 💰 MODEL SELECTION (cost-aware execution)

When delegating work to subagents or pair-programming partners, **default to the cheapest coding model that can complete the task correctly**. Cost-aware routing is the default; expensive models are the exception, not the baseline.

### Claude family
- **Haiku** — quick reads, transforms, summarization, lint sweeps, deterministic mechanical edits, single-file lookups, pollers/monitors/watch loops.
- **Sonnet** — routine implementation, multi-file edits, test generation, conventional refactors, most code-pair work, PR fix lanes, conflict resolution, evidence packaging.
- **Opus / Fable** — reserve ONLY for genuinely hard architectural reasoning, cross-context synthesis, ambiguous debugging, adversarial design judgment, or when Sonnet demonstrably fails (state which failure). Do not reach for the top tier by default — and NEVER by omission: an `Agent()`/workflow `agent()` spawn without an explicit `model` silently inherits the session model, which usually IS the top tier. Set `model` on every spawn (see ~/.claude/CLAUDE.md § "Subagent model routing").

### Codex family
- **Codex Spark** (or other GPT-medium variants) — fast code generation, scaffolding, mechanical edits, well-scoped refactors.
- **GPT-large** — reserve ONLY for hard architectural tasks where Codex Spark has demonstrably failed.

### Other providers
- **Cerebras / Gemini Flash / GLM-5.1 / wafer.ai** — preferred for high-volume mechanical code generation.
- **Premium tiers (Claude Opus, GPT-large, top Gemini)** — reserve for low-volume, high-stakes decisions.

### Decision rule
If the task is **well-scoped** (clear inputs, deterministic output, no architectural ambiguity, single-file or small blast radius), pick the **cheapest model that can complete it**. Use a more expensive model ONLY when:
1. The cheaper tier has demonstrably failed (with evidence), OR
2. The task requires cross-context synthesis that cheaper tiers cannot handle.

This guidance is binding for `/e` execution: do not pick Opus / GPT-large by reflex.

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
Execute the task: $ARGUMENTS

Follow the complete /execute workflow:

1. **Phase 1 - Planning**: Show execution plan with complexity assessment, execution method decision (parallel vs sequential), tool requirements, implementation approach, and timeline estimate

2. **Phase 2 - Auto-approval**: Display "User already approves - proceeding with execution"

3. **Phase 3 - Implementation**: Execute the plan using TodoWrite progress tracking

## 📋 REFERENCE DOCUMENTATION

Execute the task: $ARGUMENTS

Follow the complete /execute workflow:

1. **Phase 1 - Planning**: Show execution plan with complexity assessment, execution method decision (parallel vs sequential), tool requirements, implementation approach, and timeline estimate

2. **Phase 2 - Auto-approval**: Display "User already approves - proceeding with execution"

3. **Phase 3 - Implementation**: Execute the plan using TodoWrite progress tracking
