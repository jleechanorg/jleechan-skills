---
name: consensus
description: /consensus Command - Multi-Agent Consensus Review
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Mode Selection & Parallel Agent Execution

**Action Steps:**
1. Determine the execution mode using the "Modes & Scopes" defaults and inspect the available scope and context first. Ask the user to choose only if an essential intent decision remains unresolved after those checks; otherwise make a reasonable reversible choice and proceed.
2. Load the corresponding five reviewer roles. The roster defines review coverage, not a fixed concurrency requirement.
3. Route scheduling through the canonical `/parallel` resource-admission and host-selection policy before launching reviewers. Measure CPU and memory, choose only eligible hosts, and run independent roles concurrently up to the measured ceiling. If heavy roles must be deferred, continue safe, resource-eligible review and preparation; report deferred roles and their recheck condition. Do not count deferred roles as votes or claim consensus before the completed votes and validation meet the stated threshold.

## 📋 REFERENCE DOCUMENTATION

# /consensus Command - Multi-Agent Consensus Review

**Purpose**: Evidence-based multi-agent analysis for code reviews, product specifications, launch readiness, and operational decisions. Continue through review and fixes until acceptance criteria are met or a verified blocker or authorized deadline applies.

**⚡ Performance**: Run independent reviewer roles concurrently to the eligible resource ceiling; continue until the acceptance criteria are met or a verified blocker applies.

Shared security, authorization, and review requirements apply regardless of launch status or user count. A rollback path does not replace those requirements.

## Modes & Scopes

`/consensus` adapts to the given scope. Claude must select an execution mode before delegating:

- **Code Review Mode** (default when scope includes code changes or active PR): Uses software-focused agents and expects diff context.
- **Documentation & Spec Mode** (when reviewing docs, research, requirements, or validation evidence): Prioritizes accuracy checks, traceability to evidence, and clarity of product decisions.
- **Operational Decision Mode** (release go/no-go, launch readiness, roadmap decisions): Emphasizes risk analysis, stakeholder impacts, and mitigation steps.

Inspect the supplied scope and available project context to choose the applicable mode. Ask the user only when an essential intent decision remains unresolved after those checks; otherwise choose the closest mode and proceed.

## Usage

```
/consensus [<scope>]
/cons [<scope>]          # Alias
```
- **Default scope**: Current PR (if tracking a GitHub pull request) plus any local unmerged files.
- **Optional scope**: Specific file(s), folder(s), or PR number to narrow the review focus.

## Context Acquisition (Always Performed First)

1. **Detect active PR** using `gh pr status` or `git config branch.<name>.merge` to extract the PR number and remote.
2. **Record latest commit** with `git log -1 --stat`.
3. **Capture local changes**:
   - `git status --short` for staged/unstaged files.
   - `git diff --stat` and targeted `git diff` snippets for modified files.
4. **Verify synchronization with GitHub**:
   - Fetch PR files: `gh pr view <pr> --json files,headRefName,baseRefName`.
   - Confirm branch alignment (`git rev-parse HEAD` vs PR head SHA).
5. **Credential handling**: Apply the active credential policy and exclude secrets and credentials from every agent's context.
6. **Assemble review bundle** containing: PR description, latest commit message, diff summaries, and local-only edits.

### Simplified Consensus Rules

**Mode-Specific Reviewer Roster**: Use the five defined roles for the selected mode. Calculate majority agreement only with at least 3 completed roles; when fewer than 3 complete, report DEFERRED rather than a majority verdict. Schedule independent roles through the measured resource and host policy; the roster is not a simultaneous worker count:
- **Code Review Mode (default)**: `code-review`, `codex-consultant`, `gemini-consultant`, `cursor-consultant`, `code-centralization-consultant`
- **Documentation & Spec Mode**: `accuracy-reviewer`, `evidence-verifier`, `product-strategist`, `delivery-ops`, `clarity-editor`
- **Operational Decision Mode**: `risk-analyst`, `product-strategist`, `delivery-ops`, `customer-advocate`, `exec-synthesizer`

