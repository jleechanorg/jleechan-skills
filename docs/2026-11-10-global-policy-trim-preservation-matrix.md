# Global policy trim — preservation matrix (2026-11-10)

Scope: `md_files/AGENTS.shared.md`, the canonical source of the shared global policy that installs to
`${CODEX_HOME:-$HOME/.codex}/AGENTS.md` (see `md_files/README.md`). This file lets a reviewer verify that the
trim dropped or weakened no rule, and what stayed inline for the one block that moved to a skill. Nothing is installed by this change.

## Baselines and bytes

Three texts existed before the trim, so each number names its baseline:

| Text | Bytes | What it is |
|---|---:|---|
| Source at `origin/main` | 71,216 | `md_files/AGENTS.shared.md` before this change |
| Installed copy on the author's host ("live") | 76,494 | Had drifted from the source in both directions |
| Lossless union of the two (not committed) | 79,254 | Every rule from either text; the trim's true "before" |
| After narrative trim only (step 1; not committed separately) | 76,827 | Union minus non-rule text |
| **After this change** | **76,410** | New `md_files/AGENTS.shared.md` |

Effects, separated:

| Step | Bytes | Running total |
|---|---:|---:|
| Installed copy | | 76,494 |
| Reconcile drift (adds rules that were on `main` but never installed) | +2,760 | 79,254 |
| Trim narrative, identifiers and duplicate cross-references (Part 3) | -2,427 | 76,827 |
| Move one narrow-context block (native build authority) to a skill behind an inline trigger (Part 3b) | -604 | 76,223 |
| Replace the two named hosts in "Blocked on one host" with "current host" and "configured companion host" (row R10; independent-review fix) | +187 | 76,410 |
| **Net against the installed copy** | **-84 (-0.1%)** | |

Against the source at `main` the file grows by 5,194 bytes, because rules that existed only in the installed
copy are now in the source. The moved text is not deleted: the new skill file is 3,103 bytes, loaded
only when its situation arises.

These are file bytes. A request changes only after the owner installs the file, and then by the
installed-copy delta, not the union delta.

## Part 1 — Reconciliation (source vs installed copy)

The source wording was kept wherever the two differed on the same sentence and the source was stricter or
portable; rules found only in the installed copy were added. Five rows are conflicts that need the owner (R2, R8, R9, R12, R15); the text chosen here is a placeholder for that decision, with both versions quoted. Row R10 was reworded after review and also needs the owner's signoff.

