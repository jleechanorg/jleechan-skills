# PR 659 specification: optional Grok browser transport

## Outcome

Add a secondary, read-only Node/Playwright transport for the existing grokbot skill. It opens a dedicated Grok Chrome profile for user sign-in, lists bot-navigation links as unverified candidates, and reads the tail of one explicitly supplied bot URL. The supported browser-control workflow remains the default. This helper does not send messages.

## Non-goals

- Proving which Grok account is signed in or that a bot URL belongs to that account.
- Treating listed links or titles as an authoritative account inventory.
- Sending messages, creating bots, changing account state, repairing authentication, or automating credentials.
- Proving authenticated Grok behavior or the current external Grok UI through offline tests.
- Replacing the supported browser-control interface or its identity and one-writer checks.

## Acceptance

- `login` opens the dedicated `~/.config/grokbot-chrome` profile visibly for user sign-in; it does not enter credentials.
- `list` and `read` stop unless `GROKBOT_IDENTITY_CONFIRMED=1` is supplied as caller acknowledgment. This flag is not identity verification.
- `list` accepts only Grok home or a valid Grok bot URL, extracts links only from the configured navigation selectors, filters them through the shared URL guard, and labels all returned candidates `verified: false`. With no matching navigation scope it returns no routes and reports `none-matched`.
- `read` accepts only a normalized `https://grok.com/bot/<id>` URL and prints page text only when navigation lands on the requested bot pathname.
- The focused contract suite imports the shipped URL-guard module and covers URL, redirect, list-scope, and portability/skill assertions. Passing that suite establishes offline source contracts only; it does not establish account identity, successful sign-in, or correct live conversation content.
- No helper mode sends or mutates Grok content.

## User stories

As an operator who has already checked the signed-in account through an authorized interface, I want an optional way to inspect candidate bot routes and read one existing conversation without sending or changing anything.

As a reviewer, I need the tool to disclose that route and account ownership remain unverified, so I do not mistake a navigation link or page text for proof of identity or conversation correctness.

## Proof plan

Run `python3 -m unittest tests.test_grokbot_and_private_reminder -v` and `node --check` on both `grok_chrome.mjs` and `url-guard.mjs`. Inspect the actual diff and portability of exported skill content. Keep any live authenticated-browser claim open unless a separately authorized, isolated session produces direct rendered-page evidence; this PR's existing body says no authenticated Grok session was run.

## Mock or justified exemption

No product UI is changed, and the external Grok sign-in UI is not controlled by this repository; a visual mock would falsely imply control over that page. This CLI output sketch is a contract example, not a runtime capture:

```text
login: GROKBOT_LOGIN_OPEN sign in in the window; close it when done
list:  {"scope":"bot-navigation", "verified":false, "candidates":[...]}
read:  final conversation page text, only after exact requested-path check
```

An unmatched navigation scope yields `scope: none-matched` and an empty candidate list.

## Risk

The helper does not establish account identity. `GROKBOT_IDENTITY_CONFIRMED=1` is only an operator acknowledgment, and navigation links are candidates rather than proof of account ownership. Even an exact-path page can contain an error or empty state; the helper does not verify that its body is a valid conversation. The helper therefore remains optional, read-only, and secondary to the supported browser-control route. No authenticated runtime proof is included in the current receipts.
