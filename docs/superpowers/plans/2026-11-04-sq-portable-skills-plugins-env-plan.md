# Portable skills: plugin folders and env vars — Implementation Plan

> Execute task by task with one implementation subagent per PR, reviewing between PRs.

**Goal:** Remove machine-, account-, and product-specific content from the generic
`.claude/skills/` export by moving product-only skills into opt-in plugin folders and
replacing literals with registry environment variables.

**Architecture:** Product-only skills move to `plugins/<name>/` Claude Code plugins
registered in `.claude-plugin/marketplace.json`; generic skills resolve values via
`docs/portability-env-vars.md`; two mechanical tests (plugin structure, product-token
ratchet) prevent regressions. Spec:
`docs/superpowers/specs/2026-11-04-sq-portable-skills-plugins-env-design.md`.

**Tech Stack:** Markdown skills, JSON manifests, Python `unittest`/pytest, bash.

**Inputs:** per-skill leak records from the four audit passes (file, line, text, kind,
replacement). Implementers re-grep each skill before editing; line numbers are hints.

**Baseline:** `python3 -m pytest -q tests` on `main` in this container has exactly 3
pre-existing failures (`test_code_review_export.py` ×2 Hermes import, `test_md_files_bootstrap_regression.py`
backup test). "Green" below means: no failures beyond that set.

---

## PR 1 — Policy and design (`claude/elegant-einstein-gfcch1`)

### Task 1.1: Fresh-machine invariant

**Files:** Modify `AGENTS.md` (Repository Guide bullets), `CLAUDE.md` (one pointer bullet).

TDD: N/A — instruction prose; AGENTS.md forbids wording-pin tests.
Verification: `python3 -m pytest -q tests` failure set equals the baseline.

### Task 1.2: Spec, plan, env registry

**Files:** Create the spec, this plan, `docs/portability-env-vars.md`.

TDD: N/A — documentation. Verification: `python3 -m pytest -q tests/test_skill_export_no_personal_paths.py`
passes; `grep -nE '/(Users|home)/[a-z]' docs/portability-env-vars.md` prints nothing; and grepping the
three new documents for every personal host alias, personal name and personal path listed in the audit
records (kept outside the repository) prints nothing.

Commit, push, open draft PR 1.

---

## PR 2 — Plugin folders (`claude/elegant-einstein-gfcch1-plugins`, base PR 1)

### Task 2.1: Plugin structure test (RED)

**Files:** Create `tests/test_plugin_folders.py`.

```python
import json, re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS = ROOT / "plugins"
EXPECTED = {"worldarchitect", "ai-universe", "self-hosted-runners"}
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")

def frontmatter_name(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return None

def plugin_dirs():
    return sorted(p for p in PLUGINS.iterdir() if p.is_dir()) if PLUGINS.is_dir() else []

def skill_dirs(plugin):
    skills = plugin / "skills"
    return sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []

class PluginFoldersTest(unittest.TestCase):
    def test_marketplace_sources_exist(self):
        for p in json.loads(MARKET.read_text())["plugins"]:
            if isinstance(p["source"], str):
                self.assertTrue((ROOT / p["source"]).is_dir(), p["source"])

    def test_expected_plugins_registered(self):
        names = {p["name"] for p in json.loads(MARKET.read_text())["plugins"]}
        self.assertTrue(EXPECTED <= names, EXPECTED - names)

    def test_plugin_manifests_and_skills(self):
        self.assertTrue(PLUGINS.is_dir(), "plugins/ missing")
        for d in plugin_dirs():
            manifest = json.loads((d / ".claude-plugin" / "plugin.json").read_text())
            self.assertEqual(manifest["name"], d.name)
            for skill in skill_dirs(d):
                with self.subTest(skill=str(skill)):
                    self.assertEqual(frontmatter_name((skill / "SKILL.md").read_text()), skill.name)

    def test_no_name_in_both_export_and_plugin(self):
        self.assertTrue(PLUGINS.is_dir(), "plugins/ missing")
        export = {p.name for p in (ROOT / ".claude" / "skills").iterdir() if p.is_dir()}
        for d in plugin_dirs():
            self.assertFalse(export & {p.name for p in skill_dirs(d)}, d.name)

    def test_relative_links_stay_inside_plugin(self):
        for d in plugin_dirs():
            for md in d.rglob("*.md"):
                for target in LINK.findall(md.read_text(encoding="utf-8")):
                    if "://" in target or target.startswith(("mailto:", "$")):
                        continue
                    resolved = (md.parent / target).resolve()
                    with self.subTest(file=str(md), link=target):
                        self.assertTrue(resolved.is_relative_to(d.resolve()) and resolved.exists())
```

