# /ready — drive PR(s) to merge-ready

Load and follow `${CLAUDE_HOME:-$HOME/.claude}/skills/ready/SKILL.md` (Skill tool: `ready`).

PRs should satisfy — or be made to satisfy — ALL of: /es, /er, then /green,
with all comments, cross-thread regressions, and merge conflicts handled,
verified at the current head SHA. `/advice` remains available as an optional
second opinion, but is not a readiness gate. Then report READY (and merge only
under explicit or standing approval).

ARGUMENTS: optional PR numbers/repo; default = the PRs in the current working
context.
