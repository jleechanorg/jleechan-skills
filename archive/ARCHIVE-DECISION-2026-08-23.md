# Archive decision — jleechan-skills top-20/top-20 (max-40) command archival

**Bead:** `bd-cmdtop40-archive-decision-eo9` (decision bead, TDD-exempt)
**Derived from:** `archive/CLOSURE-REPORT-2026-08-23.json` (committed at `a5dbd263`), mechanically, via set operations against the live `.claude/commands/*.md` file list — not eyeballed.
**Reconciliation script:**

```python
import json, glob, os
closure = set(json.load(open('archive/CLOSURE-REPORT-2026-08-23.json'))['closure'])
active = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob('.claude/commands/*.md')}
keep = sorted(active & closure)
archive_list = sorted(active - closure)
assert set(keep) == closure  # KEEP must set-equal the closure JSON exactly
```

Ran live: `keep` set-equals `closure` (94 == 94, verified). `archive_list` = `active - closure` = 145.

## The literal ask vs. the computed result

User's literal words: **"i only want top 20 user initiated and top 20 agent initiatled skillsc/ommands aka max 40, lets archive the rest in the repo."**

**Final keep set: 94 commands (54 over the literal max-40 ask).**
**Final archive set: 145 commands** (= `239 - 94`, reconciles exactly against the current active count).

