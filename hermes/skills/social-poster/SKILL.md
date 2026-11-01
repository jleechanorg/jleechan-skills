---
name: social-poster
version: 0.1.0
description: |
  Discover relevant Reddit communities and existing Reddit/X discussions for
  each source post; draft standalone posts or tailored replies. Reddit and X
  are the default destinations. Other supported platforms are explicit opt-ins.
  Draft requests never auto-stage or publish. Publication requires explicit
  authorization for reviewed content, account, and destinations.
when_to_use: |
  Use when the user asks to draft a post for any social platform, share a project
  on LinkedIn/HN/Twitter, post to Reddit, prepare a Show HN, draft an Instagram
  caption, or any "draft a post" / "post to <platform>" / "share on social" /
  "/social <intent>" request. Also fires on "/social <intent>" slash command.
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
  - Grep
triggers:
  - "draft a social post"
  - "draft a post"
  - "post to social"
  - "post to linkedin"
  - "post to hacker news"
  - "post to reddit"
  - "post to twitter"
  - "post to threads"
  - "post to facebook"
  - "post to instagram"
  - "draft linkedin post"
  - "draft hacker news post"
  - "draft reddit post"
  - "draft tweet"
  - "draft twitter thread"
  - "draft instagram caption"
  - "draft threads post"
  - "show hn"
  - "social poster"
  - "/social"
context: inline
---

# Social Poster — Draft-Only, POST APPROVED Gated

## Request scope and supported access (takes precedence over legacy recipes)

Default research, drafting, staging, and publishing destination allowlist:
`reddit,twitter` (`x` is an alias for `twitter`). LinkedIn, Instagram, Facebook,
and **Meta Threads** are excluded unless explicitly selected in the current
request. “X threads” means discussions on Twitter/X, never Meta Threads.
Other supported platforms remain explicit opt-ins. A supplied source URL may
be read as source evidence without opting its platform into destination research.

Pass the same resolved allowlist to the drafter's `--platforms`, stagers'
`--only`, and publisher's `--platforms`. Omitted script flags default to
Reddit/X, even if a directory contains old excluded-platform drafts. Never
infer opt-in from stale files, manifest history, or enabled cross-share toggles.
For Instagram, keep Threads/Facebook cross-share disabled unless each is
explicitly selected; stop if that cannot be verified. Selection does not grant
publication permission.

`reddit` selects the Reddit family; `reddit_example` selects only r/example.
The drafter accepts either form. `--reddit-subs` narrows the Reddit targets;
without it, scoped selections name their own targets and a bare `reddit` creates
an untargeted local draft. For example, `--platforms reddit_example
--reddit-subs example,sibling` produces only `reddit_example.md`. Disjoint
subreddit selections and empty/invalid allowlists are errors, not successful
empty draft runs. The publisher intersects token and flag scopes symmetrically:
`POST APPROVED reddit_example` plus `--platforms reddit` still authorizes only
`reddit_example`, never sibling communities. An empty intersection exits with
an error before submission; it cannot fall back to default permission.

The latest request controls the action: **draft/research means discovery and
local drafts only**, with no auto-staging, scheduling, or publishing. Stage only
when requested. Publish only reviewed content to the verified account and
selected destinations after explicit authorization; preserve any independently
required tool confirmation. A prior approval does not override a later draft
request. No magic user phrase is required; legacy tokens are internal bookkeeping.

Use supported read-only search, authorized connectors, or the normal browser
session. Stop and report access limits rather than extracting cookies/tokens,
copying credentials, decrypting browser stores, or using hidden API fallbacks.
Do not run `cookie_inject_and_stage.py` or legacy credential/fallback recipes.
These rules apply to every platform and all referenced historical notes.

## Phase 0 — Per-source discovery (agent workflow, not a crawler)

For **each input source URL**, independently:

1. Inspect the original post, author, full text, linked context, and original
   photo/video. Record what was actually visible and any inaccessible media;
   search snippets are leads, not proof the full source was read. Do not invent
   details or reuse the announcement template for unrelated commentary.
2. Find relevant Reddit communities **and specific existing Reddit/X threads**.
   Search by the source's topic, claims, terminology, and canonical links.
   Open candidate discussions, verify their original and latest activity dates,
   and read enough context to explain relevance. Prefer active discussions;
   label older threads, locked/archived threads, and any uncertainty.
3. **Mandatory Reddit promotion-rule gate:** before recommending a destination or drafting for it,
   verify current subreddit-specific rules and pinned guidance for promotion eligibility,
   affiliation disclosure, required flair, frequency/duplicate limits,
   AI/bot restrictions, account eligibility (such as age, karma, or prior
   participation), and link policies. Record each rule source URL and check date,
   relevant restrictions, and a disposition: `allowed`, `conditional`,
   `prohibited`, or `unverified`. For `conditional`, identify the conditions and
   verify that the proposed content and intended account satisfy them before
   recommending or drafting. If rules or account eligibility are inaccessible or ambiguous,
   do not assume promotion is allowed: mark the destination `unverified` and
   withhold a destination-specific promotional draft, or choose a verified alternative.
   Skip prohibited promotion even if the community was explicitly requested.
   Historical rule tables are leads only, never current verification. Passing
   this gate does not grant publication permission.
