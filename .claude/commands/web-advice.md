---
description: Get independent multi-model Web Chat advice or review for any subject, including PRs, designs, docs, plans, and evidence when applicable, via browser / aside-mcp
aliases: [webadvice]
type: command
execution_mode: immediate
---

# `/web-advice`

Thin command pointer for independent multi-model Web LLM advice or review (ChatGPT, Grok, Gemini Web, and other available providers) on any subject. Evidence verification is used only when an evidence bundle or production claim is part of the request.

## Usage

```bash
/web-advice <subject or optional-pr-number>
```

## Protocol

When invoked, load and follow the canonical skill at `~/.claude/skills/web-advice/SKILL.md`:

1. **Load Skill**: Read `~/.claude/skills/web-advice/SKILL.md` via `view_file`.
2. **Execute the canonical workflow**:
   - **Phase 1**: Context aggregation appropriate to the subject (for example: PR diff, design, document, plan, or video proof).
   - **Phase 2**: Browser Session Connection via `aside-mcp` (`gemini.google.com`, `chatgpt.com`, `grok.com`).
   - **Phase 3**: Structured prompt submission using applicable review dimensions.
   - **Phase 4**: Response Capture & Synthesis (multi-model verdicts table).
   - **Phase 5**: Synthesis and recommended next action; do not require universal model approval.
