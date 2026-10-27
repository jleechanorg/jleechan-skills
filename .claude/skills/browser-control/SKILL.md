---
name: browser-control
description: Control real websites and authenticated browser sessions, inspect pages, complete approved UI flows, or troubleshoot browser automation. Use for general browser work, site settings, OAuth consent, existing tabs, and Slack app configuration. Uses the connected runtime browser when available; routes deterministic app testing to playwright-ui-testing.
---

# Browser control

## Personal browser isolation — required for every route

Personal desktop browser windows, tabs, profiles, cookies, and login state are
off-limits to automation. No browser task or visible-browser request authorizes
their use. Use an isolated agent-owned context; the only cookie exception is an
explicitly authorized transfer from exactly one named agent-owned profile below.

- Use an agent-owned browser and profile. Prefer bundled Playwright Chromium for
  headless launches; a separate profile alone does not prevent macOS launch/window
  interference when launching the installed Google Chrome application.
- Before attaching through CDP, an extension, or a runtime browser API, verify the
  target browser, process/profile, and task-owned tabs. Never auto-discover or
  auto-connect to desktop Chrome, including agent-browser `--auto-connect`.
- Never select, copy, decrypt, or import the personal Chrome profile or its cookies,
  including agent-browser `--profile Default`. Cookie-transfer recipes below apply
  only to an explicitly authorized agent-owned source profile.
- Aside may be used only when an already-running process and task-owned context
  are proven to operate in the background. Do not launch or activate it. Metadata
  probes do not prove navigation is background-safe. Otherwise use isolated
  headless Chromium.
- Keep Chromium headless by default. A current-thread explicit request for visible
  automation permits a headed window only in a separate, verified task-owned
  browser process/profile/context. Never use a personal or default profile, a bare
  system/default-browser launch, `open -a "Google Chrome"`, or AppleScript
  activation/quit. Do not launch or activate a desktop browser as spontaneous
  recovery, change default-browser registration, or enable a continuous relaunch
  service.
- Close only exact tabs/contexts/processes created by the current task. Never use
  `closeAllTabs()`, `killall`, or broad `pkill` against shared browsers. Never remove
  profile locks while their holder is alive; Dot profiles remain exclusive to Dot.
- Verify the launched executable, dedicated profile or isolated context, endpoint
  ownership when attaching, and headless mode by default before navigation. For
  explicitly requested headed automation, verify the separate task-owned process
  and profile instead. If ownership cannot be verified, do not attach to another
  browser as a fallback. Report instruction checks separately from runtime proof
  that the main window stayed untouched.

## Supported runtime browser API

Use a connected browser API only when it connects to a separate, task-owned
browser context. Do not use a Chrome extension bridge or existing-tab API to
inspect personal desktop tabs or profiles. Verify ownership before navigation;
if it cannot be proven, use isolated headless Chromium or report the blocker.
Do not use a browser or copied credential to bypass login, consent, MFA, or site
access rules.

On Ubuntu without Aside, an explicitly authorized, already-configured Playwright
MCP or CLI may be used when runtime instructions permit it and it has a supported
connection to the requested browser. CLI authorization does not create a connection
to existing profiles: a default isolated Playwright browser is not a personal
signed-in browser. Do not install software, grant access, expose a debugging port,
or launch a second agent merely to manufacture missing access.

Do not bypass tab ownership locks, disabled controls, or denied permissions.
Inspect another relevant unlocked tab when available; report a locked tab as a
scoped blocker. Do not treat one locked tab as proof that all browsers are blocked.
Verify account identity in visible account UI, not from tab titles or profile names.
Distinguish background operation through an existing extension from launching a
new headless browser: they have different authentication and display requirements.
An existing-tab request never authorizes inspection of personal desktop tabs,
relaunching Chrome, or switching accounts.

## Route the task

Use a supported runtime API only for an isolated task-owned context. Otherwise
follow the numbered **Routing order** below. A personal signed-in tab is never a
route or fallback.

- **Live websites, authenticated sessions, account settings, OAuth:** use an already-running, verified agent-owned Aside background context when available; otherwise use isolated headless Chromium and the provider-supported authentication flow.
- **Authenticated fallback on fingerprint-TOLERANT sites:** use the guarded browserclaw decrypt → headless inject lifecycle only after both Aside paths fail to complete the authenticated task, AND only when the user has explicitly authorized local cookie transfer for the requested authenticated-content task. **Fingerprint-sensitive sites (LinkedIn, banks/brokerages, Cloudflare/Akamai-protected, user-declared no-headless) NEVER advance past Aside.** When Aside is unavailable on a fingerprint-sensitive target, post a ONE-LINE display/input blocker; do not fall through to cookie injection, capture, learn, reverse, or Playwright.
- **Deterministic local-app testing, CI, isolated profiles, traces, video, multi-browser:** use Playwright headless / `playwright-ui-testing` after the authenticated routes are inapplicable.
- **Visible/headed browser:** not a default fallback. Use headless by default; if the current thread explicitly requests visible automation, use only a separate verified task-owned browser/profile. Never access the personal desktop browser.