4. Inspect the intended user's prior posts **and replies** for matching source
   links, text/media, or the same topic in each candidate community/thread.
   Record existing permalinks and the history window searched. If identity or
   history access is missing, mark duplicate checking incomplete, do not claim
   no duplicates, and do not publish until the uncertainty is resolved.
5. Choose a new **standalone post**, a useful **tailored reply**, or **skip** for
   each target. Replies must answer the actual discussion and add value; avoid
   promotional link drops or repeating the user's existing contribution.
   Return an existing matching permalink instead of another copy, even if
   publishing was approved. Recheck live history immediately before any
   authorized submission and after uncertain outcomes before retrying.
6. Hand-author source-faithful drafts for the chosen targets. Use separate local
   directories per source if invoking the single-source template CLI. The CLI
   does not search, inspect media, verify rules/dates, or check account history;
   its manifest explicitly reports `discovery_status: not_performed`.

### Per-source discovery output contract

Return a separate section keyed by **every input source URL**, including sources
that are blocked or have no suitable targets. Do not pool multiple source posts
into a single unmapped recommendation. Each section must include:

- Source URL, verified source summary, original media inspection and access limits.
- For each target: platform, exact community URL and exact existing thread URL
  (for replies), discussion date/latest activity, relevance, current rules URL
  and checked-at date, flair/link constraints, and prior-user-post/reply evidence.
  For Reddit, include the promotion disposition (`allowed`, `conditional`,
  `prohibited`, or `unverified`) and evidence for any eligibility conditions.
- Decision: `standalone`, `reply`, `existing`, or `skip`, with rationale. Include
  the exact existing permalink when found; no duplicate draft for that target.
- The complete tailored draft (Reddit title/body for standalone; reply text for
  replies), explicitly mapped to its target URL and source URL. Standalone
  targets use the community URL, not an invented future post permalink.
- Coverage limits: searches and history window actually checked, inaccessible
  sources/media/rules/history, unverified dates, and platforms excluded by scope.
  If no suitable target exists, say so; never fabricate links or search receipts.
- State: `draft only`, `staged` only with verified requested staging evidence,
  or `published` only with an authorized, verified final permalink.

This is a procedural output contract. Offline instruction tests can check that
it is present; they cannot establish that a real discovery run occurred.

## Twitter/X browser workflow

This section takes precedence over generic staging/auth recipes for Twitter/X.
Draft and stage requests remain unpublished. An ordinary explicit request such
as "Cross post this to Twitter" authorizes publishing the identified, reviewed
content to the intended account and destination. Do not require the user to
repeat a magic phrase. Ask only for missing content/account/destination details
or confirmation independently required by the active tool or policy. Material
changes to the approved content or destination need renewed approval.

`POST APPROVED` is an internal execution token for legacy publisher scripts,
not a required user phrase. Supply it only after recording the actual user
instruction and verified account/content, and always pass the selected platform
allowlist; never use the token to manufacture permission. If an active tool or
policy requires separate confirmation, obtain it normally. Invocation, login,
and staging alone do not authorize posting, and no future posts are approved.

1. Reuse a supported browser session and inspect the signed-in handle before
   drafting or staging. If signed out, prefer the normal **Continue with Google**
   flow when offered, select the intended existing Google account, and verify
   the resulting X handle. A Google email alone does not prove the X identity.
2. For a normal login failure, try one supported recovery (return to the official
   login page or select the intended existing account), then report the exact
   blocker. Stop for human-only challenges or denied actions. Never extract or
   decrypt cookies, tokens, passwords, or browser credential stores; never bypass
   access denial or switch to a hidden API to work around a blocked UI.
3. Read the source post and retain its original text and original photo/video
   when requested. Verify the uploaded media preview; do not silently replace
   the original asset with a screenshot or omit it. Report inaccessible media.
4. Inspect the verified account's recent posts for the source link and matching
   text/media before submission. If a matching post exists, return its permalink
   rather than creating a duplicate. If history cannot be checked, resolve that
   uncertainty before posting. Recheck after any timeout or uncertain submission
   before retrying; a timeout is not proof that posting failed.
5. Before shortening text or building a thread, check the current account's
   composer for supported long posts. When the full source fits, prefer one post
   with the original media unless the user requested a thread. If it does not
   fit, prepare a faithful shorter draft or thread for review. Do not assume a
   subscription or a fixed limit from an old template; verify the full text
   remains in the composer with no truncation or limit warning.
6. Verify the exact visible text, intended handle, and media before the gated
   publish action. Submit once. Then open the resulting permalink and verify
   the author handle, visible full text (expand when needed), and original media.
   Return the permalink with the verification result. A cleared composer or
   success toast alone is not proof; report an uncertain outcome without retrying
   until the profile/history check establishes whether the post exists.

## Contract

