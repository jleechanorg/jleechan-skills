# Shared skill catalog

Use the repository as the versioned distribution source. Canonical Claude
workflows remain in `.claude/skills`; the 30 reviewed cross-runtime derivatives
in `portable/skills` take precedence only in `~/.agents/skills`. Thin aliases
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

First run the isolated tests and review the dry-run names:

```bash
python3 -m unittest discover -s tests -p 'test_cross_host_catalog.py'
python3 scripts/install_shared_catalog.py --release <reviewed-commit> --dry-run
python3 scripts/install_shared_catalog.py --release <reviewed-commit>
python3 scripts/install_shared_catalog.py --release <reviewed-commit> --verify
```

The installer copies complete packages to a new directory under
`~/.local/share/jleechan-shared-skills/<release>`, verifies file hashes before
changing discovery, and moves each replaced entry intact to a private undo
directory. It never follows an old discovery link to overwrite its target.
Existing releases are immutable by convention: updates use a new release name.
The printed undo path contains `receipt.json` with old targets and moved entries.
A failure restores only links still owned by this installation.

Use the same reviewed repository commit and installer on each host through an
existing authorized transport. Compare the installed `catalog.json` file hashes
and verify results. Do not synchronize whole home directories or profile data.

## Discovery and limits

Disk verification proves package bytes and discovery link targets. Reload the
host's skill catalog or start a fresh task to test discovery; the current task's
injected catalog can remain unchanged. Test the visual picker and representative
workflows separately. Skills do not install browser extensions, connect absent
profiles, change permissions, or override another session's tab lock. `/browser`
is also a Claude command; `$browser` discovery depends on the current host.
