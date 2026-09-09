---
description: Start a fresh branch from main and release the current branch's test-server resources
name: integrate
type: skill
execution_mode: immediate
---

# `/integrate`

Run the installed integration utility from the target repository's working
directory. The utility resolves the Git root itself and must be invoked from a
repository. It performs the safety checks, optional test-server cleanup, main
branch update, and fresh-branch creation described below.

## Runtime script

Use the user-scope installed script:

```text
${CLAUDE_HOME:-$HOME/.claude}/scripts/integrate.sh
```

Require that path to be executable before running it. Do not look for,
require, copy, or invoke `./integrate.sh` or any other repository-local copy.
The repository's `scripts/integrate.sh` is the export source used by the
installer; the runtime entry point is the copy under the active Claude home.

## Argument mapping

Interpret the text after `/integrate` as the script's explicit argv list. The
supported forms are one optional branch name and these flags:

- no arguments: run the script with no arguments;
- `<branch-name>`: pass that branch name as one positional argument;
- `--force`: pass the force flag;
- `--new-branch`: pass the new-branch flag;
- `--help` or `-h`: pass the help flag.

Preserve every supplied argument and its order when constructing argv. Do not
use `$@`, `eval`, unquoted expansion, or pass the entire `$ARGUMENTS` string as
one shell argument. Let the script apply its own argument validation and
multiple-name warning rather than silently changing that behavior. Run it from
the current target repository directory and report its exit status and output.

Examples:

```text
/integrate
/integrate feature/my-feature
/integrate fix/bug-123 --force
/integrate --new-branch feature/my-feature
```

## Workflow contract

- The script fetches `origin/main` and creates a timestamped `dev<epoch>` branch
  when no branch name is supplied.
- It skips test-server cleanup on `main` and detached HEAD.
- If `test_server_manager.sh` is absent at the Git root, it reports `SKIPPED`
  and continues.
- If the manager is present but not executable, or its stop command fails, it
  reports the original error and exits before checkout, stash, or branch
  deletion.
- A successful manager call proves only that the manager returned success; it
  does not prove that no orphaned processes remain.
- `--force` and `--new-branch` retain the script's documented safety semantics.

After the script succeeds, use `/push` when the new branch needs its test
server started. Then follow the existing post-integration workflow: invoke
`/learn` to capture an authorized durable learning and run
`/factory-evolve --taxonomy` for the fast structural reviewer-node check. If
the current task does not authorize a memory write, report `/learn` as skipped
instead of creating memory. Do not claim that server cleanup or branch
integration occurred until the script output and exit status establish it.