1. **Draft only by default** — produce discovery results and local drafts. No browser staging without a stage request and no publishing without explicit authorization.
2. **Supported browser session** — reuse the intended signed-in account and verify identity; do not copy credentials between browsers.
3. **Per-platform conformance** — character limits, title rules, hashtag placement, threading, self-promo ratios checked at draft time (no "fix it after posting").
4. **Current community rules** — verify live rules during Phase 0; `references/subreddit-rules.md` is historical guidance only.
5. **POST APPROVED token** — `scripts/post_approved.py` checks for literal `POST APPROVED` (or per-platform like `POST APPROVED linkedin,hackernews`) before clicking any submit button. Without the token, exits code 2 with "BLOCKED — no POST APPROVED token".
6. **No provider calls in the template CLI** — deterministic local text only. Discovery and tailored drafting are agent instructions, not an implemented search or LLM backend.
7. **No auto-stage on /social** — follow the latest request. Discovery/drafting stops before Phase 2 unless staging is requested.

## Supported Platforms

| Platform | Template | Has web compose? | Notes |
|----------|----------|------------------|-------|
| LinkedIn | `templates/linkedin.md` | ✅ | long-form + 300-char short variant |
| Hacker News | `templates/hackernews.md` | ✅ | "Show HN:" prefix when self-promo; title ≤80 chars |
| Twitter/X | `templates/twitter.md` | ✅ | single tweet + thread; hashtags at end of last tweet only |
| Reddit | `templates/reddit.md` | ✅ | one file per subreddit; text-post preferred over link-post |
| Threads | `templates/threads.md` | ✅ | ≤500 chars, casual |
| Facebook | `templates/facebook.md` | ✅ | medium-length, link-friendly |
| Instagram | `templates/instagram.md` | ⚠️ no web compose | caption + 30-hashtag block; surfaces mobile instructions |
| Mastodon | `templates/mastodon.md` | ✅ | 500-char default; configurable instance |
| Dev.to | `templates/devto.md` | ✅ | markdown article format |

## Phases

### Phase 1 — Draft (deterministic, no browser)

Run `scripts/draft_social_post.py` with intent + key-points + link + platforms. Produces per-platform files in `--out <dir>`. Character-limit hard-rejects; spam-rule soft-warns.

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/draft_social_post.py
python3 "$PY" \
  --intent "announce jleechanclaw open-source release" \
  --key-points "AI agent orchestration, hermes deploy pipeline, skill framework" \
  --link "https://github.com/jleechanorg/jleechanclaw" \
  --platforms reddit,twitter \
  --reddit-subs "LocalLLaMA,Rag,OpenAI" \
  --image "" \
  --out /tmp/drafts/social-2026-07-06/
```

Output: one `.md` file per platform (or per subreddit for Reddit). Filename-safe slugs.

### Phase 2 — Stage in Aside (browser, no auto-post)

**Prefer the MCP path (`stage_in_aside_mcp.py`) when available.** The `aside repl` CLI silently no-ops on programmatic paste (lesson #11; verified 2026-07-17 across 9/11 platforms failed despite "compose-ready" status). The HTTP MCP at 127.0.0.1:8013/mcp with `openTab()` + Playwright `locator().fill()` reliably pastes when the session is healthy.

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/stage_in_aside_mcp.py
python3 "$PY" --drafts /tmp/drafts/social-2026-07-17/
# allowlist sub-stage, e.g. only HN + Twitter for retry runs:
python3 "$PY" --drafts /tmp/drafts/social-2026-07-17/ --only hackernews,twitter
```

Falls back to the legacy `aside repl` script when MCP is unreachable:

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/stage_in_aside.py
python3 "$PY" --drafts /tmp/drafts/social-2026-07-17/
```

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/stage_in_aside.py
python3 "$PY" --drafts /tmp/drafts/social-2026-07-06/
```

**Contract (v3, 2026-07-11):** The script now enforces paste-and-verify. For each platform:

1. Opens a new Aside tab on the platform's compose URL.
2. Optional trigger click (LinkedIn "Start a post", Facebook "What's on your mind").
3. Pastes the draft into the relevant field via per-platform paste function:
   - `react_textarea` — vanilla `<textarea>` / `<input>` (Reddit, HN, Mastodon, Dev.to)
   - `exec_command` — contentEditable (Twitter, LinkedIn, Facebook, Threads); uses `document.execCommand('insertText', false, text)` after `el.focus()` — the only reliable pattern for React-controlled contentEditable fields.
4. **Reads the field back** with `verify_text(selector)` and compares against expected draft length (≥70% threshold to allow for trailing whitespace stripping).
5. Captures post-paste screenshot → `/tmp/drafts/social-2026-07-06/screenshots/<platform>.png`.
6. Sets status:
   - `"staged"` — paste verified, screenshot saved
   - `"paste_failed"` — compose form loaded but text didn't persist (user must paste manually)
   - `"login_wall"` — page is a sign-in screen, no paste attempted
   - `"load_only"` — Instagram (no web compose)
   - `"failed"` — Aside subprocess error (e.g. extension bridge dead)

The script will NOT claim a platform is "ready" unless the draft text was verified inside the field. Vision-verify at least one screenshot per platform after staging for a final cross-check.

**Aside recipes** for each platform's compose URL live in `references/aside-recipes.md`.

### Phase 3 — Surface to user

Return the per-source discovery output contract above, plus draft paths. Include screenshots only for requested, verified staging. Deliver in the current conversation unless another destination was explicitly requested.

### Phase 4 — Post (gated)

