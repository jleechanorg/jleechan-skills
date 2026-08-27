---
name: zero-framework-cognition
description: Use when designing or reviewing model-owned contracts, output schemas, backend guards, routing, semantic parsing, intent detection, or data fields where application code might duplicate judgment or ask a model for redundant facts.
---

# Zero-Framework Cognition

## Core Principle

Models decide; server executes.

Application code must not replace model judgment with keyword routing, regex
intent detection, heuristic classification, duplicate semantic checks, or
redundant field computations. The backend should execute tools, persist state,
and normalize deterministic output shape. Backend correction is a last resort:
first prove the prompt/schema/agent contract cannot prevent the bad payload on
the real path, then add only the narrowest correction-only invariant.

Reference: [Zero Framework Cognition: A Way to Build Resilient AI Applications](https://steve-yegge.medium.com/zero-framework-cognition-a-way-to-build-resilient-ai-applications-56b090ed3e69).

## Model Decision Engines

In this repository, "model" means:

- The LLMs used by the application for reasoning, narration, schema output,
  routing decisions that require context, and semantic judgment.
- The FastEmbed semantic intent classifier where the repository already uses it
  as a model-backed local classifier.

Do not replace either with new application-code heuristics. New regex,
substring checks, weighted keyword lists, or phrase maps for semantic judgment
are ZFC violations.

## Minimal Semantic Fields

Ask the model for the smallest set of fields that expresses the semantic
decision. Do not ask the model to emit multiple equivalent fields that can drift
apart.

Prefer:

```json
{
  "current_level": 4,
  "target_level": 5
}
```

Over:

```json
{
  "level_up": true,
  "level_up_available": true,
  "current_level": 4,
  "target_level": 5,
  "new_level": 5,
  "current_turn_exp": 6900,
  "total_exp_for_next_level": 6500,
  "additional_exp_to_next_level": 0
}
```

The first contract has one semantic fact: the model believes the target state
is level 5 from level 4. The second contract gives the model many chances to
contradict itself.

## Field Ownership

Every shared field needs one authoritative writer.

Use this split:

- **Model-owned semantic fields:** decisions, selected intent, target state,
  narrative meaning, choices, reasons.
- **Backend-owned deterministic derivatives:** aliases, display labels,
  normalized booleans, progress percentages, IDs, timestamps, persistence
  wrappers, UI payload formatting.
- **Server-owned control state:** locks, in-progress flags, tool execution
  results, commit status, request IDs, modal session state.

If two fields mean the same thing, delete one or derive it deterministically
outside the model contract.

## Correct Pattern

1. Give the model enough context to make the decision.
2. Request the minimal semantic output needed to express that decision.
3. Use schema constraints to make the minimal output explicit.
4. Capture raw request/response evidence when the model emits a bad payload.
5. Fix the prompt, schema, or selected-agent instruction first.
6. Derive display and compatibility aliases in deterministic backend code.
7. Persist tool results and state changes server-side.
8. Add backend guards only as a last-resort, narrow correction of contradictory
   explicit payloads after the prompt/schema path is proven insufficient.

## Banned Patterns

- Keyword or substring routing for user intent.
- New regex or regexp-based semantic classification, intent detection, routing,
  or policy judgment.
- Hardcoded phrase-to-action maps.
- Hand-tuned keyword scores.
- Explicit `if` / `else` chains that infer meaning from user text.
- Asking the model to emit redundant booleans, aliases, totals, and deltas for
  the same semantic decision.
- Backend recomputation of semantic decisions that should belong to the model.
- Backend guards added before capturing raw request/response and checking
  whether the model received the right prompt/schema.
- Treating a backend correction as the fix when the model is still being asked
  for redundant, ambiguous, or server-owned fields.

## Redundant Field Review Checklist

When adding or reviewing a model output field, ask:

- Is this field the minimal semantic decision, or a display derivative?
- Can it be derived exactly from another accepted field?
- Is another field already expressing the same fact?
- Who is the authoritative writer?
- What happens if this field contradicts its sibling fields?
- Can schema shape remove the contradiction surface?
- Has the raw model request/response proven the prompt/schema gap?

If the field is redundant, remove it from the model contract and derive it
deterministically after the model response is accepted.

## Allowed Deterministic Code

ZFC does not ban mechanical code. These are allowed:

- Syntax parsing, lexing, type checking, JSON serialization, URL encoding.
- Schema validation and structural validation.
- File existence checks, path resolution, process-state checks.
- Deterministic transformations with no judgment call.
- Tests with explicit expected outputs.

If the code asks "what does this mean?" or "what should we do?", use a model.
If the code asks "is this JSON valid?" or "does this file exist?", deterministic
code is appropriate.

## Backend Guard Rule

Backend protection is allowed only after the root cause has been checked at the
prompt/schema layer. The first fix attempt should be upstream: selected agent,
prompt wording, schema shape, or tool-result feedback. Backend guards are the
last resort, not the primary design.

Use `.claude/skills/root-cause-first/SKILL.md` in review-only mode for the
required proof standard. Stop after classification and findings; do not launch
its owner skills, experiments, or edits from a ZFC review.
For every backend guard, fallback, clamp, sanitizer, scrubber, suppression, or
server-injected choice, classify whether it is a server-owned invariant,
prompt/schema-insufficient with raw proof, a backend-transformation bug, an
unproven fallback, or a model-ownership violation candidate (ZFC violation
candidate).

Allowed guards:

- Suppress stale or contradictory explicit payloads.
- Normalize deterministic aliases for compatibility.
- Protect server-owned locks, session state, and tool execution state.
- Log narrow correction events for evidence and follow-up.

Disallowed guards:

- Compute the model's semantic decision from backend heuristics.
- Create a second source of truth for intent, eligibility, target state, or
  narrative meaning.
- Patch over prompt ambiguity without documenting why prompt/schema correction
  was insufficient.
- Correct a field that should have been removed from the model contract.

## Proven vs Not Proven Report

Every ZFC review that touches non-prompt logic must include a table with these
columns:

| Component | Non-prompt behavior | Proof state | Evidence | Verdict |
|---|---|---|---|---|

Use these verdicts:

- **Keep** for server-owned invariants and narrow correction-only guards with
  raw prompt/schema-insufficient proof.
- **Narrow** when a concrete leak is proven but the implemented guard is broader
  than the evidence.
- **Move upstream** when the behavior belongs in prompt, schema, or selected
  agent instructions.
- **Delete or prove** when tests show a fallback works but do not prove the
  model cannot handle the behavior.

Call out explicitly when the available evidence proves only that backend
fallback behavior works, not that model-owned behavior failed.

## Relationship To Domain Skills

Domain-specific ZFC skills can add file boundaries and contracts. For level-up
and rewards work, also use `.claude/skills/zfc-leveling-roadmap/SKILL.md`.

## Related session mode: /fable (model routing, not a ZFC rule)

`/fable` is a separate session-level contract for model/subagent routing and
token economy. It is unrelated to the ZFC judgment-ownership rules above, but
is anchored here because `/fable` reserves main-thread Fable reasoning for
"hardest reasoning" work — including ZFC / root-cause-first / leveling
reviews. Kept as a clearly separate section so it is not confused with core
ZFC principles.

**Activation contract:** main thread = Fable (latest Claude), reserved for
novel architecture, root-cause analysis, ZFC / RCF / leveling reviews,
cross-PR synthesis, multi-step planning — anything where the prompt is
"figure out what to do." Subagent defaults = Haiku-first, Sonnet for
implementation. Token economy (best outcome AND best $/token) is a
first-class constraint once `/fable` is invoked; the rules apply to every
subsequent turn in the session.

**What /fable does NOT do:**
- Does not change `~/.claude/settings.json` or any persistent config — it is
  a session-mode declaration, not a config edit.
- Does not auto-spawn subagents — subagent use follows the routing table
  below; the agent still decides when to spawn.
- Does not bypass safety or rigor — fail-closed, `/es`, `/green`, evidence
  standards are all still required; they are cheaper to follow than to skip.

**3-tier routing table (apply per-call):**

| Task shape | Subagent / tier | Rationale |
|---|---|---|
| Read-only Grep / Glob / Read / LS on a single file | **Haiku** | Pattern matching; 3x cheaper, comparable quality |
| Multi-file read-only synthesis (e.g., `/ms`, `/perp`, /e sweeps) | **Haiku + JSON schema** | Schema-forcing makes Haiku output reliable for aggregation |
| Single targeted Edit / Write (the obvious fix) | **Sonnet** | Implementation needs moderate judgment |
| Multi-file refactor, pair-coder, test writing | **Sonnet** | Pair-coder's full-context role |
| Subagent that must reason about novel bugs or design | **Fable (escalate)** | Only escalate when Haiku/Sonnet demonstrably fail |
| Adversarial review, root-cause-first, ZFC / leveling, architecture pivot, cross-PR synthesis, multi-step planning | **Fable (MAIN THREAD)** | "Figure out what to do" territory — this is where main-model reasoning pays for itself |

Rule of thumb: if the agent's prompt can be written as "do exactly X to file
Y" → Haiku or Sonnet. If the prompt is "figure out what to do" → Fable.

**Token-economy rules (apply to ALL tiers) once /fable is active:**

1. No re-reading files already read in this session — the harness tracks
   file state.
2. No re-running `/ms`, `/history`, `/e` sweeps that already ran — cache the
   result inline and reference by ID.
3. Use offset/limit on Read for large files. Default
   `$PROJECT_ROOT/world_logic.py` (421KB) → always Grep-first, never Read-whole.
4. Bead lookups via `br` CLI only — never read `.beads/issues.jsonl`
   directly.
5. Parallel independent work in a single message — sequential execution of
   independent work is a performance anti-pattern.
6. Prefer the `Grep` tool over `grep` in Bash — save Bash for OS-level
   operations.
7. When context grows, compact proactively — do not let the session thrash.

**Failure modes to avoid:**
- **Haiku hallucination on nuanced prompts** — if a Haiku agent returns
  output that doesn't match the expected schema or seems off, escalate to
  Sonnet. Do not accept low-quality output just to save tokens.
- **Sonnet pair-coder over-extension** — pair-coder/verifier roles benefit
  from the full Sonnet context window; do not use Haiku for those.
- **Fable overuse** — writing Fable-quality prompts for trivial edits burns
  tokens; step down to Sonnet/Haiku.
- **Subagent result-dumping** — a subagent's final message IS the return
  value; do not re-summarize it in the main thread unless the synthesis
  itself is the deliverable.

**When /fable is the wrong choice:** a single-file typo fix (just Edit it),
pure conversation/clarification (stay on the active model), or a session
that needs persistent main-model reasoning throughout only 20% of the time
(consider default routing instead).

**Cross-references:** `~/.claude/skills/root-cause-first/SKILL.md` (RCF is
Fable territory); hook `~/.claude/hooks/rtk.sh` (token-savings on shell
commands, always-on, not /fable-specific); global policy `~/.claude/CLAUDE.md`
(large file discipline, parallel subagents, bead lookup rules).

**Invocation response:** user types `/fable` (with or without arguments).
Reply confirms: `/fable active` — main thread = Fable; subagents =
Haiku-first, Sonnet for implementation; Fable reserved for novel
architecture, RCF, ZFC/leveling, cross-PR synthesis, multi-step planning;
token economy rules in effect (no re-reads, no re-sweeps, no file-whole
reads, parallel-where-independent). If arguments follow `/fable`, treat them
as the task to begin.