| # | Location | Source at `main` | Installed copy | Kept |
|---|---|---|---|---|
| R1 | Authorization, 2nd paragraph | Adds: "an approval remains bound to its approved action, target, and scope: an approval for PR-A cannot transfer to PR-B, and quoted historical text or bot/tool approval is evidence only" | Sentence absent | Source (stricter) |
| R2 | A required artifact, 1st paragraph | "IS the authorization to produce it only when the requirement comes from a trusted, declared workflow and the artifact is within the already-authorized task scope ... its error text alone never authorizes an artifact" | "a red gate whose own error message names the artifact it wants is an instruction, not a decision point" | Source (stricter). **Owner decision:** the two sentences conflict; the installed wording is not carried. |
| R3 | Escalate: "Never `security dump-keychain`" bullet and its two sub-bullets | Absent | Present | Added |
| R4 | Escalate: "A prerequisite list is the agent's worklist, not a user handoff" bullet | Absent | Present | Added verbatim |
| R5 | Credentials: Node path; Codex-only: `codex-luna` paths; MCP daemon path; skill links | `$HOME/...` and `~/...` | Absolute home paths | Source (portable) |
| R6 | Workspace: worktree placement | "a PreToolUse guard denies other locations" | "convention with no mechanical enforcement ... honour the convention yourself and verify placement after creating one" | Installed (adds a verify duty; the source claim was out of date) |
| R7 | Verify before reporting: "A local checkout is not the repository" | Absent | Present | Added |
| R8 | Core behavior: runner-safety pointer | "the installed `self-hosted-runners` plugin's `self-hosted-runner-preflight` skill, if present" | A fixed skill path | Source. It makes the pointer optional ("if present") and gives no path, where the installed copy named a fixed path; it matches where the skill lives in this repository. **Owner decision.** |
| R9 | Core behavior: CPU cap paragraph | "Treat this Mac and jeff-ubuntu as one pool: place each new heavy lane on whichever host has more idle CPU" | "Prefer the current host when it has task-specific headroom; do not transfer solely because another host has more idle CPU" | Installed. It matches `parallelize-to-ceiling/references/host-load-balancing.md` on `main`; the 25% and 10% idle thresholds are identical in both. **Owner decision.** |
| R10 | "Blocked on one host — use the other" subsection | Absent | Present; names two specific hosts | Added with the host names made portable: "the current host" and "a configured companion host", plus the two cases the named-host text did not need (an unreachable companion counts as blocked; with no companion configured, report that and treat the blocker normally). The rest is verbatim. An independent review blocked the verbatim text under the repository's fresh-machine invariant. This rewording was not approved by the owner: **owner signoff needed.** |
| R11 | "Unmandated enforcement gates" subsection | Absent | Present | Added |
| R12 | Disk diagnosis | Longer paragraph separating root-cause questions from quick capacity checks | Shorter paragraph | Source. It narrows the installed copy's unconditional "before any other measurement" to root-cause questions and routes quick capacity checks to `disk-audit`; merged on `main` on 2026-11-02. **Owner decision.** |
| R13 | "Native iOS proof for user-visible UI changes (canonical)" section | Present | Absent | Source, verbatim |
| R14 | Goals heading and `/f`, `/factory`, `/af`, `/auto-factory` lines | Absent | Present | Added. **Unsure, left in place:** the two skills these lines name are not in the active catalog on the author's host or in this repository, so the pointers do not resolve. |
| R15 | Skill sync wording (two sentences) | Host-neutral: "any authorized remote-peer comparison selected by the existing sync owner"; "For the cross-session skill source and scoped host-propagation contract, follow ..." | Names one host for the peer diff; "For every skill change in the shared catalog, follow ..." | Source wording for the peer diff (the repository forbids naming a personal host), which makes that diff depend on the sync owner's selection: **owner decision.** The installed trigger "For every skill change in the shared catalog, follow" is restored on the source's link. |
| R16 | "Agent workspaces live on the scratch volume, never in /tmp" section | Absent | Present | Added |

## Part 2 — Sections left byte-identical

Every section marked "identical" in this table is byte-for-byte the installed copy or the source at `main`,
checked mechanically per heading. Only the "changed" rows needed a rule-by-rule check (Parts 3 and 3b); a row is also
"changed" when it only carries a Part 1 reconciliation.

