---
description: Claude Skills & Commands - Modular Agent Skills Library for Claude Code, Antigravity, Codex, and Cursor
type: llm-orchestration
execution_mode: immediate
---

# 🧠 Agent Skills

Portable `SKILL.md` packages for debugging, evidence, research, reviews, and
agent workflows. Skills are the source of truth; slash commands are optional
shortcuts.

---

## Executive Summary

Six highlighted skills form a portable quality loop around implementation.
Shift left to challenge decisions and prove the problem before code is trusted;
shift right to locate failures, audit evidence, and prevent repeat escapes.

### Highlighted skills · left/right shift strategy

| Shift left · before the code | Shift right · after the code |
|---|---|
| **[Superpowers brainstorm](https://github.com/obra/superpowers) (third-party)** — made by Jesse Vincent; design before writing code. | **[`/4layer`](.claude/skills/4layer/SKILL.md)** — unit → end-to-end → MCP/HTTP → browser; the first reproducing layer owns the investigation. |
| **[`/advice`](.claude/skills/advice/SKILL.md) + [`/web-advice`](.claude/skills/web-advice/SKILL.md)** — fan out independent reviewers before committing to an approach. | **[`/evidence-review`](.claude/skills/evidence-review/SKILL.md)** — require every claim to resolve to a real, provenance-backed artifact. |
| **[`/redgreen`](.claude/skills/redgreen/SKILL.md)** — require a test you watched fail before accepting the bug or its fix as real. | **[`/harness`](.claude/skills/harness-engineering/SKILL.md)** — when a failure repeats, fix the process that allowed it through. |

The six highlighted `jleechanorg` skills are `/advice`, `/web-advice`,
`/redgreen`, `/4layer`, `/evidence-review`, and `/harness`. They are portable
prompts and packages that do not depend on WorldAI or private infrastructure.

> **Third-party attribution:** [Superpowers](https://github.com/obra/superpowers)
> is made by Jesse Vincent. It can complement the shift-left side of this
> strategy, but it is **not authored, owned, or maintained by Jeffrey Lee or
> jleechanorg**, and it is not one of the six skills highlighted above.

Strategy source: [“Shift left, shift right — a portable skill system”](https://docs.google.com/presentation/d/1rGk2ZUIlJw3AkVJmJbdVB5OqAixR6M_xp7lc6lP2awA/edit?slide=id.gogSlide1787597443235634000#slide=id.gogSlide1787597443235634000).

---

## Intelligent self-setup (any platform)

Ask your coding agent to inspect the repository and install only what it needs:

```text
"Inspect https://github.com/jleechanorg/jleechan-skills and set up the skills most useful for my tech stack."
```

For a deterministic install, use the bundled installer. It installs complete
skill packages (including their helper files), commands, agents, and scripts
under `CLAUDE_HOME` (default: `~/.claude`). It refuses a nonempty target by
default; `--backup` preserves that target before installing and `--merge`
updates it in place.

```bash
INSTALL_ROOT=$(mktemp -d /tmp/jleechan-skills.XXXXXX)
git clone https://github.com/jleechanorg/jleechan-skills.git "$INSTALL_ROOT/source"
CLAUDE_HOME="$INSTALL_ROOT/claude" \
  bash "$INSTALL_ROOT/source/install-claude-commands.sh"
```

This is an isolated smoke test: inspect `"$INSTALL_ROOT/claude/skills"` and
remove only that exact temporary directory when finished. For an install into
your real `~/.claude`, first read the backup and rollback notes in
[INSTALL.md](INSTALL.md).

See [INSTALL.md](INSTALL.md) for target locations, isolated verification, and
safe rollback.

## 🏛️ How It Works: Skills First, Thin Slash Pointers

```
                  ┌──────────────────────────────────────────────┐
                  │                 Developer / AI               │
                  │   types /repro, /es, /ms, /f, etc.           │
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
                  │   • Portable: Claude Code, Antigravity, Codex, Cursor │
                  └──────────────────────────────────────────────┘
```

1. **Skills (`.claude/skills/`) are the source of truth** — protocols, schemas, checklists, and helper scripts live in standard `SKILL.md` folders.
2. **Slash commands (`.claude/commands/`) are thin pointers** — no separate logic, just an ergonomic shortcut that loads and runs the skill.
3. **Cross-agent portability** — because every skill follows the `SKILL.md` spec, it runs natively in Claude Code, Antigravity, Codex, and Cursor without translation.

Read a skill before using it: some skills require a local binary, browser
session, or integration that is not bundled with this export.

---

## 📋 Skills at a Glance

The catalog below links to the canonical skills. Commands are convenience
pointers and are intentionally not the documentation target.

| Command | Full name / skill | When to use it / expected outcome |
|---|---|---|
| `/advice` (`/smart-advisor`) | [`advice`](.claude/skills/advice/SKILL.md) | Use at a design or implementation decision. Give the question plus a PR, ref, or path; independent reviewers read the real scope and return a synthesized recommendation. For a PR gate, incomplete or truncated review context can only yield `WITHHELD`, never approval. |
| `/repro` | [`repro-evidence`](.claude/skills/repro-evidence/SKILL.md) | Use before fixing a reported bug that needs proof. State the symptom and real target; it creates an isolated replay, captures provenance, and returns `REPRO`, `RELATED`, or `NON-REPRO` rather than guessing. |
| `/research` | [`research`](.claude/skills/research/SKILL.md) | Use when a decision depends on facts rather than recollection. Ask a focused question; a background agent gathers primary sources and writes a cited Markdown finding in the repo’s established notes location. |
| `/memory-search` (`/ms`) | [`memory-search`](.claude/skills/memory-search/SKILL.md) | Use to recover prior work, decisions, or incidents. Ask a specific query; it searches the configured roadmap, Beads, local memories, history, wiki, and Slack in parallel, then returns merged, cacheable leads. |
| `/evidence-review` (`/er`) | [`evidence-review`](.claude/skills/evidence-review/SKILL.md) | Use after collecting evidence for a claim or PR, especially production behavior. Supply the bundle or subject; it checks integrity and provenance, maps artifacts to claims, and returns `PASS`, `PARTIAL`, `FAIL`, or `INCONCLUSIVE`. |
| `/factory` (`/f`) | [`dark-factory`](.claude/skills/dark-factory/SKILL.md) | Use when you want a replayable external pipeline rather than an in-chat agent loop. Give it a concrete goal on a machine with Dark Factory installed; it records the graph run and evaluates against sealed holdouts. |
| `/es` | [`evidence-standards`](.claude/skills/evidence-standards/SKILL.md) | Use before claiming a production behavior is fixed or before asking for `/er`. State the claim and its scope; it tells you which real-path artifacts are needed and what those artifacts can, and cannot, prove. |
| `/web-advice` (`/webadvice`) | [`web-advice`](.claude/skills/web-advice/SKILL.md) | Use for an independent external perspective on code, plans, documents, designs, or decisions. Provide the review scope and relevant links/material; authenticated web models are compared with declared coverage and any unavailable-model gap is disclosed. |
| `/browser` | [`browser-control`](.claude/skills/browser-control/SKILL.md) | Use to inspect or complete an approved live-browser task. Name the site, target state, and allowed side effect; it selects the right browser tool, works from current page state, and confirms the resulting UI state. |
| `/skillify` | [`skillify`](.claude/skills/skillify/SKILL.md) | Use when a useful script, feature, or repeatable procedure should become a durable skill. Give the target path and purpose; it audits the completeness contract and identifies or creates the missing skill, test, resolver, and command pieces. |
| `/harness` | [`harness-engineering`](.claude/skills/harness-engineering/SKILL.md) | Use after a recurring agent mistake, review escape, or workflow failure. Describe the incident; it traces the cause through instructions, skills, memory, tests, and automation, then fixes the most durable layer. |
| `/learn` | [`learn`](.claude/skills/learn/SKILL.md) | Use to preserve a concrete correction or recovery pattern after it is understood. State the lesson and context; it files it in the configured durable stores and reports any persistence destination that is unavailable. |
| `/4layer` | [`4layer`](.claude/skills/4layer/SKILL.md) | Use to locate a PR blocker with the smallest credible reproduction. Give the bug and target repo; it discovers the project’s runner, tries unit → end-to-end → API → browser, and stops at the first conclusive layer. |
| `/redgreen` (`/rg`) | [`redgreen`](.claude/skills/redgreen/SKILL.md) | Use to repair one known defect test-first. Provide the current symptom; it requires a fresh failing reproduction, a minimal fix, a passing rerun, and evidence that the full RED → CODE → GREEN flow actually happened. |
| `/parallel` | [`parallelize-to-ceiling`](.claude/skills/parallelize-to-ceiling/SKILL.md) | Use whenever work has independent files, tests, rows, jobs, or agent lanes. List the work and constraints; it identifies the real CPU, I/O, network, or shared-state limit and proposes safe shards instead of an arbitrary worker count. |
| `/superpowers-quick` | [`superpowers-quick`](.claude/skills/superpowers-quick/SKILL.md) | Use when you want the normal Superpowers design process to select its recommended defaults autonomously. Give it the idea or requested change; it writes a self-reviewed design specification and implementation plan without pausing for preference or approval questions. |
| `/history` | [`conversation-history-sparse`](.claude/skills/conversation-history-sparse/SKILL.md) | Use for fast orientation on what the current repo or branch has been doing. Ask a focused question; it samples high-signal Claude, Codex, and Hermes history without loading full transcripts; add `--deep` only when the sparse pass is insufficient. |
| `/sidekick` | [`sidekick`](.claude/skills/sidekick/SKILL.md) | Use for one long-running mission that must survive a session crash. Give a named outcome and success criteria; it assigns a persistent teammate and checkpoints durable state plus a resumption Bead. |
| `/swarm` | [`swarm`](.claude/skills/swarm/SKILL.md) | Use when a goal decomposes into independent, adversarially reviewable lanes. State the goal and optional shape/engine; it sizes the fan-out, assigns explicit models and disjoint outputs, and requires multi-lens verification before synthesis. |

---

## 📖 Detailed Skill Reference

### [`advice`](.claude/skills/advice/SKILL.md) — `/advice`, alias `/smart-advisor`

Use this when you need independent reasoning at a real decision point. Give it a concise question and a pointer to the actual subject—a PR number, `base...head` ref, or file list—rather than pasting a preselected diff. It fans out to up to four reviewers concurrently: an Opus subagent (with a cursor→agy→`claude -p` fallback chain), `/research`, `/secondo`, and `/web-advice`, then returns a comparison table and recommendation. In `draft-first-pr`, an `APPROVED at <SHA>` verdict requires two independent reviewers whose declared coverage together spans the whole change; fewer than two such reviewers, partial coverage, or a truncated inline fallback produces `WITHHELD`, not approval.

```bash
/advice "Should we switch this cache from LRU to LFU eviction?"
```

### [`repro-evidence`](.claude/skills/repro-evidence/SKILL.md) — `/repro`

Generic, domain-agnostic reproduction workflow: isolate the reported state into a safe test sandbox, replay only the exact triggering action against a real (never mocked) target, and enforce a strict same-symptom rule — a repro only counts if the identical user-visible phenotype reappears. Every RED/GREEN claim must record explicit code and environment provenance. Closes with a mandatory REPRO / RELATED / NON-REPRO verdict table and exported evidence (raw request/response, logs, state diffs).

```bash
/repro "Checkout fails with 500 error when applying coupon code"
```

### [`research`](.claude/skills/research/SKILL.md) — `/research`

Spins up a background agent that investigates a question strictly against primary sources — official docs, source code, specs, first-party APIs — never secondary summaries. Every claim traces back to the source that owns it; findings land as a single cited Markdown file in whatever location the repo already uses for such notes. Runs async so the calling session keeps working.

```bash
/research "PostgreSQL 17 logical replication improvements and zero-downtime schema upgrades"
```

### [`memory-search`](.claude/skills/memory-search/SKILL.md) — `/memory-search` (`/ms`)

Fans a query out in parallel across ten distinct memory sources — roadmap, beads, Claude Code session memories, Hermes SQLite (FTS5), Hermes briefings, the Hermes memory index, OpenClaw memories, the local LLM wiki, raw conversation history, and Slack — instead of searching just one. Caches merged results by query hash with a 1-hour TTL so repeat lookups short-circuit.

```bash
/memory-search "recent deployment failure"
```

### [`evidence-review`](.claude/skills/evidence-review/SKILL.md) — `/evidence-review` (`/er`)

Use this after evidence has been captured, not as a substitute for capturing it. Point it at the evidence bundle or claim path; it checks artifact integrity and whether the claimed evidence has real execution provenance, then returns PASS / PARTIAL / FAIL / INCONCLUSIVE with file:line citations. Checksums protect an artifact’s integrity but do not establish its provenance. A production-tier `/green` requires PASS, while non-production work can use a disclosed PARTIAL waiver.

```bash
/evidence-review docs/evidence/checkout-latency-fix/
```

### [`dark-factory`](.claude/skills/dark-factory/SKILL.md) — `/factory` (`/f`)

Runs a goal through the real external `dark-factory` binary and `.dot`-graph pipeline runner (StrongDM's Attractor pattern), recording every step in a SQLite CXDB rather than a conversation transcript, and grading against sealed holdout scenarios in a separate repo the agent is never allowed to read. It trades interactive in-session flexibility for replayability and a hard separation between the coding agent and adversarial evaluator, while generally reducing session-context cost to one CLI call per node.

```bash
/factory "Implement idempotent webhook signature validation with HMAC-SHA256"
```

### [`evidence-standards`](.claude/skills/evidence-standards/SKILL.md) — `/es`

Cross-project evidence-strength policy: a raw request/response capture from the real production code path is the strongest proof; an isolated unit test with mocked internals proves nothing about real behavior. For any breadth claim ("all/every/across N"), first declare the requested and reachable sets plus expansion cost and get acceptance; then report from a per-item Evidence Envelope ledger, leading with any undelivered scope. Names mocking an SDK at the in-process boundary (instead of the real network boundary) as a specific fabricated-evidence anti-pattern.

```bash
/es "Verify API response latency reduction under 200 concurrent requests"
```

### [`web-advice`](.claude/skills/web-advice/SKILL.md) — `/web-advice`, alias `/webadvice`

Use this when an external, web-grounded, multi-model perspective will improve a code review, design, document, plan, research question, or operational decision. Provide the subject, scope, and any relevant links or artifacts; it uses real authenticated browser sessions on ChatGPT, Gemini, Grok, and Perplexity Web—never a provider API or CLI substitute—and records each available model’s verdict and coverage. Run `/er` separately only when the subject includes an evidence bundle or production claim.

```bash
/web-advice "Should we migrate auth session storage from Redis to DynamoDB with TTL?"
```

### [`browser-control`](.claude/skills/browser-control/SKILL.md) — `/browser`

General-purpose live-browser task router: Aside first for authenticated sessions/site settings/OAuth/existing tabs, `playwright-ui-testing` for deterministic app testing, and `browserclaw` for headless fallback work. For an authenticated share flow, `browserclaw` may copy cookies from a locally authorized browser profile into its headless session; it does not bypass login, MFA, or consent.

```bash
/browser "open the billing settings page and check the current plan tier"
```

### [`skillify`](.claude/skills/skillify/SKILL.md) — `/skillify`

Audits a target script, feature, or workflow against a completeness checklist (SKILL.md frontmatter, tests, evals if it calls an LLM, resolver trigger, E2E test, memory filing) and generates whatever's missing, so useful procedures stop living only as ad-hoc scripts. If the result exposes a slash command, it also requires a thin pointer command so workflow logic lives only in `SKILL.md`.

```bash
/skillify scripts/deploy-staging.sh
```

### [`harness-engineering`](.claude/skills/harness-engineering/SKILL.md) — `/harness`

Diagnoses whether a mistake is a gap in the agent's own harness (instructions, skills, memory, tests, CI — ordered by durability) rather than a one-off bug, then drives a fix at the correct layer. Requires two separate 5-Whys drill-downs: one technical, one on why the agent's own reasoning let the failure through.

```bash
/harness "Test stripe webhook idempotency under concurrent retries"
```

### [`learn`](.claude/skills/learn/SKILL.md) — `/learn`

Captures a durable lesson from a failure or correction and writes it into every persistent knowledge store — a Claude auto-memory file, an optional mem0 save, a monthly roadmap log, a closed/referenced bead, and an LLM wiki ingest — rather than leaving it as a one-off chat summary. Applies a "fix vs. document" rule: small blocking config fixes get fixed immediately, not just recorded.

```bash
/learn "we kept re-discovering the same env-var name mismatch — write it down"
```

### [`4layer`](.claude/skills/4layer/SKILL.md) — `/4layer` (`/extended-library:4layer`)

A four-tier minimal-repro escalation ladder for PR blockers — unit → end2end → MCP/HTTP API → browser — halted at the first layer that reproduces the bug. The reproducing layer itself tells you where the bug lives (unit failure implies backend logic, browser failure implies UI/frontend).

```bash
/extended-library:4layer "checkout button does nothing on mobile Safari"
```

### [`redgreen`](.claude/skills/redgreen/SKILL.md) — `/redgreen` (`/rg`)

Strict four-phase debugging: RED requires a fresh, real failing test reproducing the exact error in the current session (an old CI failure doesn't count); CODE requires a minimal targeted fix, no unrelated refactoring; GREEN confirms the test now passes and checks for regressions; CONSENSUS validates the whole flow was legitimately executed with evidence at each step.

```bash
/extended-library:rg "intermittent 500 on /api/checkout under load"
```

### [`parallelize-to-ceiling`](.claude/skills/parallelize-to-ceiling/SKILL.md) — `/parallel` (`/extended-library:parallel`)

One law: for independent work, the speed ceiling is the real per-item resource bound, never an arbitrary worker count and never serial. Gives a five-step decision procedure (enumerate independent items, classify by resource profile, shard at the machine level first, scale the fleet to the workload, then prove concurrency by sampling live process counts — never trust a passed flag alone).

```bash
/extended-library:parallel "run these 12 independent lint fixes"
```

### [`superpowers-quick`](.claude/skills/superpowers-quick/SKILL.md) — `/superpowers-quick`

An opt-in autonomous wrapper around `superpowers:brainstorming`. It inspects the project, selects and records its recommended answers, completes the architectural design path, and then invokes `superpowers:writing-plans`. The terminal result is a self-reviewed specification under `docs/superpowers/specs/` and an executable plan under `docs/superpowers/plans/`; it does not start implementation.

```bash
/superpowers-quick "add offline-first notes sync"
```

### [`conversation-history-sparse`](.claude/skills/conversation-history-sparse/SKILL.md) — `/history`

Sparse, budget-capped search across the 3 canonical history stores (Claude Code JSONL, Codex SQLite threads, Hermes FTS5) with hard sampling limits — never `cat`s a full file. `--deep` escalates to the seven-source, larger-budget `history-search` pass when sparse results are not enough.

```bash
/history "why did the worktree cleanup script get deleted"
```

### [`sidekick`](.claude/skills/sidekick/SKILL.md) — `/sidekick`

Spawns a single named, in-session Claude Agent-Team teammate — visible in the panel, SendMessage-addressable — to own a long-running mission (PR fleets, research sweeps, migrations). Durability comes from disk state (a `STATE.md` + a priority-1 resumption bead, checkpointed every ≤5 minutes), not the running process, so a crashed session can respawn the same teammate with zero conversation context.

```bash
/sidekick "drive all open CI-red PRs to green overnight"
```

### [`swarm`](.claude/skills/swarm/SKILL.md) — `/swarm`

Orchestrates a multi-agent swarm — either a deterministic Workflow-tool fan-out or named Agent-team lanes — with adversarial verification baked in (3-lens refute-by-default, ≥2/3 must survive). Always runs inside a sidekick for durability, regardless of engine. Every spawned agent must set its model tier explicitly; an unset model silently inheriting the session model is treated as a policy violation.

```bash
/swarm "audit code quality across the whole payments module" --shape review
```

---

## 🗂️ Command Layout & Catalog

Browse [`.claude/skills/`](.claude/skills/) for the complete skill library.
Commands are grouped into the flat core and `extended-library` namespaces.

---

## 🔗 Chaining & Composition

Commands and skills compose naturally in a single prompt:

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

- [INSTALL.md](INSTALL.md) — extended installation guide and troubleshooting.
- [`.claude/skills/`](.claude/skills/) — complete skill library.
- [INSTALL.md](INSTALL.md) — installation and verification.

---

🚀 **Built for modern AI-assisted engineering — portable across Claude Code, Antigravity, Codex, and Cursor.**