Run: `python3 -m pytest -q tests/test_plugin_folders.py`
Expected RED: `test_expected_plugins_registered` fails (set difference lists all three);
`test_plugin_manifests_and_skills` and `test_no_name_in_both_export_and_plugin` fail with
`plugins/ missing`; `test_marketplace_sources_exist` and `test_relative_links_stay_inside_plugin`
pass vacuously until plugins exist.

### Task 2.2: Scaffold plugins and marketplace (GREEN for registration)

**Files:** Create `plugins/{worldarchitect,ai-universe,self-hosted-runners}/.claude-plugin/plugin.json`
(`name`, `description`, `version: "0.1.0"`, `author` copied from the root plugin.json,
`"skills": ["./skills/"]`; Task 2.3 adds `"commands": ["./commands/"]` when it creates a commands dir),
`plugins/<name>/README.md` (purpose, `/plugin install <name>@jleechan-skills`, the env vars
from the registry it needs). Modify `.claude-plugin/marketplace.json`: append three
`plugins[]` entries with `"source": "./plugins/<name>"`.

Run: `python3 -m pytest -q tests/test_plugin_folders.py` → `test_expected_plugins_registered`
and `test_marketplace_sources_exist` PASS; the manifest test still fails until skills exist.

### Task 2.3: Move skills (`git mv`)

First list every command whose only skill target moves: for each moved name,
`grep -rlE 'skills/<name>/SKILL\.md' .claude/commands`. Those commands move with their skills.

Move each skill directory listed in spec D1 "What moves" with `git mv .claude/skills/<s> plugins/<plugin>/skills/<s>`;
rename `agents` → `plugins/worldarchitect/skills/worldai-agent-routing` and update its frontmatter
`name`. Move `.claude/scripts/auth-worldai.mjs` to `plugins/worldarchitect/scripts/` and reference it
as `node "${CLAUDE_PLUGIN_ROOT}/scripts/auth-worldai.mjs"`. In every moved file, grep for
`\.\./`, `scripts/`, `shared/` and `\.claude/`: address plugin-local files via `${CLAUDE_PLUGIN_ROOT}`,
name generic skills instead of linking them, and copy any needed repository script into the plugin. Move commands whose only target moved
(`.claude/commands/levelup.md`, `extended-library/generatetest.md`, `extended-library/repro_copy.md`,
`extended-library/smoke-local.md`, `extended-library/bq.md`, `extended-library/second_opinion.md`
— verify each target with `grep -n 'skills/' <cmd>` first) to `plugins/<plugin>/commands/`.

Inside moved files: replace real UIDs, campaign IDs, project numbers, Slack IDs, prod URLs
and personal hosts/paths with registry variables or placeholders (audit records list each).

Run: `python3 -m pytest -q tests/test_plugin_folders.py` → all PASS, including
`test_relative_links_stay_inside_plugin`.

### Task 2.3b: Privacy scans cover plugins (RED → GREEN)

**Files:** Modify `tests/test_skill_export_no_personal_paths.py` (scanned roots) and
`tests/test_skill_personal_identifiers.py` (`SKILL_ROOTS`) to include `plugins`.
Step 1: plant `/home/alice/x` in a moved plugin skill file; run
`python3 -m pytest -q tests/test_skill_export_no_personal_paths.py` → FAIL naming that file.
Step 2: revert the plant → PASS. If real leaks in moved files fail the scan, scrub them.

### Task 2.4: Repair references to moved skills

**Files:** every hit of `grep -rlE '(\.\./|skills/)(<moved-names-regex>)/' .claude shared tests scripts .claude-plugin .agents docs install-claude-commands.sh *.md`
and backticked names in generic skills. Replace relative links with product-neutral convention
wording ("if an installed product plugin provides a companion for this skill, read it"), so the
new text passes the ratchet. Update
`shared/install-profiles.json` / `shared/retain-local.json` entries naming moved skills.
For tests that pin a moved skill's path (`test_skill_portability_batch1..4.py`,
`test_failure_boundary_skill_contract.py`, `test_workflow_command_pairs.py`, others found
by the grep), repoint them at `plugins/<plugin>/skills/<s>` when they test structure, or
delete the assertion when it pins wording (AGENTS.md policy).

Run: `python3 -m pytest -q tests` → failure set equals the baseline. Also
`bash install-claude-commands.sh --help` exits 0, and `python3 scripts/install_profiles.py . --resolve prw`
exits 0.

### Task 2.5: Product-token ratchet (RED → GREEN)

**Files:** Create `tests/test_product_token_ratchet.py` and `tests/fixtures/product_token_allowlist.txt`.