Only after the latest user request explicitly authorizes publishing the reviewed content, verified account, and selected destinations, complete the live duplicate check and tool confirmations, then run:

```bash
PY=$HOME/.hermes/skills/social-poster/scripts/post_approved.py
python3 "$PY" \
  --drafts /tmp/drafts/social-2026-07-06/ \
  --approval-token "POST APPROVED" \
  --publish-request \
  --platforms reddit,twitter  # always pass the current request allowlist
```

Behavior per platform:
- LinkedIn / HN / Twitter / Reddit / Threads / Facebook / Mastodon / Dev.to → click submit, capture post-URL.
- Instagram → surface draft caption as text + print mobile instructions (no web compose). Manual copy-paste from phone.

Posting log written to `--drafts/posted.json` with timestamps + captured URLs.
Completed, existing, and uncertain submissions in that directory are not retried.
For a live-discovered duplicate, record `{"status": "existing", "url": "<permalink>"}`
under its platform key in `posted.json` → `results` and return the permalink.
This local retry guard is not a live history search; Phase 0 and the pre-submit
live check remain required. Keep each source in its own draft directory.

## Safety Gates

1. **`POST APPROVED` required** — see `scripts/post_approved.py` `check_approval()` function. Hard exit 2 if missing.
2. **Current publish request** — `--publish-request` is an operator attestation of the latest explicit authorization, never supplied for draft/stage requests. Without it, existing drafts cannot be published even with a stale approval token.
3. **Per-platform allowlist** — `POST APPROVED linkedin` only posts LinkedIn. Comma-separated = OR. Default = Reddit/X only; flags cannot broaden a token allowlist.
4. **No silent failures** — any platform that fails to post writes to `posted.json` with `{"status": "failed", "error": "..."}`. User is notified.
5. **Audit log** — every draft run writes `--out/manifest.json` with timestamp, intent, platforms, character counts, spam-rule warnings.

## Historical subreddit leads (reverify current rules and relevance)

| Content type | Primary | Secondary | Tertiary |
|---|---|---|---|
| Open-source / local AI tool | r/LocalLLaMA | r/OpenSourceAI | r/singularity (opinion-only) |
| RAG / retrieval / vector DB | r/Rag | r/LocalLLaMA | — |
| Coding agent / dev tool | r/OpenAI (text post) | r/LocalLLaMA | — |
| General AI news / opinion | r/OpenAI | r/LocalLLaMA | r/ClaudeAI (Claude-specific) |

**Banned / avoid:**
- r/AItools, r/AutoGen, r/LMStudio → banned subs.
- r/singularity, r/AGI, r/Futurism, r/MachineLearning → zero self-promo.
- r/philosophy, r/ProgrammerHumor → AI content banned outright.

## Anti-Patterns

- ❌ Auto-posting without `POST APPROVED` (bypasses the safety gate)
- ❌ Using `mcp__playwright-mcp__*` for localhost testing — use `aside` (signed-in session)
- ❌ Calling `aside show_browser` / headed mode without explicit opt-in (headless-only default)
- ❌ Hardcoding API keys in `draft_social_post.py` (LLM augmentation must route through `~/.hermes/config.yaml`)
- ❌ Stripping 10/90 framing from Reddit drafts ("I built this, here's the link") — guarantees removal
- ❌ Posting the same draft verbatim across Reddit subs (each sub has different norms; per-sub files required)
- ❌ Posting link-only to r/OpenAI — requires text post + context (verified rule)
- ❌ Clicking submit in Phase 2 (stage-only)
- ❌ **Treating `draft_social_post.py` output as final without reading it** — the templater hallucinates key-points into the wrong slots when the intent is a commentary/opinion piece rather than a project announcement (e.g. "Fable AI oneshot a 2D game" gets turned into "jleechanclaw does X"). **Always read every generated `.md` file before staging.** If templating misfires, hand-author the drafts directly (write `.md` files in `--out`) and re-run staging on the hand-authored files. Worked example: `references/fable-2d-game-2026-07-11.md`.
- ❌ **Trusting `stage_in_aside.py`'s "compose-ready" DOM verdict without vision-verification.** The script's DOM-detector only checks for selectors like `input[name="title"]`; it does NOT verify that the text was actually pasted into the field. Programmatic paste via React setter / contentEditable frequently fails silently on Twitter, LinkedIn, HN, and Reddit modals. After every staging run, vision-verify AT LEAST ONE screenshot per platform (`vision_analyze("Is the draft text visible in the compose field, or is it empty?")`). If empty, the compose form is loaded but paste didn't stick — user must paste manually from the `.md` files.
- ❌ **Trusting `listBrowserTabs()` as proof the platform is signed in** — it proves the *tab* is signed in, but `openTab(compose-url)` may still hit a session-revalidation redirect to a login wall (LinkedIn, Facebook, Dev.to, Mastodon, Threads all did this on 2026-07-11). The source-of-truth check is: vision-verify the staged screenshot shows a compose form with user avatar/handle visible, NOT a login wall.
- ❌ **Staging a Twitter draft that exceeds 280 chars (verified 2026-07-17).** The compose modal accepts arbitrary input but disables the Post button (red highlight + "-666" counter visible) once the limit is exceeded. The drafter must keep single-tweet drafts ≤280 chars; longer content needs a `--thread` flag that splits into N tweets. The default `templates/twitter.md` does NOT enforce this — check after drafting.
- ❌ **Splitting the staging workflow across multiple MCP `tools/call` invocations** (verified 2026-07-17). See lesson 19 — each `openTab` opens a fresh tab, so call 2's paste lands on a different form instance than call 1's open. Always bundle `(openTab → fill → verify → screenshot)` in ONE IIFE per platform.

