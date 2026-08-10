---
name: browser-control
description: Control real websites and authenticated browser sessions, inspect pages, complete approved UI flows, or troubleshoot browser automation. Use for general browser work, site settings, OAuth consent, existing tabs, and Slack app configuration. Uses Aside first and routes deterministic app testing to playwright-ui-testing.
---

# Browser control

## Route the task

The numbered **Routing order** below is the only authoritative sequence; these bullet categories are a non-binding restatement. A route is considered to have **succeeded** only when it completes the authenticated task the user asked for — a single transport error, a missing-tab condition, or one failed CLI call is not enough to advance. When a route fails to complete the authenticated task, fall back to the next numbered route.

- **Live websites, authenticated sessions, account settings, OAuth, existing tabs:** start at Aside MCP, then Aside CLI (the only signed-in path that does not copy session material).
- **Authenticated fallback on fingerprint-TOLERANT sites:** use the guarded browserclaw decrypt → headless inject lifecycle only after both Aside paths fail to complete the authenticated task. **Fingerprint-sensitive sites (LinkedIn, banks/brokerages, Cloudflare/Akamai-protected, user-declared no-headless) NEVER advance past Aside.** When Aside is unavailable on a fingerprint-sensitive target, post a ONE-LINE display/input blocker; do not fall through to cookie injection, capture, learn, reverse, or Playwright.
- **Deterministic local-app testing, CI, isolated profiles, traces, video, multi-browser:** use Playwright headless / `playwright-ui-testing` after the authenticated routes are inapplicable.
- **Visible/headed browser:** only when the user explicitly asked for it in the current thread. Headed Chromium is the user's existing Chrome session; do not use it from a sandboxed Bash call unless the user opts in.

## Routing order (operational, in priority order)

Apply these in order; proceed only after the current route fails to complete the authenticated task (not merely after one transport or tab call errors). The order intentionally prefers tools that already have the user's session over tools that copy session material.

1. **Aside-MCP if available.** Most specific, lowest friction: the user's existing signed-in tabs and session are preserved across calls. Detect by listing MCP tools in the active runtime.
2. **Aside CLI** (`aside repl` / `aside "<prompt>"` / `aside account list`) — `repl` mode for interactive navigation, `agent`/`<prompt>` mode for an Aside-driven task. Use the already-running `Aside.app` profile. `account list` returns the active profile(s). Aside drives a real browser session; it remains the primary signed-in path, even though it is not the headless fallback.
3. **browserclaw cookies decrypt → inject** — for fingerprint-tolerant sites where Aside is unavailable, not signed-in, or on a headless host. The fingerprint-sensitive Aside-only exception below overrides this fallback. Decrypt the user's existing cookies from the local Chromium profile, inject into Playwright Chromium headless, navigate. Profile sweep order: **Aside → Chrome Default → Chrome Profile 1 → Chrome Profile 2 → Brave → Microsoft Edge**. Chrome path: `~/Library/Application Support/Google/Chrome/<Profile>/Cookies`. Aside/Edge/Brave use the same shape with a different `--keychain-service`/`--keychain-account`. Discover profile locations from the installed browserclaw skill, but apply only the guarded lifecycle below; do not execute older fixed-path output snippets.
4. **Playwright headless (no auth)** — for unauthenticated/deterministic flows, scraping public pages, scripted sweeps, or CI-style checks. Use `playwright-ui-testing` if the task is a real test (isolated profiles, traces, video).
5. **Visible/headed browser** — only when the user explicitly asked for it in the current thread. Headed Chromium is the user's existing Chrome session; do not use it from a sandboxed Bash call unless the user opts in.

> **Footnote — `browserclaw capture` / `learn` / `reverse` (NOT a route).** These subcommands persist full HTTP request/response traffic to a `capture.har` file on disk, which can contain the new secret in plaintext. They are allowed ONLY for tasks where no credentials, cookies, authorization headers, tokens, or secret pages can enter the capture — e.g. API documentation discovery against a public docs site. They are NOT the headless fallback for any of the numbered routes above; if you need an authenticated page, use route 3 (browserclaw `cookies decrypt` + `cookies inject`) instead.

## Live-browser workflow