```python
import re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = (ROOT / ".claude" / "skills", ROOT / ".claude" / "commands")
ALLOW = ROOT / "tests" / "fixtures" / "product_token_allowlist.txt"
TOKENS = re.compile(r"worldarchitect|worldai|mvp_site|your-project\.com|testing_mcp", re.I)

def offenders():
    out = set()
    for f in (f for root in SCAN for f in root.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            try:
                if TOKENS.search(f.read_text(encoding="utf-8")):
                    out.add(f.relative_to(ROOT).as_posix())
            except (UnicodeDecodeError, OSError):
                pass
    return out

class ProductTokenRatchetTest(unittest.TestCase):
    def test_no_new_product_tokens_in_generic_skills(self):
        allowed = {l.strip() for l in ALLOW.read_text().splitlines() if l.strip() and not l.startswith("#")}
        self.assertEqual(sorted(offenders() - allowed), [])
```

Step 1: write the test with an empty allowlist (header comment only).
Run: `python3 -m pytest -q tests/test_product_token_ratchet.py` → RED listing remaining offenders.
Step 2: generate the allowlist from the post-move tree, overwriting it:
`{ echo '# Files allowed to contain product tokens; may only shrink.'; python3 -c "import sys; sys.path.insert(0,'tests'); import test_product_token_ratchet as t; print('\n'.join(sorted(t.offenders())))" | sort -u; } > tests/fixtures/product_token_allowlist.txt`.
Run again → PASS. Step 3: prove it bites: create a temporary `.claude/skills/zz-ratchet-probe/SKILL.md`
containing `mvp_site` (confirmed absent from the allowlist), run → FAIL naming it, delete the probe
directory, run → PASS.

Commit, push, open draft PR 2.

---

## PR 3 — Machine values (`claude/elegant-einstein-gfcch1-env-machine`, base PR 1)

Skills: mac-remote, linux-remote, crash, gmail (host part), disk-audit, host-disk-guardian,
backup-verification, browser-control, aside-browser-default, systemd, cmux-bulk-steer,
cmux-backup, conversation-history-sparse, dot, disk-root-cause, soak, vibe-code-2d-game,
antigravity-computer-use, history-search, learn, wiki-assess, wiki-ingest, plan-micro,
roadmap, ironclad, swarm, design-doc, dark-factory, factory-spec, factory-evolve, callpath,
auto-factory, repro-developer.

### Task 3.1: Script behavior fixes (TDD)

For each script under these skills whose default changes (`host-disk-guardian` defaults,
`repro-developer/collect_repro.py` `"/home/$USER"` literals, `history-search` `$HOME/projects`
default), write a failing test in `tests/test_<skill>_env_defaults.py` that runs the script
with a temp `HOME` and the variable unset, asserting either the documented derived value or a
non-zero exit whose stderr names the variable.
Run: `python3 -m pytest -q tests/test_<skill>_env_defaults.py` → RED (old hardcoded default used).
Implement the registry resolution. Run → GREEN, then `python3 -m pytest -q tests` → baseline.
Each test runs in a temporary non-git working directory with a controlled `PATH`, so results do not
depend on the surrounding checkout. Add any new variable to `docs/portability-env-vars.md`.

### Task 3.2: Prose and snippet edits

TDD: N/A — Markdown wording. Replace each audited literal with the registry variable or
placeholder; delete personal-only reference files (`plan-micro/references/*` private baseline
and TSV). Verification: grepping these skills for `~/projects/`, `projects_other`, `/opt/homebrew`
and each personal host alias, name and wiki path listed in the audit records prints only intentional
`command -v` fallbacks; `python3 -m pytest -q tests` → baseline.

Commit, push, open draft PR 3.

---

## PR 4 — Accounts, repos, identities (`claude/elegant-einstein-gfcch1-env-accounts`, base PR 1)

Skills: github-cli-reference, agento-report, org-runner-audit, ci-queue-trim, luna, ao-worker-dispatch,
ao-spawn-safety, ao-spawn-gate, ao-operator-discipline, ao-lifecycle-triage, ao-model-override,
agent-orchestrator, slack-audit, slack-identity, slack-media-upload, claw-dispatch, zero-touch,
minimax, harness-postmortem, harness-engineering, sync-live-config, command-research,
credential-discipline, write-goal, goalexec, gmail (account part).

### Task 4.1: Script defaults (TDD)

