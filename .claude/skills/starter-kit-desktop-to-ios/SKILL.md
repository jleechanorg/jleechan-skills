---
name: starter-kit-desktop-to-ios
description: Turn an existing desktop app into a native-feeling Expo iOS companion or replacement. Map desktop workflows and stack choices to mobile user stories, then iterate against actual iPhone visuals.
---

# Starter Kit Desktop to iOS

This guide is standalone. Use it first to decide what to port. [Starter Kit iOS](../starter-kit-ios/SKILL.md) is optional background for a greenfield app. Read the desktop app, its screens, routes, data formats, persistence and service boundaries; do not modify it unless the user separately asks. Build the iOS app in the requested new target with separate signing, URL scheme and environments.

## Install and verify the toolchain

| When | Install | Verify |
| --- | --- | --- |
| Every project | Git, Node.js LTS compatible with the chosen Expo SDK, and npm (included with Node). Use your host package manager for Git and an official Node distribution or existing version manager. | `git --version`, `node --version`, `npm --version`. Record the exact versions and commit a Node version pin. |
| App dependencies | Use a pinned `create-expo-app` release and an explicit matching TypeScript template: `npx create-expo-app@<exact-version> <new-directory> --template <sdk-matched-template>` (substitute both pins). React, React Native, Expo CLI and TypeScript come from the project, not global installs. | Commit `package.json` and `package-lock.json`; run `npm ci`, `npx expo-doctor`, typecheck and focused tests. |
| Mobile web proof | Use a browser. If the template lacks web support, run `npx expo install react-dom react-native-web @expo/metro-runtime`. | `npx expo start --web`; exercise the real Expo screen at phone width. |
| Local native iOS proof | Install full Xcode on an authorized Mac. In Xcode select its Command Line Tools and download a compatible iOS Simulator runtime. Use CocoaPods if the resolved native project needs it; follow the project's pinned Ruby/Bundler/Gemfile if present, otherwise use the [CocoaPods installer](https://guides.cocoapods.org/using/getting-started.html). Install Watchman only if the selected Expo SDK requires it (see [Expo's simulator setup](https://docs.expo.dev/workflow/ios-simulator/)). | `xcodebuild -version`, `xcrun simctl list devices available` and, if needed, `bundle exec pod --version` or `pod --version`. On an isolated simulator use `npx expo run:ios --device` and select that simulator; open the installed app. |
| Optional integration, device distribution or cloud build | Install only the chosen service tools (e.g. a local emulator) or an exact EAS CLI version if an authorized EAS route is needed. A custom Expo development client may add `npx expo install expo-dev-client`; Android Studio and a global Expo CLI are not required for this iOS kit. | List the exact tools, versions, commands and purpose in the target README. Once Xcode is installed, no Apple Developer membership, Expo account, distribution signing, submission or paid service is required for the fixture and local simulator path. |

Use [Expo's setup guide](https://docs.expo.dev/get-started/set-up-your-environment/) to resolve compatible versions. List each task-selected package or external service tool in the README as **required** or **optional**, with platform, exact install/start commands, required environment variable *names* and a no-credentials fixture path. Never copy credentials or install unrelated software.

## 1. Choose the phone-sized job

- Inventory the desktop actions by user outcome, not by screen. Tag each as **keep**, **redesign**, **defer**, or **desktop only**. Pick a companion (capture, check, or act on the go) unless the brief asks for a full replacement. Make omitted desktop features explicit.
- Generate mobile stories before building. Example: “As a field operator, I can open the last project, add a note offline, and see it sync exactly once when I reconnect.” Add Given/When/Then for one-handed entry, returning from background/relaunch, offline or permission-denied recovery, and the actual persisted result. Use synthetic fixtures and real authorized integration only where the story requires it.
- Mock desktop → mobile for each selected task. Replace dense toolbars, keyboard shortcuts, multi-pane windows and right-click menus rather than shrinking them. Use stacks for drill-down, tabs for a few persistent destinations, sheets for bounded choices, and explicit touch actions for hidden shortcuts. Use iPad split layout only when in scope; keep serious desktop-only bulk operations on desktop unless a mobile alternative is part of the brief.

## 2. Pick a stack for what already exists

| Existing app | Recommended iOS bridge |
| --- | --- |
| Electron, Tauri, or web UI | Expo/React Native/TypeScript for screens. Reuse pure JS/TS models, validation, formatting, and API client logic when portable. Replace DOM/CSS, Node filesystem, IPC, and desktop window APIs; a WebView may show bounded web content where the story calls for it, but wrapping or merely scaling the desktop UI does not satisfy the port. |
| Python, .NET, Java, or other service-backed desktop | Keep the typed API contract. Reuse the existing service only in an explicitly approved, isolated staging or development environment; otherwise use fixtures or a separate backend. Build a new Expo client with environment selection and auth appropriate to the new app. Do not port desktop-only runtime code into mobile JS. |
| Native macOS/Swift, Windows, or Qt desktop | Preserve product behavior and portable fixtures. Reuse domain logic through an existing API or a deliberate shared core if it earns its cost. Add a native Expo module only for a capability not covered by an Expo/RN library. |
| Desktop-local files or database | Start with approved import/export or a mobile-local store. Add explicit sync only if needed, with stable IDs, retries, conflicts, and recovery tests. Never point the phone at a desktop DB file or a guessed private host. |

- Use Expo libraries for document picking, sharing, secure storage and other OS capabilities only when needed. Replace file-path assumptions with URIs and explicit import/export. Replace persistent desktop connectivity with bounded foreground reconnect and safe resume; do not promise background runtime that iOS won't provide.
- For API-backed ports, test the same synthetic record on both surfaces when allowed; compare IDs, data and changes, not visual parity. Reuse interface contracts, not desktop credentials or user data.
- Configure local dev, fixture, and approved environment separately. Record exact versions and commands in the target README. Skip Apple/Expo account setup, publishing and real service writes until the required permissions and new app identities exist.

## 3. Build, compare, and iterate

- Scaffold a new pinned Expo + React Native + TypeScript npm project using the install table. Ship a clean-clone deterministic fixture without accounts. Commit a lockfile and add project typecheck and focused tests; use `npx expo install` for native modules. Verify `npm ci`, `npx expo-doctor`, typecheck and the primary story plus failure/recovery before visual acceptance.
- Keep a unique bundle ID, URL scheme, Expo project, app registration, auth client and development data. Inspect resolved identities, signing targets and any push-triggered build/submit workflows before native build, upload or first push. Stop on collisions or unapproved automation; don't reuse reference credentials, enable publishing or upload. Local simulator verification is not TestFlight or App Store acceptance.

1. Capture the desktop task's starting and ending states as a reference, when available; label a sketch if the desktop app isn't accessible. Capture the first mobile attempt with the same story, then iterate on the actual Expo phone UI. Test the emulator/simulator with appropriate keyboard, permission, and network conditions. Use mobile web first where the same component path is supported; do not count it as native. Without an authorized Mac/runtime or a verified installed-device run, report native verification as blocked. On a simulator or authorized installed device, identify the exact bundle ID and commit, exercise the story, verify the outcome after relaunch where relevant, and capture one continuous portrait recording unless the app is landscape-only. A web run or an unlaunched build does not count.
2. Review one action at a time: is it discoverable without desktop affordances? Does the outcome match the story? Do long text, safe areas, input focus, back gestures and interrupted/resumed flows work? Record the exact commit and evidence per story; fix failures and replay before asking for sign-off.
3. Exit with a feature mapping (implemented/deferred), stack decision, test and recording receipts, and a list of open findings. Get actual visual acceptance from the designated reviewer or user if required; do not accept an uninspected recording, a desktop wrapper, or a story that fails its expected outcome.

### Handoff request

> Port **[desktop app or repo/ref]** to a new Expo iOS app in **[target]**. Start with **[one desktop task to redesign for a phone]**. Generate mobile user stories, identify which logic can be reused, choose the smallest viable stack, and build a working slice. Show desktop reference versus native mobile outcome, revise until visual acceptance, and don't upload or release.
