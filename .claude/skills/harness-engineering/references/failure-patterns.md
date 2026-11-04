# Harness engineering: worked failure patterns

Incident write-ups moved out of `../SKILL.md`. Each illustrates a rule that `SKILL.md` keeps.

## Example: CLI redacts secrets but scripts still export them

**Observable:** Gateway returns `unauthorized` / embedded fallback; logs show token value `__OPENCLAW_REDACTED__` or similar.

**Failure class:** **Silent degradation** (harness script looked correct: “get token, export, run”) plus **knowledge gap** (CLI intentionally does not echo real secrets).

**Technical 5 Whys (compressed):** Export used `openclaw config get …` → CLI prints redacted sentinel → shell passed sentinel to gateway → auth failed → embedded fallback.

**Agent 5 Whys (compressed):** Pattern “export token then call CLI” is common in docs → agent did not verify the *value* was non-redacted → no instruction forbidding export of `config get` for secrets → recurrence.

**Harness fixes (typical):**
1. **Instructions** — `~/.claude/CLAUDE.md`: never `export` gateway tokens from `config get` when output can be redacted; `unset` override env vars; read JSON or use provider-specific keys (`MINIMAX_API_KEY`) as documented.
2. **Commands** — `~/.claude/commands/claw.md` (or repo overlay): validate token with a file read / non-redacted check; document the redaction trap explicitly.
3. **Memory** — one-line feedback memory so project agents see it in `MEMORY.md`.

**Verification:** Run the command path and confirm the exported string is not a known redaction sentinel and gateway returns `status: ok` without “falling back to embedded”.

## Historical: retired Gate 7 trusted aggregate workflow status

**Historical observable:** before the 2026-07-28 policy change, an agent trusted
Green Gate `completed/success` while a separate Skeptic verdict was missing.
This mechanism is retired; current policy is the canonical two-gate `/green`.

**Failure class:** **Silent CI success** — a workflow can exit 0 at the job level while an inner step fails. The harness layer (Green Gate) is present and running, but it reports the wrong thing at the job level.

**Technical 5 Whys:**
1. Why did the PR show Green Gate `completed/success` even though Gate 7 was failing?
2. Why does the workflow exit 0 at job level even when the VERDICT check step exits 1?
3. Why is the VERDICT check inside a step rather than as a separate job with its own status?
4. Why does the polling step swallow the step failure without propagating it to job status?
5. Why is there no CI gate that independently verifies VERDICT existence as a separate job?
→ Root cause: The Green Gate conflates “trigger posted” with “skeptic evaluated”; the job always exits 0 because the trigger step succeeds, and the VERDICT step failure is swallowed inside the job.

**Agent 5 Whys:**
1. Why did the agent trust `gh pr checks` output to determine Gate 7 status?
2. Why didn't the agent read the workflow log to verify gate outcomes?
3. Why was there no instruction telling the agent that `gh pr checks` is insufficient for Gate 7?
4. Why did the existing 7-green definition not include a verification procedure for Gate 7?
5. Why was the skill written as policy without a mandatory verification step?
→ Agent root cause: The harness defined 7-green as policy without requiring independent VERDICT verification, so agents trusted the workflow's job-level status.

**Harness fixes:**
1. **Skill** — `pr-green-definition.md`: Add mandatory REST API VERDICT check procedure (not just policy statement)
2. **Skill** — `pr-green-definition.md`: Add counter-example showing Green Gate `completed/success` while Gate 7 fails
3. **Command** — `/green.md`: Already exists but relied on workflow logs only; updated to mandate REST check for Gate 7
4. **Memory** — `feedback_2026_04_21_silent_ci_success.md`: Document the specific PRs where this was observed

**Current verification:** follow
`~/.claude/skills/pr-green-definition/SKILL.md`; independently verify
current-head CI conclusions and mergeability rather than trusting the Green Gate
display status.