`ci-queue-trim` (`DEFAULT_REPO`), `luna` (repo and scratch folder), `slack-media-upload`
(DM channel env name), `command-research` (stop-list prefixes), `credential-discipline`
(blocklist file). For each: failing test asserting the env/derived resolution (e.g.
`ci-queue-trim` with `GITHUB_REPOSITORY=acme/widgets` targets `acme/widgets`; with it unset
and no `gh` repo, exits non-zero naming `GITHUB_REPOSITORY`). Each such test runs in a temporary
non-git working directory with a stub `gh` on a temporary `PATH` that exits non-zero.
Run → RED; implement; run → GREEN. Add new variables (DM-channel rename, luna scratch folder,
command-research prefixes) to `docs/portability-env-vars.md`. Update `tests/test_luna_report_containment.py` expectations
to the derived scratch folder.

### Task 4.2: Prose edits

TDD: N/A — wording. Replace `jleechanorg/<repo>` defaults with `$GITHUB_REPOSITORY`/`$GITHUB_ORG`,
Slack IDs with registry vars, personal names with "the operator". Move real identifiers out of
`credential-discipline` into the machine-local blocklist file description.
Verification: `python3 scripts/skill_portability_scan.py --check-personal --base origin/main` exits 0;
`python3 -m pytest -q tests` → baseline.

Commit, push, open draft PR 4.

---

## PR 5 — Product examples and splits (`claude/elegant-einstein-gfcch1-product-examples`, base PR 2)

Splits: testing-layers, smoke, harness-guardrails, evidence-review, evidence-standards
(`references/bundle-anatomy.md`), ui-video-evidence, llm-testing → generic skill keeps rules;
product content to `plugins/worldarchitect/skills/worldai-<skill>/SKILL.md`.
Example-only edits: user-story, document-standards, runtime-activation-claim, timeline,
evidence-coverage, pr-summary, browserclaw (drop the product bundle from `examples/`; make
`capture.py` probes configurable via `BROWSERCLAW_PROBE_ENDPOINTS`), beads-issue-tracking,
zero-framework-cognition, zfc-adjuster, code-centralization, ablation, pr-driver-protocol,
web-advice, experiment, sidekick, code-standards, agy-dot-coordinator.

### Task 5.1: browserclaw probes (TDD)

Failing test `tests/test_browserclaw_probes.py`: importing `capture.py`'s probe list with
`BROWSERCLAW_PROBE_ENDPOINTS` unset yields `[]`; with `"/api/a,/api/b"` yields both.
RED (hardcoded product probe), implement, GREEN. Register `BROWSERCLAW_PROBE_ENDPOINTS` in
`docs/portability-env-vars.md`.

### Task 5.2: Companion skills and edits

TDD: N/A — Markdown moves. Verification: `python3 -m pytest -q tests/test_plugin_folders.py tests/test_product_token_ratchet.py`
PASS; then copy the allowlist to a scratch file, regenerate it with the overwrite command in
Task 2.5 Step 2, and confirm it only shrank: `comm -13 <old> tests/fixtures/product_token_allowlist.txt`
prints nothing. List any remaining entries with a reason in the PR body; full suite → baseline.

Commit, push, open draft PR 5.

---

## TDD Plan Check

| Task | Behavior change? | Checked sequence |
|---|---|---|
| 1.1, 1.2 | No | TDD: N/A — prose/docs; verified by suite baseline + path grep |
| 2.1–2.3 | Yes (repository structure consumed by Claude Code) | RED: 2.1 test fails on missing plugins → minimal scaffold 2.2 → moves 2.3 → GREEN (including link containment) → commit |
| 2.3b | Yes (scan scope) | Plant fake path in plugin → FAIL → revert → PASS |
| 2.4 | Yes (references, profiles) | Existing suite is the RED/GREEN oracle; moved paths fail tests until repointed; run full suite → baseline |
| 2.5 | Yes (new guard) | RED with empty allowlist → generate (overwrite) allowlist → GREEN → probe skill FAIL → delete probe → PASS |
| 3.1 | Yes (script defaults) | Per-script failing env-default test → implement → GREEN → full suite |
| 3.2 | No | TDD: N/A — wording; verified by targeted grep + suite baseline |
| 4.1 | Yes (script defaults) | Per-script failing test → implement → GREEN → luna test updated |
| 4.2 | No | TDD: N/A — wording; verified by `--check-personal` + suite |
| 5.1 | Yes (probe config) | RED on hardcoded probes → env-driven → GREEN |
| 5.2 | No (content relocation) | TDD: N/A — verified by plugin/ratchet tests + `comm -13` shrink-only check |

## Implementation Preconditions

- Suffixed branch pushes depend on the multi-PR request; on refusal, stack onto
  `claude/elegant-einstein-gfcch1` and list combined scope in its PR.
- PR 5 starts only after PR 2's branch exists (it is its base).
