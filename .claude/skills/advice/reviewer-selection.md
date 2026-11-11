## 2. Select independent reviewers

**Required quorum.** Use two independent full-scope source votes by default.
Use one only when pr-lifecycle positively selects a one-source-review route and
the reviewer confirms its eligibility; preserve that route rather than starting
extra advice seats. An explicitly requested advice invocation follows the same
qualified count. Archive-integrity review is not source approval.
Stricter user, repository, security and domain requirements remain binding. The
mandatory supplementary-review substitution still needs two eligible advice
votes and applicable evidence review. Record the route/count before dispatch;
neither one-vote readiness nor advice approval changes merge authority.

### Capability profile and tier selection

Use only capabilities actually available and authorized. Keep one machine-local profile of seat label, host, actual
account/identity key, model, transport and command or profile reference, permitted scope/isolation row, disclosure
authorization, availability and attempt receipt. Use existing ADVICE configuration and owning transport skills; this
is an orchestration record, not a new runner, configuration parser or prompt framework. Do not put personal accounts,
destinations, credentials or host paths in this repository. Preference for a different CLI/model does not make aliases
of one account independent.

| Tier | Available reviewers | Admission and counting |
|---|---|---|
| 1 — preferred | Available authorized CLI seats, including configured extra CLIs; authorized ChatGPT Dot accounts; the Instinct peer (`/instinct`) | Prefer different eligible CLI/model identities. CLI, Dot and Instinct are alternatives in the same tier; no brand or mixture is mandatory. Count at most one Dot vote and at most one Instinct vote, and never combine Dot with Instinct into a two-vote quorum. |
| 2 — fallback | Native static subagents; Hermes or Hermes-PC | Static subagents collectively count as at most one vote; Hermes instances collectively count as at most one distinct vote. Each counted vote must independently cover the entire scope. |
| 3 — last fallback | Existing authorized authenticated web chats through /web-advice | Use only after earlier-tier candidates cannot fill the remaining quorum. Preserve packet, upload, account-attestation and receipt rules. |

Start independent eligible reviews concurrently for the missing votes where transport, resource and runtime dispatch
limits permit. Retain valid votes and in-flight attempts with their existing deadlines. When a selected candidate
is unavailable, failed or timed out, use another eligible account or CLI; advance tiers when the current tier cannot
fill the remaining quorum. One unavailable provider does not exhaust the roster. Avoid duplicate requests and stop
new dispatch once quorum is met unless another authorized obligation requires it. Retain competent findings from
valid in-flight attempts. Every replacement is a new assignment under any per-PR dispatch budget.
The author, orchestrator and /research do not vote. One competent blocking objection can block.

Record availability separately from verdicts: AVAILABLE; UNAVAILABLE with missing capability, unsupported scope
or authorization reason; BUSY with an existing handle when known; QUOTA with a printed reset time when available;
or DUPLICATE with the shared identity key. Busy, missing, quota-blocked and duplicate seats do not reserve votes
or justify indefinite waits. Do not duplicate an active request. Keep the existing deadline and explicit-wait
rules for in-flight attempts. Delivery, acknowledgement and assignment are not approval.

### Candidate checks, fan-out and fallback

Before dispatch, enumerate the configured accounts and hosts in the capability profile, including alternate
CLIs and outside routes. Carry that roster, authorization sources, existing attempts and remaining dispatch
budget into orchestration delegates' task briefs, never cold reviewer prompts, which retain §1's exact templates.
Any exclusion needs its controlling instruction or observed constraint; a preferred CLI pair must not become
the delegate's only permitted reviewers. Preserve the active runtime's dispatch limits.

Check candidates with existing configuration, executable/auth status, verified account bindings and applicable
quota-cache receipts first. Independent read-only checks may run concurrently within host/profile limits.
Use a supported non-message health probe when it resolves an unknown needed for selection; record its scope
and time. A successful probe proves only what it checked, not review capacity or a vote. Do not send chat pings
or model prompts to every candidate as a health check, or make all probes finish before useful work starts.

**Account for every candidate in the existing receipt and user-facing report.** Separate health checks from actual
review launches/sends. Use disclosure-safe aliases; keep verified identities and private evidence machine-local.

| Candidate / host alias | Health evidence and time | Review attempted? | Outcome or reason not attempted | Receipt / next action |
|---|---|---|---|---|
| Claude / host A | executable and binding verified | Yes | approved | complete review receipt |
| Codex / host A | explicit quota refusal, reset recorded | Yes | quota | refusal receipt; use eligible fallback |
| Cursor / host A | not checked | No | quorum filled by other eligible votes | counted vote receipts |
| AGY / host B | confirmed unexpired account quota cache | No | quota cache applies | original refusal and reset |

These rows illustrate the format, not actual attempts. Include configured extra and outside candidates. Valid skip
reasons include quorum met, an existing request, duplicate identity, a verified quota window, missing capability,
profile/resource contention, exhausted dispatch budget or a scoped authorization restriction. Cite the evidence or
instruction; unknown availability stays UNKNOWN. A probe is not a review attempt; missing receipts make a claimed
attempt UNVERIFIED. Never report all routes exhausted while an eligible unattempted candidate can fill a missing
vote within the remaining authority and budget. Show the unresolved gate and next eligible action when none can.