1. Check for usable existing tabs before opening a new one.
2. Read the page with an accessibility snapshot before acting. Use current refs, not guessed selectors or coordinates.
3. Treat login, consent, chooser, and MFA screens as recoverable states. Never bypass them. Treat any cookie/session material you copy as a credential.
4. Confirm any side effect from the resulting page state. Before sending, submitting, deleting, installing, authorizing, or publishing, verify the target and requested scope.
5. Close tabs opened solely for the task when they are no longer useful.

## Authorized credential reuse (the safe cookie-copy contract)

`browserclaw` documents the cookie decrypt + inject flow as the headless fallback for sites where the user is already authenticated. That is the supported, authorized path for any site where the user has an existing signed-in profile — Gemini / ChatGPT / Google Docs / Notion share links, Slack, GitHub, GCP Console, Firebase Console, etc. The actual ban is on **credential exposure**, not on the act of carrying an authenticated session from one Chromium profile to a headless session for the same user.

Use this contract for any credential-bearing flow:

```bash
# One guarded lifecycle: create → decrypt → inject → delete.
# Fail-closed: any nonzero exit (set -euo pipefail) runs cleanup before abort.
# One canonical cleanup trap removes BOTH the cookie file and the page
# text on every success, error, and signal. The secret branch runs
# INSIDE this trap, and the multi-profile sweep produces a cookie
# artifact the canonical recipe consumes before cleanup.
set -euo pipefail
# Restrict the process umask so any mktemp / redirect that does
# not respect an explicit chmod still ends up owner-only. The
# canonical recipe also re-applies chmod 600 after every sweep
# write because browserclaw's writer uses Path.write_text()
# which honors the process umask.
umask 077
TMP_COOKIES="$(mktemp -t browserclaw-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-page-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE"
# INT/TERM/HUP handlers MUST terminate nonzero after cleanup so
# a signal during a long decrypt/inject does not let bash
# continue past the trap and recreate credential files.
cleanup_browser_creds() {
  local rc=$?
  rm -f "$TMP_COOKIES" "$TMP_PAGE"
  return "$rc"
}
exit_on_signal() {
  local rc=$?
  cleanup_browser_creds || true
  # Exit immediately with 128+signal so bash does NOT continue
  # past the trap. Re-raising via `kill -SIG $$` is unreliable
  # because bash defers re-entry of the same signal while the
  # handler is still running; a direct `exit` is the documented
  # and race-free way to terminate from a signal trap.
  if [ -n "${1:-}" ]; then
    case "${1}" in
      INT)  exit 130 ;;
      TERM) exit 143 ;;
      HUP)  exit 129 ;;
      *)    exit "$rc" ;;
    esac
  fi
  exit "$rc"
}
trap 'exit_on_signal TERM' TERM
trap 'exit_on_signal HUP' HUP
trap 'exit_on_signal INT' INT
trap cleanup_browser_creds EXIT

# 1. Multi-profile sweep runs FIRST, Aside first — the canonical
#    recipe does NOT depend on Chrome Default being non-empty
#    before falling through to other profiles. The sweep writes
#    the first non-empty cookie JSON to $TMP_COOKIES and short-
#    circuits. Each browserclaw write is followed by chmod 600
#    because browserclaw's writer honors the process umask.
set +e
for entry in \
  "Aside:$HOME/Library/Application Support/Aside/Default/Cookies:Aside Safe Storage:Aside" \
  "Aside-Profile1:$HOME/Library/Application Support/Aside/Profile 1/Cookies:Aside Safe Storage:Aside-Profile1" \
  "Chrome-Default:$HOME/Library/Application Support/Google/Chrome/Default/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile1:$HOME/Library/Application Support/Google/Chrome/Profile 1/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile2:$HOME/Library/Application Support/Google/Chrome/Profile 2/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile3:$HOME/Library/Application Support/Google/Chrome/Profile 3/Cookies:Chrome Safe Storage:Chrome" \
  "Brave:$HOME/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies:Brave Safe Storage:Brave" \
  "Edge:$HOME/Library/Application Support/Microsoft Edge/Default/Cookies:Microsoft Edge Safe Storage:Microsoft Edge"; do
  IFS=: read label db svc acct <<< "$entry"
  [ -f "$db" ] || continue
  env -i HOME="$HOME" \
    PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    browserclaw cookies decrypt --db "$db" \
      --output "$TMP_COOKIES" \
      --keychain-service "$svc" --keychain-account "$acct" \
      --domain-filter '%<target-domain>%' --summary >/dev/null 2>&1 || true
  if [ -s "$TMP_COOKIES" ]; then
    count="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
    if [ "$count" -gt 0 ]; then
      chmod 600 "$TMP_COOKIES"
      echo "MATCH: $label (${count} cookies) — stopping sweep" >&2
      break
    fi
  fi
  rm -f "$TMP_COOKIES"
done
set -e

DECRYPT_COUNT="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
if [ "$DECRYPT_COUNT" -le 0 ]; then
  echo "BLOCKER: no <target-domain> cookies in any profile. Ask the user to log in once." >&2
  exit 11
fi

# 3. Inject + navigate headless Chromium. Keep body text private and temporary.
#    Do not write a screenshot by default; capture one only when the user
#    explicitly requested visual evidence AND the page is known not to
#    display secrets.
env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  browserclaw cookies inject \
    --cookies "$TMP_COOKIES" \
    --goto "<full-authenticated-url>" \
    --browser-channel chromium \
    --headless \
    --wait-after-load 12 \
    --print-text 100000 > "$TMP_PAGE"

# 4. Read only the fields needed for the task, then trust the EXIT
#    trap to remove both the cookie file and the captured private
#    text on both success and failure. The trap is the cleanup;
#    there is no disarm line and no explicit cleanup call here —
#    keeping the trap armed is the fail-closed contract: any signal
#    arriving after step 3 still removes both files. The trap's
#    `rm -f` is idempotent, so a normal exit that fires the EXIT
#    trap is the same as an explicit cleanup call.
```