| Section | Live bytes | Source@main bytes | After bytes | Delta vs live | Status |
|---|---:|---:|---:|---:|---|
| (preamble) | 1 | 1 | 1 | +0 | identical to live |
| Shared Global Policy | 778 | 778 | 778 | +0 | identical to live |
| Reading a cmux terminal before deciding (full-buffer rule) | 2362 | 2362 | 2172 | -190 | changed |
| Editing shared policy or runtime adapters — semantic signoff + behavio | 691 | 691 | 691 | +0 | identical to live |
| Authorization, scope, and instruction authority | 1387 | 1678 | 1678 | +291 | identical to source |
| Standing authorization: documents to /web-advice (`/wa`) | 547 | 547 | 547 | +0 | identical to live |
| Do not offload work to the user | 376 | 376 | 376 | +0 | identical to live |
| Act, don't ask, on read-only and reversible work | 1322 | 1322 | 1322 | +0 | identical to live |
| A required artifact is pre-authorized — produce it, don't ask | 1563 | 1743 | 1743 | +180 | identical to source |
| Escalate only what only the user can do | 4630 | 2783 | 4497 | -133 | changed |
| Visible progress — never look frozen | 517 | 517 | 517 | +0 | identical to live |
| Credentials and environment | 861 | 851 | 851 | -10 | identical to source |
| Workspace and method fidelity | 2895 | 2391 | 2508 | -387 | changed |
| Reports and Markdown deliverables go in the roadmap repo, not `/tmp` | 1880 | 1866 | 1529 | -351 | changed |
| Full-permission transport fidelity | 729 | 729 | 729 | +0 | identical to live |
| Destructive action safety | 1948 | 1948 | 1948 | +0 | identical to live |
| Destructive-path guard (incident jleechan-lwn, 2026-10-18) | 1700 | 1686 | 1452 | -248 | changed |
| What the guard (`cc-safety-net`, level `standard`) blocks — work with  | 1798 | 1798 | 1380 | -418 | changed |
| Verify before reporting | 3359 | 2532 | 3199 | -160 | changed |
| Core behavior | 18 | 18 | 18 | +0 | identical to live |
| Model-owned domain state and semantic decisions | 3429 | 3208 | 3466 | +37 | changed |
| Blocked on one host — use the other (user directive 2026-11-03) | 993 | — | 1180 | +187 | changed (row R10) |
| Upstream and root-cause engineering | 524 | 524 | 524 | +0 | identical to live |
| Unmandated enforcement gates | 1563 | — | 1382 | -181 | changed |
| Ponytail — lazy senior dev mode | 403 | 403 | 403 | +0 | identical to live |
| Local tool and UI pointers | 1489 | 1489 | 1489 | +0 | identical to live |
| Slack media delivery — native attachments required | 575 | 575 | 575 | +0 | identical to live |
| SSO test sessions | 628 | 628 | 628 | +0 | identical to live |
| Dot (ChatGPT assistant) logins — do not clobber | 546 | 546 | 546 | +0 | identical to live |
| Disk diagnosis | 300 | 705 | 705 | +405 | identical to source |
| Beads and memory | 906 | 906 | 906 | +0 | identical to live |
| Commitment integrity | 1032 | 1032 | 1032 | +0 | identical to live |
| Autonomy time-box | 1048 | 1048 | 1048 | +0 | identical to live |
| Proportionality, evidence, and autonomous execution | 1512 | 1512 | 1512 | +0 | identical to live |
| Push safety | 1439 | 1439 | 1439 | +0 | identical to live |
| PR descriptions (canonical owner) | 2440 | 2440 | 2440 | +0 | identical to live |
| Git, PR, and API pointers | 2646 | 2632 | 2632 | -14 | identical to source |
| Slow/backlogged CI runners — run locally + post proof, don't just wait | 925 | 925 | 925 | +0 | identical to live |
| Merge safety — size-tiered approval | 1790 | 1776 | 1776 | -14 | identical to source |
| Native iOS proof for user-visible UI changes (canonical) | — | 1901 | 1901 |  | identical to source |
| Configuration and service safety | 1059 | 1045 | 1045 | -14 | identical to source |
| Goals, slash commands, /af, and directory safety | 741 | 361 | 727 | -14 | changed |
| Shared provider & review-gate policy (canonical) | 227 | 227 | 142 | -85 | changed |
| Review gates - CodeRabbit/Bugbot are optional | 667 | 667 | 667 | +0 | identical to live |
| PR-review priority and merge blocking | 665 | 665 | 665 | +0 | identical to live |
| WorldAI API fallback when AGY quota is exhausted | 962 | 962 | 962 | +0 | identical to live |
| Review, output, and scope discipline | 2516 | 2516 | 2516 | +0 | identical to live |
| Autonomous follow-through | 2112 | 2112 | 2112 | +0 | identical to live |
| Inherited failures — fix them in an independent PR, don't ask | 687 | 687 | 687 | +0 | identical to live |
| Branch and task ownership — agents settle it, the human gets an FYI | 650 | 650 | 650 | +0 | identical to live |
| Skill, command, and shared execution contracts | 2251 | 2325 | 2369 | +118 | changed |
| Codex-only runtime configuration and delegation | 3417 | 3397 | 3329 | -88 | changed |
| Model routing and Gemini invariant | 674 | 674 | 674 | +0 | identical to live |
| Codex reply footer | 683 | 683 | 683 | +0 | identical to live |
| Native build authority — canary rules (2026-10-19) | 2460 | 2460 | 1856 | -604 | changed |
| Context-full behavior — auto-compact and keep going (user directive 20 | 1481 | 1480 | 1481 | +0 | identical to live |
| Agent workspaces live on the scratch volume, never in /tmp (2026-10-29 | 1693 | — | 1401 | -292 | changed |
| **Total file** | 76494 | 71216 | 76410 | -84 | |

## Part 3 — Rule-by-rule check of the trimmed sections

"Original" quotes the union text. "After" quotes the new file. In this part nothing moved to a skill: every
rule, threshold, command, exception and list below is still inline. Part 3b covers the one moved block.

### Reading a cmux terminal before deciding (full-buffer rule)

Reflowed from hard-wrapped lines; the words of every rule are unchanged.

| # | Original rule | After |
|---|---|---|
| 1 | "read the surface's FULL available history - never a short tail" | Verbatim |
| 2 | "Read at least ~10k words ... `cmux capture-pane --workspace <ws> --surface <sf> --scrollback --lines 1500` ... If the buffer is shorter, read all of it." | Verbatim |
| 3 | "headless only: never a command that selects or focuses a workspace" | Verbatim |
| 4 | "Read in layers ... A decision made from either layer alone is incomplete." | Verbatim |
| 5 | "A `grep` over one capture is a **pre-filter, never a state verdict**." | Verbatim |
| 6 | "capture the surface twice, 20-30 s apart, into unique paths (`mktemp`, never a fixed name under `/parallel`). **Screen changed => `WORKING`, stop.**" | Verbatim |
| 7 | "**Identical screens are not proof of idleness.** ... confirming the *absence* of: post-footer tool calls or assistant text, live timer growth ..., CPU in `top_flat.tsv`, and for `pi` panes growth of the trailing `~/.pi/agent/sessions/*/*.jsonl` matched by cwd." | Verbatim |
| 8 | "These strings are **never** state on their own: ..." (five strings) | Verbatim |
| 9 | "Never classify a surface as idle/working/stalled, and never nudge it, from a capture shorter than the full buffer. ... mark the surface UNVERIFIED rather than guessing." | Verbatim |
| 10 | "Owner: this section. Skills that steer cmux surfaces carry a one-line pointer here and must not restate the rule." | Verbatim |

Removed, not a rule: "(2026-10-12 lesson: operator questions and dialog menus were only visible 20+ lines deep)" and "measured 2026-10-18, capture-pane/read-screen/send/send-key do not;".

### Escalate only what only the user can do

| # | Original rule | After |
|---|---|---|
| 11 | "**Never `security dump-keychain`.** ... reading the ONE named item you need, never dumping the store." | Verbatim |
| 12 | "It is a credential-exfiltration shape regardless of intent, and it hangs on a headless host because `-d` needs a GUI password" | Verbatim |
| 13 | "**Use instead:** `security find-generic-password -s <exact-service> -a <account> -w` ..." | Verbatim |
| 14 | "A CI credential that fails auth ... is fixed by re-issuing or re-pointing that secret through its owner ... Report the failing secret and the exact owner to re-provision it." | Verbatim |

Removed, not a rule: the four example credential kinds and the dated incident in parentheses.

### Workspace and method fidelity

| # | Original rule | After |
|---|---|---|
| 15 | "Create git worktrees only under `~/.worktrees/<repo>/<name>` (use `diskm worktree-new <repo-path> <branch>`)." | Verbatim |
| 16 | "This is a **convention with no mechanical enforcement** ... `~/.claude/hooks/protect-worktrees.sh` blocks only removal/prune, not creation. `git worktree add` at any path therefore succeeds, so honour the convention yourself and verify placement after creating one." | "This is a **convention with no mechanical enforcement**: no guard denies other locations (`~/.claude/hooks/protect-worktrees.sh` blocks only removal/prune, not creation), so `git worktree add` at any path succeeds. Honour the convention yourself and verify placement after creating one." |
| 17 | "For local file paths in user-facing replies, follow the local artifact-path display rule in Reports and Markdown deliverables." (a cross-reference) | DEDUPED. The rule is unchanged in the Reports section: "**Local file paths in user-facing replies:** Print each full expanded absolute path as plain text on its own line. ..." |

Removed, not a rule: the retirement date of the old guard and the names of its leftover files.

### Reports and Markdown deliverables go in the roadmap repo, not `/tmp`

| # | Original rule | After |
|---|---|---|
| 18 | "Write every durable agent-authored deliverable ... under `~/roadmap/` ... as `<topic>-YYYY-MM-DD.md`." | Verbatim |
| 19 | "`/tmp` and scratch volumes are scratch, not storage. A host restart wipes `/tmp`" | "`/tmp` and scratch volumes are scratch, not storage: a host restart wipes `/tmp`." |
| 20 | "Anything a human will read, or a later session may need, must be written to `~/roadmap` **before** you report it." | Verbatim |

Removed, not a rule: "For a user-facing reply that names the artifact, follow the local file-path presentation rule in this section." (the rule is the next paragraph of the same section) and the dated restart incident.

### Destructive-path guard

| # | Original rule | After |
|---|---|---|
| 22 | "Scratch space is allocated per [scratch-space skill] via `diskm scratch-new <repo-path> <purpose> --kind build\|evidence` for repo dirs and `.../scratch-dir.sh [subpath]` for ad-hoc temp files" | DEDUPED: "Allocate scratch as § Workspace and method fidelity requires". That section holds the same sentence with both commands, unchanged. |
| 23 | "(or `mktemp -d` inside scratch for tiny non-git file scratch only" | "(`mktemp -d` inside scratch for tiny non-git file scratch only)" |
| 24 | "never hardcoding OS mountpoints or a fixed `/tmp/<name>` you then delete" | Verbatim |
| 25 | "never `git worktree add $(mktemp -d)` — all git worktrees must live under `~/.worktrees/<repo>/<name>` via `diskm worktree-new`, except roots explicitly listed in `~/.config/guards/worktree-allowlist` (e.g. `<project>/worktree_<name>` for this frontend repo)" | Same words, as its own sentence beginning "Never `git worktree add $(mktemp -d)`:" |

### What the guard blocks

| # | Original rule | After |
|---|---|---|
| 26 | "**`rm -r` on a variable target is denied** ...: `rm -rf "$D"` -> blocked even when `$D` is set. Use a literal path or narrow to a literal subdirectory." | Verbatim without the rule identifier |
| 27 | "**`rsync --delete` is only allowed into an explicit path inside the current directory, or under `/tmp`, `/var/tmp`, `$TMPDIR`**" | Verbatim without the rule identifier and version |
| 28 | "Denied: a variable destination of any form (including the "safe" `${D:?}/x`), a destination elsewhere in `$HOME` ..., and root/`~`/`$HOME`/`.git` destinations (those last ones cannot be disabled by policy)." | Verbatim |
| 29 | "Remote `user@host:/path` and non-`--delete` rsync stay allowed. To mirror outside cwd, drop `--delete` and remove the stale files explicitly, or run from the destination's parent." | Verbatim |
| 30 | "**`prog - <<'PY'` heredocs are denied** ... Sanctioned idiom: `STEP_PY=...`, `cat > "$STEP_PY" <<'PY' ... PY`, then `python3 "$STEP_PY"`. Supported consumers: `cat`, `tee`, `git apply`, `git commit`, `gh pr create`, `gh issue create`." | Verbatim without the rule identifier |
| 31 | "Our own `rsync --delete` analyzer and `~/.local/bin/guards/rsync` (`--max-delete=2000`, override `GUARD_MAX_DELETE`) stay installed as independent layers — they run before the package hook and cover forms the package skips" | Verbatim |

Removed, not a rule: package version and licence in the heading, the list of runtimes the guard is installed for, the strict-level measurement, three rule identifiers, "since 2.6.15", and the quoted rule text (a restatement of row 27).

### Verify before reporting

| # | Original rule | After |
|---|---|---|
| 32 | "Before reporting "this does not exist" ... run `git fetch` and re-read the same search against `origin/main` ... and state the commit you searched." | Verbatim |
| 33 | "Absence claims are verdicts: bind them to a fetched commit, or label them "unverified against `origin`"." | Verbatim |

Removed, not a rule: the dated incident clause after "a repository that no longer exists".

### Unmandated enforcement gates

| # | Original rule | After |
|---|---|---|
| 34 | "A guard stack larger than the change it guards is itself the defect" | Verbatim; the measurement in parentheses is removed |

### Shared provider & review-gate policy

| # | Original rule | After |
|---|---|---|
| 35 | "Edit shared rules here once." | DEDUPED. Unchanged in the file's first paragraph: "Edit shared rules here once." |
| 36 | "This is the canonical shared copy for Codex and Claude Code (Claude imports this file via `@~/.codex/AGENTS.md`; Gemini references it by path)." | "Canonical shared copy, as stated at the top of this file; Gemini references it by path." The first paragraph keeps: "This is the canonical shared policy for Codex and Claude Code ... Claude loads it through `@~/.codex/AGENTS.md`". |

### Skill, command, and shared execution contracts

| # | Original rule | After |
|---|---|---|
| 35a | Union text (source wording): "For the cross-session skill source and scoped host-propagation contract, follow [`/up`'s reusable skill source and scoped host sync section]"; installed wording: "For every skill change in the shared catalog, follow [...]" | "For every skill change in the shared catalog, follow the cross-session skill source and scoped host-propagation contract in [`/up`'s reusable skill source and scoped host sync section]". The installed trigger and the source link are both kept (see R15). |

### Codex-only runtime configuration and delegation

| # | Original rule | After |
|---|---|---|
| 37 | "compute available RAM from `vm_stat` as (free+inactive+purgeable+speculative)×page_size and attribute the top RSS consumer with `ps -Ao rss,comm -r \| head`" | Verbatim |
| 38 | "Never gate on `vm.swapusage` used/total ratio (macOS sizes the swapfile dynamically ...)" | Verbatim; the example figures are removed |
| 39 | Pressure levels and thresholds (">8GB and pressure ≤2", "4-8GB or pressure=3", "<4GB or pressure=4"); "always background + timeout"; skill is source of truth | Verbatim |

Removed, not a rule: "(corrected 2026-09-02)".

### Agent workspaces live on the scratch volume, never in /tmp

| # | Original rule | After |
|---|---|---|
| 40 | "Durable documents belong in `~/roadmap`, never in `/tmp`." | Verbatim |
| 41 | "Resolve the scratch root for anything workspace-shaped ...: `SCRATCH="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh <purpose>)"`" | Verbatim; the command is inline code instead of a fenced block |
| 42 | "`/tmp` stays legitimate, and is exempt from the guard, for: logs (`.log`), sockets, pid/lock/marker files, single temp files, `.json`/`.jsonl` state, `.sh`/`.py` probes, pip unpack directories, and X11/ssh-agent/chromium profile directories." | Verbatim |
| 43 | "Global `TMPDIR` is never remapped and `/tmp` is never replaced." | Verbatim |
| 44 | "a blocking `PreToolUse` guard ... is live for Claude Code on macOS and Linux — it refuses workspace creation under `/tmp` and names this rule. Human override for one call: `SCRATCH_GUARD_ALLOW_TMP=1`." | "A blocking `PreToolUse` scratch-routing guard is live for Claude Code on macOS and Linux: it refuses workspace creation under `/tmp` and names this rule. Human override for one call: `SCRATCH_GUARD_ALLOW_TMP=1`." A pointer to the scratch-space skill's guard section is added. |
| 45 | "Do not "fix" disk pressure by moving workspaces into the scratch volume and calling it reclaimed: the Linux scratch volume is a loop-mounted image inside the same filesystem, so relocating data there returns no host free space ... Reclamation means deleting, not relocating." | Verbatim |

Removed, not a rule: fleet counts and "each time needing destructive manual reclamation", the hook's file name and exit code, the tracker identifiers for unfinished adapters, and the note on how blocks are freed inside a loop image.

## Part 3b — One block moved to a skill behind an inline trigger

Owner decision relayed for this change: move only native build authority. The section heading is unchanged.
The new skill `.claude/skills/native-build-authority/SKILL.md` holds the original section text verbatim
(generated from the union text, not retyped). Inline stay the situation, a MUST-read of the skill before
acting, and the rules quoted in the "Inline after" column. Rows marked "Skill only" are reachable only by
reading the skill; this matrix does not claim that every sentence of the original stays inline.

| # | Original rule | Inline after | In skill |
|---|---|---|---|
| 46 | "A *local* native build (xcodebuild archive/build, simulator install, TestFlight validation) is **permitted whenever the user or the owning release operator asks for it**" | Verbatim; the build kinds are listed in the trigger sentence, which adds simulator launch and Expo/EAS | Verbatim |
| 47 | "Resource pressure, runner availability, or a missing remote runner is a **scheduling** fact, never a prohibition." | Verbatim | Verbatim |
| 48 | "A local build is the default reading of "use local build and CI"." | Skill only | Verbatim |
| 49 | "`localbuildallowedwhenrequested` — "local build" instructions authorize local builds; do not convert them into a remote-only requirement. Do not refuse a local build by citing a policy that does not name its owner, reason and expiry." | Skill only (row 46 inline already permits a requested local build) | Verbatim |
| 50 | "**iOS Simulator only.** One native operator per simulator build/device. Before a second lane builds, installs or launches on the same simulator UDID or the same app bundle, obtain the chosen UDID and the operator lock; never erase, reinstall or relaunch a device another lane is proving on." | Verbatim | Verbatim |
| 51 | "the operator lock covers the simulator UDID and app bundle and nothing else." | Verbatim | Verbatim |
| 52 | "It does not extend to accounts, credentials, environments, campaigns, quotas, or any other shared resource." | Skill only as a list; inline: "and nothing else" | Verbatim |
| 53 | "A shared test account is **never reserved**: a ledger, queue, admission, handback, or "reserved/held/locked" note is scheduling state, not a permission boundary." | "A shared test account is **never reserved**"; the list of note kinds is skill only | Verbatim |
| 54 | "Exclusivity on any shared resource is only ever *observed* — a verified live competing operator you can name — never *declared* by a coordinator." | Verbatim; the trigger also fires "before treating any shared resource as reserved" | Verbatim |
| 55 | "a load/memory/CPU/thermal gate defers a specific heavy run and MUST name its recheck condition (threshold plus how/when it is re-measured). It never becomes a standing ban." | Verbatim | Verbatim |
| 56 | "An explicit instruction to build changes who decides and requires an explicit recheck decision; it does not waive genuine thermal, power or resource-safety protection." | Verbatim | Verbatim |
| 57 | "Expo/EAS **hosted** builds stay unauthorized unless the user explicitly authorizes them." | Verbatim | Verbatim |
| 58 | "Unused EAS credit, an existing profile, or a configured token is not authorization. This is the only standing native-build prohibition, and it is about *hosted* builds only, not local ones." | Skill only | Verbatim |
| 59 | "If a persisted note, roadmap entry, summary or coordination message states a blanket "no local build" rule, treat it as stale: mark it superseded with a date and cite this section. Never delete the historical record." | "A persisted note, roadmap entry, summary or coordination message stating a blanket "no local build" rule is stale: mark it superseded with a date and cite this section. Never delete the historical record." | Verbatim |

The four canary identifiers (`localbuildallowedwhenrequested`, `no competingnativeoperator`,
`loadgate≠blanketban`, `Expoheldunlessauthorized`) are skill only; "Verbatim" in the inline column refers to
the rule text after each identifier.

Install order: `native-build-authority` is a new skill and is in no active catalog until the owner syncs
it. It must be installed before or together with the trimmed policy file; if the policy is installed
first, the MUST-read pointer does not resolve and rows 48, 49, 52, 53 (list) and 58 are unavailable on
that host.

## Part 4 — Examined and left in place

| Block | Bytes | Why it stays |
|---|---:|---|
| Reading a cmux terminal (procedure bullets) | ~1,700 | Everyday protection against acting on a misread surface. Every bullet is a threshold, command or prohibition, so an inline trigger that kept them all would save nothing; a first draft that summarised them failed review. |
| What the guard blocks (operating notes) | ~1,400 | Same: the denied shapes, their exceptions and the sanctioned idioms are needed at the moment a destructive command is written. A first draft that moved them failed review. |
| PR descriptions (canonical owner) | 2,440 | A draft that moved it behind an inline trigger failed review; restored inline |
| Native iOS proof for user-visible UI changes (canonical) | 1,901 | Same |
| WorldAI API fallback | 962 | Same |
| Model-owned domain state (first paragraph) | ~700 | Normative; overlap with the zero-framework-cognition skill not proven equivalent |
| Slack media delivery (runner flags) | ~120 | A first draft that left only the script path failed review: the command was no longer runnable as written |
| Dot logins / Dot profile directories | 546 + ~400 | Two different rules (launch vs configuration), not duplicates |
| `/f`, `/factory`, `/af` lines | ~350 | Pointers do not resolve (R14); removing them would drop a rule |
| Workspace paragraph vs Agent-workspaces section | — | They disagree on `/tmp` for evidence ("Scratch or `/tmp`" vs "never in /tmp" for workspace-shaped output). Not merged; the owner should pick one wording. |

## Independent review

One independent reviewer (adversarial, read-only) checked three candidates.

1. First draft (cmux procedure and command-guard notes moved to skills, Slack runner line shortened): **FAIL**, 17 findings. Rules became conditional on a skill being loaded. All moved text was restored inline.
2. Four-move draft (PR descriptions, native iOS proof, WorldAI fallback and native build authority moved behind inline triggers): **FAIL**. Three of the moves left a rule the inline trigger did not cover. Those three were reverted in full.
3. This candidate (narrative trim plus the native-build move), reviewed at 76,179 bytes: **PASS**. No rule conditional, narrower, weaker or absent beyond the rows marked "Skill only"; the native-build trigger is at least as broad as the original section; byte figures correct. Two non-blocking notes were applied afterwards without another review: the canary-identifier line under Part 3b, and the restored parenthesis "(threshold plus how/when it is re-measured)", which adds 44 bytes (76,223 final).
4. A second, separate reviewer (Codex CLI, full base and head content) reviewed commit `5f3ca55c3a44f611fb7877c0b01f09c76bbe9487` at 76,223 bytes: **NOT APPROVED**. One blocking finding: the "Blocked on one host" subsection named two specific hosts, against the repository's fresh-machine invariant. Row R10 records the fix. Two non-blocking findings were left unchanged for the owner: the `/f`, `/factory` and `/af` lines name skills that are not in the catalog (R14), and the scratch-volume section states a guard and a Linux scratch layout as facts about every host.

No reviewer could verify owner approval of the move, of the five reconciliation conflicts or of the R10 rewording.