### CLI capabilities

| Seat | Machine-local command override or default |
|---|---|
| Codex | `ADVICE_CODEX_CMD`, else `codex exec --yolo -m gpt-6.1-sol --config model_reasoning_effort=high` |
| Claude | `ADVICE_CLAUDE_CMD`, else `claude -p --model opus --dangerously-skip-permissions` |
| Claude alternate | `ADVICE_CLAUDE_ALT_CMD`, else the Claude argv with `--model <actual-model>` |
| Cursor | `cursor agent -p --force` |
| AGY | `agy --print="<review request>" --model gemini-3.8-flash-high --dangerously-skip-permissions --new-project` |
| Existing extra seats | `ADVICE_EXTRA_CLIS`, in configured order (unset by default); registration does not authorize a new reviewer |

These are capabilities, not required installed seats or a mandatory starting pair. Resolve eligible independent
identities from the machine-local profile before selecting them.

- **Configuration.** An `ADVICE_*` variable that is set but empty, unparseable, or names a missing or
  non-executable program makes that seat `UNAVAILABLE`. It never falls back to the default, because the default
  would run as another seat's identity. Machine-specific values (credential-store or profile directories, per-host
  wrapper paths, model aliases, account identifiers) live only in that machine's `~/.bashrc` as exported `ADVICE_*`
  values, never in this repository; this file may name a wrapper's shape (a `claudewa`-style wrapper that selects
  another credential store) but never a concrete path, digest or profile.
- **`ADVICE_EXTRA_CLIS`** registers more seats as `label=executable args`, separated by `|`, for example
  `ADVICE_EXTRA_CLIS='gemini-cli=gemini --approval-mode yolo -p|local-qwen=qwen -p'`. Parse it with shell-style
  quoting: `|` and the first `=` separate only outside quotes, then `shlex` the right-hand side into literal
  arguments, with no shell evaluation, globbing, command substitution or `~` expansion. Each `{prompt}`, as a whole
  token or inside one (`--print={prompt}`), is replaced by the request; with none, the request is appended as the
  last argument. An empty label or command, a duplicate label, an unparseable entry or a missing program makes that
  seat `UNAVAILABLE`.
- **No review-dispatch runner.** The orchestrator still launches each seat under §3 and owns its deadline and receipt.
  `quota_cache.py` only reads/writes the bounded quota hint; it never invokes a provider or starts/retries a review.
  A capability the orchestrator cannot bound end to end or cannot receipt is `UNAVAILABLE`; do not add a runner,
  wrapper, watchdog or timer.
- **Review readback discipline.** Bind each read to the existing attempt and
  inspect its complete attributable result once. An identical unchanged read is
  not a new verdict or progress: use the existing attempt deadline and
  completion signal, do independent work, and do not loop on the same capture.
  A completed, timed-out, or unavailable attempt is not polled again; route a
  missing vote through an eligible independent seat without duplicating work.

- **Quota walls fail fast.** A usage limit, quota exhaustion, exhausted 429 retry, rate limit, expired plan or similar
  account refusal makes the seat `UNAVAILABLE` with reason `quota` and the printed reset time. Do not wait, retry the
  same account or switch models around it; a separate account remains eligible.
- **Remember only confirmed quota windows.** Before launching each CLI seat, check the short-lived quota record:
  ```bash
  python3 "$HOME/.claude/skills/advice/scripts/quota_cache.py" check --provider <verified-provider> --identity-sha256 <verified-account-identity-sha256>
  ```
  `ELIGIBLE` permits the normal launch. `QUOTA_BLOCKED` means skip that exact account until its printed UTC reset
  time and continue the fallback route. Derive the identity digest from the account identity in an existing,
  verified machine-local seat binding; checking the cache must not trigger a new provider request. Do not use a
  guessed seat label, email, token, credential path or model name as identity. Pass only this SHA-256 digest, never
  the raw account identity. If no verified account binding is available, fail open and use the normal seat admission
  path; do not use the cache to skip a reviewer. The cache key combines the verified provider and account-identity
  digest. Cache only an explicit provider quota response and reset time:
  ```bash
  python3 "$HOME/.claude/skills/advice/scripts/quota_cache.py" record --provider <verified-provider> --identity-sha256 <verified-account-identity-sha256> --model <actual-model> --observed-at <quota-response-observation-time> --reset-at <provider-reported-ISO-8601-reset>
  ```
  The record includes its observation time and is stored with private permissions under `/tmp`; it contains only a
  keyed hash of the provider/account digest plus provider, model and UTC times, never credentials, raw identity or raw error text. No printed reset
  means no cache entry. Record the timestamp from when the provider response was observed, not when the record
  command happens to run. The cache orders quota and success events by that timestamp, so a delayed quota write
  cannot re-block a seat after a later successful probe. A fresh successful probe performed by the normal review
  path clears an earlier record before counting that seat as available:
  ```bash
  python3 "$HOME/.claude/skills/advice/scripts/quota_cache.py" clear --provider <verified-provider> --identity-sha256 <verified-account-identity-sha256> --observed-at <successful-probe-observation-time>
  ```
  Expired records clear themselves. Cache lock contention, invalid paths, and unavailable storage fail open and must
  not stall or deny an authorized attempt. The cache is a scheduling hint, not a second quota detector: record only a quota error actually observed
  from that exact seat; transport timeouts, unrelated tool errors and missing authentication are not quota signals.

