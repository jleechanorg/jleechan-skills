# Historical zero-use archive — 2026-08-27

These skills were removed from the installable catalog, not deleted. Restore a
package with `git mv` if a live workflow needs it again.

## Evidence

The 30-day Claude Code history pass (2026-07-28 through 2026-08-27) inspected
structured assistant `Skill` tool calls rather than raw text mentions. It found
zero calls for each archived package:

- `agent-orchestrator`
- `codex-evolve-loop`
- `skeptic-agent`

Raw-name records were intentionally ignored: they are dominated by skill
catalogues and documentation, and are not invocation evidence. The three
packages also have no project slash-command pointer. `skeptic-agent` is
explicitly marked as a deleted system in its own historical content.

## Scope

This is a deliberately narrow first tranche. It does not imply that any other
zero-observation skill is unused. Archive candidates require both a structured
usage check and a dependency check before they move here.
