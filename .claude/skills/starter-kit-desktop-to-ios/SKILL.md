---
name: starter-kit-desktop-to-ios
description: Turn an existing desktop app into a native-feeling Expo iOS companion or replacement. Map desktop workflows and stack choices to mobile user stories, then iterate against actual iPhone visuals.
---

# Starter Kit Desktop to iOS

Use [Starter Kit iOS](../starter-kit-ios/SKILL.md) for scaffold, build, evidence and release boundaries. Use this kit first to decide what to port. Read the desktop app, its screens, routes, data formats, persistence and service boundaries; do not modify it unless the user separately asks. Build the iOS app in the requested new target with separate signing, URL scheme and environments.

## 1. Choose the phone-sized job

- Inventory the desktop actions by user outcome, not by screen. Tag each as **keep**, **redesign**, **defer**, or **desktop only**. Pick a companion (capture, check, or act on the go) unless the brief asks for a full replacement. Make omitted desktop features explicit.
- Generate mobile stories before building. Example: “As a field operator, I can open the last project, add a note offline, and see it sync exactly once when I reconnect.” Add Given/When/Then for one-handed entry, returning from background/relaunch, offline or permission-denied recovery, and the actual persisted result. Use synthetic fixtures and real authorized integration only where the story requires it.
- Mock desktop → mobile for each selected task. Replace dense toolbars, keyboard shortcuts, multi-pane windows and right-click menus rather than shrinking them. Use stacks for drill-down, tabs for a few persistent destinations, sheets for bounded choices, and explicit touch actions for hidden shortcuts. Use iPad split layout only when in scope; keep serious desktop-only bulk operations on desktop unless a mobile alternative is part of the brief.

## 2. Pick a stack for what already exists

| Existing app | Recommended iOS bridge |
| --- | --- |
| Electron, Tauri, or web UI | Expo/React Native/TypeScript for screens. Reuse pure JS/TS models, validation, formatting, and API client logic when portable. Replace DOM/CSS, Node filesystem, IPC, and desktop window APIs; don't wrap the whole UI in a WebView by default. |
| Python, .NET, Java, or other service-backed desktop | Keep the typed API contract. Reuse the existing service only in an explicitly approved, isolated staging or development environment; otherwise use fixtures or a separate backend. Build a new Expo client with environment selection and auth appropriate to the new app. Do not port desktop-only runtime code into mobile JS. |
| Native macOS/Swift, Windows, or Qt desktop | Preserve product behavior and portable fixtures. Reuse domain logic through an existing API or a deliberate shared core if it earns its cost. Add a native Expo module only for a capability not covered by an Expo/RN library. |
| Desktop-local files or database | Start with approved import/export or a mobile-local store. Add explicit sync only if needed, with stable IDs, retries, conflicts, and recovery tests. Never point the phone at a desktop DB file or a guessed private host. |

- Use Expo libraries for document picking, sharing, secure storage and other OS capabilities only when needed. Replace file-path assumptions with URIs and explicit import/export. Replace persistent desktop connectivity with bounded foreground reconnect and safe resume; do not promise background runtime that iOS won't provide.
- For API-backed ports, test the same synthetic record on both surfaces when allowed; compare IDs, data and changes, not visual parity. Reuse interface contracts, not desktop credentials or user data.
- Configure local dev, fixture, and approved environment separately. Record versions as in Starter Kit iOS. Skip Apple/Expo account setup, publishing and real service writes until the required permissions and new app identities exist.

## 3. Build, compare, and iterate

1. Capture the desktop task's starting and ending states as a reference, when available; label a sketch if the desktop app isn't accessible. Capture the first mobile attempt with the same story, then iterate on the actual Expo phone UI. Test the emulator/simulator with appropriate keyboard, permission, and network conditions. Use mobile web first where the same component path is supported; do not count it as native.
2. Review one action at a time: is it discoverable without desktop affordances? Does the outcome match the story? Do long text, safe areas, input focus, back gestures and interrupted/resumed flows work? Record the exact commit and evidence per story; fix failures and replay before asking for sign-off.
3. Exit with a feature mapping (implemented/deferred), stack decision, test and recording receipts, and a list of open findings. Get actual visual acceptance from the designated reviewer or user if required; don't call an uninspected recording or an untested shared-data assumption accepted.

### Handoff request

> Port **[desktop app or repo/ref]** to a new Expo iOS app in **[target]**. Start with **[one desktop task to redesign for a phone]**. Generate mobile user stories, identify which logic can be reused, choose the smallest viable stack, and build a working slice. Show desktop reference versus native mobile outcome, revise until visual acceptance, and don't upload or release.
