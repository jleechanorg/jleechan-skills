---
name: browserclaw
description: Use the browserclaw CLI to capture browser traffic, infer API endpoints, generate Python clients, OR decrypt + inject Chrome cookies for session reuse. Use when asked to reverse-engineer a website, generate an API client from a HAR, or reuse a logged-in Chrome session in a Playwright browser.
agent_scope: Any AI agent (Codex, Claude Code, Hermes, AO)
---

# browserclaw

First apply `~/.claude/skills/browser-control/SKILL.md` § Personal browser isolation. The personal Chrome profile, cookies, and login state are off-limits. Cookie/session reuse below applies only to an explicitly authorized agent-owned source profile; existing personal sign-in is not authorization. Do not run legacy personal-profile examples as a fallback.

## What this skill covers

The `browserclaw` CLI (a single Python binary installed via `pip install -e .`) has two halves:

1. **Traffic capture + client generation** — record a Chromium session to a HAR, infer the API endpoints, emit a `requests`-based Python client + MCP tool definitions.
2. **Cookie decrypt + inject** — when the task explicitly authorizes local transfer, read one agent-owned source profile's Chromium Cookies DB, decrypt it with that source's matching macOS Keychain entry, and inject it into a task-owned Playwright context. Personal browser profiles and cookies are excluded.

This file documents the **cookies** subcommands. The capture / infer / generate flow is documented in `~/.claude/skills/browserclaw/SKILL.md` (legacy) and the upstream `browserclaw/SKILL.md`.

## ⚡ AUTH-GATED SHARE LINK — FIRE THIS ON FIRST REFUSAL (added 2026-07-20)

**Trigger (read this BEFORE running any anonymous fetch):** the user asks you to *read / save / summarize / extract / ingest / archive / make a PR from* the content of an auth-gated share link — `share.gemini.google/...`, `chatgpt.com/share/...`, `docs.google.com/document/d/.../edit` (restricted), `notion.so/...` shared page, vendor AI share dialog — AND an anonymous fetch (curl, `web_extract`, `browser_navigate` with no cookies) returns the vendor's sign-in shell with the content loaded client-side only after auth.

**Action (do NOT post an unblock menu, do NOT ask the user to paste the content):**

1. Run `browserclaw cookies decrypt` only on the one specifically authorized agent-owned source profile/DB, using its matching Safe Storage service/account and the guarded lifecycle in `~/.claude/skills/browser-control/SKILL.md`.
2. Run `browserclaw cookies inject` with `--browser-channel chromium --headless --wait-after-load 12 --print-text 100000` to dump the page text.
3. If `--print-text` truncates mid-sentence (Gemini share pages lazy-load), re-extract via Playwright + scroll-to-bottom with the same cookies.
4. Verify the page loaded as the user (expected first-user message in the dump, NOT the vendor sign-in form). Then proceed with the user's actual ask against the captured content.

**The 5-step recipe is documented in `references/gemini-share-link-as-user.md`**; use only the canonical authorized-source lifecycle and do not retain live share identifiers or credential-bearing evidence in this skill.

**Why this rule exists:** posting a 4-option unblock menu ("paste the content / re-share publicly / Doc export / proceed from title alone") on first refusal was the failure mode the user explicitly corrected in Slack thread <slack-channel-id>/p1784580748.125749 (verbatim: *"use /browser or /browserclaw headless next time without asking"*). Doing the recipe costs ~5 seconds of `browserclaw` time; asking the user costs them a full reply round-trip and breaks their flow. **Bias toward running the recipe.**