**Secret-bearing page branch:** API-key, token, password, recovery-code, banking, and similar pages MUST NOT execute the generic `--print-text` recipe above, MUST NOT capture screenshots, MUST NOT write a HAR, and MUST NOT persist DOM text. The branch must persist neither DOM text nor images. After injecting the guarded cookies, use a bare headless Playwright script that inspects only the minimum safe non-secret DOM state in memory, emits the boolean/status result to **stdout** (not a file), and persists nothing on disk. The lifecycle MUST be fail-closed: it owns combined cleanup of the cookie file and any per-branch scratch file, and INT/TERM/HUP also trigger cleanup:

```bash
# Secret-bearing page branch — fail-closed lifecycle.
# Self-contained: it runs the canonical multi-profile sweep to
# obtain $TMP_COOKIES, then a bare Playwright script that emits
# the boolean to stdout only. The EXIT/INT/TERM/HUP trap removes
# every browserclaw temp file on every signal, and the signal
# handlers re-raise the signal so the script exits nonzero.
set -euo pipefail
# Restrict the process umask so any mktemp / redirect that does
# not respect an explicit chmod still ends up owner-only. The
# canonical recipe also re-applies chmod 600 after every sweep
# write because browserclaw's writer uses Path.write_text()
# which honors the process umask.
umask 077
TMP_COOKIES="$(mktemp -t browserclaw-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-page-XXXXXX.txt)"
SECRET_STDOUT_BUF="$(mktemp -t browserclaw-secret-out-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE" "$SECRET_STDOUT_BUF"
cleanup_secret_branch() {
  local rc=$?
  rm -f "$TMP_COOKIES" "$TMP_PAGE" "$SECRET_STDOUT_BUF"
  return "$rc"
}
exit_on_signal() {
  local rc=$?
  cleanup_secret_branch || true
  # Exit immediately with 128+signal so bash does NOT continue
  # past the trap. Re-raising via `kill -SIG $$` is unreliable
  # because bash defers re-entry of the same signal while the
  # handler is still running; a direct `exit` is the documented
  # and race-free way to terminate from a signal trap.
  if [ -n "${1:-}" ]; then
    case "${1}" in
      INT)  exit 130 ;;
      TERM) exit 143 ;;
      HUP)  exit 129 ;;
      *)    exit "$rc" ;;
    esac
  fi
  exit "$rc"
}
trap 'exit_on_signal TERM' TERM
trap 'exit_on_signal HUP' HUP
trap 'exit_on_signal INT' INT
trap cleanup_secret_branch EXIT

# 1a. Multi-profile sweep — same body as the canonical recipe.
set +e
for entry in \
  "Aside:$HOME/Library/Application Support/Aside/Default/Cookies:Aside Safe Storage:Aside" \
  "Aside-Profile1:$HOME/Library/Application Support/Aside/Profile 1/Cookies:Aside Safe Storage:Aside-Profile1" \
  "Chrome-Default:$HOME/Library/Application Support/Google/Chrome/Default/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile1:$HOME/Library/Application Support/Google/Chrome/Profile 1/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile2:$HOME/Library/Application Support/Google/Chrome/Profile 2/Cookies:Chrome Safe Storage:Chrome" \
  "Chrome-Profile3:$HOME/Library/Application Support/Google/Chrome/Profile 3/Cookies:Chrome Safe Storage:Chrome" \
  "Brave:$HOME/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies:Brave Safe Storage:Brave" \
  "Edge:$HOME/Library/Application Support/Microsoft Edge/Default/Cookies:Microsoft Edge Safe Storage:Microsoft Edge"; do
  IFS=: read label db svc acct <<< "$entry"
  [ -f "$db" ] || continue
  env -i HOME="$HOME" \
    PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    browserclaw cookies decrypt --db "$db" \
      --output "$TMP_COOKIES" \
      --keychain-service "$svc" --keychain-account "$acct" \
      --domain-filter '%<target-domain>%' --summary >/dev/null 2>&1 || true
  if [ -s "$TMP_COOKIES" ]; then
    count="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
    if [ "$count" -gt 0 ]; then
      chmod 600 "$TMP_COOKIES"
      break
    fi
  fi
  rm -f "$TMP_COOKIES"
done
set -e

if [ "$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)" -le 0 ]; then
  echo "BLOCKER: no <target-domain> cookies in any profile. Ask the user to log in once." >&2
  exit 11
fi

# Bare Playwright script: reads $TMP_COOKIES, inspects DOM, emits the
# boolean to stdout only. NEVER: --print-text, capture, learn,
# reverse, persisted DOM, screenshots. The URL is defined on its own
# line so `set -u` does not trip when we expand it on the next.
BROWSE_TARGET_URL="<full-secret-bearing-url>"
"$HOME/.local/orch-venv/bin/python" - "$TMP_COOKIES" "$BROWSE_TARGET_URL" <<'PY'
import json, sys
from playwright.sync_api import sync_playwright

cookies_path, target_url = sys.argv[1], sys.argv[2]
cookies = json.loads(open(cookies_path).read())["cookies"]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="chromium")
    ctx = browser.new_context(storage_state={"cookies": cookies, "origins": []})
    page = ctx.new_page()
    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    has_secret = page.evaluate("() => !!document.querySelector('[data-secret], .token, .api-key')")
    browser.close()

# Emit the boolean to stdout; do NOT persist the result.
sys.stdout.write("present=" + ("true" if has_secret else "false") + "\n")
PY

# Trap removes every browserclaw temp file on normal exit. No disarm
# line — keeping the trap armed is the fail-closed contract.
```