**Success threshold**: At least 3 completed reviewer roles PASS with average confidence ≥6 across completed votes

**Failure threshold**: At least 3 completed reviewer roles REWORK OR average confidence <5 across completed votes

**Mixed signals**: Document disagreements. Proceed by majority only when at least 3 roles completed; with fewer than 3 completed roles, report **DEFERRED** and give the resource recheck condition.

**Simple Consensus Calculation**:
1. Schedule up to five reviewer roles using the canonical `/parallel` admission and host-selection policy; run ready roles concurrently up to the measured ceiling
2. Collect PASS/REWORK + confidence (1-10) from each agent
3. Calculate results:
   - **CONSENSUS_PASS**: At least 3 completed roles PASS AND average confidence across completed votes ≥6
   - **CONSENSUS_REWORK**: At least 3 completed roles REWORK OR average confidence across completed votes <5
   - **MIXED_SIGNALS**: Document conflicting votes; deferred roles are not votes. If fewer than 3 roles completed, report the result as DEFERRED and give the resource recheck condition.

**Agent Specialization**:
- **Code Review Mode**:
  - **`code-review`**: Architecture validation, correctness, maintainability
  - **`codex-consultant`**: System design patterns, scalability foundations
  - **`gemini-consultant`**: Current best practices relevant to the verified stack, performance, and requirements
  - **`cursor-consultant`**: Practical concerns, deployment readiness
  - **`code-centralization-consultant`**: Duplication detection, shared utility recommendations
- **Documentation & Spec Mode**:
  - **`accuracy-reviewer`**: Verifies factual correctness and catches contradictions
  - **`evidence-verifier`**: Cross-checks claims against attached logs, tests, or references
  - **`product-strategist`**: Evaluates alignment with product goals and user outcomes
  - **`delivery-ops`**: Checks operational feasibility, rollout risks, and support readiness
  - **`clarity-editor`**: Improves narrative flow, highlights ambiguous sections, ensures stakeholder readability
- **Operational Decision Mode**:
  - **`risk-analyst`**: Identifies blockers, severity, and mitigation paths
  - **`product-strategist`**: Confirms alignment with roadmap and KPIs
  - **`delivery-ops`**: Evaluates team capacity, timeline, and implementation complexity
  - **`customer-advocate`**: Represents user experience and support impact
  - **`exec-synthesizer`**: Creates concise go/no-go recommendations with rationale

### Enhanced Agent Context & Execution Framework

**Agent Infrastructure**: Uses the existing `Task` tool with `subagent_type` for independent reviewer roles. Apply measured resource admission and eligible-host routing from the canonical `/parallel` and shared host-selection owners before launch. Supply mode-specific prompts and evaluation criteria.

**Execution Guards**: Per-agent timeout (180 seconds), token caps (5000 tokens max), and maximum 10 findings per round to prevent runaway executions. Enhanced with context-aware resource allocation.

**Command Orchestration**: Delegates to `/execute` for intelligent coordination following `/reviewdeep` optimization patterns:

**Agent Execution**: Schedule up to five reviewer roles through the canonical `/parallel` admission and eligible-host policy; use the Task tool with 180-second timeouts and custom prompts per mode. Deferred roles are not counted as votes.

- **Code Review Mode**: Focus prompts on diff analysis, architecture correctness, high-impact bugs, and risks relevant to the verified product and deployment context.
- **Documentation & Spec Mode**: Direct agents to cross-reference claims with evidence, note missing validation, and highlight unclear reasoning or terminology.
- **Operational Decision Mode**: Ask agents to surface blockers, quantify risk, evaluate resource alignment, and recommend next steps.

**Current Context Applied to All Agents**:
- Determine the current product and user context from fresh evidence; do not assume launch status or user count
- A rollback path does not replace safety, authorization, or review requirements
- Focus on real bugs, architecture, factual accuracy, and serious security vulnerabilities only
- Apply shared security and authorization requirements; distinguish proven risks from unsupported speculation

