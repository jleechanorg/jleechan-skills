# Archive decision — jleechan-skills top-20/top-20 (max-40) command archival

## ⚠️ SUPERSEDED 2026-08-24T02:15:00Z — scope reversal, read this section first

The original version of this document (committed `1640dcc2`, preserved verbatim below under "Superseded version") proposed KEEP=94 via dependency-closure expansion, with overage disclosed rather than forced down to 40. **The user explicitly overrode that recommendation within the same session**, issuing a new binding decision:

1. **Hard cutoff, no softening.** The promoted "Active Core" is the top-20-human ∪ top-20-agent union — no dependency-closure expansion. No "keep referenced-but-unpromoted commands in place" exception.
2. **Force-included:** `/innov` (real file, `.claude/commands/innov.md`, confirmed not in the 27-command union) is added explicitly as a 28th member. `/web-advice` was already covered (already in the union) — no action needed for it.
3. **Destination renamed.** Non-promoted commands move to `.claude/commands/extended-library/`, **not** `archive/commands/` — the existing `archive/commands/` (51 files from PR #358) is untouched and stays a separate, older-precedent directory. `extended-library/` reflects that these are still real, usable commands, just not curated "Active Core."

**This new decision is what downstream beads (`bd-cmdtop40-migration-test-dhi`, `bd-cmdtop40-archive-execute-710`, `bd-cmdtop40-docs-update-hkv`) must implement.** The 94-command closure computation (`archive/CLOSURE-REPORT-2026-08-23.md`) is retained as background context — it demonstrates that dependency references DO reach 94 commands, which is exactly why the "no closure expansion" choice below is a real trade-off, not a free one — but it is no longer the promotion criterion.

## New binding decision (authoritative)

**Final promoted "Active Core": 28 commands** = top-20-human ∪ top-20-agent (27, unchanged from the frozen snapshot) **+ 1 forced include (`/innov`)**.

Format per the user's own example: **"28: top-27 union by usage + 1 forced include."** (The union is naturally 27, not 40, because the top-20/top-20 lists overlap by 13 commands; the hard cutoff is a ceiling of ≤40, not a floor requiring exactly 40.)

**Final `extended-library/` set: 211 commands** (= `239 active − 28 promoted`).

### Promoted list (28, verbatim)

`advice`, `auto`, `browser`, `browserclaw`, `claw`, `copilot`, `end2end-testing`, `er`, `es`, `execute`, `f`, `fixpr`, `green`, `harness`, `history`, `innov`, `learn`, `levelup`, `linux`, `ms`, `nextsteps`, `repro`, `research`, `roadmap`, `skillify`, `smoke`, `web-advice`, `wiki-search`

Reconciliation: `sorted({top20_human} | {top20_agent} | {'innov'})`, computed against the frozen snapshot (`archive/usage_snapshot_frozen_2026-08-23.json`, `2026-08-24T010617Z`), verified 27 (union) + 1 (`innov`, confirmed absent from the union) = 28, no duplicates.

### extended-library/ list (211 = 239 − 28)

`4layer`, `CLAUDE`, `README`, `README_EXPORT_TEMPLATE`, `aar`, `accept-adapt-reject`, `adde2e`, `agento_report`, `agentor`, `antig`, `ao`, `arch`, `archreview`, `automation`, `automation-audit`, `auton`, `babysit`, `bashrc`, `beads`, `benchg`, `benchg-ts`, `bq`, `c`, `callpath`, `cereb`, `cerebras`, `checkpoint`, `clonefix`, `cmux-backup`, `cmux-goal`, `cmux-restore`, `cmux-steer`, `code-quality`, `code-standards`, `coderabbit`, `command-research`, `commentcheck`, `commentfetch`, `commentreply`, `con`, `cons`, `consensus`, `contexte`, `converge`, `copilot-expanded`, `coverage`, `cq`, `cr`, `cs`, `debug`, `debug-protocol`, `debugp`, `deploy`, `design`, `design-doc`, `disk_magician`, `diskm`, `e`, `efficiency`, `eloop`, `engplan`, `evidence-check`, `evidence-coverage`, `evidence_review`, `evolve_loop`, `exportcommands`, `f-pr`, `fable`, `factory`, `factory-evolve`, `factory-spec`, `fake`, `fake3`, `fakel`, `fe`, `feature-dev`, `fs`, `gen`, `gene`, `generatetest`, `ghfixtests`, `goal_harness`, `goalexec`, `goalexec_define`, `gst`, `gstatus`, `guidelines`, `h`, `handoff`, `header`, `headless`, `hermes`, `history_resume`, `idice`, `innovate`, `integrate`, `investigatedice`, `ironclad`, `keychain_kill`, `launchd`, `list`, `llm-testing`, `localexportcommands`, `localserver`, `loop_level_zfc`, `mac`, `memory`, `memory_search`, `meta`, `mobile`, `newb`, `newbranch`, `optimize`, `orch`, `orchc`, `orchconverge`, `orchestrate`, `pair`, `pair-examples`, `pairv2`, `parallel`, `parallel-vs-subagents`, `perp`, `plan`, `planexec`, `playwright`, `polish`, `pr`, `pr-media`, `pr-report`, `pres`, `presentation`, `principalengineer`, `principalproductmanager`, `processmsgs`, `puppeteer`, `push`, `pushl`, `pushlite`, `qwen`, `r`, `ralph`, `ralph_benchmark_parallel`, `ralph_iteration`, `ralph_pair_iteration`, `redgreen`, `replicate`, `repro_copy`, `requirements-list`, `requirements-start`, `requirements-status`, `review-enhanced`, `reviewd`, `reviewdeep`, `reviewe`, `reviewsuper`, `rg`, `roadmap_orch`, `roadmapo`, `runlocal`, `savetmp`, `scaffold`, `second_opinion`, `secondo`, `sidekick`, `sim`, `simulate`, `slack-audit`, `slide`, `smoke-local`, `social`, `status`, `statusline`, `suba`, `subagentvalidate`, `swarm`, `sync`, `tdd`, `team-claude`, `team-mini`, `test`, `teste`, `tester`, `testerc`, `testhttp`, `testhttpf`, `testing-gap-close`, `testing-layers`, `testllm`, `testmcp`, `testserver`, `testui`, `testuif`, `thermo`, `think`, `thinku`, `timeout`, `topcampaigns`, `up`, `usage`, `user-story`, `validate-e2e`, `wakebugbot`, `wiki-assess`, `wiki-bfs`, `wiki-evolve`, `wiki-ingest`, `worldai-usage-email`, `zfc`, `zfc-adjuster`, `zfclevel`

### Critical finding, verified empirically before any bulk move: `extended-library/` commands remain genuinely invocable, under a different name

Investigated live, this session, before touching any files (per explicit instruction not to skip this check):

- **Official docs** (`code.claude.com/docs/en/slash-commands`, fetched live): "Custom commands have been merged into skills. A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create `/deploy`." The documented nested-directory namespacing rule for skills: a skill in a nested directory below the working directory "appears under a directory-qualified name" — e.g. `apps/web/.claude/skills/deploy/SKILL.md` → `/apps/web:deploy`.
- **First-party empirical confirmation from this exact live session:** this repository already has real command `.md` files sitting inside `.claude/commands/` subdirectories — `.claude/commands/spec-kit/{clarify,implement-spec,plan-spec,spec,tasks-spec}.md` and `.claude/commands/backup-2026-06-27-team-claude-no-teamcreate/{team-claude,team-mini}.md`. This session's own live available-command listing shows them exposed as **`spec-kit:clarify`, `spec-kit:implement-spec`, `spec-kit:plan-spec`, `spec-kit:spec`, `spec-kit:tasks-spec`, `backup-2026-06-27-team-claude-no-teamcreate:team-claude`, `backup-2026-06-27-team-claude-no-teamcreate:team-mini`** — i.e. `<subdirectory>:<filename>`, not a bare `/<filename>` and not invisible. (Other existing subdirectories under `.claude/commands/` — `cerebras/`, `_copilot_modules/`, `tests/`, `_shared/` — hold only supporting scripts/partials, not command `.md` files, so they don't appear in the command listing; that's expected and consistent, not contrary evidence.)

**Conclusion: moving a command into `.claude/commands/extended-library/<name>.md` does NOT archive/deaden it — it remains invocable, but the invocation syntax changes from `/<name>` to `/extended-library:<name>`.** This is a real, user-visible behavior change and must be stated plainly (not glossed as "seamless") in the PR description and in `archive/extended-library-README.md` (owned by `bd-cmdtop40-docs-update-hkv`).

### Reconciliation check (scriptable)

```bash
python3 -c "
import json, glob, os
ranking = json.load(open('/tmp/ranking_frozen.json')) if os.path.exists('/tmp/ranking_frozen.json') else None
# Re-derive from the frozen snapshot directly if the /tmp cache is gone:
import subprocess
out = subprocess.run(['python3','scripts/rank_commands_repo_scoped.py','--input','archive/usage_snapshot_frozen_2026-08-23.json','--json'], capture_output=True, text=True, check=True).stdout
union = set(json.loads(out)['union'])
promoted = sorted(union | {'innov'})
active = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob('.claude/commands/*.md')}
extended = sorted(active - set(promoted))
assert len(promoted) == 28, len(promoted)
assert len(extended) == 211, len(extended)
print('OK: promoted =', len(promoted), '| extended-library =', len(extended))
"
```

### Summary for PR description

- Promoted "Active Core": **28 commands** (top-20/top-20 union of 27 + 1 forced include, `/innov`). Hard cutoff, no dependency-closure softening — a deliberate, disclosed trade-off: the 94-command closure report shows real dependency references exist beyond these 28, and some of those references will now point at a renamed/namespaced location (see `extended-library/` finding above) rather than staying flat.
- `extended-library/` set: **211 commands** (`239 − 28`), a rename/reframe of the archive-move destination — same move mechanics as PR #358's `archive/commands/` precedent, different directory, because these remain real, invocable (if renamed) commands, not dead ones.
- The existing `archive/commands/` (51 files, PR #358) is untouched, kept as its own separate, older-precedent tier.
- Invocation-syntax change (`/<name>` → `/extended-library:<name>`) is a genuine user-facing behavior change, verified via live documentation + this session's own empirical command listing — must be called out explicitly in the PR body and directory README, not framed as costless.
- This reverses the prior 94-command closure-preserving recommendation in the same session; both versions are preserved in this file for provenance (see below).

---

## Superseded version (as originally committed `1640dcc2`, retained verbatim for provenance — do NOT implement this version)

# Archive decision — jleechan-skills top-20/top-20 (max-40) command archival

**Bead:** `bd-cmdtop40-archive-decision-eo9` (decision bead, TDD-exempt)
**Derived from:** `archive/CLOSURE-REPORT-2026-08-23.json` (committed at `a5dbd263`), mechanically, via set operations against the live `.claude/commands/*.md` file list — not eyeballed.

Ran live: `keep` set-equals `closure` (94 == 94, verified). `archive_list` = `active - closure` = 145.

**Final keep set: 94 commands (54 over the literal max-40 ask).** **Final archive set: 145 commands** (`239 - 94`).

This deliberately did not force the count down to 40, per the overall contract's chosen approach: accept the overage, compute it precisely, disclose it plainly. **The user reviewed this and explicitly rejected it in favor of the hard-cutoff decision above.** Full original KEEP/ARCHIVE lists and reasoning are preserved in git history at commit `1640dcc2` if needed; the operative decision for all downstream beads is the new binding decision at the top of this file.