For ordinary private content (not secret-bearing), the generic `--print-text` recipe above is permitted but must omit `--screenshot`; only capture one when the user requested visual evidence AND the page is known not to display secrets.

**Safeguards** (enforced by the contract test `tests/test_browser_command_contract.py`):

- The cookies JSON and any captured private body text live only in private mode-600 temp files, are never committed or logged, and are removed by an EXIT trap on success and failure.
- Use `--summary` when only a domain/name/length check is needed; never log raw values.
- **Never** route credential-bearing flows through `browserclaw capture` / `learn` / `reverse` — those commands persist full HTTP request/response traffic to a `capture.har` file on disk, which CAN contain the new secret in plaintext (the exact leak class this skill's credential rule already bans). For those flows, use `cookies inject` (navigation only, no HAR) or a bare Playwright script, read the result from the DOM/page text, and do not persist the raw network traffic.
- The `--browser-channel chromium` choice (not `chrome`) keeps the bundled Chromium-for-Testing always-headless and never touches the user's existing Chrome session.

## Fingerprint-sensitive sites (Aside-only exception)

Playwright cookie injection can invalidate sessions on sites that bind cookies to a device fingerprint (Cloudflare clearance, browser UUIDs, anti-bot TLS fingerprinting, etc.). For these known-bad sites, drop the cookie-copy route and use the existing signed-in Aside profile directly — even from a headless host, fail over to a host with a real attached display and use Aside instead of trying to spoof the missing fingerprint:

- LinkedIn
- Banks / brokerage sites (Chase, Fidelity, Vanguard, Schwab, etc.)
- Sites with active Cloudflare or Akamai bot-mitigation that flag the Chromium-for-Testing headless fingerprint
- Sites that the user has explicitly flagged as "do not attempt headless"

If the host is headless and the URL is fingerprint-sensitive, post a ONE-LINE BLOCKER explaining the missing display/input rather than attempting `cookies inject` and silently failing.

## Slack app and credential work

- Configure or rotate Slack credentials through the normal Slack UI. Load `hermes-slack-rotation` for manifest scopes, OAuth and Socket Mode token rotation, protected shell-file updates, and validation.
- Do not put tokens in prompts, screenshots, HAR files, shell output, artifacts, or source control.
- Do not infer a post's identity. Verify it with `auth.test` or the platform's confirmed result before claiming user versus bot behavior.

## Failure classification

Report the precise layer that failed: browser transport, current tab/profile access, page authentication or consent, website UI, or action permission. A CLI failure does not prove an existing browser tab or another browser tool is unavailable.

## Environment gotchas

- **Aside CLI in a sandboxed Bash tool call fails closed, not soft.** `aside account list` / `aside repl` / `aside "<prompt>"` return `fetch failed` immediately — before the Aside daemon writes any log line — when the Bash tool's default sandbox blocks the CLI's local IPC to the already-running `Aside.app` (a real launchd-managed process; verify with `ps -p <pid>` or `launchctl list | grep -i aside`, not `ps aux | grep aside`, since sandboxed `ps aux` may not enumerate it even though the process is alive). This is NOT an Aside outage. Fix: pass `dangerouslyDisableSandbox: true` on every Bash call that invokes `aside`. Confirmed 2026-07-16: identical command failed sandboxed, succeeded immediately unsandboxed against the same running daemon.
- **Aside additionally requires a real, rendered display — not just an unsandboxed process.** On a headless host (`ioreg -c IODisplayConnect | grep -c IODisplayConnect` returns `0`), the Aside daemon answers metadata-only calls (`account list`) fine but navigation fails with `This task is not bound to a browser profile. Open it in Aside browser and try again.` For ordinary **fingerprint-tolerant** sites, proceed to the guarded browserclaw `cookies decrypt` + `cookies inject` headless fallback (route 3 in the numbered order). **The fingerprint-sensitive Aside-only exception overrides this rule with NO fall-through:** for LinkedIn, banks/brokerages, Cloudflare/Akamai-protected, and user-declared no-headless sites, post the ONE-LINE display blocker and never attempt cookie injection, `browserclaw capture`, `learn`, `reverse`, or Playwright. The escape hatch (`browserclaw capture --headless --url ...` below) is a NARROW no-credentials discovery tool only and is NOT a substitute for the numbered routes.
- **Aside has no headless mode** (`aside --help` lists no such flag) — it drives a real, visible browser via an extension bridge tied to the active macOS GUI session. It is not a background/CI-safe tool by design.
- **`browserclaw` as a headless-chrome fallback** (route 3 in the numbered order): use `browserclaw cookies decrypt` + `cookies inject` to carry over an authenticated session from the real Chrome/Brave/Edge/Aside profile per the "Authorized credential reuse" contract above. **`browserclaw capture --headless --url <url> [--goal "<task>" --provider <p> --model <m>]` is a separate, narrow discovery tool** (Playwright-backed, no display or GUI session required, confirmed working on the same headless host where Aside failed) — it is NOT the headless fallback for authenticated flows and is NOT permitted for credential-bearing targets. **Do not route credential-bearing flows (API key creation/rotation, token/secret pages, password/banking/recovery-code pages) through `capture`/`learn`/`reverse`** — those commands persist full HTTP request/response traffic to a `capture.har` file on disk, which will contain the new secret in plaintext (the exact leak class this skill's credential rule already bans). For those flows, use `cookies inject` (navigation only, no HAR) or a bare Playwright script that reads only minimum non-secret DOM state, emit only a boolean/status result, and persist neither DOM text nor images (see the secret-bearing page branch below).

## Completion

Report browser mode, the confirmed result, and any blocker. For browser-dependent actions, attach a focused screenshot when it is safe and useful.