## LinkedIn login-wall unblock signals (verified 2026-07-11)

When LinkedIn staging returns a "Welcome back" password screen, do NOT conclude LinkedIn is unreachable. Check for these one-click unblock signals in the screenshot before declaring the platform blocked:

1. **Google One-Tap prompt** (top-right overlay, dark gray box, "Sign in to LinkedIn with Google" + blue "Continue as Jeffrey" button) — one click unblocks the session.
2. **Continue with Google button** (white button below "Sign in" with Google G logo) — same OAuth flow, one click.
3. **Sign in with Apple button** — same UX as Google.

If any of these are visible AND the email shown matches `$USER@your-project.com`, the user can unblock LinkedIn in 1-2 clicks. Tell them which button to click.

If NO unblock signal is visible (just an empty password field), the session is fully expired and the user must type their password.

## Trigger → Action Map

| User says | Action |
|-----------|--------|
| `/social <intent>` or `draft posts for <URLs>` | Phase 0 per source + Phase 1, then return the discovery output contract |
| `draft + stage a post` | Phase 0 + Phase 1 + Phase 2 for selected targets |
| Explicit publish/crosspost request | Verify approval, account/content/destinations, live duplicates and any tool confirmation before Phase 4 |
| `revise the draft` | Revise local text only unless staging is requested |

For replies, use the exact reviewed thread/comment composer when staging is
requested. The legacy scripts open standalone composers; they do not support
reply targeting. Use a supported browser workflow or return manual-use drafts,
never stage a reply as a standalone post by accident.

## Summary delivery

Return results in the current conversation. If explicitly asked to send elsewhere,
use the supported connector and its permissions. On denied/unavailable access,
report the blocker; do not switch identity or use a hidden token/API fallback.

## Files

- `scripts/draft_social_post.py` — deterministic drafter
- `scripts/stage_in_aside.py` — opens Aside tabs + screenshots (legacy `aside repl` path — silent paste failure mode)
- `scripts/stage_in_aside_mcp.py` — **preferred**: opens Aside tabs + pastes via HTTP MCP at 127.0.0.1:8013/mcp. One MCP call per platform bundles open + paste + verify + screenshot on a single `page` object (avoiding the "fresh tab = lost paste" failure). Verified selectors for HN, Twitter, Mastodon, Reddit ×3, Dev.to, LinkedIn, Facebook, Threads (2026-07-17).
- `scripts/cookie_inject_and_stage.py` — legacy, prohibited in this workflow; do not execute.
- `scripts/post_approved.py` — gated publisher
- `templates/*.md` — 9 platform templates
- `references/subreddit-rules.md` — live-verified per-sub rules
- `references/platform-character-limits.md` — hard limits + soft guidance
- `references/aside-recipes.md` — `aside repl` snippets per platform
- `references/platform-session-status.md` — per-platform cookie injection + anti-bot results (verified 2026-07-05). Historical evidence only; do not execute cookie-injection recipes.
- `references/blog-post-to-gdoc.md` — recipe for "draft a blog post in Google Docs" (canonical `gws docs` path + local-markdown fallback when gws OAuth is unauthenticated).
- `references/aside-repl-session-state.md` — verified auth state per platform for `aside repl` workflows (2026-07-06). Includes the `listBrowserTabs()` live-tab probe recipe, the `document` scope-doesn't-persist-across-REPL-calls pitfall, and per-platform paste workarounds for LinkedIn contentEditable / Facebook click-first / Twitter thread pagination.
- `references/aside-repl-playwright-pattern.md` — verified `openTab()` returns a Playwright `Page` object with `screenshot()` (Buffer→base64), `evaluate()`, `locator()`, `frameLocator()`. Includes 6 working paste/click/inspect idioms. Source of truth for the 2026-07-06 staging rewrite.
- `references/fable-2d-game-2026-07-11.md` — worked example for commentary/opinion drafts (NOT project announcements). Documents the Fable 2D-game run, the templater failure mode, the vision-verify matrix, and the recommended workflow for future commentary runs.
- `references/fable-quota-skill-2026-07-15.md` — worked example for **commentary/opinion about a third-party capability + a personal artifact (gist/skills)**. Documents lessons 15 (`require('fs')` is not in the REPL; capture screenshots via base64 stdout redirect), 16 (Mastodon URLs: `/compose` is 404, use `/publish`), and 17 (LinkedIn share-box trigger has obfuscated classes; programmatic click fails). Its historical token fallback is prohibited by the supported-access rules above.
- `tests/test_*.py` — unit + integration tests
- `references/staged-vs-pasted-verification.md` — **CRITICAL**: how to verify drafts actually got pasted into compose forms (vs. just having the page loaded). Use the explicit "what text is in the field?" vision prompt + the verification snippet. The stage script's `staged: True` is not enough.
- `references/aside-mcp-cli-gmail-profile.md` — Aside automation via HTTP MCP at 127.0.0.1:8013/mcp with `mcp-session-id` header flow + gmail (u0) profile. Reusable Python client snippet. The most reliable automation path when the Chrome extension bridge is alive. **Includes the verified openTab + locator.fill() + screenshot pipeline, per-platform selector table for HN / Twitter / Mastodon / Reddit / Dev.to / LinkedIn / Facebook / Threads, and 7 stage pitfalls (MCP degradation, Reddit fragility, login walls, subprocess.run vs Popen) verified 2026-07-17.**

