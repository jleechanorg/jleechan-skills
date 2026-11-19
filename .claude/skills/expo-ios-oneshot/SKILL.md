---
name: expo-ios-oneshot
description: Build a new Expo iOS app from a brief in one pass, from a clean project through a tested vertical slice and a native simulator handoff. Use for greenfield React Native apps; not for modifying or releasing an existing app.
---

# One-shot Expo iOS app

Turn the product brief into a runnable app, not a plan. Start in a new directory or an empty target repo. Use an existing app as a **read-only architecture reference** only if the requester supplies it and access is available. Reuse the working patterns, not the codebase, brand, identifiers, credentials, users, assets, or release automation.

## 1. Freeze the target and one user journey

- Record the app name, target repo/path, one primary user, and one journey with an observable end state. If the brief is loose, choose reversible defaults and write them down. Reserve questions for decisions that block implementation or require authorization.
- Default to Expo + React Native + TypeScript + npm lockfile. For matching a supplied reference, read its package manifest/lockfile, Node pin, app config, native plugins, CI, and build profiles at a fixed revision. Pin a compatible SDK/React/RN/Node combination; do not copy the dependency list or use a new SDK template while claiming to match an older SDK. Without a reference, pick a currently supported Expo template and record the resolved versions.
- Keep a new app's display name, bundle ID, URL scheme, Expo project, backend/auth projects and environments distinct. Set a unique dev identifier before native install. Don't link, register, or upload to an existing project as a shortcut. Choose one navigation system; keep data and service adapters outside screens.
- Start from the Expo template matching that decision ([Expo setup](https://docs.expo.dev/build/setup/)). Use `npx expo install` for Expo/native dependencies, commit package.json and its lockfile together, and prove a clean `npm ci`. Prefer config plugins over hand-edited generated projects. Never use clean prebuild over uncommitted or maintained native sources.

## 2. Build the slice

- Deliver the shortest complete flow with a polished iPhone layout and real actions. For an AI story app: Library → create/open a campaign → read the first scene → commit one choice → return to Library → reopen the same saved campaign. Give it original art or intentional placeholders, legible text, safe areas, keyboard handling, and accessible controls.
- Treat streaming and persistence separately: show incremental output, but commit one completed turn by stable ID; interrupted or rejected responses must not fabricate a turn. Exercise one failure/retry path and one empty/loading state. Build the storage seam first; real API/auth comes through an adapter when approved and required.
- Provide a deterministic local mode from a clean clone so the slice works without accounts. Label fixture data, auth and provider output explicitly. For real auth, restore sessions across restart and test account isolation; use an approved isolated backend and dedicated test users. Do not send private data to a model. Provider keys, signing keys, and server secrets never go in JS bundles or `EXPO_PUBLIC_*`. Use backend-mediated provider calls.

## 3. Prove it, web first and native second

1. Run `npm ci`, `npx expo-doctor`, the project typecheck (e.g. `npm run typecheck`), and focused tests. Add the missing scripts/tests if the template has none. Test state restoration and at least one interrupted or failed request; assert on the actual outcome, not just exit codes or UI prose.
2. Run the same Expo UI on phone-sized web where supported (`npx expo start --web`). Capture the clean baseline and the working path when a behavioral comparison exists. Label any fixture rather than presenting it as real service integration.
3. For native proof use an authorized macOS host with Xcode and an installed iOS Simulator runtime. Record `xcodebuild -version` and `xcrun simctl list devices available`, and select an isolated available simulator. Compile using the [Expo local iOS build flow](https://docs.expo.dev/guides/local-app-development/); for unattended testing use a supported headless build/install/launch route, not UI automation against a shared simulator. Verify the installed app and exact bundle ID, exercise the flow at least once, relaunch, and re-open the saved item. Capture a continuous portrait recording plus a short receipt. Expo Go, web, and a successful JS export are not installed-native proof. If no authorized Mac/runtime is available, finish the other checks and say native verification is blocked.
4. Linux CI can run typecheck and tests; an iOS simulator or signed archive uses macOS. Do not turn on CI publishing triggers as part of the first build. An EAS simulator profile is optional when already authorized. Device signing, store distribution, TestFlight upload and release are distinct steps: use only the new app's approved identities and existing authorized signing path. Stop for any required access or approval. See [EAS profiles](https://docs.expo.dev/build/eas-json/) and [submission](https://docs.expo.dev/submit/ios/). A queued build, archive, skipped CI job or successful workflow aggregate does not establish upload or App Store Connect processing.

## Agent handoff

Use the following input format, then implement without stopping at planning:

> Build **[app]** in **[empty target]**. Its first runnable journey is **[user action → visible outcome → reopen evidence]**. Use **[optional authorized Expo reference/ref]** read-only. Start with a deterministic fixture and add **[approved service, or none]**. Deliver a clean checkout, startup commands, tests, and a native simulator receipt if a supported Mac is available. Do not upload or release.

Return the repo/ref, exact install and start commands, resolved toolchain, passing/failing checks, recording or explicit blocker, and what used real services versus fixtures. If publishing was requested, use the target repo's draft PR workflow. Put outstanding store/signing steps last and report only the stage actually verified.
