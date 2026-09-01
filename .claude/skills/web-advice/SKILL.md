---
name: web-advice
description: Browser-based multi-model advice and review using ChatGPT, Gemini, and Perplexity Web. Use for an independent external perspective on any subject, including PRs, designs, docs, plans, and decisions.
---

# /web-advice — Multi-Model Browser Review

`/web-advice` queries independent web LLMs (ChatGPT, Gemini, and Perplexity when available) through their web UIs in the user's authenticated browser, then synthesizes their advice. It can review or advise on any user-supplied subject: code and PRs, designs, documents, plans, decisions, research questions, UX, and operational proposals. This is **different from `/advice`**, which is in-session and uses subagents + /secondo + /research.

| Skill | Mechanism | When to use |
|---|---|---|
| `/advice` | In-session: subagent + /secondo + /research | Architectural reasoning, ZFC reviews, code-path analysis |
| `/web-advice` | Browser: ChatGPT + Gemini + Perplexity Web; Aside preferred, browser fallbacks supported | Independent external multi-model advice or review; visual/video context; web-search grounding |
| `/er` | In-session: evidence-standards skill | Evidence bundle integrity (4-gate checksum/SHA/real-services) |

## Real-Browser Transport Contract: Runtime-Specific

> [!IMPORTANT]
> **Zero Aside Inference Invariant (Strict Hard-Fail Rule)**:
> `/web-advice` MUST use browser navigation and DOM automation against the real
> vendor web-chat sites. In an interactive chat app, prefer that app's owned
> built-in browser and create a new vendor chat. In a coding CLI or Bash run,
> launch an isolated system-Chrome process through Playwright in strict
> headless mode, with freshly decrypted local browser cookies. Do not reuse a
> shared GUI tab as a CLI review transport.
>
> **NEVER use Aside inference** (`aside "..."` NL agent, `aside --effort ultrabrowse`, `aside exec`, `aside exec -m <model>`, or Aside's backend AI models).
> Aside inference consumes Aside's token quota / usage limits and does NOT use the operator's web chat subscriptions.
> The entire purpose of `/web-advice` is to navigate to the web chat interfaces (`https://chatgpt.com/`, `https://gemini.google.com/app`, `https://www.perplexity.ai/`) to leverage the user's active web chat subscriptions (ChatGPT Plus/Team/Pro, Gemini Advanced, Perplexity Pro) via the authenticated browser.
>
> **Approved transport ladders**:
> - **Interactive app:** `builtin_browser`, then `aside_mcp`, then `aside_repl`.
> - **Coding CLI/Bash:** `chrome_headless_cookies`, then `playwright_mcp`, then
>   `chrome_headless_cdp`.
>
> Each fallback must prove the affected vendor is authenticated, exposes a
> writable composer, returns the submitted prompt's real response, and supports
> the normal response/share evidence gates. A basic page render is not enough.
>
> **Banned substitutes**: Provider APIs, CLI models (agy, codex CLI), Aside inference (`aside exec`, `aside "..."` NL agent), in-session subagents, and WebSearch/WebFetch synthesis remain strictly banned.
> If no approved real-browser seat remains reachable, report every observed transport failure and stop `/web-advice`; do not launch or relabel an inference substitute.
>
> Before opening tabs and again before labeling captured output `/web-advice`, validate the selected transport:
> `python3 ~/.claude/skills/web-advice/scripts/web_advice_transport.py assert-transport aside_mcp`
> Use `aside_repl` instead of `aside_mcp` when driving the browser API through
> `aside repl`. For a fallback, pass the observed reason, for example:
> `python3 ~/.claude/skills/web-advice/scripts/web_advice_transport.py assert-transport chrome_headless_cookies --fallback-reason aside_unavailable`.
> If Aside can browse but cannot visibly attach the packet after one clean-chat
> retry, use the literal fallback reason `aside_upload_unavailable`.

For CLI/Bash execution, the direct runner starts a clean Chrome context and
uses vendor-specific upload controls. It records authentication, attachment
chips, submission, packet echo, and response separately; a response missing
the requested head SHA or any requested filename is not a completed seat.

Use `/web-advice` when an external multi-model perspective will help, especially when you want different model families to challenge a conclusion or when external web standards matter (e.g., D&D 5e SRD, Stately XState, industry patterns). Target three models (ChatGPT, Gemini, Perplexity), but synthesize the models that are available and disclose any coverage gap.

---

## Pre-Flight Checklist (run BEFORE opening any browser)

### Step 0a — Identify and ground the subject

```bash
# For a PR: identify the live head.
gh pr view <N> --json number,title,headRefName,headRefOid,state,url

# For an evidence bundle or production claim: locate the evidence.
ls -la docs/pr<N>-evidence/ 2>/dev/null
cat docs/pr<N>-evidence/metadata.json 2>/dev/null | python3 -m json.tool
```

Use the evidence appropriate to the subject: current diff and tests for a PR, the actual document for a document review, or stated assumptions and constraints for a plan or decision. Evidence is not a universal `/web-advice` gate.

### Step 0b — Verify evidence only when it is part of the request

Run the `/er` 4-gate check **only when an evidence bundle or production claim is in scope**—for example, when the advice must assess real-service proof or decide whether a bundle supports a production conclusion.

Invoke `/er <bundle path or PR>` and record its current-HEAD verdict. Do not
replace `/er` with a partial checksum, file-existence, or metadata check: those
checks do not establish the verifier verdict, claim coverage, or provenance.

If that verification fails, fail closed for the evidence or production claim: do not present it as verified, and regenerate it or run `/er` before relying on it. The broader code, design, document, or plan review may still proceed if its scope is clearly separated from the unverified claim.

### Step 0c — Build the review prompt & context packet (MANDATORY)

For code, patch, and PR reviews, you **MUST** generate and upload the complete lossless review packet:
1. **Raw Git Diff**: Exact unified diff against base branch (`git diff origin/main...HEAD > raw_git_diff.patch` or `build_review_packets.py`).
2. **Full Changed Files**: Complete source files at HEAD for every touched file (`full_changed_files.txt` or `build_review_packets.py` output).
3. **Full Evidence Manifest**: Test results, telemetry logs, or evidence bundles when applicable.

> [!CAUTION]
> **Private Repository Anti-Guesswork Invariant**:
> Never submit a bare PR URL or a 5-line summary for private repositories. Web models operate in external sandboxes without repository credentials, receive HTTP 404, and will fail or fabricate assumptions. You **MUST attach or upload the raw diff patch and full source files** so the models perform genuine line-by-line AST and concurrency analysis.

Build a concise prompt before opening the browser so you can paste the same request to each model. Include only the sections that apply.

```markdown
You are an independent expert advising on a [PR | patch | design | document | plan | decision | research question | other].

**Subject**:
- Type: [subject type]
- Identifier: [URL | path | concise question]
- Branch / Commit: [<branch> @ <sha>]
- Working directory: <absolute path>

**Attached Files / Context** (upload full files; do not truncate):
- `raw_git_diff.patch`: Exact unified diff of the PR against base branch.
- `full_changed_files.txt`: Complete source text for all changed files at HEAD.
- <relevant tests and evidence manifests>

**Review dimensions** (pick what applies):
1. Architectural soundness (state-machine compliance, ZFC consumer split, layer isolation)
2. Edge case safety (concurrent writes, time freeze, god mode, modal locks)
3. Evidence integrity and production-claim support (only if an evidence bundle or production claim is in scope)
4. Test coverage (structural vs rendered-text, multi-turn vs single-shot)
5. Web standards alignment (cite external sources)

**Required output format** (verbatim):
VERDICT: APPROVED | APPROVED with notes | CHANGES REQUESTED | REJECTED
REASONING: 3-4 sentences quoting specific files and lines from the attachments
RISK: main risk, one sentence
CONFIDENCE: high | medium | low
COVERAGE: exact filenames from the attached packet actually read; write `none` if unavailable
WEB SOURCES: 1-3 URLs with one-line summaries (if you cited any)
```

The prompt should be materially the same for each model; adapt only for a model's input limits or required UI format.

---

## Browser Execution Protocol

First resolve the transport ladder. On macOS, probe Aside first. On non-macOS
hosts, or after both Aside routes are unavailable, continue through the
approved browser fallbacks. The examples below use Aside's Playwright-shaped
API; apply the same selectors and evidence checks to a Playwright `Page` when a
fallback is selected.

### Step 1 — Open 3 tabs

```javascript
// In aside-mcp repl (mcp__aside-mcp__repl tool)
await openTab('https://gemini.google.com/app');
await openTab('https://chatgpt.com/');
await openTab('https://www.perplexity.ai/');

const allTabs = await listBrowserTabs();
console.log('opened:', allTabs.length, 'tabs');
for (const t of allTabs) console.log(' -', t.title, '(', t.url, ')');
```

For Aside, expected output is 4 tabs (your existing tab + 3 new vendor tabs). A fallback
may use separate pages or contexts, but must report the selected transport and
the per-vendor authentication result.

### Step 2 — Verify auth state (CRITICAL)

```javascript
// Attach to each tab and check login state
const tabs = await listBrowserTabs();
const gemTab = tabs.find(t => t.title === 'Google Gemini');
const gemPage = await attachBrowserTab(gemTab.targetId);
const gemSnap = await snapshot(gemPage);
const geminiLoggedIn = !gemSnap.tree.includes('Sign in') && !gemSnap.tree.includes('Log in');
console.log('gemini logged in:', geminiLoggedIn);
```

**Repeat for ChatGPT and Perplexity.** If any model is not logged in, **stop and ask the user to log in** — do NOT try to log in for them (no credentials, no auth cookies, no OAuth flow). Login state per model:

- **Gemini**: Logged in shows "Google Account: <email>" in the sidebar
- **ChatGPT**: Logged in shows "Log in" button HIDDEN; prompt textbox visible. **Heads up:** ChatGPT may show the marketing landing page ("Where should we begin?") with a "Log in" button even when a session cookie exists, depending on cookie state. If the textbox is missing OR the page shows "Sign up for free", the session is genuinely gone — ask the user to log in. Try navigating to `chat.openai.com` as a fallback URL.
- **Perplexity**: Logged in shows username in the top-right corner (e.g., "jleechan77861") AND a "Sessions" sidebar with prior chats

If the user can't log in to one model, run /web-advice with the others as long as at least two providers remain authenticated (2-of-3 still satisfies the multi-model adversarial requirement when the two models are from different families) and note the gap in the synthesis. If fewer than two providers are authenticated, **stop and ask the user to log in** — do NOT try to log in for them (no credentials, no auth cookies, no OAuth flow).

### Step 2b — Create a clean chat and prove packet attachment (MANDATORY)

Create a new or temporary chat for each seat. Inspect the composer before the
chooser opens: a stale draft or unrelated attachment invalidates the attempt.
For `aside repl`, stage files inside that Aside session before opening its file
chooser; it rejects paths outside the session directory. Never replace a
failed upload with a bare URL.

The only successful upload state is every exact packet filename rendered by
the composer. A no-exception `set_input_files()` result, local file size, a
thumbnail, or truncated body text is not proof. The headless cookie fallback
has a report-producing runner:

```bash
python3 ~/.claude/skills/web-advice/scripts/playwright_cookie_driver.py \
  --site chatgpt --storage-state /tmp/chatgpt-storage.json \
  --prompt-file /tmp/review-prompt.md \
  --attachment /tmp/web-advice-packets/PR_<N>_FULL_CODE_FILES.txt \
  --attachment /tmp/web-advice-packets/PR_<N>_BASE_CODE_FILES_AND_DIFF.txt \
  --output /tmp/chatgpt-review-report.json
```

Require `assert_packet_attachments_verified(manifest, report)` to pass before
sending or recording a verdict. If the UI disables uploads, requests an
upgrade, or the rendered-name set is incomplete, retain the literal vendor
reason and retry only once in a clean chat.

### Step 3 — Submit prompt to each model (sequentially, not parallel)

Submit one model at a time. Submitting in parallel can hit rate limits or trigger captchas. Wait for each response before submitting the next.

**Pattern (proven to work):**

```javascript
// For Gemini (the locator ref varies — use aria-label selector)
const gemPrompt = `<your 4-section review prompt>`;
const gemTabs2 = await listBrowserTabs();
const gemT = gemTabs2.find(t => t.title === 'Google Gemini');
const gemP = await attachBrowserTab(gemT.targetId);
const textbox = await gemP.locator('div[aria-label="Enter a prompt for Gemini"]');
await textbox.click();
await gemP.keyboard.type(gemPrompt, {delay: 3});  // 3ms per char, real typing
await gemP.keyboard.press('Enter');
console.log('sent to Gemini, waiting...');
// Wait for response — Gemini Pro typically takes 15-45 seconds
await new Promise(r => setTimeout(r, 30000));
const gemResp = await snapshot(gemP);
console.log(gemResp.tree);
```

**Gotcha — duplicated text:** If a prior prompt was inserted via `el.innerText = ...`, the textbox may show duplicated content. Always clear with `Cmd+A` + `Backspace` BEFORE typing the new prompt:

```javascript
await textbox.click();
await gemP.keyboard.press('Meta+A');
await gemP.keyboard.press('Backspace');
await new Promise(r => setTimeout(r, 500));
```

**Gotcha — TrustedHTML errors:** Don't use `el.innerHTML = ...`; Gemini's textbox uses Trusted Types. Use `el.innerText = ...` (which works) OR use `keyboard.type()` (which always works).

**Gotcha — ChatGPT send:** ChatGPT requires clicking the "Send message" button, NOT pressing Enter. After typing, locate and click it.

**Perplexity (proven working pattern):**

```javascript
// Perplexity textbox is a DIV with role="textbox" — NOT a <textarea>
// Selector that works: [role="textbox"]
const perpTabs = await listBrowserTabs();
const perpTab = perpTabs.find(t => t.title === 'Perplexity');
const perpPage = await attachBrowserTab(perpTab.targetId);
const textbox = await perpPage.locator('[role="textbox"]').first();
await textbox.click();
await perpPage.keyboard.type(reviewPrompt, {delay: 3});
await perpPage.keyboard.press('Enter');  // Enter submits; no separate button click
console.log('sent to Perplexity');
```

**Perplexity quirks:**
- Textbox is a `DIV` with `role="textbox"` and no `aria-label` — use the role selector, not the aria-label pattern
- After response, the new textbox ref changes (Perplexity regenerates the textbox element); always re-snapshot to get the fresh ref before the next prompt
- Perplexity answers include a `Sources` accordion (collapsed by default) and a `Pro` badge; responses are typically citation-rich — useful for "cite your web sources" requirements
- Perplexity defaults to "Search" mode (web-grounded); for code-only review, switch to "Reasoning" mode via the model selector button before submitting

### Step 4 — Capture responses

```javascript
// For each model, after the response finishes (look for the "regenerate" / "thumbs up" footer)
const respSnap = await snapshot(modelPage);
const respText = respSnap.tree;
// Parse for VERDICT:, REASONING:, RISK:, CONFIDENCE:, COVERAGE:
const verdictMatch = respText.match(/VERDICT:\s*([^\n]+)/);
const reasoningMatch = respText.match(/REASONING:\s*([^\n]+(?:\n[^\n]+){0,3})/);
const coverageMatch = respText.match(/COVERAGE:\s*([^\n]+)/);
console.log('verdict:', verdictMatch?.[1]);
console.log('reasoning:', reasoningMatch?.[1]);
console.log('coverage:', coverageMatch?.[1]);
```

Models don't always format in the exact section headers. If the regex misses, look for the verdict line in the visible response:

- **Gemini Pro**: Structured output, "Copy code" button visible, response in dedicated region
- **ChatGPT**: Most conversational, may not return structured output unless explicitly reminded
- **Perplexity**: Citation-rich, "Sources" accordion; "Helpful"/"Not helpful" footer; verdict usually at the end

**Parser fallback** if structured regex fails — re-prompt the model with: *"Reply with ONLY this exact format (no other text): VERDICT: <one line> | REASONING: <one line> | RISK: <one line> | CONFIDENCE: high/med/low | COVERAGE: <material actually read, or none>"*. This is the most reliable cross-model pattern.

### Step 4b — Interactive Follow-up & Clarification Loop (MANDATORY)

Web chat LLM review sessions are stateful and interactive, not single-turn scripts:
- If a model responds with questions, requests additional files, or asks for clarification on an unattached caller or dependency:
  1. **Do NOT terminate early or report an inconclusive verdict**: The review is still actively in flight.
  2. **Locate the requested context**: Extract the relevant files, function definitions, or caller paths from the workspace.
  3. **Reply in the active chat thread**: Type/upload the requested code or explanation directly into the existing browser tab session.
  4. **Wait for re-evaluation**: Allow the model to re-analyze the updated context and render its finalized, fully grounded verdict.

### Step 5 — Synthesize

```markdown
## /web-advice synthesis

| Model | Verdict | Confidence | Coverage | Key finding |
|---|---|---|---|---|
| ChatGPT | <verdict> | high/med/low | <declared material read> | <one line> |
| Gemini Pro | <verdict> | high/med/low | <declared material read> | <one line> |
| Perplexity | <verdict> | high/med/low | <declared material read> | <one line> (note: web-grounded, citation-rich) |

**Convergence:** <3-of-3 agree / all 3 agree / 2-1 split / other>
**Recommended action:** <APPROVE / approve with conditions / change requests>
**Open web sources cited:** <list URLs from Perplexity + any model that cited external standards>
```

**Decision rule:** 3-of-3 agreement is sufficient (or 2-of-3 if both verdicts strongly converge). 2-of-3 is acceptable when the two models are from different model families. If all 3 diverge, surface the disagreement to the user and ask which axis (speed / safety / cost) matters most. Perplexity's web grounding often breaks ties by surfacing external standards (D&D 5e SRD, RFC, etc.) that the other models lack.

---

## Failure Recovery

### Aside daemon disconnects

Symptom: `Task failed: fetch failed: other side closed. Aside daemon is not reachable — make sure Aside Browser is running, then retry.`

Recovery:
1. Check that the Aside Browser app is still running (not crashed)
2. Reopen any lost tabs: `await openTab('https://gemini.google.com/app')` etc.
3. Re-snapshot before each fill (refs are NOT stable across `attachBrowserTab` cycles)
4. If recovery fails 3 times, probe the approved browser fallbacks. Mark a seat
   unavailable only after its eligible browser routes fail, and report the
   exact errors for each attempted route.

### Captcha or rate limit

Symptom: a "I'm not a robot" or "You've reached your limit" page.

Recovery:
1. Stop the affected model — don't retry
2. Note the rate-limit in the synthesis
3. Continue with the other 2 models
4. If 2-of-3 already returned, synthesize and stop; if only one seat returned, report a single-seat result and the coverage gap without substitution

### Login required

Symptom: ChatGPT shows "Log in" button; Gemini shows "Sign in to continue"; Perplexity shows "Sign in" page.

Recovery:
1. **Do NOT attempt login** — no credentials, no OAuth flow
2. Stop and ask the user to log in manually
3. Continue with the other models
4. If only 1 model is logged in, that's a single-model review, not multi-model — note this in synthesis

### Packet upload unavailable

Symptoms: the chooser is disabled, the vendor asks for an upgrade, a file path
is rejected, or the composer does not render every exact packet filename.

1. Start one clean temporary/new chat and retry once.
2. For an Aside session-path rejection, stage the files in that session directory.
3. If still unavailable, do not submit a prompt or accept a verdict from that
   seat. Record the vendor condition; when switching from Aside to a browser
   fallback, use `aside_upload_unavailable`.

### Stale evidence (verification FAIL)

Symptom: `metadata.json:git_provenance.git_head` ≠ PR HEAD `headRefOid`.

Recovery:
1. Mark the evidence or production claim unverified; do not use it to support a recommendation.
2. Regenerate the evidence bundle against current HEAD.
3. Re-run `/er` before making an evidence-backed or production conclusion.
4. Continue or repeat the broader advice only if that is useful after the evidence is fresh.

---

## Scope notes

- `/advice` remains useful when the work is best handled with in-session repository analysis.
- `/er` remains the authoritative evidence-integrity workflow when a bundle or production claim must be verified.
- `/web-advice` is appropriate for any subject when external, independent model input is wanted; it does not require a PR, evidence bundle, or video.

---

## Token Budget

| Step | Tokens |
|---|---|
| Pre-flight + prompt build | ~2K |
| Browser session | ~5K (state management) |
| Per-model response | ~2-3K |
| Synthesis | ~500 |
| **Total** | **~13K** vs ~50-100K for full advisor() |

**~85-90% fewer tokens** than `advisor()` while still getting 3-model adversarial coverage.

---

## Reference

- Provenance: artifact `~/roadmap/2026-08-01-web-advice-and-evidence-review-guide.md` (Antigravity Genesis Coder, 2026-08-01)
- 4-gate pre-flight: `~/.claude/skills/evidence-standards/SKILL.md`
- Browser automation: Aside first; approved Playwright/Chrome fallbacks when
  Aside is unavailable or unsupported
- Companion skill: `/advice` (in-session multi-reviewer)