### Outside-route authorization and transports

**Authorization is machine-local.** These routes send PR content off the machine, so this portable skill grants
nothing by itself. A route is authorized only when `ADVICE_OUTSIDE_ROUTES` lists it (comma-separated `dot,hermes,web`)
in that machine's `~/.bashrc`, or the current task explicitly authorizes it. That opt-in is the standing authorization
required by pr-lifecycle's optional-`/wa` rule and `/hermes`'s disclosure rule. Unlisted routes without task authorization are `UNAVAILABLE —
disclosure not authorized`, as are routes restricted by the user, task or repository, or content holding secrets. (The
repository owner opted in on 2026-11-04: "when all cli reviewers out of quota ... it should try to use /wa and ask
hermes hermes pc and the dots in dot coordination for a review".)

For Instinct, resolve authorization through [instinct](../instinct/SKILL.md); tier membership alone grants none.
Record each outside candidate's authorization source and scope in the orchestration receipt and delegation context,
never the cold reviewer prompt.

Each Dot account gets its own §3 attempt, capped at the Dot route's absolute deadline: one budget B after its
first send. No account is asked after that deadline; record a running one TIMED_OUT at it unless the user
explicitly required waiting under §3. Rotate on unavailable or failed attempts while a Dot vote is still needed.
After one eligible Dot vote, do not request another Dot to fill a second vote.

| Route | Transport and scope |
|---|---|
| Dot (tier 1) | Use the host-installed [dot](../dot/SKILL.md#account-rotation-on-limits-mandatory) interactive transport and configured rotation. The advice caller selects each `--account <name>` with `DOT_ROTATE_ON_LIMIT=0` and owns attempts/readback; `isolation: remote`, revision review only. The scheduled dot-coordinator sends reminders, not review requests. |
| Hermes or Hermes-PC (tier 2) | Use the host-installed /hermes Slack-only transport, coordinator ask and `isolation: remote`, revision review only. Resolve the configured eligible instance; another instance may replace a failed/unavailable one, not add a second Hermes vote. Use an available authorized machine-local `ADVICE_HERMES_CHANNEL` destination, otherwise the conversation /hermes resolves. |
| Web (tier 3) | Use host-installed [web-advice](../web-advice/SKILL.md); `isolation: packet` for revisions, `none` for documents. Record the authenticated provider/account from the session as `attested.account`. |

Missing transports are UNAVAILABLE with the exact blocker; never substitute a forbidden transport. A reply
counts only with full-scope COVERAGE and the exact SHA-bound VERDICT read back at its source, not an
acknowledgement, reaction or promise. Route availability does not override disclosure restrictions.

### Native static fallback

Static reviewers follow [static-review](../static-review/SKILL.md) for cold input, full coverage, identity, deadlines
and receipts. Spawn each native seat (for example Codex `spawn_agent`) with packet-only context, its preamble and
template, never a parent-history fork such as `fork_turns: "all"`. Admit them in tier 2 with an eligible Hermes
instance when needed; §2's aggregate caps still apply (static reviewers collectively at most one vote, Hermes
instances collectively at most one), and each counted verdict covers the whole scope. Eligible CLI pairs, CLI plus
static, or eligible outside combinations may supply the quorum.
There is no generic remote minimum or remote-only prohibition; preserve any separately explicit outside-review
obligation. Review votes never replace missing substantive evidence.

### Identity

- One account is one vote, whatever its label, wrapper, alias or retry; seats reaching the same account count once,
  including an outside reviewer whose coder used the account that hit quota.
- A CLI seat needs its actual model from reliable CLI/runtime metadata, or it is `UNAVAILABLE`. Outside routes record
  exposed model/account fields as `attested.` values; never invent a hidden runtime SKU. A verified Dot account is its
  own CLI/model identity under the one-Dot cap. Missing public fields do not invalidate a privately verified session;
  an actually unverified account is unavailable. Keep its frozen expected binding, positive identity probe and source-
  author independence proof. Codex models may be only `gpt-6-astra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-6.1-terra` or `gpt-6.1-sol`.
- Neither the author nor the orchestrator awards itself a vote, and no verdict counts twice: a Dot account whose verdict fills the
  pr-lifecycle `/dot` leg at this head is not also an `/advice` vote.
- Run every seat with full permissions and record its actual command, model, account and transport.

Use the [candidate report](#candidate-checks-fan-out-and-fallback) for unavailable and unattempted seats;
a skipped candidate is not necessarily unavailable. A failure on one host says nothing about another host:
account for each configured host separately. When eligible candidates cannot supply the required votes under
the counting caps, authority and dispatch budget, report `WITHHELD` with the remaining gap and earliest known reset.
