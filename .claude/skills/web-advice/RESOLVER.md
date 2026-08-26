# web-advice Skill Resolver (local)

Portable resolver entry for the `web-advice` skill. This file is the
skill-local equivalent so
`/skillify` item 6 ("Resolver trigger — entry in the skills resolver with
trigger patterns the user actually types") and item 7 ("Resolver trigger
eval") have something concrete to point at and test.

**Known-bug guidance (skillify SKILL.md, "Known Bugs in skillify Test Suite",
Bug 2):** the standard resolver-trigger regex used by trigger-eval tests is
non-greedy and stops at the first blank line after the heading —
`(name.*?)(?=\n\n|\n##)`. If trigger words live in a `**Triggers:**` sub-line
below a blank line, that regex silently misses them and the trigger eval
false-negatives. The fix: put **ALL** trigger words directly **on the heading
line**, not in a sub-line below it. This file follows that fix.

---

## web-advice — web advice, multi model review, ask chatgpt gemini grok perplexity, external model review, browser review, second opinion from the web

**File:** `~/.claude/skills/web-advice/SKILL.md`
**Command:** `/web-advice`
**Mechanism:** real browser sessions on the actual
ChatGPT/Gemini/Grok/Perplexity websites. Prefer `aside-mcp` or `aside repl`;
when Aside is unavailable or unsupported, use the approved Playwright/Chrome
browser fallbacks after proving vendor auth and a writable composer. Provider
APIs, CLI models, Aside inference (`aside exec`, `aside "..."` NL agent),
subagents, and WebSearch/WebFetch synthesis are BANNED substitutes — see the HARD-FAIL CONTRACT in SKILL.md.
**Distinct from:** `/advice` (in-session subagent + `/secondo` + `/research`
— see `~/.claude/skills/advice/SKILL.md`) and `/er` (evidence-standards
4-gate check — see `~/.claude/skills/evidence-review/SKILL.md`). `/web-advice`
is for an independent multi-model *browser* adversarial pass, not in-session
reasoning and not evidence-bundle integrity checking.
**Evals:** `evals/web_advice_evals.md` (skillify item 5, including happy-path,
honest-accounting, substitution, attachment, retrieval, and share-proof cases).
**Resolver trigger eval:** `evals/test_resolver_trigger.py` (skillify item 7).
**E2E transport smoke:** `scripts/e2e_smoke.sh` (skillify item 9, diagnostic
probe of Aside REPL first and clean Chrome headless when Aside is unavailable;
probe `aside-mcp` through its MCP tool and qualify vendor auth separately).