## Operator rules

Use the supported session; report unavailable staging without blocking drafts.
Verify actual visible text, account, media, and selected destinations before
claiming staging succeeded. Do not run historical credential-copy recipes.

## Critical lessons (from real sessions, not theoretical)

0. **`staged` ≠ `pasted`.** The stage_in_aside.py script labels every successfully-navigated compose form as "staged" even when the paste silently failed (React-controlled-field re-render ate the programmatic input). **Vision-verify the actual TEXT inside the title input + body textarea, not just the page state.** A logged-in compose form with empty fields looks identical to a logged-in compose form with empty fields — vision models will say "compose form ready" either way unless explicitly asked "what text is currently inside the field?" (lesson from 2026-07-11 Fable-2D-game run, user pushback: "all of those drafts are obviously wrong and just random login screens so youre not even close to working"). See `references/staged-vs-pasted-verification.md` for the verify-paste checklist + reusable paste verification snippet.

0a. **Use `--account u0` ($USER@gmail.com) for `aside repl` automation.** Default active is `u1` (your-project.com) and the extension bridge can be more brittle on that profile. Verified 2026-07-11 — user pushed "use $USER@gmail.com profile next time and use the mcp or cli its supposed dto work". See `references/aside-mcp-cli-gmail-profile.md`.

0b. **Aside HTTP MCP at 127.0.0.1:8013/mcp is the most reliable automation path** (when the extension bridge is alive). Tools surface: just `repl` (single tool wrapping the persistent JS REPL). MCP initialize handshake requires reading the `mcp-session-id` header from the response and sending it on subsequent calls + `notifications/initialized`. Top-level `await` is NOT allowed in the REPL — wrap in `(async () => { ... })();`. The REPL has persistent scope (vars persist across calls), `fs` module via `node:fs/promises`, `display()` for inline image preview, `sleep(ms)`, `fetch()` with user cookies. See `references/aside-mcp-cli-gmail-profile.md` for the full request flow + reusable client snippet.

1. **`aside account list` does NOT show per-platform auth state.** It only shows the active Google account ID. To gauge whether LinkedIn/Twitter/Facebook/etc. are actually signed in, run `aside repl "const tabs = await listBrowserTabs(); console.log(tabs.map(t => t.url).join(' | '))"`. A signed-in tab on the platform = the session is valid, even if a fresh `openTab(compose-url)` shows a login wall (compose-URL navigation may trigger session re-auth).

2. **`document` scope does NOT persist across `aside repl` calls.** Each call gets a fresh JS context. Multi-step workflows (open → click → paste → verify) must be bundled in ONE async IIFE in a single call. Screenshot via `annotatedScreenshot(pageObj)` returned from `openTab()`, not `annotatedScreenshot(null)`.

3. **Programmatic paste into LinkedIn/Twitter/Facebook compose modals is unreliable.** Twitter's textarea + React setter trick works in a single bundled call. LinkedIn's contentEditable div + `el.innerHTML = text` works but React state may not sync (manual paste is more reliable). Facebook requires click-first on "What's on your mind, [Name]?" before the modal opens. **When staging is requested and paste fails: report the empty composer honestly and return manual-use drafts.** This avoids the React control gymnastics entirely and the user still gets visual proof the compose UI is loaded.

4. Publishing requires explicit current authorization; the script token is internal bookkeeping, not a magic user phrase.

5. **`aside session` ≠ `account list` ≠ Chrome cookie DB.** The source of truth is `listBrowserTabs()`. If the user says "I'm signed in to LinkedIn", verify with that probe before declaring a platform unreachable.

6. **`openTab(url)` returns a Playwright `Page` object**, not a serializable tab descriptor. Use `p.screenshot()` directly (returns a Buffer that base64-encodes for stdout), or `p.locator(...)` / `p.evaluate(() => ...)` for DOM ops. `annotatedScreenshot(null)` throws `Cannot read properties of null (reading 'snapshot')`; `annotatedScreenshot(pageObj)` works but `p.screenshot()` is simpler. See `references/aside-repl-playwright-pattern.md` for the verified idioms.

7. **Reddit compose URL must end in `?selftext=true`.** `https://old.reddit.com/r/<sub>/submit` lands on the link-post form by default, which navigates through the "link vs text" tab UI and triggers a session re-auth redirect. The `?selftext=true` param lands directly on the text-post form with title (textarea[name="title"]) + body (textarea[name="text"]) fields visible. `stage_in_aside.py`'s compose URL for Reddit MUST include this param. Verified 2026-07-06 for r/LocalLLaMA, r/OpenAI, r/Rag — all three compose forms loaded immediately with no auth redirect when the `?selftext=true` suffix was used.