## Routing order (operational, in priority order)

Apply these in order. Aside is allowed only when its already-running context is
verified agent-owned and background-safe. No route may use personal desktop
browser state.

1. **Aside-MCP only if already connected to a verified agent-owned background context.** Tool availability or account-list output is not proof of context ownership.
2. **Aside CLI only for a verified agent-owned background context already running.** Do not launch/activate Aside or use a desktop/personal profile. If ownership/background behavior is not established, skip to isolated headless Chromium.
3. **browserclaw cookies decrypt → inject** — for fingerprint-tolerant sites where Aside is unavailable, not signed-in, or on a headless host, and the user has explicitly authorized local cookie transfer from exactly one named agent-owned source for the task. The fingerprint-sensitive Aside-only exception below overrides this fallback. Never sweep personal browser profiles or enumerate source candidates; use only that authorized source, its matching Safe Storage service/account, and the guarded lifecycle below.
4. **Playwright headless in an isolated context** — for unauthenticated/deterministic flows, public pages, scripted checks, and authorized agent-owned cookie transfer. Use `playwright-ui-testing` for real tests.
5. **Visible/headed mode is exceptional.** Keep Chromium headless by default. If the current thread explicitly requests visible automation, use only a separate verified task-owned browser/profile; report a blocker if that isolation cannot be established.

> **`browserclaw capture` / `learn` / `reverse` are public, non-sensitive discovery only.** They persist full traffic to HAR, so never use them with credentials, cookies, tokens, private content, or secret-bearing pages. Explicitly authorized transfer from one named agent-owned profile only feeds an isolated browser context; it never authorizes direct API requests with copied cookies, headers, or bearer tokens.

## Live-browser workflow

1. Check for usable existing tabs before opening a new one.
2. Read the page with an accessibility snapshot before acting. Use current refs, not guessed selectors or coordinates.
3. Treat login, consent, chooser, and MFA screens as recoverable states. Never bypass them or extract secrets. When the user explicitly authorizes local cookie transfer for the requested authenticated-content task, it is permitted only from one specifically authorized agent-owned source profile; scope it to the minimum domains and task, do not reveal cookie values, and do not use it to bypass MFA, consent, or account-access controls.
4. Confirm any side effect from the resulting page state. Before sending, submitting, deleting, installing, authorizing, or publishing, verify the target and requested scope.
5. Close tabs opened solely for the task when they are no longer useful.

## Authorized credential reuse (the safe cookie-copy contract)

`browserclaw` documents the cookie decrypt + inject flow as the headless fallback for fingerprint-tolerant sites. **Credential reuse requires explicit task authorization.** An existing sign-in alone is NOT sufficient authorization to copy or decrypt cookies. When the user explicitly authorizes local cookie transfer for the requested authenticated-content task, the guarded lifecycle below is permitted. If explicit authorization has not been granted for the task, credential reuse MUST be denied: fail closed and emit a one-line blocker asking the user for authorization or manual action.

When authorized, use this contract for any credential-bearing flow:

