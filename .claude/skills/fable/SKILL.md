---
name: fable
description: "Agent model rule: no Fable subagents. Delegated agents, subagents and workflow stages run on Sonnet (claude-sonnet-5-5) for judgement and Haiku (claude-haiku-5-5) for collection. Use when the user types /fable, mentions agent models or agent count, or before spawning or dispatching any agent."
---

# /fable — Sonnet and Haiku subagents only (revised 2026-11-11)

Operator rule, 2026-11-11: "stop using fable subagents use sonnet haiku". This replaces the earlier rule below.

- The main session may stay on Fable. Every agent, subagent, teammate and workflow stage it starts sets `model: "sonnet"` (work needing judgement: code, review, art selection) or `model: "haiku"` (collection, mechanical steps). Never omit the model, because omission inherits Fable.
- Do not use `subagent_type: "fork"` (a fork always runs on the parent's model).
- No Opus, no other CLIs as substitutes, no silent fallback: if Sonnet or Haiku is unavailable, stop and say so.
- Reason: Fable usage credits ran out twice mid-task on 2026-11-11.

## Superseded rule (kept for history; do not follow where it conflicts)


# /fable — Fable where needed (max 3), Haiku for the rest

Operator rule (set 2026-11-10, revised the same day): delegated work uses only two models.

- **Fable** (`claude-fable-5-2`, alias `fable`) for work that needs judgement. **At most 3 Fable agents running at the same time**, counting subagents, workflow agents and remote lane sessions the current session started. The main session itself does not count toward the 3.
- **Haiku** (`claude-haiku-5-5`, alias `haiku`) for everything else.
- No Opus, no Sonnet, no non-Claude models, unless the operator names an exception in the current conversation.

## Which model for which work

Use **Fable** when the agent must: design or change code, debug, review code or art, judge quality (frames, stills, test honesty), weigh evidence and recommend, or resolve merge conflicts.

Use **Haiku** when the agent only: runs searches and fetches pages, collects posts or links into a table, extracts video frames, renders stills or contact sheets, runs a fixed command and reports its output, copies or converts files, or polls for status.

Split mixed jobs: a Haiku collector gathers and returns raw material; a Fable agent (or the main session) judges it. Do not give a Haiku agent a verdict to reach, and do not spend a Fable slot on pure collection.

## What to do every time this skill is invoked

1. State which model the current session is on.
2. Count Fable agents currently running that this session started, and list each with what it is doing. If more than 3, say so and name which to stop or let finish; do not start another Fable agent until the count is under 3.
3. For each running agent, say whether its work is judgement (Fable) or collection (should be Haiku). Do not switch an agent mid-run if that would lose its work; apply the rule to new spawns.
4. Report anything on a model other than Fable or Haiku, and what you did about it.

## Rules for spawning

- **Agent tool:** pass `model: "haiku"` for collection work. For judgement work omit `model` when the session is on Fable (the subagent inherits it) or pass `model: "fable"`. Never pass `opus` or `sonnet`. Before spawning a Fable agent, check the running count; if it is already 3, either wait, run the work in the main session, or make it a Haiku job if it qualifies.
- **Workflow scripts:** set `opts.model: 'haiku'` on collection stages; leave judgement stages to inherit Fable. Cap concurrent Fable agents at 3: run Fable stages in batches of at most 3 (for example chunk the list and `await parallel()` per chunk) rather than fanning out wide. Haiku stages may fan out freely. `log()` how many agents ran on each model.
- **Custom agent types:** check the frontmatter `model:` of any `.claude/agents/*.md` or plugin agent before using it. If it pins Opus or Sonnet, do not use that type; use `general-purpose` with the model set per this rule.
- **Remote or tmux lane sessions (for example on jeff-ubuntu):** launch with `claude --model claude-fable-5-2` for judgement lanes or `--model claude-haiku-5-5` for collection lanes; Fable lanes count toward the 3. For a session already running, send `/model <id>` and confirm from the pane that it took effect before sending it work. "Network error" or no confirmation means it did not switch.
- **Other CLIs (codex, gemini, agy and similar):** do not dispatch work to them under this rule; ask the operator first.
- **Commit attribution:** commits carry the tag of the model that made them.
- **If Fable or Haiku is unavailable** (rate limit, outage, not offered on a machine): stop and tell the operator. Do not fall back to another model silently.

## Audit steps

1. `ListAgents` for in-process subagents and peer sessions; note the ones this session started and their models.
2. For each remote lane dispatched this session, read its pane or status line for the model name.
3. Check machine defaults that could override the rule: `"model"` in `~/.claude/settings.json` on each machine sessions are launched on. Report it; change it only if the operator asks.
4. Report per agent: model, judgement or collection, and action taken; then the Fable count out of 3.

## Notes

- This rule covers delegated work; it does not change the operator's own interactive session model.
- History: before 2026-11-10 `/fable` was an alias for the `zero-framework-cognition` skill (unchanged, still available under its own name; old alias text in `SKILL.md.bak-20261110`). The first version of this rule that day was "Fable only" (`SKILL.md.bak-20261110b`); the operator revised it to "Fable as needed, max 3, rest Haiku".