8. **Vision-verify compose-vs-login, don't DOM-detect.** A DOM-only check like `document.querySelector('input[name="title"]')` can give false negatives if the page is still loading. The deterministic check is `p.screenshot()` → save → `vision_analyze(image_url, "Is the compose form for posting to r/X visible, with title input and body textarea? Or is it a login wall?")`. The user said "Many of these screenshots are login screens I wanna find the draft post screen / Still not good enough" on 2026-07-06 — the lesson: ALWAYS confirm by vision, never trust URL or DOM-only state when the user wants visual proof.

9. **Aside daemon restart = sessions break.** If `aside repl` returns "fetch failed" and you `pkill -f AsideDaemon` to recover, all open tabs are lost. Subsequent `openTab()` calls hit login walls even though the underlying Chrome cookie DB still has valid sessions, because Aside's tab-object state is gone. `listBrowserTabs()` returns `TOTAL_TABS 1` (a single fresh tab) instead of the prior 17-tab state. **Fix:** instead of `pkill`, try `open -a "Aside"` first — sometimes the daemon recovers without losing tabs. If you must restart, plan for a sign-in re-pass on platforms that were "previously signed in."

10. **`draft_social_post.py` cannot tell a project announcement from a commentary/opinion piece.** When the source URL is a personal reaction to a third-party capability (e.g. "Fable AI oneshot a 2D game from my text sim"), the templater will hallucinate the user's open-source project as the subject and stuff every key-point into the wrong slot. **Always read every generated `.md` before staging.** If misfires, hand-author directly into the same files. Worked example: `references/fable-2d-game-2026-07-11.md`.

11. **Compose-ready ≠ paste-stuck (re-confirmed 2026-07-11).** Even when the compose form is loaded and vision-verified, programmatic paste via React setter / contentEditable frequently fails silently on Twitter, HN, Reddit, and LinkedIn. After staging, vision-verify ONE screenshot per platform with the question "What text is actually in the compose field? Empty or has content?" If empty, the form loaded but paste didn't stick — surface this to the user as "compose form ready, paste manually from the `.md` file." Do NOT claim the draft is staged-and-pasted when the field is empty.

12. **`web_extract` cannot fetch LinkedIn post bodies (re-confirmed 2026-07-11).** The `ddgs` backend returned `ddgs is a search-only backend and cannot extract URL content`. Workaround: `curl -A "Mozilla/5.0 ... Chrome/126.0.0.0 ..." <linkedin-url> -o /tmp/post.html`, then `python3 -c "import re; m = re.search(r'<meta[^>]+property=\"og:description\"[^>]+content=\"([^\"]+)\"', open('/tmp/post.html').read()); print(m.group(1) if m else 'NONE')"`. LinkedIn embeds the full post body in og:description.

13. **Aside MCP `repl` tool: SKIP `notifications/initialized` (verified 2026-07-11).** The MCP initialize handshake works, but if you send `notifications/initialized` after the initialize, subsequent `tools/call` requests return `Bad Request: No valid session ID provided` even though the session-id header is correctly attached. **The working pattern:** init → read `mcp-session-id` from response header → call `tools/call` immediately, skip `notifications/initialized`. Also: use top-level `await` directly in REPL code (the REPL is in module mode) — DO NOT wrap in `(async () => { ... })();` IIFEs because the IIFE swallows `console.log` output via the SSE stream. Top-level `console.log('HELLO')` works synchronously; `await fetch('https://api.ipify.org')` then `console.log(await r.text())` works async.

14. Legacy cookie-injection recovery is prohibited. Use normal supported login or return drafts with the access limitation.

15. **`require('fs')` is NOT available in the Aside REPL (verified 2026-07-15).** Trying `require('fs').writeFileSync(...)` inside `aside repl` returns `Error: External modules are not available in the REPL.` The screenshot Buffer from `p.screenshot()` cannot be saved directly from inside the REPL. **The verified pattern** — capture the base64 via `console.log` then grep+decode in the parent shell:

```bash
aside repl "
const p = await openTab('<url>');
await sleep(3000);
const ss = await p.screenshot();
console.log('SCREENSHOT_B64:' + ss.toString('base64'));
" > /tmp/out.txt 2>&1
grep '^SCREENSHOT_B64:' /tmp/out.txt | sed 's/^SCREENSHOT_B64://' | base64 --decode > /tmp/shot.png
```

This works because top-level `await` is allowed directly in the REPL (no IIFE wrapper needed — see lesson 13). For multi-platform staging loops, wrap in a Python `subprocess.run` loop that parses each `SCREENSHOT_B64:` line and decodes to disk.

16. **Mastodon URLs: `mastodon.social/compose` is a 404; use `mastodon.social/publish` (verified 2026-07-15).** Old docs and recipes reference `/compose`, but the modern Mastodon (v4.x) instance returns a 404 Not Found for that path. The compose preview lives at `/publish`. **Caveat:** `/publish` shows the compose form to unauthenticated users, but the "Post" button won't work until you sign in. Verify session state with vision ("Login / Create account buttons visible on the right?") before staging. Other instances (e.g. `mastodon.social/@user`) have different canonical paths; check the instance's help docs.