**Implementation Details**:
- **`code-review`**: `Task(subagent_type="code-review", description="Architecture validation", prompt="...")`
- **`codex-consultant`**: `Task(subagent_type="codex-consultant", description="System design analysis", prompt="...")`
- **`gemini-consultant`**: `Task(subagent_type="gemini-consultant", description="Best practices review", prompt="...")`
- **`cursor-consultant`**: `Task(subagent_type="cursor-consultant", description="Practical reality check", prompt="...")`
- **`code-centralization-consultant`**: `Task(subagent_type="code-centralization-consultant", description="Duplication analysis", prompt="...")`

**Speed Optimizations**:
- **Parallel execution**: Run independent roles concurrently up to the measured resource ceiling; serialize only for a real dependency, shared-state constraint, or resource limit
- **Early termination**: End the current review round on an architectural blocker or critical bug; continue safe diagnosis, fixes, and re-review.
- **Simple consensus**: Agents provide PASS/REWORK verdict with confidence (1-10)
- **Evidence required**: Findings must include file:line references
- **Context-aware review**: Assess architecture, security, and operational risks against verified requirements and evidence; do not assume a rollback is available or sufficient.

## Consensus and Follow-Through

Streamlined workflow optimized for speed and simplicity:

1. **Parallel Agent Consultation**
   - Use the five-agent roster as defined reviewer roles, not as a fixed simultaneous worker count.
   - Before launch, follow `~/.claude/skills/parallelize-to-ceiling/SKILL.md` for measured resource admission and `~/.codex/AGENTS.md` § Core behavior for eligible Mac/Linux host selection. Launch independent roles concurrently only up to the measured ceiling.
   - If heavy roles are deferred because no host is eligible, continue safe and resource-eligible review or preparation; record the deferred roles and exact recheck condition.
   - **Context Provided to Each Agent**:
     - Verified product, launch, user, and team context, with sources; label unknowns as unknown
     - Current PR/branch context and file changes
     - Acceptance criteria and applicable security, authorization, and operational requirements
     - Verified rollback and recovery options, if any; treat rollback as mitigation rather than authorization or a substitute for safeguards
     - Current practices relevant to the project's actual stack and constraints
   - Each completed role provides: PASS/REWORK + confidence (1-10) + specific issues. Do not count deferred or unlaunched roles as votes.
   - A critical architectural issue ends the current review round; capture evidence, proceed to in-scope diagnosis/fix, then re-review.
   - Collect findings in structured format with file:line evidence
   - **Agent Context Awareness**: Each agent receives the verified orchestration, product, and user context, with unknowns labeled

2. **Simple Consensus Calculation** (30 seconds)
   - **CONSENSUS_PASS**: At least 3 completed roles PASS + average confidence across completed votes ≥6
   - **CONSENSUS_REWORK**: At least 3 completed roles REWORK OR average confidence across completed votes <5
   - **MIXED_SIGNALS**: Document conflicts. Proceed by majority only when at least 3 roles completed; with fewer than 3 completed roles, report **DEFERRED** and give the resource recheck condition.

3. **Quick Fix Application** (If REWORK, 1-2 minutes)
   - Apply highest-confidence architectural fixes with clear file:line references
   - Skip complex remediation planning - fix obvious issues immediately
   - Document all changes made during this round

4. **Automated Test Validation** (1-3 minutes)
   - **Syntax Validation**: Quick linting/parsing checks
     ```bash
     # Auto-detect and run project-specific linters
     if command -v npm >/dev/null 2>&1 && [ -f package.json ] && npm run --silent 2>/dev/null | grep -q "lint"; then
       npm run lint
     elif command -v eslint >/dev/null 2>&1; then
       eslint .
     elif command -v flake8 >/dev/null 2>&1; then
       flake8 .
     elif command -v ruff >/dev/null 2>&1; then
       ruff check .
     else
       echo "No supported linter found - manual validation required"
     fi
     ```
   - **Unit Tests**: Select focused coverage using the repository's `/test` and test-layer guidance; CI owns the unfiltered full suite.
   - **Integration Tests**: If APIs/interfaces changed, use the repository's approved integration runner and real-service contract; do not guess a generic integration command.
   - **Manual Validation**: Use available tools for manual checks when automated tests are insufficient. Ask the user to participate only when a physical action or an essential intent choice cannot be resolved through available tools and source context.

