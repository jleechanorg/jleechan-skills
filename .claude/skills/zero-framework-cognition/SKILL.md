---
name: zero-framework-cognition
description: Use when designing or reviewing model-owned contracts, gameplay, tools, backend guards, semantic routing, or provider request flows. Resolve repository policy before applying portable ZFC guidance.
---

# Zero-Framework Cognition

Models decide; the server executes authorized operations. Invocation is review-only
unless edits are already user-authorized; preserve that implementation scope
without expanding it. Recommendations alone never authorize repairs.
This portable skill is REFERENCE guidance; the active repository's ZFC policy is PRIMARY.

## Resolve authority

On every invocation, including aliases and review lanes, first locate the active
repository root and the requested file/diff scope. Read root and in-scope
`AGENTS.md` / `CLAUDE.md` instructions. Follow their ZFC policy pointers before
applying this reference. Also check these conventional repository locations:
`.claude/skills/worldai-zfc/SKILL.md`, `.claude/skills/zfc/SKILL.md`,
`.claude/skills/zero-framework-cognition/SKILL.md`, and their `.codex/skills/`
equivalents. Resolve aliases/symlinks to the actual policy, read its required
companions, and record resolved paths and source revisions. Deduplicate canonical
paths and detect pointer cycles; do not crawl home directories or unrelated repos.
An installed alias or this portable file is not evidence of a repository policy.

Discovery reads identify the applicable policy and its required companions;
they do not yet apply substantive rules. If a local policy orders global-first
loading while this dispatcher orders repository-first, read each identified
source once, record the conflicting order, and report it unresolved rather than
recursing or claiming compatibility. Read repository policy and companions FIRST
for discovery; then consult the portable reference. Apply the repository's instruction hierarchy to conflicting
local policies; report unresolved conflicts. Repository precedence never overrides
higher-priority instructions, safety constraints, scope limits, or user holds.

If no active repo or local policy is found, or required policy/companions cannot
be read, state exactly what is absent or inaccessible. Use this reference only
for provisional analysis: do not invent repository exceptions or certify repository
compliance. Continue independent read-only work; block only dependent conclusions.

## Assign decision ownership

Model ownership also covers non-game semantic interpretation, intent routing,
classification, and domain decisions. Do not replace model judgment or existing
model-backed classifiers with keyword/substring/regex intent routing, phrase maps
or hand-tuned scores. Mechanical syntax parsing is not semantic interpretation.
Gameplay semantics belong to the LLM: interpretation, eligibility, progression,
combat outcomes, rankings, rewards, and context selection. Backend gameplay starts
at zero. Defaults, aliases, clamps, totals, normalization, and deterministic formulas
are not blanket exceptions. Recommend removing duplicate semantic checklists and requesting the minimal
model-owned contract; do not edit it unless explicitly authorized. Never replace
it silently with backend reasoning.

Each shared semantic/control field has one authoritative writer and canonical
home. Avoid redundant independently authored equivalents and silent reconciliation.
Any derivation remains subject to active repository policy, not blanket
deterministic permission.

Retain server-owned authentication, tenant isolation, credentials, request identity,
tool-result provenance, storage integrity and measured resource limits. Pure
parsing/serialization may preserve values; it must not reinterpret domain fields,
filter unknown model-owned domain fields, or manufacture gameplay decisions.
Preserve those fields through merge, save, load and the next authorized consumer.
Validate the trusted server envelope independently: model-authored auth, tenant
or control fields never grant authority or override server-owned values.
A model's choice to call
a tool does not justify a procedural game engine or decision loop inside that tool.
Trace the implementation behind the tool name, including its downstream calls.

For every proposed or retained backend exception, record the exact function and
purpose, active policy basis, concrete necessity, model-owned fields it must not
reinterpret, and proof. Genuine trust/storage controls need boundary evidence;
domain exceptions need the active policy's proof and must respect its absolute bans.
Registry membership, determinism and a passing fallback test are not sufficient.
Recommend removing backend decisions or moving contracts upstream; never add a second
registry, queue, ledger or compensator merely to make a review pass.

## Account for provider requests

For an application/provider flow under review, distinguish external requests,
responses, retries, model continuations, and provider-internal execution when
the evidence supports those counts. A wrapper call, cache hit, stream, logical
operation, or tool phase does not by itself establish how many provider requests
occurred. Trace the actual application-to-provider boundary and do not infer a
request-policy violation merely from a phase name or from separate user actions.

The active repository owns production request budgets and authorization. This
reference imposes no numeric limit and creates no approval phrase or permission
requirement. Its production request accounting does not govern local coding,
subagents, review, test execution, or orchestration workflows. Report local
inference separately from external provider requests. Disclose unknown completion
and possible duplicate processing after a timeout when relevant; do not claim
exactly-once execution without proof.

Provider-native execution may establish facts within a request only when the
selected API/model contract supports it. Count internal steps and cost separately
when known; do not claim zero internal reasoning or guaranteed low latency. Do not
finalize outcome-dependent narration or state before outcome facts exist: use
established inputs, verified native execution, or explicit deferral under the
active contract. Do not invent a backend gameplay validator or hidden
continuation to resolve this causality constraint.

## Inspect and report

Scope to the requested change and actual consumers. Reuse existing inventories and
owner evidence; re-read changed paths, not an entire audit by default. Trace prompt
and schema → provider attempts → tool implementation → parsing/merge → persistence
→ next consumer. Load [root-cause-first](../root-cause-first/SKILL.md) in review-only mode as a proof
standard after local policy/companions; do not launch its owner skills, experiments,
provider calls or edits merely because this review found a gap.

| Function / purpose | Field owner and protected boundary | Active policy basis / necessity | Proof and limitations | Verdict |
|---|---|---|---|---|

Use **Keep**, **Narrow**, **Move upstream**, or **Delete or prove** per finding;
report overall **PASS**, **WARN**, or **FAIL** with file/line evidence. Distinguish
source-level paths, captured execution and runtime counts. Source citations require
an exact revision and file:line; conditional branches do not prove they executed.
Report unresolved authority, missing captures, unknown counts and review coverage.
A passing fixture or string check is not proof of model compliance or production
behavior. No repository-compliance PASS when required policy is missing.

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

1. Reuse prior reads only while their inputs remain unchanged. Re-pin mutable
   files, branch heads and check results before verification or a status claim.
2. Reuse `/ms`, `/history`, `/e` results by ID for the same bounded question;
   refresh when the scope, source state or required time window changes.
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
token economy rules in effect (reuse unchanged inputs, re-pin mutable state, bounded
reads, parallel-where-independent). If arguments follow `/fable`, treat them
as the task to begin.
