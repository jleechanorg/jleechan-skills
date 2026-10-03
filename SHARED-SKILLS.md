# Shared Claude, Codex, and cloud skills

`shared-skills.json` selects complete packages from `.claude/skills/`. That directory
is the repository source, not a Claude-only variant. The same reviewed bytes apply to
all supported runtimes. Runtime qualifications live in the shared instructions.
Four-layer is the first reconciled bundle; the remaining accepted skills need semantic
reconciliation before their discovery links can move. Do not use the older portable
installer or the whole-home Claude installer to update this selected bundle.

## Review and direct live-root activation

The live canonical source on each host is `~/.claude/skills/<name>`. Codex and Agents
link directly to that directory. There is no versioned local package or snapshot target;
a reviewed Git commit supplies provenance, not another runtime-specific copy.

First review source-to-live differences for the selected packages. Apply any approved
source edits to the existing Claude canonical files while preserving local additions
and private preimages. This link installer does not edit or replace canonical content:
it refuses activation until required canonical files match the reviewed manifest.
Extra canonical files are preserved and recorded; subsequent drift requires a new plan.

From the reviewed repository checkout, create a private plan with absolute paths:

```bash
python3 scripts/install_shared_skills.py \
  --home "$HOME" \
  --undo "$HOME/.local/share/jleechan-skills-undo/UNIQUE_OPERATION" \
  --plan /tmp/shared-skills-plan.json
```

Review the plan, then apply that exact plan with `--apply /tmp/shared-skills-plan.json`.
The selected `.codex/skills` and `.agents/skills` entries become direct links to the
corresponding live `.claude/skills` directories. Existing discovery entries move intact
to numbered undo entries; symlinks are not followed into old release directories.
Claude directories and all old releases remain unchanged. Source or destination drift
is refused. The private receipt records each operation before mutation. A partial
failure remains visible; inspect its receipt before any retry.

The existing `/4layer` command remains unchanged. Review and install the thin
`.claude/commands/four-layer.md` separately, preserving any previous command. Both read
the same live 4layer definition; the included skill alias also dispatches to 4layer.

For Ubuntu, use its existing authorized SSH route and normal host verification.
Inspect and reconcile its own live canonical preimages, then generate its own plan.
Do not reuse a Mac plan or transfer whole homes, credentials, or history.

Cloud materializes the same selected package sources from the reviewed Git commit via
its supported personal-skill registry; it cannot symlink to a Mac path. Reconcile the
required companion packages and exact-name alias before claiming catalog discovery.
Disk bytes, catalog discovery, invocation, and GUI proof remain separate.

## Undo

For each receipt entry, confirm the discovery link still points to its recorded live
Claude target, remove only that link, then restore its numbered preimage. If it changed
later, preserve it and report the conflict. Originally absent entries have no preimage.
Do not modify the canonical Claude package or old release directories to undo links.
A canonical source edit has its own separately reviewed preimage and undo operation.

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