**Companion contract test:** `tests/test_browser_command_mentions_browserclaw.py` in `~/jleechanclaw` (PR jleechanorg/jleechanclaw#788) fails if `~/.claude/commands/browser.md` drops the `browserclaw` reference or the auth-gate recipe pointer. SOUL.md `## COMMIT: read-auth-gated-share-links-with-browserclaw` (53rd COMMIT, added 2026-07-20) is the trigger-based contract that enforces this on every session. The contract test + the SOUL.md COMMIT + this SKILL.md section are the three layers of the durable fix.

## When to use `cookies decrypt` + `cookies inject`

Use this pair when:

- The site is behind a login that requires MFA / SSO / WebAuthn (programmatic re-auth is impractical).
- The explicitly authorized agent-owned source profile already has the target session.
- You need a Playwright session that **appears as the user** — same cookies, same session, same auth tokens.
- A token rotation / `invalid_auth` incident requires you to inspect the authorized source so you can decide whether to re-decrypt or escalate.
- **The user asks you to "read" or "save" content from an auth-gated share link** (Gemini share `https://share.gemini.google/…`, ChatGPT shared conversation `https://chatgpt.com/share/…`, Google Doc with restricted access, Notion shared page, etc.) and the page returns a sign-in shell when fetched anonymously. **Don't ask the user to paste the content** — reach for this pair on the first refusal and read the page as them, headless. Verified recipe at `references/gemini-share-link-as-user.md`.

Do **not** use this for:

- Sites you do not have permission to access. The skill trusts the user's local keychain; if you are not the user, this is unauthorized access.
- Bypassing 2FA, CAPTCHAs, or anti-bot protections. The skill reuses an existing logged-in session — it does not break new ones.
- Linux/Windows browsers. The PBKDF2 + Keychain parameters are macOS-only (salt `saltysalt`, iterations `1003`, IV = 16 spaces). Linux Chromium uses `peanuts` / 1 iteration and is not supported by this CLI yet.

## Prerequisites

```bash
# From a checked-out browserclaw worktree or installed wheel
pip install -e '.[dev]'
python -m playwright install chromium
# cryptography>=42.0.0 is the only new dep introduced by PR #6
```

- macOS only (uses `security find-generic-password` against the Login keychain).
- An explicitly authorized agent-owned Chromium profile with explicit `--keychain-service` / `--keychain-account` flags.
- The source profile must already contain the target session; an existing personal sign-in is not authorization.
- The source DB must be readable. The CLI copies the authorized source DB to a private temp file before opening.

## Subcommand: `browserclaw cookies decrypt`

Read one explicitly authorized agent-owned Chromium Cookies SQLite DB, decrypt its values with the matching Keychain-derived AES key, and write a Playwright-compatible JSON.

### Synopsis

```bash
browserclaw cookies decrypt \
  --db '<agent-owned-source-db>' \
  --output ./cookies.json \
  [--domain-filter '%slack.com%'] \
  [--keychain-service 'Chrome Safe Storage'] \
  [--keychain-account 'Chrome'] \
  [--summary]
```

### Arguments

| Flag | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `--db` | path | — | yes | Absolute path to the Chromium-format Cookies SQLite. The CLI copies it to a temp file before opening, so passing the live Chrome-locked path is safe. |
| `--output`, `-o` | path | — | yes | Destination for the decrypted JSON (Playwright `storage_state` shape: `{"cookies": [...], "origins": []}`). |
| `--domain-filter` | str | `%` | no | SQL `LIKE` pattern against `host_key`. Use `%slack.com%` to grab only Slack cookies, `%.google.com%` to grab all subdomains. |
| `--keychain-service` | str | `Chrome Safe Storage` | no | Override for Brave (`Brave Safe Storage`) or Edge (`Microsoft Edge Safe Storage`). |
| `--keychain-account` | str | `Chrome` | no | Override for Brave (`Brave`) or Edge (`Microsoft Edge`). |
| `--summary` | flag | off | no | Print a one-line `domain name len=N` per cookie instead of full values. Use when debugging to avoid logging tokens. |

### Outputs

- Writes `--output` as a Playwright storage_state JSON: `{"cookies": [{"name","value","domain","path","expires","secure","httpOnly","sameSite"}, ...], "origins": []}`.
- Prints either the JSON summary (default) or the per-cookie summary lines (`--summary`).
- Exit code `0` on success, non-zero on `CookieDecryptError` (missing DB, empty file, no `meta.version` row, Keychain lookup failure).

### Example — decrypt cookies for an authorized agent run

Set the source values from the task's explicit authorization. Keep the source
and target in the same browser/session family; do not substitute a personal
desktop profile or sweep other browser databases.

```bash
SOURCE_DB='<agent-owned-source-db>'
SOURCE_KEYCHAIN_SERVICE='<agent-owned-keychain-service>'
SOURCE_KEYCHAIN_ACCOUNT='<agent-owned-keychain-account>'

browserclaw cookies decrypt \
  --db "$SOURCE_DB" \
  --output '<private-temp-cookie-json>' \
  --domain-filter '%<target-domain>%' \
  --keychain-service "$SOURCE_KEYCHAIN_SERVICE" \
  --keychain-account "$SOURCE_KEYCHAIN_ACCOUNT" \
  --summary
```

### Edge cases / failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `CookieDecryptError: Cookie DB not found` | Wrong path or the authorized agent-owned browser is not installed | Confirm the explicitly authorized source DB path; do not fall back to a desktop profile |
| `CookieDecryptError: Cookie DB is empty` | The authorized source browser is currently writing to it; live copy is zero bytes | Stop and report the source-state blocker; do not poll or relaunch a browser |
| `CookieDecryptError: is not a Chromium Cookies DB (no meta.version row)` | Wrong file — it's not a Chromium Cookies SQLite | Check `--db` is a `Cookies` file, not `Cookies-journal` or `Login Data` |
| `Keychain lookup failed for service='Chrome Safe Storage' account='Chrome'` | User clicked "Deny" on the keychain prompt, or the entry was removed | Open Keychain Access.app, search for `Chrome Safe Storage`, ensure it exists; re-run and click "Always Allow" |
| Output JSON has 0 cookies | `--domain-filter` is too narrow, or the authorized source lacks that session | Recheck the target domain and the explicitly authorized source; do not sweep other profiles |
| Output JSON has N>0 cookies but every `value` is `""` (length fields populated) | **Chromium App-Bound Encryption** — Safe Storage decrypt is necessary but may no longer be sufficient; this CLI handles only the supported cookie formats | Do not copy a personal profile or attach CDP to a desktop browser. Use the documented in-process API for the same explicitly authorized agent-owned browser/session, or stop and report the limitation. |
| `browserclaw --help` returns empty / `ModuleNotFoundError: No module named 'browserclaw.cli'` (verified 2026-07-11) | Editable install's source worktree was deleted but the `.pth` still points to it. `pip show browserclaw` shows `Editable project location: <some-path>`; that directory no longer exists | **Fastest fix (verified 2026-07-12):** the editable-install `.pth` file (e.g. `_editable_impl_browserclaw.pth` under `~/.local/orch-venv/lib/python3.13/site-packages/`) contains the **absolute path** to where the worktree used to live. Don't repoint the `.pth` — recreate the worktree at the same path: `git -C $HOME/projects/browserclaw worktree add $HOME/<original-pth-path> <branch-with-cookies.py>`. Then CLI works without `pip` reinstall. **Fallback:** (a) `pip install -e /path/to/browserclaw/repo --force-reinstall --no-deps`; (b) `pip uninstall browserclaw && pip install browserclaw`. While the install is broken, the Playwright + cookie inject pattern still works without `browserclaw` — see `social-poster/scripts/headless_stage_paste.py` for a self-contained alternative. **Branch selection:** `cookies.py` does NOT live on `main`; the historical branch is `feat/cookie-decrypt-inject` (commit `9320bc0`) but the most-recent local branch that contains `src/browserclaw/cookies.py` is typically `feat/drive-pr-16-to-green-er-via-auto-factory-batch-push-to-exist`. Verify first: `git -C /path/to/browserclaw ls-tree <branch> src/browserclaw/` must list `cookies.py`. |

## Subcommand: `browserclaw cookies inject`

Open a task-owned Playwright Chromium session, inject the cookies from a previously-decrypted JSON, navigate to a target URL, and optionally dump non-sensitive page text.

### Synopsis

```bash
browserclaw cookies inject \
  --cookies ./cookies.json \
  --goto https://app.slack.com/client \
  [--browser-channel chromium] \
  --headless \
  [--wait-after-load 5] \
  [--print-text 500]
```

### Arguments

| Flag | Type | Default | Required | Purpose |
|---|---|---|---|---|
| `--cookies` | path | — | yes | Path to a cookies JSON. Either the output of `cookies decrypt` or any Playwright `storage_state` file. |
| `--goto` | URL | — | yes | Where to navigate after injection. Must be a URL whose domain matches the cookies (cookies are domain-scoped). |
| `--browser-channel` | str | `chromium` | no | Playwright channel. Use the bundled `chromium` for the task-owned headless session; use another channel only for a separately authorized agent-owned browser/session. |
| `--headless` | flag | on | no | Run without a visible window. A separately authorized headed agent-owned browser is an exception. |
| `--wait-after-load` | float | `5.0` | no | Seconds to wait after `page.goto` returns, before printing diagnostics. Increase for SPAs that hydrate slowly. |
| `--screenshot` | path | off | no | Use only when the task explicitly requests visual evidence and the page is known not to display secrets; keep output private and temporary. |
| `--print-text` | int | `0` | no | If `> 0`, print the first N characters of `document.body.innerText` after navigation. Useful for verifying the page loaded as the expected user. |

### Outputs

- Opens a task-owned browser context; headless Chromium is the default.
- Prints the final URL, page title, and any `--print-text` content to stdout.
- Writes screenshot to `--screenshot` path if provided.
- Exit code `0` on successful navigation; non-zero if Playwright cannot launch, cookies JSON is empty, or `page.goto` errors.

### Example — inject an authorized session into headless Chromium

```bash
browserclaw cookies inject \
  --cookies '<private-temp-cookie-json>' \
  --goto https://app.slack.com/client \
  --browser-channel chromium \
  --headless \
  --wait-after-load 5 \
  --print-text 800
```

### Example — headless evidence capture

```bash
browserclaw cookies inject \
  --cookies '<private-temp-cookie-json>' \
  --goto https://app.slack.com/client \
  --browser-channel chromium \
  --headless \
  --wait-after-load 3 \
  --print-text 800
```

### Edge cases / failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `No cookies found in <path>` | JSON is empty or has no `cookies` key | Re-run `cookies decrypt` and confirm the file has `{"cookies": [...]}` |
| Navigation lands on login page despite valid cookies | Domain mismatch — `--goto` is on a domain that does not match the cookie's `host_key` | Use a URL whose host matches at least one cookie domain |
| Navigation lands on login page despite valid cookies AND correct domain | **Browser fingerprinting** — site rejects Playwright-launched Chrome even with valid session cookies (LinkedIn, Twitter/X, Threads, Facebook, Dev.to observed 2026-07-05). The cookies are accepted by the HTTP layer but the site's JS anti-bot detects the Playwright Chrome fingerprint and redirects. `browserclaw cookies inject` is NOT a universal login bypass — it only works on sites that don't fingerprint-auth the session. | (1) Check the same explicitly authorized agent-owned browser/session with the same cookies. (2) Try `--browser-channel chromium` instead of `chrome` (different fingerprint, sometimes passes). (3) For sites that always reject Playwright, use the authorized Aside/browser-control route if it is agent-owned. (4) If all fail, report the session blocker or use the provider-owned recovery path. Never inspect or attach to personal Chrome. |
| `channel='chrome'` opens a visible Chrome window during launch even with `--headless` flag (verified 2026-07-18, multi-portal tax drive) | Playwright's `channel='chrome'` spawns the system Chrome binary which has different headless-launch behavior than bundled Chromium-for-Testing — it briefly opens a visible window before transitioning to headless, AND the user's existing Chrome session can gain new tabs that pollute their work. **This is the user's #1 complaint ("use headless browser, stop doing normal browser", "use headless chrome, it keeps opening up").** | **Default: `--browser-channel chromium` (the bundled Chromium-for-Testing)** — it's always headless and never opens a visible window, even though its TLS fingerprint fails more bot-detection checks. Only fall back to `channel='chrome'` when (a) the user has explicitly opted in ("show browser" / "headed mode" / "I want to see the window") AND (b) the target site blocks bundled Chromium's fingerprint. If `channel='chrome'` is unavoidable, use `--browser-channel chrome --headless --headless=new --disable-blink-features=AutomationControlled` AND verify with `lsof -iTCP -sTCP:LISTEN -P -n` and `osascript -e 'tell application "System Events" to count windows of process "Google Chrome"'` that no new visible window appeared. |
| Cookie values decrypt to empty strings (`"value": ""`) for Chromium v20+ App-Bound Encryption cookies (verified 2026-07-18) | `cookies.py` only handles v10/v11 (PBKDF2 + AES-128-CBC). Newer Chromium versions may require decryption by the running, authorized browser process. | Do not copy a personal profile or attach CDP to a desktop browser. Use the documented in-process API for the same explicitly authorized agent-owned browser/session, or report the App-Bound Encryption blocker and use the provider-owned recovery path. |
| Navigation lands on login page when target SPA uses Firebase Auth, even though the authorized source contains provider cookies | **Cross-domain OAuth ≠ SPA authDomain cookies**. Firebase Auth needs the project's authDomain and the SPA app-domain cookies in the same authorized source; provider cookies alone may be insufficient. | Decrypt only the one explicitly authorized agent-owned source and inject into the same browser/session family. If the source lacks the app session, report the blocker or use the provider-owned recovery route. Do not ask an operator to seed a personal browser, poll for cookies, or relaunch a desktop profile. |
| `BrowserType.launch: Executable doesn't exist` | Playwright browsers not installed | `python -m playwright install chrome` (or `chromium`) |
| Page is blank | SPA not yet hydrated when `--wait-after-load` expired | Increase `--wait-after-load` to `8`–`15` for SPAs |
| Session expires within seconds | Cookie `expires` is in the past or the site re-validates the session on every navigation | Re-decrypt (`cookies decrypt`); some sites rotate session tokens on page load |

## Session recovery when the authorized source is empty

Do not sweep browser profiles, poll cookie stores, create recurring jobs, or relaunch a browser when a source is empty. Stop and report the missing session as a blocker.

When the task explicitly authorizes local cookie transfer, use one specifically authorized agent-owned source profile/DB and its matching Safe Storage service/account. Run the guarded lifecycle in `~/.claude/skills/browser-control/SKILL.md` with the source values quoted, for example:

```bash
SOURCE_DB='<agent-owned-source-db>'
SOURCE_KEYCHAIN_SERVICE='<agent-owned-keychain-service>'
SOURCE_KEYCHAIN_ACCOUNT='<agent-owned-keychain-account>'
browserclaw cookies decrypt \
  --db "$SOURCE_DB" \
  --output '<private-temp-cookie-json>' \
  --keychain-service "$SOURCE_KEYCHAIN_SERVICE" \
  --keychain-account "$SOURCE_KEYCHAIN_ACCOUNT" \
  --domain-filter '%<target-domain>%' --summary
```

Use the same browser/session family for injection, never copy a personal profile, and never attach CDP to a desktop browser. If the authorized agent-owned source does not contain the session, request the required manual or provider-owned recovery path.

## Security implications (READ BEFORE USING)

Cookie decryption is **sensitive**. The keychain password unlocks every cookie Chrome has stored for the user — Slack `d` tokens, GitHub `user_session`, Google `SID`, banking sessions, etc. Operators MUST:

1. **Treat decrypted cookies like raw passwords.** Do not log full cookie values to Slack, GitHub PR comments, gist attachments, or any external surface. Prefer `--summary` when sharing evidence.
2. **Never commit the output JSON.** Add `cookies.json` and `*-cookies.json` to `.gitignore` immediately. Delete after use with `shred -u cookies.json` if the disk is encrypted, otherwise `rm` is sufficient on APFS.
3. **Run in a private context.** If you invoke this from an AO worker, treat the worker session as if it has root-level access to the user's identity. Do not dispatch this skill into shared / multi-tenant AO lanes.
4. **Respect the trust model.** This skill reads only one explicitly authorized agent-owned source profile, using that source's matching macOS Keychain entry. The personal Chrome profile and cookies are off-limits. Do not sweep or extend access beyond the authorized source.
5. **No bypass claims.** This skill does not bypass 2FA, CAPTCHA, or anti-bot systems. It reuses an existing logged-in session. Do not advertise it as a "login bypass."
6. **Audit logging.** Every invocation should appear in the agent's session log. If you are dispatching this via AO, include `--summary` output in the worker report and never the raw cookie values.

## Trust model diagram

```text
┌──────────────┐    security find-generic-password   ┌──────────────────┐
│  user        │ ─────────────────────────────────▶ │  macOS Keychain   │
│  (you)       │ ◀─────── "Chrome Safe Storage" ─── │  Login keychain   │
└──────┬───────┘                                      └──────────────────┘
       │ grants access once per session
       ▼
┌──────────────┐    PBKDF2-HMAC-SHA1 (1003 iters)   ┌──────────────────┐
│ browserclaw  │ ─────────────────────────────────▶ │  AES-128-CBC key  │
│ cookies.py   │                                      └────────┬─────────┘
└──────┬───────┘                                               │
       │ reads Cookies SQLite (copy to tmp)                   │
       ▼                                                       ▼
┌──────────────┐   v10 || AES(plaintext)                  ┌──────────────┐
│   cookies    │ ──────decrypt──────────────────────────▶ │  JSON output │
│   .json      │                                          │  (Playwright) │
└──────────────┘                                          └──────────────┘
```

## Test script

A bash regression test lives at `tests/test_browserclaw_skill.sh` (this repo). It verifies:

1. This SKILL.md exists and is non-empty.
2. `browserclaw cookies decrypt` is documented with a real example.
3. `browserclaw cookies inject` is documented with a real example.
4. The security warning section is present.
5. The installed `browserclaw` CLI exposes the `cookies` subcommand (real binary surface, not just docs).
6. An `--help` invocation of `cookies decrypt` returns exit code 0.

Run it from this repo:

```bash
bash tests/test_browserclaw_skill.sh
```

## Eval criteria — "working" looks like

- `browserclaw cookies decrypt --db '<agent-owned-source-db>' --output '<private-temp-cookie-json>' --domain-filter '%<target-domain>%'` exits 0 and writes a JSON with `>=1` cookie for the explicitly authorized source.
- `browserclaw cookies inject --cookies '<private-temp-cookie-json>' --goto https://app.slack.com/client --browser-channel chromium --headless --wait-after-load 5 --print-text 800` exits 0 and prints non-sensitive page text when requested.
- End-to-end (decrypt → inject → bounded text status) is captured only through the guarded private lifecycle for PR /es layer-2 verification on PR [#6](https://github.com/jleechanorg/browserclaw/pull/6).

## Cross-references

- Source repo: [github.com/jleechanorg/browserclaw](https://github.com/jleechanorg/browserclaw)
- PR introducing the feature: [#6 — feat(cookies): Chrome cookie decrypt + Playwright inject for reuse of logged-in sessions](https://github.com/jleechanorg/browserclaw/pull/6)
- Module source: `src/browserclaw/cookies.py` (dataclasses, AES decrypt, Keychain lookup, JSON I/O)
- CLI source: `src/browserclaw/cli.py` (argparse for `cookies decrypt` / `cookies inject`)
- Tests (10 cases, all green on macOS): `tests/test_cookies_decrypt.py`
- Reference Chromium source: `os_crypt_mac.mm` (PBKDF2 params, AES key derivation)
- Inspiration: [pycookiecheat](https://github.com/n8henrie/pycookiecheat) (MIT) — adapted for Python 3.11+ and DB v24+ SHA256(host) prefix.
- Related Hermes skills: `~/.claude/skills/browser-testing` (Playwright MCP for localhost UI testing, headless) — use this skill for **session-less** UI testing, not for "act as user X" flows.
- **v2 design (validated 2026-07-30, NOT YET IMPLEMENTED)**: `references/browserclaw-v2-design-2026-07-30.md` — historical design reference only. It cannot override the current personal-browser-isolation, explicitly authorized agent-owned-source, MFA/consent, and no-bypass ceilings in `~/.claude/skills/browser-control/SKILL.md`. Read it for background before proposing browserclaw feature work.

## Version / metadata
- Last updated: 2026-10-25 (agent-owned source and same-browser/session isolation; unsupported App-Bound Encryption paths fail closed)
- browserclaw version: 0.1.0 (cookies added in commit `9320bc0` on branch `feat/cookie-decrypt-inject`)
- Tracking PR: [#6](https://github.com/jleechanorg/browserclaw/pull/6)
- Hermes skill location: `skills/browserclaw/SKILL.md` (this file); also mirrored at `~/.claude/skills/browserclaw/SKILL.md`

## Empty authorized source

When the explicitly authorized agent-owned source contains zero matching
cookies, stop and report the missing session. Do not sweep other browser
profiles, query personal stores, or create a recurring poll. Use the manual or
provider-owned recovery path that the task authorizes.

## When `cookies decrypt` returns empty values

Do not copy a desktop browser profile, launch the installed browser against a
profile copy, attach CDP to a user's tabs, or run parallel browser instances
to recover cookie values. Stop and report the App-Bound Encryption limitation.

If an explicitly authorized agent-owned browser provides a supported in-process
session path, use that same browser/profile and its documented API under the
browser-control isolation contract. Keep the target and source in the same
browser/session family, and write any temporary state through the guarded
private lifecycle. When that path is unavailable, use the manual or
provider-owned recovery route.

## Current authorization ceiling

The current personal-browser-isolation contract in
`~/.claude/skills/browser-control/SKILL.md` takes precedence over every
historical reference below. Those links are background only and MUST NOT be
executed as alternate fallbacks. Do not inspect or copy a personal cookie
store, sweep profiles, use stolen-cookie or direct-API material, or recover
through an alternate browser. Authenticated reuse requires explicit task
authorization naming exactly one agent-owned source, with the canonical
fail-closed lifecycle and its MFA/consent boundaries. If that route fails,
stop and report the blocker or use a provider-owned recovery path.

## Pair with

- `references/gemini-share-link-stopping-pattern.md` — historical incident and contract background; do not execute any legacy recovery recipe. Apply the current browser-control ceiling when an auth-gate refusal occurs.
- `references/gemini-share-link-as-user.md` — historical recipe background only; any authorized execution must use the canonical one-agent-owned-source lifecycle and current browser-control contract.
- `~/.claude/skills/browser-control/SKILL.md` — canonical guarded lifecycle for one explicitly authorized agent-owned source and same-browser/session injection
- `references/gmail-as-fallback-when-sso-clickthrough-blocked.md` — historical background only; do not execute it as a fallback. Current browser-control precedence and the one authorized agent-owned source rule apply.
- `references/direct-graphql-stolen-cookie-auth.md` — historical background only; do not execute direct-API, stolen-cookie, or alternate-browser recovery instructions. Current browser-control precedence applies.
- `references/data-extraction-recipes-from-stolen-cookies.md` — historical background only; do not execute profile-sweep, personal-cookie, or alternate-browser recovery instructions. Current browser-control precedence applies.
- `references/block-kit-verification-rule.md` — when Slack Block Kits arrive in conversation that *were not produced by the visible tool-call history* (ie. "Lane J1-J4 tried direct login", "we successfully retrieved historical balances"), verify the most-load-bearing specific dollar figure against a fresh tool call before amplifying it. Lists the five common fabrication classes (wrong-direction bridges, wrong-window public market quotes, "we retrieved X from API" when the API gates it, cookie-expiry claims that miss the file-copy workaround, asking for credentials the user already has) with one-liner verify-with recipes. Verified 2026-07-22 on a Monarch Money session where the Block Kit's "$437,238.97 brokerage→depository bridge" was actually $272,438.91, "BTC -36.9%" was actually +78.6%, and "Chrome Login Data DB is locked" was false (cp succeeded).
- `references/cookie-expiry-vs-server-session.md` — the silent-fail mode where `cookies decrypt` returns N>0 cookies with valid expiry but `cookies inject` 302-redirects to a login page because the *server-side session* (not the cookie record) is dead. Use only its one-shot status probe to distinguish session death from bot-detect or CSRF/paid-tier gates; this skill prohibits recurring polling and personal-profile recovery.
- `references/slack-file-fetch.md` — when the task starts from a Slack file attachment and MCP can't `files.info`, the recipe to download + vision-analyze it (uses XOX-P from `~/.profile`)
- `~/.hermes/skills/repro/references/auth-gate-fallback-repro.md` Step 6 — when headless-Chrome is blocked by an auth gate AND the bug is per-campaign / server-side, GCP Cloud Logging filtered to `campaign_id` is a more productive diagnostic path than wrestling with auth. Use this in tandem with `browserclaw` for /repro work: try browserclaw first (full session → full repro), fall back to Step 6 if the auth gate blocks you.
- `~/.hermes/skills/repro/SKILL.md` — the canonical /repro workflow that calls browserclaw for the headless-Chrome portion of "is the bug reproducible in the user's browser?"
- `~/.hermes/skills/repro/references/json-serialization-leak.md` — concrete bug class browserclaw + GCP logs together surfaced (verified 2026-07-12). Pattern is reusable: server-side 500 + intermittent symptom → GCP logs first, headless-Chrome second.
