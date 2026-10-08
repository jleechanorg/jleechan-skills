# Curated portable skills

These opt-in derivatives support native agent tools without changing the
canonical Claude workflows in `.claude/skills`. The manifest is the exact scope;
this is not a conversion of the whole catalog. Complete references and aliases
are included. Operational dependencies such as cmux, browser authentication,
and independent reviewer capacity must still be verified when invoked.

The source-bundle SHA-256 values identify the accepted priority and cmux
derivatives. File hashes identify this public distribution. Private usage
receipts, account preferences, transcripts and runtime audit files are excluded.
The parallelization provenance paragraph was adjusted to remove a private
receipt link; its timeline reference remains bundled. Preserve Superpowers'
attribution to Jesse Vincent/obra in the wrapper.

## Install and update

Python 3 and Bash are required. Choose a dedicated absolute package directory
outside agent homes. The existing installer copies only the curated skills and
manifest, verifies every file, and refuses nonempty targets by default:

```bash
PORTABLE_HOME="$HOME/.local/share/jleechan-portable-skills/current" \
  bash install-claude-commands.sh --portable
```

For an existing installation, `--portable --backup` stages and verifies a new
copy before moving the old directory to a printed timestamped sibling backup.
Local edits and extra files remain in that backup. A nonempty destination must
already carry this distribution's manifest. `--merge`, archive migration,
linked destinations and agent-home destinations are refused. Canonical skills,
commands, scripts, history and credentials are not copied by this mode.

Use the rollback procedure in [INSTALL.md](../INSTALL.md#rollback), substituting
the dedicated portable directory and its printed backup path. Preserve the
post-install directory before restoring a backup.

## Discovery and remote use

Review the manifest and the destination's existing entries before installing
discovery links. For each manifest skill, move any existing same-named entry
intact to a unique private undo directory, then link that exact name in the
host's supported discovery root to the installed `skills/<name>` directory.
Record old link targets and moved entries. Do not replace discovery roots or
follow existing links into canonical packages. Roll back only links that still
point to this installation; preserve later changes for review.

For Ubuntu or another authorized host, transfer only this portable directory,
the installer and its verification script into a new isolated staging directory.
Use the existing authenticated transport with normal host verification. Run the
same installer there and compare manifest hashes before changing discovery.
Never synchronize a whole home directory or overwrite a dirty repository.

Disk hashes prove installed bytes. Discovery requires a fresh host catalog read;
workflow execution and the visual picker are separate evidence. A Markdown
package alone does not prove that a runtime dependency or GUI workflow works.

## Validation

```bash
python3 scripts/verify_portable_skills.py portable
python3 -m unittest discover -s tests -p 'test_portable_install.py'
python3 -m unittest discover -s tests -p 'test_installer.py'
```
