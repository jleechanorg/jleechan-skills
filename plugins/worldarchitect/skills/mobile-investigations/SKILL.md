---
name: mobile-investigations
description: Use for mobile browser investigations in this repo, especially Firebase/Google auth, iOS Safari or Chrome iOS, Incognito/Private Browsing, storage partitioning, redirect flows, and user-visible mobile-only failures.
---

# Mobile Investigations

Use this workflow when investigating a mobile-only bug, especially auth flows
involving Firebase, Google OAuth, redirects, iframes, browser storage, or
Safari/Chrome iOS behavior.

## First classify the claim

Before running tests, write the exact same-symptom target and use one of these
verdict labels:

- `REPRO`: the same user-visible symptom happens. For the mobile auth bug, that
  means the browser returns from Google to the app and remains unauthenticated
  on the welcome/sign-in surface.
- `RELATED_REDIRECT_BOUNDARY_REACHED`: the flow reaches a related boundary such
  as `worldarchitecture-ai.firebaseapp.com/__/auth/handler` or
  `accounts.google.com`, but does not prove the user-visible failure.
- `RELATED_SILENT_NULL_SIGNATURE`: `getRedirectResult()` resolves without an
  error and without a user, e.g. `{resolved: true, hasUser: false, error: null}`.
- `NON_REPRO`: auth succeeds, or failure is an unrelated OAuth/config/network
  error such as `redirect_uri_mismatch`, blocked connection, or missing test
  credentials.

Do not call a lower-fidelity storage or redirect boundary test an exact repro
unless it produces the same user-visible symptom.

## Fidelity ladder

Climb only as far as the claim requires:

1. Refresh live PR/branch/deploy state: PR URL, head SHA, preview/prod URL,
   `authDomain`, `/__/auth/handler`, CSP/proxy behavior, and current evidence.
2. Prefer an existing repo harness before inventing one. For this mobile auth
   family, check:
   - `$PROJECT_ROOT/frontend_v1/tests/mobile_auth_emulator_repro/README.md`
   - `testing_ui/mobile_3pc_repro/` when present on the branch or related PR.
3. Use Playwright Chromium for basic redirect and third-party-storage boundary
   checks. Treat it as related evidence, not iOS proof.
4. Use Playwright WebKit with an iPhone profile for the WebKit storage
   signature. Record the exact JSON state and screenshots.
5. Use iOS Simulator Safari or MobileSafari Private Browsing when the claim is
   iOS-engine behavior. Capture the before/action/after screenshots or video.
6. Use a physical device or trusted device cloud only for exact Chrome iOS
   Incognito claims. Verify BrowserStack/Sauce/test-account environment
   variables by name only; never print secret values.

## Commands

Use Node 22 for Node-based mobile harnesses:

```bash
PATH=$HOME/.nvm/versions/node/v22.22.0/bin:$PATH node --version
```

For the same-origin Firebase auth helper repro in this PR family:

```bash
cd $PROJECT_ROOT/frontend_v1/tests/mobile_auth_emulator_repro
PATH=$HOME/.nvm/versions/node/v22.22.0/bin:$PATH node run_repro.mjs
```

For the third-party-storage/silent-null repro when available:

```bash
PATH=$HOME/.nvm/versions/node/v22.22.0/bin:$PATH \
  node --test --test-timeout=90000 testing_ui/mobile_3pc_repro/repro_3pc_auth.spec.mjs
```

Run targeted unit/integration checks for any code you change. For the mobile auth
same-origin fix, the minimum local regression checks are:

```bash
PATH=$HOME/.nvm/versions/node/v22.22.0/bin:$PATH \
  node --test $PROJECT_ROOT/frontend_v1/tests/auth_domain_resolution.test.js

TESTING=true ./vpython -m pytest $PROJECT_ROOT/tests/test_firebase_auth_helper_proxy.py -q
```

## Evidence requirements

Produce a short evidence table with:

- exact repo path, branch, PR URL, and head SHA
- browser/device mode and whether it is normal, Private Browsing, or Incognito
- exact URL topology: app origin, auth handler origin, same-origin vs
  cross-site/cross-origin
- verdict label from the first section
- artifact paths for JSON, screenshots, GIF/video, logs, and checksums when
  evidence will be cited in a PR
- remaining unproven scope

For mobile auth, explicitly say whether the evidence proves:

- popup-to-redirect transport
- third-party-storage or partitioning boundary
- WebKit/iOS engine behavior
- exact Chrome iOS Incognito user-visible failure
- production readiness after OAuth Authorized redirect URI registration

## Common pitfalls

- Do not mistake reaching `/__/auth/handler` for reproducing the final failure.
- Do not overclaim desktop Chromium evidence for Chrome iOS; Chrome iOS uses
  WebKit.
- Do not use dynamic preview hosts as same-origin `authDomain` unless their
  exact `https://<host>/__/auth/handler` URI is registered in Google Cloud.
- Do not print passwords, OAuth tokens, Firebase keys beyond already-public
  client config, or BrowserStack/Sauce credentials.
- If the flow succeeds on iOS Safari/Chrome normal mode, classify it as
  `NON_REPRO` for the exact failure and keep climbing only if the claim requires
  Incognito/Private Browsing.