**Context-Aware Validation**:
- **Code Review Mode**:
  - **High Context**: Required full regression through CI; run only scoped local equivalents
  - **Medium Context**: Targeted test execution based on changed files
  - **Low Context**: Essential syntax and unit tests only
- **Documentation & Spec Mode**:
  - Corroborate claims against linked evidence, logs, and test artifacts
  - Highlight unsupported statements and request clarification or new experiments
  - Ensure timelines, metrics, and MCP/tool names match underlying data sources
- **Operational Decision Mode**:
  - Validate assumptions with available telemetry, user data, or roadmap docs
  - Stress-test mitigation plans and identify missing owners or follow-up actions
  - Confirm launch checklists or go/no-go criteria are satisfied

**Test/Validation Selection (Code Review Mode)**: Use `/test` and the owning
repository's test-layer guidance to choose focused checks. Never infer a test
command from package presence or run an unfiltered local full suite.

For documentation and decision scopes, replace automated tests with evidence checklists and explicit sign-off from responsible agents.

5. **Round Completion Decision**
   - **CONSENSUS_PASS**: At least 3 completed roles PASS + average confidence across completed votes ≥6 + validation complete for the selected mode
   - **CONSENSUS_REWORK**: At least 3 completed roles REWORK OR validation gaps OR average confidence across completed votes <5
   - **TEST_FAILURE_ABORT / VALIDATION_ABORT**: Critical test or evidence failures close this review round; diagnose/fix, rerun affected checks, and re-review before deciding the workflow outcome.

#### Consensus Calculation Rules:

- **✅ SUCCESS**: CONSENSUS_PASS achieved (workflow complete)
- **🔄 CONTINUE**: REWORK status and the next safe action is clear; batch fixes, then re-review
- **❌ ABORT**: Close only the current round for TEST_FAILURE_ABORT or critical agent blockers; continue authorized fixes and re-review unless a verified blocker, unmet authority boundary, or deadline prevents progress.
- **⚠️ BLOCKED**: State the exact verified blocker and the resumption trigger

Continue through required review and fixes until PASS or a verified blocker/deadline. Do not stop on a round count or repeated score. Keep safe independent work moving while a separate action is blocked.

Early termination, `ABORT`, and `VALIDATION_ABORT` close only the current review round, not the authorized task. Preserve finding evidence, address the cause, rerun affected validation, and re-review until PASS or a verified blocker, unmet authority boundary, or deadline applies.

#### Early Termination Triggers:

- **✅ CONSENSUS_PASS**: At least 3 completed roles PASS + average confidence across completed votes ≥6 + validation complete
- **❌ CRITICAL_BUG**: Any agent reports severity 9-10 issue
- **❌ TEST_FAILURE / EVIDENCE_FAILURE**: Automated tests or evidence cross-checks fail
- **❌ COMPILATION_ERROR / EXECUTION_BLOCKER**: Code doesn't compile/parse or operational criteria can't be executed

## General Consensus Principles

- **Progress**: Parallelize independent work and continue safe follow-through to the acceptance criteria
- **Evidence Based**: All findings require references (file:line, document section, metric source) + confidence scores
- **Clear Thresholds**: PASS ≥6 confidence, REWORK <5 confidence, mixed signals documented
- **Mode-Aware Focus**: Tailor evaluation criteria to code quality, factual accuracy, or decision readiness
- **Practical Focus**: Fix or flag the highest-impact issues now, document lower-priority work for later
- **Safety**: Apply the active security, authorization, and credential-handling requirements; ground findings in the scope and evidence
- **Recovery**: Verify available rollback and recovery paths; they do not replace safeguards, approvals, or review requirements

