# Shared skill catalog

Use the repository as the versioned distribution source. Canonical Claude
workflows remain in `.claude/skills`; the reviewed cross-runtime derivatives
in `portable/skills` remain distribution inputs, without overriding same-name live
Claude packages. Thin aliases
provide `browser`, `mac`, `linux`, and `playwright` without duplicating workflows.

`install_shared_catalog.py` manages active canonical packages plus portable
variants and aliases. `retain-local.json` identifies operational packages that
must remain owned by their local integration. Other host-only names, archived
copies, generated wrappers, plugin-managed skills, settings, credentials,
commands and histories are not replaced. This is an identical managed catalog,
not a claim that every pre-existing local skill or runtime capability is equal.

## Comparison and selection

The October 3, 2026 review inventoried complete active packages in both
`~/.agents/skills` and `~/.claude/skills` on Linux and macOS, including helper
file hashes and link targets. The union contained 968 distinct names; 373 were
generated command wrappers. Individual SKILL.md variants were grouped after
normalizing home paths. Package helper differences were inspected separately.
`comparison-decisions.json` records the disposition of every name, including
preserved local-only entries; an inventory disposition is not a claim that an
unmanaged integration passed a runtime behavior test.

The comparison baseline is upstream commit `36ac5c1`; the release also includes
the subsequent upstream research update from `daad801`. Selection favors maintained,
portable behavior and complete packages, not timestamp or word count:

- Adopt live improvements to Beads canonical-store ownership and recovery,
  PATH guard checks, backup scope, bounded GitHub API fallback, executable
  planning contracts, and learning capture outside a Git working directory.
- Preserve upstream integration/learning authorization and adapt the restored goal
  template to available workflows and repository-specific gates.
- Preserve upstream proportional planning/testing and authorized evidence
  destinations. Do not propagate local mandatory gist publication or fixed
  fleet counts as universal rules.
- Add connected browser API routing before the Aside fallback. A supported
  Chrome connection can use Playwright locators without copying cookies.
  Installed Playwright MCP alone does not prove attachment to signed-in Chrome.
- Restore missing complete-package helpers and licenses for Beads, MCP builder,
  frontend design, webapp testing, goal templates and spreadsheets.
- Preserve local operational variants listed in `retain-local.json`; their
  provider runners, authenticated integrations, host resource policies or
  project-specific command contracts need their owning integration's validation.
  They are not overwritten merely because upstream has a file of the same name.

## Install

First run the isolated tests and review the dry-run source paths, canonical destinations, consumer destinations and link targets (paths relative to the selected home):

```bash
python3 -m unittest discover -s tests -p 'test_cross_host_catalog.py'
python3 scripts/install_shared_catalog.py --release <reviewed-commit> --dry-run
python3 scripts/install_shared_catalog.py --release <reviewed-commit>
python3 scripts/install_shared_catalog.py --release <reviewed-commit> --verify
```

The installer updates real files in `~/.claude/skills` and links
`~/.agents/skills/<name>` directly to that live canonical package. It does not
create active release snapshots or a `.codex/skills` projection. Same-name
portable variants do not override canonical Claude workflows; aliases fill only
missing names. Retained local integrations remain excluded.

Local files that differ from the reviewed source cause a pre-mutation conflict.
For a subsequent reviewed update, pass `--baseline-receipt <prior-receipt>`;
only unchanged previously managed bytes may be updated. Previously managed files
removed from that source, including all owned files and the owned consumer link
of a removed package, are moved intact to undo only when their prior hashes
still match; changed retired files cause a pre-mutation conflict. Unmanaged local
extensions are preserved. Reconcile divergent content explicitly before retrying. Existing
snapshot links must be reconciled into real canonical directories first.

Adding a previously managed name to `retain-local.json` is an explicit ownership
handoff, not deletion: its files and discovery entries remain intact, and the new
receipt records the prior ownership in `retained_handoff`. The shared installer
then excludes that name from writes in both runtimes. It does not remove a locally
owned operational integration merely because it is now retained.

Each operation records exact replaced files and consumer entries in a private
undo directory under `~/.local/state/jleechan-shared-skills/<release>`. Undo is
retained; no old backups or snapshot directories are deleted. Verification reads
live managed bytes and consumer targets, so later local edits are visible.

To restore a successful release, run
`python3 scripts/install_shared_catalog.py --release <release> --rollback`.
Rollback first checks every affected postimage and refuses later local edits,
linked ancestors, or missing preimages before restoring anything. It restores
replaced files and consumer entries, removes only this release's additions from
active paths, and retains both original backups and moved postimages in the
same undo directory. Unmanaged extensions and empty parent directories remain.
Undo dependent later releases first. A partially interrupted rollback is recorded
as `rolling-back` with a restore map; inspect that receipt and preserve intervening
edits rather than automatically retrying or overwriting them.

Use the same reviewed repository commit and installer on each host through an
existing authorized transport. Compare the `managed` file-hash maps in each
generated `receipt.json` and the `--verify` results; host-specific backup paths
and action records are not portable manifest identity. No `catalog.json` is
generated. Do not synchronize whole home directories or profile data.

## Discovery and limits

Disk verification proves package bytes and discovery link targets. Reload the
host's skill catalog or start a fresh task to test discovery; the current task's
injected catalog can remain unchanged. Test the visual picker and representative
workflows separately. Skills do not install browser extensions, connect absent
profiles, change permissions, or override another session's tab lock. `/browser`
is also a Claude command; `$browser` discovery depends on the current host.
