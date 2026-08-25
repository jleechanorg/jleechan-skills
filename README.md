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

| Command | Full name / skill | One-line summary |
|---|---|---|
| `/advice` (`/smart-advisor`) | [`advice`](.claude/skills/advice/SKILL.md) | Parallel second opinion and synthesis. |
| `/repro` | [`repro-evidence`](.claude/skills/repro-evidence/SKILL.md) | Reproduces a reported problem against a real target. |
| `/research` | [`research`](.claude/skills/research/SKILL.md) | Primary-source research with citations. |
| `/memory-search` (`/ms`) | [`memory-search`](.claude/skills/memory-search/SKILL.md) | Searches configured memory stores in parallel. |
| `/evidence-review` (`/er`) | [`evidence-review`](.claude/skills/evidence-review/SKILL.md) | Reviews evidence against the evidence standard. |
| `/factory` (`/f`) | [`dark-factory`](.claude/skills/dark-factory/SKILL.md) | Runs an external Dark Factory pipeline. |
| `/es` | [`evidence-standards`](.claude/skills/evidence-standards/SKILL.md) | Defines evidence strength and required artifacts. |
| `/web-advice` (`/webadvice`) | [`web-advice`](.claude/skills/web-advice/SKILL.md) | Authenticated browser-based multi-model review. |
| `/browser` | [`browser-control`](.claude/skills/browser-control/SKILL.md) | Routes live-browser tasks to the right tool. |
| `/skillify` | [`skillify`](.claude/skills/skillify/SKILL.md) | Turns a reusable procedure into a skill package. |
| `/harness` | [`harness-engineering`](.claude/skills/harness-engineering/SKILL.md) | Finds and repairs durable harness gaps. |
| `/learn` | [`learn`](.claude/skills/learn/SKILL.md) | Captures a reusable lesson in configured stores. |
| `/4layer` | [`4layer`](.claude/skills/4layer/SKILL.md) | Escalates a minimal reproduction through four layers. |
| `/redgreen` (`/rg`) | [`redgreen`](.claude/skills/redgreen/SKILL.md) | Requires RED, targeted CODE, GREEN, and consensus. |
| `/parallel` | [`parallelize-to-ceiling`](.claude/skills/parallelize-to-ceiling/SKILL.md) | Sizes independent work to real resource limits. |
| `/history` | [`conversation-history-sparse`](.claude/skills/conversation-history-sparse/SKILL.md) | Searches conversation history with bounded scope. |
| `/sidekick` | [`sidekick`](.claude/skills/sidekick/SKILL.md) | Runs a persistent named teammate. |
| `/swarm` | [`swarm`](.claude/skills/swarm/SKILL.md) | Coordinates multi-agent work with adversarial verification. |

---

## 📖 Detailed Skill Reference

### [`advice`](.claude/skills/advice/SKILL.md) — `/advice`, alias `/smart-advisor`

Gets a fast, cheap second opinion at a decision point without shipping the whole conversation to another model. Extracts a tight decision (3-5 sentences) plus a ≤150-line artifact, then fans out to up to four reviewers concurrently: an Opus subagent (with a cursor→agy→`claude -p` fallback chain), `/research`, `/secondo`, and `/web-advice`. Results synthesize into a comparison table; inside the `draft-first-pr` lifecycle it ends with a binary, SHA-bound verdict (`VERDICT: APPROVED at <SHA>`) so a later commit invalidates a stale approval. Degrades gracefully if a reviewer CLI is missing rather than failing outright.

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

The enforcement layer on top of `evidence-standards`' "what to produce" layer. Runs mandatory bundle-integrity checks (checksum verification) before judging, then returns PASS / PARTIAL / FAIL / INCONCLUSIVE with file:line-level artifact citations. PASS requires every claim backed by a STRONG-quality artifact and is mandatory for `/green` on production-tier PRs; its verdict is parsed directly into `/green`'s merge-gate table.

```bash
/evidence-review docs/evidence/checkout-latency-fix/
```

### [`dark-factory`](.claude/skills/dark-factory/SKILL.md) — `/factory` (`/f`)

Runs a goal through the real external `dark-factory` binary and `.dot`-graph pipeline runner (StrongDM's Attractor pattern), recording every step in a SQLite CXDB rather than a conversation transcript, and grading against sealed holdout scenarios in a separate repo the agent is never allowed to read. Trades higher session cost for full replayability and a hard separation between the coding agent and the adversarial evaluator.

```bash
/factory "Implement idempotent webhook signature validation with HMAC-SHA256"
```

### [`evidence-standards`](.claude/skills/evidence-standards/SKILL.md) — `/es`

Cross-project evidence-strength policy: a raw request/response capture from the real production code path is the strongest proof; an isolated unit test with mocked internals proves nothing about real behavior. Requires an "Evidence Envelope Declaration" — a per-item ledger, not free narration — for any breadth claim ("all/every/across N"). Names mocking an SDK at the in-process boundary (instead of the real network boundary) as a specific fabricated-evidence anti-pattern.

```bash
/es "Verify API response latency reduction under 200 concurrent requests"
```

### [`web-advice`](.claude/skills/web-advice/SKILL.md) — `/web-advice`, alias `/webadvice`

Multi-model adversarial review through real, authenticated browser sessions on ChatGPT, Gemini, Grok, and Perplexity Web — never a provider API or CLI substitute. Reserved for reviews needing genuine cross-model-family convergence or web-grounded fact-checking. Requires the PR/evidence bundle to already be ready before any browser session opens.

```bash
/web-advice "Should we migrate auth session storage from Redis to DynamoDB with TTL?"
```

### [`browser-control`](.claude/skills/browser-control/SKILL.md) — `/browser`

General-purpose live-browser task router: Aside first for authenticated sessions/site settings/OAuth/existing tabs, `playwright-ui-testing` for deterministic app testing, and `browserclaw` for headless fallback work. For an authenticated share flow, `browserclaw` may copy cookies from a locally authorized browser profile into its headless session; it does not bypass login, MFA, or consent.

```bash
/browser "open the billing settings page and check the current plan tier"
```

### [`skillify`](.claude/skills/skillify/SKILL.md) — `/skillify`

Audits a target script, feature, or workflow against a completeness checklist (SKILL.md frontmatter, tests, evals if it calls an LLM, resolver trigger, E2E test, memory filing) and generates whatever's missing, so useful procedures stop living only as ad-hoc scripts.

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

### [`conversation-history-sparse`](.claude/skills/conversation-history-sparse/SKILL.md) — `/history`

Sparse, budget-capped search across the 3 canonical history stores (Claude Code JSONL, Codex SQLite threads, Hermes FTS5) with hard sampling limits — never `cat`s a full file. `--deep` escalates to a 6-source search (adds Antigravity, OpenCode, and Cursor history) when sparse results aren't enough.

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