## Output Format

```

# Consensus Review Report

## Summary

- Rounds completed: <count>
- Final workflow status: PASS | REWORK | BLOCKED
- Most recent round: PASS | REWORK | VALIDATION_ABORT | DEFERRED
- Mode: Code Review | Documentation & Spec | Operational Decision
- Key validated areas

## Major Findings

| Round | Source Agent | File/Section/Artifact | Severity | Resolution |
|-------|--------------|------------------------|----------|------------|

## Implemented Fixes / Actions

- <bullet list of code updates, document edits, or operational decisions per round>

## Evidence & Validation Log

- Tests run / evidence cross-checked / stakeholders consulted

## Round-by-Round Summaries

- Round <n>: <main conversation highlights>
  - <agent name>: <key takeaways>

## Remaining Follow-Ups

- <nitpicks, deferred improvements, outstanding risks>
```
Include references to executed test commands, reviewed evidence files, and any required stakeholder approvals.

## Context-Aware Review Focus

Derive project, launch, user, team, and operational constraints from current source material. Do not carry assumptions from a template or prior review into the current task. Mark unavailable context as unknown and avoid conclusions that depend on it.

### **Code Review Mode Focus Areas**

- Architecture quality, real bugs, maintainability, integration issues, and risks supported by the current requirements and evidence
- Assess security and compliance obligations proportionately to applicable requirements and the evidenced threat model

### **Documentation & Spec Mode Focus Areas**

- Factual accuracy, evidence traceability, clarity for stakeholders
- Flag unsupported claims, contradictory metrics, or missing validation
- Skip exhaustive copy edits unless they block comprehension

### **Operational Decision Mode Focus Areas**

- Launch risk, mitigation planning, stakeholder readiness
- Confirm owners, timelines, and fallback options
- Skip deep program-management artifacts unless the decision depends on them

## 🔧 Agent Prompt Structure (Implementation Details)

Following `/reviewdeep` and `/arch` patterns for proper agent context. Claude must adapt the templates per mode.

### **Enhanced Agent Prompt Template** (Mode-Aware Multi-Agent Analysis)

```markdown
[Agent Role] consensus analysis of [target] using the verified project and user context.

**ENHANCED CONTEXT FRAMEWORK**:
- **Project Context**: [verified product, launch, user, team, and operational facts with sources; mark unknowns]
- **Current Scope**: [scope definition, e.g., PR details, document path, decision statement]
- **Infrastructure**: Working multi-agent consensus system using Task tool parallel execution
- **Agent Network**: Part of 5-agent consensus ([list selected agents])
- **Goal**: Reach evidence-backed consensus and carry safe follow-through to completion
- **Mode**: Code Review | Documentation & Spec | Operational Decision (pick one)

**ROLE-SPECIFIC CONTEXT SPECIALIZATION**:
- Outline what this agent must evaluate based on the chosen mode

**COMPREHENSIVE ANALYSIS FRAMEWORK**:
1. **Strategic Layer**: Architecture/design/product implications
2. **Tactical Layer**: Implementation details, factual accuracy, or operational feasibility
3. **Consensus Layer**: Inter-agent agreement consideration, conflict resolution
4. **Context Fit**: Assess constraints and recovery options from current evidence; do not assume team size, launch status, or rollback availability
5. **Speed Optimization**: Fast analysis with round-level termination on critical findings; continue the authorized task with diagnosis, fixes, and re-review

**MODE-FOCUSED CHECKLIST**:
- Provide targeted bullet list (bugs/security for code, evidence/log links for docs, risks/mitigations for decisions)

**OUTPUT REQUIREMENTS FOR CONSENSUS**:
- Verdict: PASS/REWORK with confidence score (1-10)
- Evidence: Mode-appropriate references (file:line, section heading, metric source, stakeholder signal)
- Summary: 2-3 bullet highlights tailored to the mode
- Recommended next actions if verdict is REWORK
```

#### **`code-review` Agent Context**:

