# Shared Claude, Codex, and cloud skills

`shared-skills.json` selects complete packages from `.claude/skills/`. That directory
is the repository source, not a Claude-only variant. The same reviewed bytes apply to
all supported runtimes. Runtime qualifications live in the shared instructions.
Four-layer is the first reconciled bundle; the remaining accepted skills need semantic
reconciliation before their discovery links can move. Do not use the older portable
installer or the whole-home Claude installer to update this selected bundle.

## Review and local activation

From a checkout of the reviewed commit, create a private plan with absolute paths:

```bash
python3 scripts/install_shared_skills.py \
  --home "$HOME" \
  --package "$HOME/.local/share/jleechan-skills/REVIEWED_REVISION" \
  --undo "$HOME/.local/share/jleechan-skills/REVIEWED_REVISION-undo" \
  --plan /tmp/shared-skills-plan.json
```

The plan records exact source hashes and all selected preimages. Review local changes
before approving it. Apply only that reviewed plan with `--apply /tmp/shared-skills-plan.json`.
Changed source/destination state requires a fresh plan and review. All selected entries
in `.claude/skills`, `.codex/skills`, and `.agents/skills` become links to one versioned
package. Existing directories and symlinks move intact to numbered undo entries;
symlinks are not followed into old canonical directories. No whole-home copy occurs.
The receipt records each operation before mutation and confirms installed link targets.
A partial failure remains visible in the receipt; do not blindly rerun it.

The `/4layer` Claude command stays unchanged. Install the new thin
`.claude/commands/four-layer.md` only after checking its target is absent or matches the
reviewed preimage; preserve any existing command before replacement. Both commands
read the same shared `4layer` definition. Skill discovery of `four-layer` uses the
included thin alias. No command or package copy proves runtime discovery or execution.

For Ubuntu, use the existing authorized SSH route and normal host verification; stage
only this manifest, its selected packages, and the installer from the same reviewed
commit. Inspect Ubuntu's own preimages and generate its plan there. Do not reuse a Mac
plan, assume matching homes, or copy credentials/history.

For cloud, materialize these same selected packages from the reviewed repository
commit through the supported personal-skill registry. Preserve package identity and
publish/reconcile each dependency before claiming discovery. Cloud cannot symlink to
a Mac path. Catalog-only companion resolution uses exact skill names.

## Undo

Read the private undo receipt. For each completed entry, verify it still is a symlink
to the recorded target before removing that link and restoring its numbered preimage.
If it changed after installation, leave it intact and report the conflict. For an
originally absent entry, remove only the still-matching created link. Keep package and
undo directories until verification finishes; never overwrite later user edits.

## Four-layer semantic mapping

Baseline repository: `62366cabd34d6c9ba2e889d7ffd7ff06f1b44524`.
Current canonical 4layer source SHA256:
`737035ce2ba661bf975c82530a19f761e321f64bd5fb420061f80d283dc0d1dd`.
Previous portable adapter SHA256:
`d4d68696d150959456b4f460b4ca0cb161f382d0b5742707570c576f74e7bab7`.

| Source requirement | Shared resolution |
| --- | --- |
| Canonical ladder and examples | Retained; actual project runner must be discovered |
| Mandatory blocker companion | Read sibling package, or exact catalog name; project BYOK examples retained with runtime/authorization qualifications |
| Integration verification | Required companion plus core Three Evidence Rule: configuration, automatic trigger, automatic-run logs; manual output is insufficient |
| Missing global extended command | Explicitly dispatch-only, not a protocol dependency; no project overlay substituted |
| /4layer and four-layer | Both route to one definition; alias contains no duplicated ladder |
| Portable safety/evidence | Shared runtime boundary preserves unsupported status, minimal scope, redaction, isolation, and no implied provider/shared-state authority |
| Companion environmental jump vs source pass-only order | Owning 4layer pass-only order takes precedence; environmental browser example requires preceding passes |

The old portable 4layer body is removed from its manifest, avoiding a second maintained
implementation. Its existing installed bytes are preserved until reviewed activation.
The other 29 portable entries remain untouched during this first bounded migration.