17. **LinkedIn share-box trigger uses obfuscated class names that defeat programmatic clicks (verified 2026-07-15).** `.locator('button[aria-label*="Start a post"]')` returns 0 matches. Click-by-text (`document.querySelectorAll('button').forEach(el => { if (el.textContent.includes('Start a post')) el.click() })`) also returns 0 — LinkedIn renders the "Start a post" box as a `<div>` with `role="button"` and randomized class names like `share-box-feed-entry__closed-share-box`. After 3 failed attempts (locator, click-by-text, click-by-placeholder), the recommended path is: **tell the user "click 'Start a post' manually, then paste from linkedin.md"**. Same fallback applies to Threads (sometimes), Facebook (modal requires click on "What's on your mind, [Name]?" first), and Instagram (no web compose at all).

18. **`aside repl` CLI silently no-ops on programmatic paste — use Aside HTTP MCP instead (verified 2026-07-17).** Switching the staging script from `aside repl "..."` to the HTTP MCP at `127.0.0.1:8013/mcp` is the difference between 9/11 platforms stuck at "compose-ready with empty fields" and 3/11 platforms actually having the draft text in the field. The `aside repl` path looks identical — every `await loc.fill(...)` returns without error — but the field stays empty because the underlying Chrome DevTools clipboard-write hook is silently disabled in that mode. Use `scripts/stage_in_aside_mcp.py` as the canonical staging entry point; treat `aside repl` paste as a known-broken path.

19. **Bundle open + paste + verify + screenshot in ONE MCP call per platform, never split (verified 2026-07-17).** Each `openTab(url)` opens a fresh tab. If the JS code is split across multiple MCP calls — call 1 opens the tab, call 2 types, call 3 verifies — the typed text is lost because call 2's `openTab` reopens a new tab on the same URL, which resets the compose form. The fix is one MCP `tools/call` per platform wrapping `(async () => { openTab → fill → verify → screenshot })()` in a single IIFE; the screenshot base64 emits on a separate `SHOT_<var>:` line so the companion `RESULT_<var>=<json>` line stays small enough to parse reliably.

20. **MCP server at 127.0.0.1:8013/mcp degrades after ~6-8 bundled calls (verified 2026-07-17).** Symptom: subsequent `tools/call` requests return 0 bytes (no SSE error, no console output, the curl process times out after 180s with empty body). Cause: Chrome / Aside daemon contention from too many open tabs / `playwright.Page` handles held across calls. Recovery: `pkill -9 -f aside` then `open -a "Aside"` and wait 10s; `aside account use u0`; `openTab <warmup-url>` once to confirm the window has focus; re-run. Or, if the same script that worked minutes ago now returns empty, restart Between MCP sessions — every fresh session starts healthy.

21. **Reddit's old.reddit.com form is fragile — fill sometimes hangs Chrome entirely (verified 2026-07-17).** Symptom: `locator.fill()` for `textarea[name='text']` on `/r/X/submit?selftext=true` triggers an indefinite Chrome hang (no MCP response after 60s+). The same code works for HN (`textarea[name='text']`) and Mastodon (`<textarea>`) — the difference is old.reddit's anti-spam heuristics. Workaround: run each Reddit subreddit in its own fresh MCP session, fill title first, then body in a separate call. If the body fill still hangs, surface the draft `.md` file to the user for manual paste.

22. **Login walls silently reappeared for LinkedIn / Facebook / Threads / Dev.to with Chrome profile u0 = $USER@gmail.com (verified 2026-07-17).** Earlier sessions (2026-07-11) reported these platforms as "signed in for the session via fresh `openTab`"; the cookies appear to have rotated or expired between sessions. Symptom: `openTab` on the compose URL redirects to the platform's sign-in form (Dev.to shows `input#user_email` + `input#user_password`; LinkedIn shows "Welcome back" page). Fix: one-time manual login in the Aside GUI, then re-run staging — u0 cookies refresh for the next 24-72h. If login is unavailable, return local drafts and report the blocker.

23. **Use `subprocess.Popen + .communicate(timeout=...)`, NOT `subprocess.run(timeout=...)` for MCP `curl` calls (verified 2026-07-17).** `subprocess.run(..., timeout=180)` silently drops output if the curl process writes its SSE bytes between Python's timeout firing and the process exiting cleanly. `Popen` + `communicate(timeout=180)` captures the same data. Indistinguishable on a happy path; visible failure mode is `len(out) == 0` after a "successful" call.

24. **Always vision-verify the actual TEXT inside the field after staging (verified 2026-07-17 re-confirmation).** The HN stage reported `paste: ok=true, len=1131` via the verify step, but the saved screenshot showed only the last 2 sentences of a multi-paragraph body. Playwright's `locator.fill()` silently truncates on certain React-controlled textareas when the input exceeds ~1000 chars and the field has not been focused first. The fix is `await loc.click(); await sleep(300); await loc.fill(text)` (already in `stage_in_aside_mcp.py`), BUT vision-verify is the only reliable cross-check — the verify step reads `document.querySelector().value.length` which disagrees with what's actually visible after a re-render. Always end Phase 2 with one `vision_analyze` per platform asking "what text is currently in the field?" before declaring success.