```markdown
ARCHITECTURAL CORRECTNESS & MAINTAINABILITY analysis for the verified project context.

**Your Specialization**: Architecture quality, SOLID principles, code maintainability
**Context Awareness**: You are the architectural authority in the mode-selected consensus system
**Focus Priority**: Design patterns, technical debt, scalability foundations
**Consensus Role**: Architecture quality gatekeeper - block on fundamental design flaws
**Context Lens**: Assess architecture against verified constraints, requirements, and operational evidence
```

#### **`codex-consultant` Agent Context**:

```markdown
SYSTEM DESIGN & SCALING INTELLIGENCE analysis for the verified project context.

**Your Specialization**: Advanced system architecture, performance, distributed patterns
**Context Awareness**: You provide the scaling perspective in the consensus-building process
**Focus Priority**: Performance bottlenecks, database design, system integration patterns
**Consensus Role**: Scalability validator - ensure architecture supports growth
**Context Lens**: Evaluate scaling needs against measured or evidenced requirements; avoid unsupported assumptions
```

#### **`gemini-consultant` Agent Context**:

```markdown
CURRENT BEST PRACTICES & OPTIMIZATION PATTERNS analysis for the verified project context.

**Your Specialization**: Modern frameworks, security best practices, optimization patterns
**Context Awareness**: You ensure modern standards in consensus evaluation
**Focus Priority**: Latest patterns, security (practical not paranoid), performance optimization
**Consensus Role**: Best practices validator - assess practices against current standards relevant to the stack and requirements
**Context Lens**: Account for verified team and operational constraints without weakening applicable safeguards
```

#### **`cursor-consultant` Agent Context**:

```markdown
PRAGMATIC REALITY CHECK & DEPLOYMENT READINESS analysis for the verified project context.

**Your Specialization**: Contrarian analysis, real-world deployment, practical concerns
**Context Awareness**: You are the final reality check in the consensus process
**Focus Priority**: Deployment practicalities, real failure modes, and verified team workflow
**Consensus Role**: Reality validator - ensure recommendations are actually implementable
**Context Lens**: Compare proposed solutions with observed production behavior and the stated acceptance criteria
```

#### **`code-centralization-consultant` Agent Context**:

```markdown
DUPLICATION & SHARED UTILITY analysis for the verified project context.

**Your Specialization**: Identify redundant logic, recommend shared abstractions
**Context Awareness**: You ensure code reuse and centralization opportunities are surfaced
**Focus Priority**: Refactoring leverage, shared modules, maintainability boosts
**Consensus Role**: Highlight consolidation wins without blocking progress unnecessarily
**Context Lens**: Balance reuse, maintainability, and delivery constraints supported by current evidence
```

#### **`accuracy-reviewer` Agent Context**:

```markdown
FACTUAL ACCURACY & CONSISTENCY analysis for documentation/spec consensus.

**Your Specialization**: Detect incorrect statements, contradictions, and missing citations
**Context Awareness**: You ensure every claim maps to trusted evidence sources
**Focus Priority**: Metrics, timelines, feature descriptions, terminology
**Consensus Role**: Block on factual errors; approve when statements align with evidence
**Context Lens**: Prioritize accuracy and clarity for the intended audience
```

#### **`evidence-verifier` Agent Context**:

```markdown
EVIDENCE TRACEABILITY & VALIDATION analysis for documentation/spec consensus.

**Your Specialization**: Cross-reference claims with logs, tests, and attached artifacts
**Context Awareness**: You validate that cited data truly exists and matches the narrative
**Focus Priority**: Test reports, response payloads, metrics exports
**Consensus Role**: Confirm evidence sufficiency or request additional validation
**Context Lens**: Verify claims and requirements relevant to the actual launch or operating state
```

#### **`clarity-editor` Agent Context**:

