---
description: Guided feature development with systematic codebase understanding and architecture focus (your-project.com only — defaults to $PROJECT_ROOT/ layouts and Flask/Firebase/Gemini patterns)
type: llm-orchestration
execution_mode: immediate
argument-hint: Optional feature description
---

> **Worldai-only command.** Hardcoded to the Your Project narrative
> (Python / Flask / Firebase / Gemini) and the `$PROJECT_ROOT/` package layout.
> The repo-local counterpart lives at
> `$GITHUB_REPOSITORY/.claude/commands/feature-dev.md` and is
> preferred when working in that repo. When invoked outside the worldai
> repo, the layout and stack assumptions will not apply.

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately.**
**Use TodoWrite to track progress through all phases.**

Source: adapted from anthropics/claude-plugins-official/feature-dev

# Feature Development

You are helping implement a new feature for Your Project (AI-powered tabletop RPG platform, Python/Flask/Firebase/Gemini). Follow a systematic approach: understand the codebase deeply, ask about all underspecified details, design elegant architectures, then implement.

## Core Principles

- **Ask clarifying questions first**: Identify all ambiguities, edge cases, and underspecified behaviors. Ask specific, concrete questions rather than making assumptions. Wait for user answers before proceeding with implementation.
- **Understand before acting**: Read and comprehend existing code patterns first
- **Read files identified by agents**: When launching agents, ask them to return lists of the most important files to read. After agents complete, read those files to build detailed context.
- **Simple and elegant**: Prioritize readable, maintainable, architecturally sound code (SOLID, DRY)
- **CLAUDE.md compliance**: Follow all rules in CLAUDE.md — no new env vars, no try/except around imports, use vpython, etc.
- **Use TodoWrite**: Track all progress throughout

---

## Phase 1: Discovery

**Goal**: Understand what needs to be built

Initial request: $ARGUMENTS

**Actions**:
1. Create todo list with all phases
2. If feature is unclear, ask user:
   - What problem are they solving?
   - What should the feature do?
   - Any constraints or requirements?
   - Which part of the stack (frontend JS, Flask backend, Firebase, Gemini API)?
3. Summarize understanding and confirm with user before proceeding

---

## Phase 2: Codebase Exploration

**Goal**: Understand relevant existing code and patterns at both high and low levels

**Actions**:
1. Launch 2-3 parallel Explore agents, each targeting a different aspect:
   - "Find features similar to [feature] and trace through their implementation in $PROJECT_ROOT/"
   - "Map the Flask routes, Firebase models, and Gemini API integration for [feature area]"
   - "Identify UI patterns (vanilla JS/Bootstrap), testing approaches, and extension points relevant to [feature]"
   - Each agent should return a list of 5-10 key files to read

2. Read all files identified by agents to build deep understanding
3. Present comprehensive summary of findings, patterns, and integration points discovered

---

## Phase 3: Clarifying Questions

**Goal**: Fill in gaps and resolve all ambiguities before designing

**CRITICAL**: Do NOT skip this phase.

**Actions**:
1. Review codebase findings and original feature request
2. Identify underspecified aspects: edge cases, error handling, integration points, scope boundaries, backward compatibility, performance needs, Gemini API usage patterns
3. **Present all questions to the user in a clear, organized list**
4. **Wait for answers before proceeding to architecture design**

If the user says "whatever you think is best", provide your recommendation and get explicit confirmation.

---

## Phase 4: Architecture Design

**Goal**: Design multiple implementation approaches with different trade-offs

**Actions**:
1. Launch 2-3 parallel architect agents with different focuses:
   - **Minimal changes**: Smallest change, maximum reuse of existing $PROJECT_ROOT/ patterns
   - **Clean architecture**: Maintainability, elegant abstractions, SOLID principles
   - **Pragmatic balance**: Speed + quality for solo developer context

2. Review all approaches and form your recommendation (consider: small fix vs large feature, complexity, CLAUDE.md constraints)
3. Present to user:
   - Brief summary of each approach
   - Trade-offs comparison
   - **Your recommendation with reasoning**
   - Concrete implementation differences (files changed, new files if unavoidable)
4. **Ask user which approach they prefer**

---

## Phase 5: Implementation

**Goal**: Build the feature

**DO NOT START WITHOUT USER APPROVAL FROM PHASE 4**

**Actions**:
1. Wait for explicit user approval of chosen approach
2. Read all relevant files identified in previous phases
3. Implement following chosen architecture
4. Follow codebase conventions strictly:
   - Python → `$PROJECT_ROOT/`; Tests → `$PROJECT_ROOT/tests/`; Scripts → `scripts/`
   - Use `vpython` for running; `TESTING_AUTH_BYPASS=true vpython` for local tests
   - No new env vars (use constants); no try/except around imports; no inline imports
   - All imports at module top, alphabetically sorted within groups
5. Write clean, well-commented code (explain *why*, not *what*)
6. Update todos as you progress

---

## Phase 6: Quality Review

**Goal**: Ensure code is simple, DRY, elegant, and functionally correct

**Actions**:
1. Launch 3 parallel reviewer agents with different focuses:
   - Simplicity/DRY/elegance
   - Bugs/functional correctness/edge cases
   - CLAUDE.md compliance/project conventions
2. Apply confidence scoring (0-100) to each finding — present only issues scoring ≥80
3. **Present findings to user and ask what they want to do** (fix now, fix later, or proceed as-is)
4. Address issues based on user decision

---

## Phase 7: Summary

**Goal**: Document what was accomplished

**Actions**:
1. Mark all todos complete
2. Summarize:
   - What was built and where files live
   - Key decisions made and why
   - Files modified (repo-relative or `~`-prefixed paths, per CLAUDE.md)
   - Suggested next steps (tests to write, docs to update, etc.)