```bash
# Canonical guarded lifecycle for authorized credential reuse.
# Fail-closed: any decrypt/inject/Playwright failure aborts before
# persisted credential state, and INT/TERM/HUP also trigger cleanup.
# One canonical cleanup trap removes BOTH the cookie file and the page
# text on every success, error, and signal. The secret branch runs
# INSIDE this trap, and the explicitly authorized agent-owned source
# produces the cookie artifact the canonical recipe consumes before cleanup.
set -euo pipefail
# Restrict the process umask so any mktemp / redirect that does
# not respect an explicit chmod still ends up owner-only. The
# browserclaw's writer uses Path.write_text(), so chmod 600 is
# re-applied after the decrypt write.
umask 077
# Pre-initialize variables and arm cleanup traps BEFORE allocating
# temp files so INT/TERM/HUP cannot leave orphaned artifacts during
# the allocation window.
TMP_COOKIES=""
TMP_PAGE=""
# INT/TERM/HUP handlers MUST terminate nonzero after cleanup so
# a signal during a long decrypt/inject does not let bash
# continue past the trap and recreate credential files.
cleanup_browser_creds() {
  local rc=$?
  rm -f ${TMP_COOKIES:+"$TMP_COOKIES"} ${TMP_PAGE:+"$TMP_PAGE"}
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

TMP_COOKIES="$(mktemp -t browserclaw-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-page-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE"

# 1. Decrypt exactly one explicitly authorized agent-owned source. The
#    caller must set these values to the task-owned profile/DB and its
#    matching Safe Storage entry; placeholders fail closed rather than
#    selecting a desktop browser profile by convention.
SOURCE_DB='<agent-owned-source-db>'
SOURCE_KEYCHAIN_SERVICE='<agent-owned-keychain-service>'
SOURCE_KEYCHAIN_ACCOUNT='<agent-owned-keychain-account>'
# Credential acquisition has one bounded status-capture boundary. It is not a
# source sweep: the caller supplies exactly one authorized agent-owned source.
# Errexit is restored before the decrypted artifact is chmod'd or consumed.
source_status=0
set +e
if [ ! -f "$SOURCE_DB" ]; then
  echo "BLOCKER: authorized agent-owned source DB is unavailable" >&2
  source_status=11
else
  env -i HOME="$HOME" \
    PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    browserclaw cookies decrypt --db "$SOURCE_DB" \
      --output "$TMP_COOKIES" \
      --keychain-service "$SOURCE_KEYCHAIN_SERVICE" \
      --keychain-account "$SOURCE_KEYCHAIN_ACCOUNT" \
      --domain-filter '%<target-domain>%' --summary >/dev/null
  source_status=$?
fi
set -e
if [ "$source_status" -eq 11 ]; then
  exit 11
fi
if [ "$source_status" -ne 0 ]; then
  echo "BLOCKER: authorized agent-owned source cookie decryption failed" >&2
  exit "$source_status"
fi
chmod 600 "$TMP_COOKIES"

DECRYPT_COUNT="$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)"
if [ "$DECRYPT_COUNT" -le 0 ]; then
  echo "BLOCKER: no <target-domain> cookies in the authorized agent-owned source." >&2
  exit 11
fi

# 2. Inject + navigate headless Chromium. Keep body text private and temporary.
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

# 3. Read only the fields needed for the task, then trust the EXIT
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
# Self-contained: it decrypts one explicitly authorized agent-owned
# source profile/DB to obtain $TMP_COOKIES, then a bare Playwright script that emits
# the boolean to stdout only. The EXIT/INT/TERM/HUP trap removes
# every browserclaw temp file on every signal, and the signal
# handlers re-raise the signal so the script exits nonzero.
set -euo pipefail
# Restrict the process umask so any mktemp / redirect that does
# not respect an explicit chmod still ends up owner-only. The
# browserclaw's writer uses Path.write_text(), so chmod 600 is
# re-applied after the decrypt write.
umask 077
# Pre-initialize variables and arm cleanup traps BEFORE allocating
# temp files so INT/TERM/HUP cannot leave orphaned artifacts during
# the allocation window.
TMP_COOKIES=""
TMP_PAGE=""
SECRET_STDOUT_BUF=""
cleanup_secret_branch() {
  local rc=$?
  rm -f ${TMP_COOKIES:+"$TMP_COOKIES"} ${TMP_PAGE:+"$TMP_PAGE"} ${SECRET_STDOUT_BUF:+"$SECRET_STDOUT_BUF"}
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

TMP_COOKIES="$(mktemp -t browserclaw-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-page-XXXXXX.txt)"
SECRET_STDOUT_BUF="$(mktemp -t browserclaw-secret-out-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE" "$SECRET_STDOUT_BUF"

# 1. Decrypt exactly one explicitly authorized agent-owned source.
SOURCE_DB='<agent-owned-source-db>'
SOURCE_KEYCHAIN_SERVICE='<agent-owned-keychain-service>'
SOURCE_KEYCHAIN_ACCOUNT='<agent-owned-keychain-account>'
# Credential acquisition has one bounded status-capture boundary. It is not a
# source sweep: the caller supplies exactly one authorized agent-owned source.
# Errexit is restored before the decrypted artifact is chmod'd or consumed.
source_status=0
set +e
if [ ! -f "$SOURCE_DB" ]; then
  echo "BLOCKER: authorized agent-owned source DB is unavailable" >&2
  source_status=11
else
  env -i HOME="$HOME" \
    PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    browserclaw cookies decrypt --db "$SOURCE_DB" \
      --output "$TMP_COOKIES" \
      --keychain-service "$SOURCE_KEYCHAIN_SERVICE" \
      --keychain-account "$SOURCE_KEYCHAIN_ACCOUNT" \
      --domain-filter '%<target-domain>%' --summary >/dev/null
  source_status=$?
fi
set -e
if [ "$source_status" -eq 11 ]; then
  exit 11
fi
if [ "$source_status" -ne 0 ]; then
  echo "BLOCKER: authorized agent-owned source cookie decryption failed" >&2
  exit "$source_status"
fi
chmod 600 "$TMP_COOKIES"

if [ "$(jq -r '.cookies | length' "$TMP_COOKIES" 2>/dev/null || echo 0)" -le 0 ]; then
  echo "BLOCKER: no <target-domain> cookies in the authorized agent-owned source." >&2
  exit 11
fi

# 2. Run a bare Playwright script: read $TMP_COOKIES, inspect DOM, emit the
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

- Credential reuse requires explicit task authorization; existing sign-in alone is not sufficient authorization to sweep or decrypt cookies.
- The cookies JSON and any captured private body text live only in private mode-600 temp files, are never committed or logged, and are removed by an EXIT trap on success and failure.
- Use `--summary` when only a domain/name/length check is needed; never log raw values.
- **Never** route credential-bearing flows through `browserclaw capture` / `learn` / `reverse` — those commands persist full HTTP request/response traffic to a `capture.har` file on disk, which CAN contain the new secret in plaintext (the exact leak class this skill's credential rule already bans). For those flows, use `cookies inject` (navigation only, no HAR) or a bare Playwright script, read the result from the DOM/page text, and do not persist the raw network traffic.
- A channel choice alone proves neither headless launch mode nor session isolation. Set headless mode explicitly, use an isolated task-owned profile, and verify the launched process arguments and profile path. Do not launch system Chrome or enumerate desktop windows/listeners as a fallback.

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
- **Aside additionally requires a real, rendered display — not just an unsandboxed process.** On a headless host (`ioreg -c IODisplayConnect | grep -c IODisplayConnect` returns `0`), the Aside daemon answers metadata-only calls (`account list`) fine but navigation fails with `This task is not bound to a browser profile. Open it in Aside browser and try again.` For ordinary **fingerprint-tolerant** sites, proceed to the guarded browserclaw `cookies decrypt` + `cookies inject` headless fallback (route 3 in the numbered order) if explicitly authorized. **The fingerprint-sensitive Aside-only exception overrides this rule with NO fall-through:** for LinkedIn, banks/brokerages, Cloudflare/Akamai-protected, and user-declared no-headless sites, post the ONE-LINE display blocker and never attempt cookie injection, `browserclaw capture`, `learn`, `reverse`, or Playwright. The escape hatch (`browserclaw capture --headless --url ...` below) is a NARROW no-credentials discovery tool only and is NOT a substitute for the numbered routes.
- **Aside has no headless mode** (`aside --help` lists no such flag) — it drives real browser profiles of the running macOS app, so it is not CI-safe. With a connected agent-owned profile, `aside repl --account <id>` tabs run without changing the frontmost app (measured 2026-10-27, CLI 1.26.1023.1115). After an app restart, profiles show `disconnected` in `aside host profiles` and `aside repl` fails with `profile ... is not connected to the daemon`; treat that as Aside unavailable and use isolated headless Chromium, except for the fingerprint-sensitive Aside-only sites above, which stop at the one-line display blocker.
- **`browserclaw` as a headless-Chromium fallback** (route 3 in the numbered order): when explicitly authorized for the task, use `browserclaw cookies decrypt` + `cookies inject` to carry over an authenticated session from one specifically authorized agent-owned source profile, using the matching Safe Storage entry and the same browser/session family per the "Authorized credential reuse" contract above. **`browserclaw capture --headless --url <url> [--goal "<task>" --provider <p> --model <m>]` is a separate, narrow discovery tool** (Playwright-backed, no display or GUI session required, confirmed working on the same headless host where Aside failed) — it is NOT the headless fallback for authenticated flows and is NOT permitted for credential-bearing targets. **Do not route credential-bearing flows (API key creation/rotation, token/secret pages, password/banking/recovery-code pages) through `capture`/`learn`/`reverse`** — those commands persist full HTTP request/response traffic to a `capture.har` file on disk, which will contain the new secret in plaintext (the exact leak class this skill's credential rule already bans). For those flows, use `cookies inject` (navigation only, no HAR) or a bare Playwright script that reads only minimum non-secret DOM state, emit only a boolean/status result, and persist neither DOM text nor images (see the secret-bearing page branch below).

## Completion

Report browser mode, the confirmed result, and any blocker. For browser-dependent actions, attach a focused screenshot when it is safe and useful.