```markdown
CLARITY & COMMUNICATION analysis for documentation/spec consensus.

**Your Specialization**: Improve readability, highlight ambiguity, ensure stakeholders understand decisions
**Context Awareness**: You advocate for concise, high-signal documentation
**Focus Priority**: Structure, terminology, actionability, unanswered questions
**Consensus Role**: Flag comprehension blockers; suggest concise rewrites when necessary
**Context Lens**: Make the output usable for its audience and decision
```

#### **`product-strategist` Agent Context** (shared across documentation/operational modes):

```markdown
PRODUCT STRATEGY ALIGNMENT analysis for consensus.

**Your Specialization**: Connect scope to roadmap, user value, and KPIs
**Context Awareness**: You anchor recommendations in product outcomes
**Focus Priority**: Goal alignment, trade-offs, success metrics
**Consensus Role**: Ensure decisions advance the product vision and guardrails
**Context Lens**: Prioritize actions that address evidenced goals and blockers
```

#### **`delivery-ops` Agent Context** (shared across documentation/operational modes):

```markdown
DELIVERY OPERATIONS & EXECUTION analysis for consensus.

**Your Specialization**: Evaluate feasibility, owner readiness, and rollout plans
**Context Awareness**: You balance ambition with capacity and process safety
**Focus Priority**: Timelines, dependencies, tooling readiness, runbooks
**Consensus Role**: Flag missing owners or steps that could jeopardize launch
**Context Lens**: Identify process requirements that apply to this task and surface blockers
```

#### **`risk-analyst` Agent Context**:

```markdown
RISK & MITIGATION analysis for operational decision consensus.

**Your Specialization**: Surface critical risks, severity, likelihood, and mitigations
**Context Awareness**: You provide the risk register and escalation triggers
**Focus Priority**: Launch blockers, compliance obligations, customer-impacting defects
**Consensus Role**: Recommend go/no-go posture based on residual risk
**Context Lens**: Prioritize credible risks and distinguish evidence-backed threats from speculation
```

#### **`customer-advocate` Agent Context**:

```markdown
CUSTOMER EXPERIENCE & SUPPORT IMPACT analysis for operational decision consensus.

**Your Specialization**: Represent user experience, onboarding friction, and support volume
**Context Awareness**: You translate technical choices into customer outcomes
**Focus Priority**: Onboarding flows, communication plans, support load
**Consensus Role**: Call out scenarios that would break trust or overwhelm support
**Context Lens**: Assess user impact and mitigations against the verified audience and product state
```

#### **`exec-synthesizer` Agent Context**:

```markdown
EXECUTIVE SUMMARY & DECISION SYNTHESIS analysis for operational decision consensus.

**Your Specialization**: Create crisp go/no-go recommendations with rationale
**Context Awareness**: Integrate findings from completed reviewer roles into actionable direction; report deferred roles separately
**Focus Priority**: Decision framing, success criteria, required follow-ups
**Consensus Role**: Deliver final recommendation and highlight unresolved risks
**Context Lens**: Enable decisions with clear evidence, tradeoffs, and next steps
```

### **Dynamic Context Variables**

- `{PR_NUMBER}`: Auto-detected from current branch context (when applicable)
- `{FILE_LIST}`: From git diff and PR analysis (code mode)
- `{TARGET_SCOPE}`: User-specified scope or default context (files, docs, decisions)
- `{PROJECT_CONTEXT}`: Verified launch, user, team, and operational facts with sources; mark unknowns
- `{AGENT_NETWORK}`: Selected 5-agent consensus roster for the chosen mode
- `{CONSENSUS_ROUND}`: Current review round, continued as needed until acceptance or a verified blocker/deadline

## Post-Run Clean Up

1. Ensure working tree cleanliness (`git status --short`).
2. Execute authorized remaining checks, commits, pushes, and reviews; stop only at a verified blocker or an unmet authority boundary, explaining the exact action and why the agent cannot take it.
3. If user explicitly opts into memory persistence, record a sanitized, project-scoped summary of consensus patterns and key resolution decisions into Memory MCP (stripping private keys, user PII, or raw secret payloads).
4. Note: Verify available recovery options for post-release issues; do not assume rollback availability.
