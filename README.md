---
description: Claude Skills & Commands - Modular Agent Skills Library for Claude Code, Antigravity, Codex, and Cursor
type: llm-orchestration
execution_mode: immediate
---

# 🧠 Claude Skills & Commands

## TL;DR

This repo packages hard-won engineering discipline — empirical debugging, evidence-backed claims, multi-model review, autonomous PR pipelines, resource-ceiling parallelism — as portable **skills** (`SKILL.md` packages) with thin slash-command pointers on top. Skills are the source of truth; commands are just the typing shortcut. Because every skill follows the same YAML-frontmatter + Markdown spec, the same skill runs unmodified in **Claude Code**, **Google Antigravity**, **OpenAI Codex**, and **Cursor 2.4+**. Install once, use everywhere.

The set below is not a guess — every command's usage count comes from mining real session logs (`/command-research`) across this machine's Claude Code, Hermes, and Codex history, then independently re-verified against the raw conversation files before being trusted.

---

## Table of Contents

- [Install](#-install)
- [How It Works: Skills First, Thin Slash Pointers](#-how-it-works-skills-first-thin-slash-pointers)
- [Skills at a Glance](#-skills-at-a-glance)
- [Detailed Skill Reference](#-detailed-skill-reference)
- [Command Layout & Catalog](#-command-layout--catalog)
- [Chaining & Composition](#-chaining--composition)
- [References](#-references--contributing)

---

## 📦 Install

### Claude Code

```bash
/plugin marketplace add jleechanorg/jleechan-skills
/plugin install jleechan-skills@jleechan-skills
```

Restart your CLI session, then run `/help` to confirm commands and skills appear.

### Google Antigravity

This repo ships a plugin manifest at [`.agents/plugins/plugin.json`](.agents/plugins/plugin.json) and [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json) (`skills: ".claude/skills/"`), intended for `agy plugin install`. That install path is structurally present but has not yet been proven with a live end-to-end run — until confirmed, the reliable path is manual:

```bash
git clone https://github.com/jleechanorg/jleechan-skills.git /tmp/jleechan-skills
mkdir -p .claude/skills
cp -r /tmp/jleechan-skills/.claude/skills/* .claude/skills/
```

Antigravity's own IDE and `agy` CLI discover `SKILL.md` packages under `.claude/skills/` directly.

### OpenAI Codex CLI

Codex does not have a plugin marketplace equivalent yet. Copy the skills directory into your project (or `~/.codex/skills/` for a user-global install):

```bash
git clone https://github.com/jleechanorg/jleechan-skills.git /tmp/jleechan-skills
mkdir -p .claude/skills
cp -r /tmp/jleechan-skills/.claude/skills/* .claude/skills/
```

### Cursor (2.4+)

Cursor's skill discovery scans `.claude/skills/` directly — no separate install step or format conversion needed:

```bash
git clone https://github.com/jleechanorg/jleechan-skills.git /tmp/jleechan-skills
mkdir -p .claude/skills
cp -r /tmp/jleechan-skills/.claude/skills/* .claude/skills/
```

### Intelligent self-setup (any platform)

Ask your coding agent to inspect the repo and install only what it needs:

```text
"Inspect https://github.com/jleechanorg/jleechan-skills and set up the skills most useful for my tech stack."
```

---

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

---

## 📋 Skills at a Glance

**30 Active Core commands** live flat in `.claude/commands/` (`/<name>`). The other **209 commands** live in `.claude/commands/extended-library/` (`/extended-library:<name>`) — still real and invocable, just namespaced. The 18 below are hand-picked from the empirical top-40 usage ranking across both tiers — most are Active Core, but `/4layer`, `/rg`, and `/parallel` were chosen from Extended Library because they're genuinely useful even though their raw usage counts didn't clear the automatic Active Core cutoff.

| Command | Full name / skill | One-line summary |
|---|---|---|
| [`/advice`](.claude/commands/advice.md) (alias `/smart-advisor`) | [`advice`](.claude/skills/advice/SKILL.md) | Token-efficient parallel second opinion — Opus subagent + `/research` + `/secondo` + `/web-advice`, synthesized into a verdict table. |
| [`/repro`](.claude/commands/repro.md) | [`repro-twin-clone-evidence`](.claude/skills/repro-twin-clone-evidence/SKILL.md) | Clones a real campaign, replays the exact bug action against a real server, verdicts REPRO/RELATED/NON-REPRO. **WorldArchitect.ai-specific** — not portable as-is. |
| [`/research`](.claude/commands/research.md) | [`research`](hermes/skills/research/SKILL.md) | Background agent investigates a question against primary sources only, cites everything, writes a Markdown note. |
| [`/ms`](.claude/commands/ms.md) (full `/extended-library:memory_search`) | [`memory-search`](.claude/skills/memory-search/SKILL.md) | Parallel, cached search across ten memory stores (roadmap, beads, Claude/Codex history, Hermes, wiki, Slack). |
| [`/er`](.claude/commands/er.md) (full `/extended-library:evidence_review`) | [`evidence-review`](.claude/skills/evidence-review/SKILL.md) | Judges an evidence bundle against evidence-standards; PASS/PARTIAL/FAIL/INCONCLUSIVE, gates `/green` on production PRs. |
| [`/f`](.claude/commands/f.md) (full `/extended-library:factory`) | [`dark-factory`](.claude/skills/dark-factory/SKILL.md) | Runs a goal through the real `dark-factory` binary against sealed holdout evaluation — replayable, agent never sees the holdout. |
| [`/es`](.claude/commands/es.md) | [`evidence-standards`](.claude/skills/evidence-standards/SKILL.md) | Evidence-strength policy: raw request/response beats mocked-at-boundary beats nothing; every claim needs a `[Layer N source]`. |
| [`/web-advice`](.claude/commands/web-advice.md) (alias `/webadvice`) | [`web-advice`](.claude/skills/web-advice/SKILL.md) | Real, authenticated multi-model browser review (ChatGPT, Gemini, Grok, Perplexity) — no API substitution allowed. |
| [`/browser`](.claude/commands/browser.md) | [`browser-control`](.claude/skills/browser-control/SKILL.md) | Live-browser task router — Aside first for authenticated sessions, Playwright for deterministic testing, browserclaw only for credential-free discovery. |
| [`/skillify`](.claude/commands/skillify.md) | [`skillify`](.claude/skills/skillify/SKILL.md) | Turns any script/runbook into a properly-tested, auditable `SKILL.md` package. |
| [`/harness`](.claude/commands/harness.md) | [`harness-engineering`](.claude/skills/harness-engineering/SKILL.md) | Diagnoses whether a failure is a harness-layer gap (instructions/skills/memory/tests/CI) and fixes at that durable layer. |
| [`/learn`](.claude/commands/learn.md) | [`learn`](.claude/skills/learn/SKILL.md) | Captures a durable lesson into every persistent store — memory, roadmap, beads, wiki — not just a chat summary. |
| [`/4layer`](.claude/commands/extended-library/4layer.md) (`/extended-library:4layer`) | [`4layer`](.claude/skills/4layer/SKILL.md) | Four-tier minimal-repro ladder (unit → e2e → MCP/HTTP → browser); the layer that reproduces the bug tells you where to fix it. |
| [`/rg`](.claude/commands/extended-library/rg.md) (`/extended-library:rg`, full `/redgreen`) | [`redgreen`](.claude/commands/extended-library/redgreen.md) | Strict RED→CODE→GREEN→CONSENSUS: a fresh real failing test must exist before any fix is written. |
| [`/parallel`](.claude/commands/extended-library/parallel.md) (`/extended-library:parallel`) | [`parallelize-to-ceiling`](.claude/skills/parallelize-to-ceiling/SKILL.md) | Independent work always runs at its real resource ceiling — never an arbitrary worker count, never serial. |
| [`/history`](.claude/commands/history.md) | [`conversation-history-sparse`](.claude/skills/conversation-history-sparse/SKILL.md) | Budget-capped sparse search across the 3 canonical history stores (Claude Code, Codex, Hermes); `--deep` escalates to a 6-source search. |
| [`/sidekick`](.claude/commands/sidekick.md) | [`sidekick`](.claude/skills/sidekick/SKILL.md) | Spawns a persistent, crash-recoverable, SendMessage-addressable teammate for long-running missions. |
| [`/swarm`](.claude/commands/swarm.md) | [`swarm`](.claude/skills/swarm/SKILL.md) | Multi-agent swarm orchestration with adversarial verification, always durably wrapped in a sidekick. |

---

## 📖 Detailed Skill Reference

### [`advice`](.claude/skills/advice/SKILL.md) — `/advice`, alias `/smart-advisor`

Gets a fast, cheap second opinion at a decision point without shipping the whole conversation to another model. Extracts a tight decision (3-5 sentences) plus a ≤150-line artifact, then fans out to up to four reviewers concurrently: an Opus subagent (with a cursor→agy→`claude -p` fallback chain), `/research`, `/secondo`, and `/web-advice`. Results synthesize into a comparison table; inside the `draft-first-pr` lifecycle it ends with a binary, SHA-bound verdict (`VERDICT: APPROVED at <SHA>`) so a later commit invalidates a stale approval. Degrades gracefully if a reviewer CLI is missing rather than failing outright.

```bash
/advice "Should we switch this cache from LRU to LFU eviction?"
```

### [`repro-twin-clone-evidence`](.claude/skills/repro-twin-clone-evidence/SKILL.md) — `/repro`

> **WorldArchitect.ai-specific — not generically portable.** Every mechanism here (Firestore "campaigns", `copy_campaign.py`/`download_campaign.py`, `WORLDAI_DEV_MODE`, `/game/<id>` URL parsing) is bespoke to that repo's D&D-style RPG platform. External adopters would need to fully replace the routing and data model before this does anything.

Given a campaign URL, clones the real production campaign into a test account, replays only the exact user action that triggers the bug against a real local server (real Firestore, real LLM — never mocked), and enforces a strict same-symptom rule: a repro only counts if the identical user-visible phenotype reappears. Closes with a mandatory REPRO / RELATED / NON-REPRO verdict and exported request/response/Firestore snapshots.

```bash
/repro "Checkout fails with 500 error when applying coupon code"
```

### [`research`](hermes/skills/research/SKILL.md) — `/research`

Spins up a background agent that investigates a question strictly against primary sources — official docs, source code, specs, first-party APIs — never secondary summaries. Every claim traces back to the source that owns it; findings land as a single cited Markdown file in whatever location the repo already uses for such notes. Runs async so the calling session keeps working.

```bash
/research "PostgreSQL 17 logical replication improvements and zero-downtime schema upgrades"
```

### [`memory-search`](.claude/skills/memory-search/SKILL.md) — `/ms`, full form `/extended-library:memory_search`

Fans a query out in parallel across ten distinct memory sources — roadmap, beads, Claude Code session memories, Hermes SQLite (FTS5), Hermes briefings, the Hermes memory index, OpenClaw memories, the local LLM wiki, raw conversation history, and Slack — instead of searching just one. Caches merged results by query hash with a 1-hour TTL so repeat lookups short-circuit.

```bash
/ms "hermes deploy failure last 7 days"
```

### [`evidence-review`](.claude/skills/evidence-review/SKILL.md) — `/er`, full form `/extended-library:evidence_review`

The enforcement layer on top of `evidence-standards`' "what to produce" layer. Runs mandatory bundle-integrity checks (checksum verification) before judging, then returns PASS / PARTIAL / FAIL / INCONCLUSIVE with file:line-level artifact citations. PASS requires every claim backed by a STRONG-quality artifact and is mandatory for `/green` on production-tier PRs; its verdict is parsed directly into `/green`'s merge-gate table.

```bash
/er docs/evidence/checkout-latency-fix/
```

### [`dark-factory`](.claude/skills/dark-factory/SKILL.md) — `/f`, full form `/extended-library:factory`

Runs a goal through the real external `dark-factory` binary and `.dot`-graph pipeline runner (StrongDM's Attractor pattern), recording every step in a SQLite CXDB rather than a conversation transcript, and grading against sealed holdout scenarios in a separate repo the agent is never allowed to read. Trades higher session cost for full replayability and a hard separation between the coding agent and the adversarial evaluator.

```bash
/f "Implement idempotent webhook signature validation with HMAC-SHA256"
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

General-purpose live-browser task router: Aside first for authenticated sessions/site settings/OAuth/existing tabs, `playwright-ui-testing` for deterministic app testing, `browserclaw` last and only for credential-free API discovery. Never bypasses login/MFA/consent and never copies cookies between profiles.

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

### [`redgreen`](.claude/commands/extended-library/redgreen.md) — `/rg` (`/extended-library:rg`, full form `/redgreen`)

Strict four-phase debugging: RED requires a fresh, real failing test reproducing the exact error in the current session (an old CI failure doesn't count); CODE requires a minimal targeted fix, no unrelated refactoring; GREEN confirms the test now passes and checks for regressions; CONSENSUS validates the whole flow was legitimately executed with evidence at each step. This skill has no separate `SKILL.md` — the full protocol lives directly in the command file.

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

The repository includes **30 Active Core commands** and **209 extended library commands** (239 total).

**Active Core** (flat `/<name>`) is a hard top-20-human ∪ top-20-agent usage cutoff (27 union, plus `/innov` forced in = 28), with `/sidekick` and `/swarm` manually promoted back from Extended Library per explicit selection = 30 — see [`archive/ARCHIVE-DECISION-2026-08-23.md`](archive/ARCHIVE-DECISION-2026-08-23.md) for the full methodology and its disclosed trade-offs.

**Extended Library** (`/extended-library:<name>`) holds the other 209 — not deleted, not dead, just namespaced. See [`archive/extended-library-README.md`](archive/extended-library-README.md).

A separate, older tier — [`archive/commands/`](archive/commands/) (51 files, from an earlier zero-usage pass) — uses a different criterion entirely and is untouched by the two-tier split above.

Browse [`.claude/skills/`](.claude/skills/) for the full skill library, [`.claude/commands/`](.claude/commands/) and [`.claude/commands/extended-library/`](.claude/commands/extended-library/) for all slash shortcuts. 61 hooks and 28 top-level scripts round out the library — 246 skill directories in total live under `.claude/skills/`.

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
- [archive/ARCHIVE-DECISION-2026-08-23.md](archive/ARCHIVE-DECISION-2026-08-23.md) — command ranking and two-tier architecture decision record.
- [archive/extended-library-README.md](archive/extended-library-README.md) — guide for extended library commands and promotion mechanics.
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — version history and release notes.

---

🚀 **Built for modern AI-assisted engineering — portable across Claude Code, Antigravity, Codex, and Cursor.**