This deliberately does **not** force the count down to 40. Forcing it down would require either (a) dropping real top-20/top-20 seed commands (forbidden — see criterion below, all 27 seeds are in KEEP), or (b) severing genuine dependency-closure references (rejected — this repeats the exact failure mode of the already-rejected `bd-11g.3` hand-picked-22 proposal, whose own closure note is the origin of this epic's "don't do a raw top-N cutoff" warning). Per the overall contract's chosen approach: **accept the overage, compute it precisely, disclose it plainly — do not silently force compliance with the literal number.**

**This is the flag for the user to see at merge time:** the safe, reference-preserving keep set is 94, not 40. If a stricter 40-command surface is still wanted after seeing this number, that requires either explicit acceptance of some broken cross-references, or a follow-up decision to redesign lower-tier commands to route through wrapper aliases instead of direct delegation — both out of scope for this plan-micro and not decided here.

## KEEP list (94, verbatim, = `archive/CLOSURE-REPORT-2026-08-23.json`'s `closure` key)

`advice`, `arch`, `archreview`, `auto`, `bq`, `browser`, `browserclaw`, `c`, `cereb`, `cerebras`, `claw`, `code-standards`, `commentcheck`, `commentfetch`, `commentreply`, `cons`, `consensus`, `converge`, `copilot`, `debug`, `deploy`, `e`, `end2end-testing`, `er`, `es`, `evidence_review`, `execute`, `exportcommands`, `f`, `f-pr`, `factory`, `factory-evolve`, `factory-spec`, `fake`, `fakel`, `fixpr`, `fs`, `goal_harness`, `goalexec`, `green`, `gstatus`, `guidelines`, `h`, `handoff`, `harness`, `header`, `history`, `integrate`, `learn`, `levelup`, `linux`, `localexportcommands`, `mac`, `memory`, `memory_search`, `ms`, `newbranch`, `nextsteps`, `orch`, `orchestrate`, `pair`, `parallel`, `perp`, `plan`, `planexec`, `pr`, `push`, `pushl`, `pushlite`, `qwen`, `r`, `repro`, `research`, `review-enhanced`, `reviewd`, `reviewdeep`, `reviewe`, `roadmap`, `second_opinion`, `secondo`, `skillify`, `smoke`, `status`, `test`, `testhttp`, `testhttpf`, `testserver`, `thermo`, `think`, `thinku`, `up`, `usage`, `web-advice`, `wiki-search`

**All 27 seed (top-20 human ∪ top-20 agent) commands are present in KEEP** — verified by set-containment: `{advice, green, repro, research, ms, claw, history, er, linux, f, es, web-advice, browser, skillify, browserclaw, auto, wiki-search, smoke, roadmap, levelup, execute, copilot, fixpr, nextsteps, harness, learn, end2end-testing}.issubset(keep)` → `True`.

## ARCHIVE list (145 = 239 active − 94 keep)

`4layer`, `CLAUDE`, `README`, `README_EXPORT_TEMPLATE`, `aar`, `accept-adapt-reject`, `adde2e`, `agento_report`, `agentor`, `antig`, `ao`, `automation`, `automation-audit`, `auton`, `babysit`, `bashrc`, `beads`, `benchg`, `benchg-ts`, `callpath`, `checkpoint`, `clonefix`, `cmux-backup`, `cmux-goal`, `cmux-restore`, `cmux-steer`, `code-quality`, `coderabbit`, `command-research`, `con`, `contexte`, `copilot-expanded`, `coverage`, `cq`, `cr`, `cs`, `debug-protocol`, `debugp`, `design`, `design-doc`, `disk_magician`, `diskm`, `efficiency`, `eloop`, `engplan`, `evidence-check`, `evidence-coverage`, `evolve_loop`, `fable`, `fake3`, `fe`, `feature-dev`, `gen`, `gene`, `generatetest`, `ghfixtests`, `goalexec_define`, `gst`, `headless`, `hermes`, `history_resume`, `idice`, `innov`, `innovate`, `investigatedice`, `ironclad`, `keychain_kill`, `launchd`, `list`, `llm-testing`, `localserver`, `loop_level_zfc`, `meta`, `mobile`, `newb`, `optimize`, `orchc`, `orchconverge`, `pair-examples`, `pairv2`, `parallel-vs-subagents`, `playwright`, `polish`, `pr-media`, `pr-report`, `pres`, `presentation`, `principalengineer`, `principalproductmanager`, `processmsgs`, `puppeteer`, `ralph`, `ralph_benchmark_parallel`, `ralph_iteration`, `ralph_pair_iteration`, `redgreen`, `replicate`, `repro_copy`, `requirements-list`, `requirements-start`, `requirements-status`, `reviewsuper`, `rg`, `roadmap_orch`, `roadmapo`, `runlocal`, `savetmp`, `scaffold`, `sidekick`, `sim`, `simulate`, `slack-audit`, `slide`, `smoke-local`, `social`, `statusline`, `suba`, `subagentvalidate`, `swarm`, `sync`, `tdd`, `team-claude`, `team-mini`, `teste`, `tester`, `testerc`, `testing-gap-close`, `testing-layers`, `testllm`, `testmcp`, `testui`, `testuif`, `timeout`, `topcampaigns`, `user-story`, `validate-e2e`, `wakebugbot`, `wiki-assess`, `wiki-bfs`, `wiki-evolve`, `wiki-ingest`, `worldai-usage-email`, `zfc`, `zfc-adjuster`, `zfclevel`

## Flagged disclosure: 3 non-command index/meta files are swept into ARCHIVE by the mechanical rule

`.claude/commands/README.md`, `.claude/commands/CLAUDE.md`, and `.claude/commands/README_EXPORT_TEMPLATE.md` are structurally `.md` files inside `.claude/commands/` (same frontmatter shape as real commands, so they were included in the "239 active" count and the closure algorithm's candidate universe), but they are the **directory's own index/documentation**, not invokable slash commands — `.claude/commands/CLAUDE.md`'s own frontmatter says `execution_mode: none, type: documentation`.

Applying the mechanical rule literally (criterion: KEEP must set-equal the closure JSON exactly, no manual additions) puts all three in ARCHIVE, since the closure algorithm found no runtime delegation reference *to* them (nothing "calls" a README). **This is disclosed here rather than silently patched** so the downstream beads know: `bd-cmdtop40-archive-execute-710` should move these three like any other archive-list entry (no special-casing, per its own anti-gaming rule against selective re-interpretation), and `bd-cmdtop40-docs-update-hkv` — which already separately owns `.claude/commands/README.md` in its file list — must **write a fresh `.claude/commands/README.md`** post-migration as the new 94-command directory index, rather than assuming the old one survived in place. This is exactly the kind of doc-sync work that bead's ironclad contract already calls for (criterion 1: "README.md's Active Core section states the real post-migration active count").

## Reconciliation check (must be scriptable, not eyeballed)

```bash
python3 -c "
import json, glob, os
decision_keep = set('''advice arch archreview auto bq browser browserclaw c cereb cerebras claw code-standards commentcheck commentfetch commentreply cons consensus converge copilot debug deploy e end2end-testing er es evidence_review execute exportcommands f f-pr factory factory-evolve factory-spec fake fakel fixpr fs goal_harness goalexec green gstatus guidelines h handoff harness header history integrate learn levelup linux localexportcommands mac memory memory_search ms newbranch nextsteps orch orchestrate pair parallel perp plan planexec pr push pushl pushlite qwen r repro research review-enhanced reviewd reviewdeep reviewe roadmap second_opinion secondo skillify smoke status test testhttp testhttpf testserver thermo think thinku up usage web-advice wiki-search'''.split())
closure = set(json.load(open('archive/CLOSURE-REPORT-2026-08-23.json'))['closure'])
assert decision_keep == closure, (decision_keep - closure, closure - decision_keep)
print('OK: decision KEEP set-equals closure JSON exactly,', len(decision_keep), 'entries')
"
```

## Summary for PR description

- Closure-adjusted final active set: **94 commands** (source: `archive/CLOSURE-REPORT-2026-08-23.md`, frozen-snapshot reproducible).
- Literal ask was max 40 — **exceeded by 54**, disclosed and accepted per this epic's own prior rejected-hand-picked-list lesson.
- All 27 measured top-20/top-20 seed commands preserved, zero real delegation references severed.
- 145 commands move to `archive/commands/` (`239 − 94`), including 3 non-command index/meta files (`README.md`, `CLAUDE.md`, `README_EXPORT_TEMPLATE.md`) that the docs-update bead must regenerate fresh post-migration.
