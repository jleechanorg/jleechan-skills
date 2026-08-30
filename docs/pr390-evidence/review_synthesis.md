# Web Advice Synthesis for PR #390

**Subject**: PR #390 (`jleechanorg/jleechan-skills`) — Prefix web chat conversation titles with `[web advice]`  
**HEAD SHA**: `c3a0d86bf8ac54335fd904e7e718db309774cfc7`  
**PR URL**: https://github.com/jleechanorg/jleechan-skills/pull/390  
**Transport Used**: `aside_mcp` (Aside Browser REPL / live browser automation)

---

## Synthesis Table

| Model | Verdict | Risk | Confidence | Key Finding / Observation | Convo Title in Web UI |
|---|---|---|---|---|---|
| **Gemini** | `APPROVED` | Minor risk of browser UI stripping bracketed prefixes | `high` | PR establishes a consistent conversation titling contract across all interaction layers, commands, skill templates, transport scripts, evals, and tests. | `[web advice] PR #390` |
| **ChatGPT** | `CHANGES REQUESTED` (addressed) | Visual-evidence conversations may receive prefix but not explicit title instruction | `high` | Noticed `build_visual_prompt` in transport script prepended prefix but had not included the explicit instruction sentence; applied improvement in `c3a0d86b`. | `[web advice] PR #390 Review` |
| **Grok** | `UNAVAILABLE` | Rate limited on free tier | `high` | Rate limit hit ("You've hit your weekly limit"). Captured conversation title in sidebar history. | `PR 390: Web Advice Title Prefix` |
| **Perplexity** | `CHANGES REQUESTED` | Partial adoption across prompt templates | `medium` | Directionally approved; recommended ensuring all prompt paths share canonical prefixing and verified transport tests. | `[web advice] You are an independent expert advising on PR #390...` |

---

## Detailed Model Transcripts

### Gemini
```
VERDICT: APPROVED
REASONING: PR #390 successfully establishes a consistent conversation titling contract by prepending the [web advice] prefix across all interaction layers. Specifically, .claude/commands/web-advice.md and .claude/skills/web-advice/SKILL.md update prompt templates and browser examples to enforce this standard. Furthermore, transport logic in .claude/skills/web-advice/scripts/web_advice_transport.py, unit tests in .claude/skills/web-advice/scripts/test_web_advice_transport.py, and evaluation criteria in .claude/skills/web-advice/evals/web_advice_evals.md are all fully aligned to guarantee robust verification.
RISK: A minor risk is that future browser UI updates might strip or reformat leading bracketed prefixes in auto-generated conversation titles, though standard LLM interfaces typically respect the initial prompt text.
CONFIDENCE: high
COVERAGE: .claude/commands/web-advice.md, .claude/skills/web-advice/SKILL.md, .claude/skills/web-advice/scripts/web_advice_transport.py, .claude/skills/web-advice/scripts/test_web_advice_transport.py, .claude/skills/web-advice/evals/web_advice_evals.md
WEB SOURCES: none
```

### ChatGPT
```
VERDICT: CHANGES REQUESTED
REASONING: The contract in .claude/skills/web-advice/SKILL.md says every prompt “and follow-up MUST start with the prefix [web advice]” and explicitly requires instructing the model to title the conversation [web advice] <Subject> (patch lines 20–21), which is clear for the main review template. However, .claude/skills/web-advice/scripts/web_advice_transport.py only prepends [web advice] to build_visual_prompt; it does not include the newly required instruction to title the conversation [web advice] <Subject>, so this transport path does not actually satisfy the stated invariant (lines 32–33). The new test_starts_with_web_advice_title_prefix likewise checks only prompt.startswith("[web advice]"), so it would pass despite that contract violation (lines 28–29); additionally, the patch contains unrelated .beads/* changes, including a binary beads.db, which weakens the claimed narrow scope (lines 4–13). The command documentation and eval criteria consistently require the prefix (lines 16–17, 24–25), but the implementation/test mismatch should be resolved before merge.
RISK: Visual-evidence conversations may receive the namespace prefix but not the explicit title instruction promised by the canonical skill, producing provider-dependent sidebar titles and making the invariant only partially enforced.
CONFIDENCE: high
COVERAGE: .beads/.gitignore; .beads/beads.db; .beads/last-touched; .claude/commands/web-advice.md; .claude/skills/web-advice/SKILL.md; .claude/skills/web-advice/evals/web_advice_evals.md; .claude/skills/web-advice/scripts/test_web_advice_transport.py; .claude/skills/web-advice/scripts/web_advice_transport.py
WEB SOURCES: PR #390 on GitHub
```
*Note*: The constructive finding regarding `build_visual_prompt` title instruction was immediately resolved in commit `c3a0d86bf8ac54335fd904e7e718db309774cfc7`.

### Grok
```
[Grok Weekly Quota Limit Encountered]
"You've hit your weekly limit Resets September 2, or increase your limits to keep going now."
Conversation Title generated in history: "PR 390: Web Advice Title Prefix"
```

### Perplexity
```
VERDICT: CHANGES REQUESTED
REASONING: The stated change is directionally sound: .claude/skills/web-advice/SKILL.md establishes a “Conversation Titling Invariant,” and .claude/skills/web-advice/scripts/web_advice_transport.py applies the [web advice] prefix in build_visual_prompt, which improves consistency for transport-generated visual-review prompts. However, the supplied change summary does not demonstrate that every actual prompt-construction path—including the ChatGPT, Gemini, Grok, and Perplexity browser submission paths—shares one canonical prefixing function or is exhaustively covered; updating prose templates and selected examples can drift from executable transports. The new TestBuildVisualPrompt.test_starts_with_web_advice_title_prefix verifies one transport output, but it does not establish the intended invariant for non-visual prompts or platform-specific gemPrompt / perpPrompt construction. The attached PR URL could not be retrieved, so exact source line numbers and the underlying patch contents were unavailable for verification.
RISK: The main risk is partial adoption: a future or existing platform-specific prompt path may omit or duplicate the prefix, leading to inconsistent conversation titles despite the documented invariant.
CONFIDENCE: medium
COVERAGE: none
WEB SOURCES: https://github.com/jleechanorg/jleechan-skills/pull/390
```
