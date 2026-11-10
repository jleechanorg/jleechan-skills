# Harness optimization mode (`/harness --optimize`)

Use this mode to review active coding-agent harness files and suggest useful,
small improvements. In scope: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, skills,
agents, slash commands, and their discovery metadata. It retains the mandatory
analysis requirements that apply to the finding and the shared Step 7 closure
in the parent skill.

## Scope guard

The product is the instruction harness itself. Start from the named harness
files and keep proposed edits inside those surfaces. Do not turn this task into
an AO, beads, evaluation-corpus, notification, or general process project.

If most planned work does not directly inspect, test, or change instruction
surfaces, stop: the task has drifted.

## Review posture

1. Start from the active skill and command catalog descriptions. Read the
   bodies of selected high-traffic or ambiguous owners and references only
   when needed to answer a concrete question; do not expand context by default.
2. Batch cheap discovery with `rg`, metadata parsing, broken-link checks, and
   word counts.
3. Consult recent `/history` and `/ms` evidence for repeated corrections and
   concrete friction.
4. Read focused evidence for the highest-value findings; do not recursively
   expand context without a concrete question.
5. Rank ideas by expected agent-quality benefit, confidence, and change risk.
6. Prefer an existing canonical file over creating another skill or command.
7. Prefer small, reviewable change groups over broad prompt rewrites.
8. If evidence is weak or no improvement is worthwhile, report `no change`.
9. After editing, reread the active source and exercise the real path; a source,
   installed copy, or automation label alone does not prove behavior.

For a proposed or implemented change, record enough before/after evidence to
explain the decision. A frozen corpus, new gate, or organization-wide cleanup
campaign is not required.

## Weekly job contract

A weekly job may automate this mode. Keep it thin:

- inspect the authorized harness roots read-only;
- produce a short ranked list of optimization ideas with exact file evidence;
- open small, focused harness-only PRs when changes are high-confidence and can
  be validated with existing checks;
- otherwise publish the ideas or an explicit `no change` result;
- deliver the report and PR links through the already configured weekly
  Slack/email notification path;
- never make direct user-scope harness-source edits from the scheduled run;
- never require a frozen evaluation corpus, AO workers, or unrelated process
  changes as prerequisites. Step 7 is the same scoped closure after the work,
  not a prerequisite to inspection or permission for additional source edits.

The scheduler and delivery mechanism belong to the owning repository. They are
implementation details of this one weekly job, not a new harness workflow.

## Source principles

- [Dropbox: optimizing Dash's relevance judge with DSPy](https://dropbox.tech/machine-learning/optimizing-dropbox-dash-relevance-judge-with-dspy) — use measured evidence, make model-specific improvements, and constrain high-blast-radius prompt changes.
- [GitHub: better tools made Copilot code review worse](https://github.blog/ai-and-ml/github-copilot/better-tools-made-copilot-code-review-worse-heres-how-we-actually-improved-it/) — job-specific tool instructions matter; start from a narrow question; batch discovery; read focused evidence; use traces to diagnose context-expansion loops.
- [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) — favor lean prompts, state instructions once, expose only relevant tools, remove one instruction group at a time, and rerun representative evals before accepting a change.

## Output contract

Return:

1. a short ranked idea list with exact file evidence;
2. the recommended minimal change, if any;
3. validation evidence for any implemented change;
4. PR URLs when the weekly job opened any, or `no change`.

Unless invoked with `--fix` or separately authorized by the user, do not edit
the harness. Report the recommendation or `no change`, then complete Step 7 and
return to any already-authorized caller workflow.
