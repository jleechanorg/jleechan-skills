# Reddit draft media: permission, editor persistence, and control-routing failures

## Status and scope

This is a sanitized incident/reproduction report, not a fix, browser instruction,
permission change, or claim that Reddit universally rejects draft images.
The observed task was to add existing, genuine gameplay screenshots to an existing
saved Reddit text draft without publishing it. The final inspected saved draft
remained text-only. No Post control was activated.

The incident occurred on October 26, 2026 in America/Los_Angeles (PDT, UTC−07:00),
corresponding to October 27 UTC. Exact application/browser builds were not captured.
Times below are original action/receipt times where available, not status-check
times. Approximate times and relayed observations are explicitly marked.

## Seven-element specification for this documentation change

1. **Outcome:** preserve a detailed, reproducible, privacy-safe account of four
   distinct failures and their recovery attempts, with honest evidence boundaries.
2. **Non-goals:** repair Reddit or the browser controller; change consent policy,
   custom rules, credentials, accounts, services, native state, or publication scope;
   publish a social post; claim a verified root cause.
3. **Acceptance:** distinguish observations from hypotheses; retain expected versus
   actual behavior, original times, reproduction prerequisites, steps, result checks,
   privacy exclusions, impact, recovery attempts, and open investigation questions.
4. **User story:** an operator investigating an unsuccessful draft-media task can
   identify which boundary failed without interpreting upload as saved persistence
   or repeating an uncertain external action. No product/UI change is shipped.
5. **Proof plan:** source-review this complete report against the available receipts;
   validate Markdown structure, whitespace, and absence of private identifiers;
   independently review the full document. No fresh browser reproduction is needed
   to validate this historical report; future reproductions need their own authority.
6. **Mock:** not applicable; this is an incident document, not a visual design.
7. **Risk:** public documentation could leak account/draft identifiers, private
   content, or overstate causality. Use symbolic identifiers and factual limits.

## Environment and prerequisites

| Component | Observed value or limit |
|---|---|
| OS/UI | Linux desktop with Chromium and X11 native window observations |
| Browser-control surface | Cloud/CDP tab controls, accessibility snapshots, screenshots, and documented native desktop controls |
| Editor | Reddit saved text-draft composer, rich-text body, Image control, Update Draft control |
| Browser/editor versions | Unknown; no version collection was performed |
| Account | Existing authenticated account; identifier intentionally omitted |
| Draft | One existing saved draft, referenced here as `DRAFT_A`; exact ID/URL omitted |
| Other saved drafts | Five were visible and inspected; they were not evidence that image persistence worked |
| Input media | Two existing PNG gameplay captures, `CHOICES.png` and `NARRATIVE.png`; not generated mocks |
| Media safety | Pixels inspected for private/authentication content before the authorized upload |
| Concurrent work | Another browser task yielded focus; unrelated application tabs were to remain unchanged |
| Control complication | Both an original Reddit tab and a separate inspection tab existed with the same saved-draft URL |

No credentials, auth storage, cookies, OTPs, native session IDs, account names,
private message IDs, private draft URLs, local personal paths, or screenshot pixels
are included here. Evidence labels below are report-local aliases, not public links.

## Four separate incident boundaries

### A. Upload approval pause versus task intent

An earlier upload attempt was reported as paused for approval. The operator later
had an explicit request for gameplay media in the drafts, inspected the current
saved drafts as text-only, and made one normal upload attempt with the new task
context. That later file-selection operation completed and visibly produced a two-item
carousel; remote upload completion was not independently observed.

The earlier pause does not establish that a later upload was prohibited, and the
later success does not establish that the earlier gate was erroneous. The exact
earlier policy decision payload is not reproduced in this public report. Task intent,
tool authorization, successful upload, editor insertion, and saved persistence are
five distinct facts. No alternate credential/API route was used to bypass a denial.

### B. Custom-rule save failure, separate from media persistence

The coordinating operator inspected two original completion receipts and supplied
these sanitized fields for this report. At October 26, 2026, 22:33:48 PDT, the
completion kind was `customRuleNotSaved`, reason `unavailable`, and public reason
was null. The next-step text said the rule could not be checked and could be tried
later. Approval of the displayed card did not mean the rule was saved.

After a separately requested retry, the October 26, 2026, 22:37:11 PDT completion
again had kind `customRuleNotSaved`, now with reason `invalid`. Its public reason
was: “Uploading files requires your approval, so this standing permission cannot
make uploads automatic.” The next step was to ask how to proceed. These are the
observed service outcomes, not a universal policy analysis or a successful change.
The document author received these receipt fields from the coordinating operator;
the author did not personally invoke or inspect the original rule-save operation.
No successfully saved standing rule is claimed. This is separate from the later
per-action upload result and the Reddit persistence failure.

The rule body, private instructions, and private communications are deliberately
excluded. This branch must be investigated with the original rule-save receipt in
its authorized private context, rather than reconstructed from this report.

### C. Successful file selection and carousel preview, failed saved-draft acceptance

Directly observed sequence:

1. The existing draft contained its original title, flair, and body text, with no
   attached media visible in the saved readback.
2. The normal Image/filechooser flow accepted two existing PNGs.
3. The editor displayed a carousel with `Item 1 of 2`, navigation controls,
   `Add images`, `Edit media`, `Add media to body`, and `Remove media`.
4. A screenshot showed the actual first gameplay image in the carousel.
5. `Update Draft` was disabled while the carousel was present; `Post` existed but
   was not selected.
6. The operator selected `Add media to body`. The carousel disappeared and
   `Update Draft` became enabled, but no image was visible in the body snapshot.
7. The operator selected `Update Draft`. The button became disabled afterward.
   No explicit success toast was captured, so button state alone was not accepted
   as proof that all desired content had saved.
8. Reopening the same saved-draft URL returned the original text without images.

**Expected:** media accepted by the composer can be inserted into the intended body
position, saved without publication, and remains present after reopening the draft.

**Actual:** upload preview was visible, but the final reopened saved draft was
text-only. File-selection/preview success was not persistence success. This does not prove whether
the fault lay in editor state, insertion behavior, upload processing, save semantics,
or automation control routing.

### D. Control/focus mismatch and bounded native recovery

Further recovery revealed an important confounder: a browser-tab snapshot and the
native desktop's active tab were not the same visible surface, although both showed
the same saved-draft URL. The native active tab was the older original tab; the
separate inspection tab was elsewhere in the strip. This was established from
actual desktop pixels, not inferred merely from a tab title.

Attempts to place the caret at the end through element-based key calls instead
inserted a paragraph break inside existing text. The unintended break was undone,
and the original paragraph was verified restored before continuing. This is a
control-target/caret observation, not proof that every browser API misrouted input.

The operator then explicitly selected the inspection tab with native controls,
clicked after the last text line, and used native end-of-document/newline keys.
A screenshot showed the caret on a new trailing paragraph, with the original text
intact. This materially changed the insertion prerequisite before the next attempt.

The native Image control opened an OS `Open Files` dialog. A parallel documented
filechooser listener on the tab timed out after 10 seconds even though the native
dialog was visibly open. The timeout was not a completed upload, nor proof that
the Image click did nothing. No repeated Image click was issued blindly.

Native location-entry recovery initially encountered an AT-SPI provider unavailable
error for the file dialog. The location field was visibly empty afterward. The
documented native character-entry fallback entered the existing PNG path and
confirmed the selection. The dialog closed, but no image/carousel appeared in the
editor. That attempt did not establish successful upload or insertion.

Bounded browser error inspection returned repeated `Error sending browser metadata
to extension: Object` messages. Those messages demonstrate a controller/extension
error was reported; they do not prove the causal chain to the missing image.
No Reddit-specific rejection or platform-level text-draft incompatibility was proven.

## Original action timeline

All times in this table are October 26, 2026, PDT. The date conversion matters:
the corresponding tool receipts were dated October 27 in UTC.

| Original time | Action/result | Evidence quality |
|---|---|---|
| 22:33:48 | Custom-rule completion: unavailable, not saved | Original completion fields inspected by coordinator; relayed to author |
| Before 22:34; exact time unavailable | Normal upload returned a two-image carousel | Direct upload result and subsequent pixels; exact completion time not retained here |
| 22:34:40–22:34:47 | Carousel screenshot showed gameplay and disabled Update Draft | Direct screenshot and accessibility observation; not a save claim |
| 22:34:53–22:34:56 | Add media to body removed carousel and enabled Update Draft | Direct before/after accessibility result |
| 22:34:56–22:35:13 | Update Draft selected; button disabled afterward | Direct action/result; no explicit saved-media confirmation |
| 22:35:20–22:35:35 | Same draft reopened and rendered text-only | Direct readback; persistence acceptance failed |
| 22:36:29–22:37:31 | Caret recovery attempts introduced a paragraph break, then undo restored original text | Direct text snapshots; no claim of saved text modification |
| 22:37:11 | Retried custom-rule completion: invalid, not saved | Original completion fields inspected by coordinator; relayed to author |
| 22:37:49–22:38:09 | Native desktop inspection identified original-tab versus inspection-tab mismatch; correct tab selected | Direct desktop pixels |
| 22:38:09–22:38:15 | Native caret placed on trailing blank paragraph | Direct screenshot |
| 22:38:15–22:38:36 | Native Image click; listener timed out after 10 seconds | Tool timeout; later screenshot proved dialog open |
| 22:38:46–22:39:08 | Native location entry hit AT-SPI error; empty field verified | Tool error plus screenshot |
| 22:39:14–22:39:41 | Supported character-entry fallback selected PNG; dialog closed; editor showed no image | Direct action/result and pixels; upload not verified |
| 22:39:41–22:39:50 | Read-only browser log inspection surfaced extension metadata errors | Log entries had original timestamps from 22:37:21 through 22:39:25 |
| 22:40:04–22:40:16 | Inspection tab retained for handoff | Handoff only, not repair or persistence proof |

## Reproduction protocol for an authorized investigation

This protocol describes the observed route. Do not run it against a real account
without explicit draft/media scope and an existing authorized session. Use a
non-sensitive disposable draft and synthetic local fixtures for a new investigation
when separately authorized; doing so would be a new reproduction, not this incident.

1. Record OS, browser build, controller build, editor variant, and draft type.
2. Use one identified writer and one target tab. Record a private target binding;
   public reports should use `DRAFT_A`, not the live account or draft identifier.
3. Read back the saved title/body/flair and media state. Preserve a private baseline.
4. Verify native focus and tab-specific snapshot refer to the same surface before
   key input. A matching URL/title alone is insufficient when duplicate tabs exist.
5. Place a caret in a known trailing paragraph and visually verify it. Do not assume
   an element-focused key call preserves the previous selection/caret.
6. Activate Image through the supported UI and select one approved PNG. Observe
   the chooser outcome before retrying anything. If a listener times out, inspect
   whether a native dialog is already open.
7. Record upload progress/completion, preview count, insertion controls, and whether
   Update Draft is enabled. A local preview alone is not proof of remote upload.
8. If the UI requires Add media to body, record the body before and after selecting
   it. Stop to diagnose if media vanishes; do not immediately declare insertion.
9. Save only through Update Draft, never Post. Record any actual confirmation/error.
10. Reopen the same saved draft after a known save completion. Verify image count,
    actual decoded pixels, body text, title, and flair. Reopening is mandatory for
    the persistence acceptance claim; a transient composer preview is insufficient.
11. If content is absent, classify the failed boundary and retain receipts. Avoid
    blind uploads, duplicated posts, hidden API calls, or credential workarounds.

## Evidence inventory and limits

| Alias | Retained observation | What it does not prove |
|---|---|---|
| E1 | Five saved-draft list and full-text screenshots in private storage | Media attached, public publication, or current media persistence |
| E2 | Two-item carousel accessibility state and gameplay preview pixels | Completed save or retained media after reopen |
| E3 | Add-to-body and Update-Draft before/after tool results | Server-side save acceptance for images |
| E4 | Same-URL reopened draft, original text and no visible images | Root cause or all Reddit draft types being unsupported |
| E5 | Desktop screenshots of original tab, selected inspection tab, and trailing caret | Stable routing for all later tool calls |
| E6 | Filechooser timeout plus native Open Files screenshot | Upload failure on the remote service; dialog was still open |
| E7 | AT-SPI error, empty location field, fallback selection, no inserted media | A confirmed uploaded file on that recovery attempt |
| E8 | Browser extension metadata errors with original timestamps | Causal explanation for media loss |
| E9 | Coordinator-inspected original custom-rule completion fields, unavailable then invalid | Author's direct inspection of original operation, a universal policy conclusion, or saved rule |

Original receipts/screenshots remain private. Public evidence aliases intentionally
omit access URLs, account identifiers, opaque tool/session IDs, and private pixels.
No raw network traffic, DOM-internal application state, credentials, or backend logs
were collected. Uploaded bytes were existing gameplay screenshots, not a new runtime
capture. This report is not a fairness, gameplay, authentication, or release test.

## Impact and investigation priorities

- The requested draft-media deliverable was not achieved despite visible upload
  preview; reporting it as completed would mislead the user.
- A permission pause and an invalid/unavailable custom-rule write can be confused
  with an editor defect. Keep separate incident IDs and receipts for each boundary.
- Duplicate tabs and mixed control surfaces can obscure which editor receives keys.
- Listener timeout and native dialog opening can coexist. Treat timeout as an
  uncertain intermediate state until the UI is inspected.
- Unintended text edits can occur during caret recovery. Undo and verify original
  content before further action; do not save damaged text.
- Prioritize a controlled tab-binding/caret test, then a single-image insertion/save
  test, then a two-image case. Collect actual application confirmation if exposed.
- Determine whether Add media to body requires a selection, placement, editor mode,
  or completed upload state not evident in the observed snapshots.
- Investigate controller metadata errors and chooser event routing independently.
  Correlation with the incident is not a proven root cause.

## Resolution criteria and current disposition

A fix is verified only when an authorized reproduction preserves original text,
inserts the intended genuine or test media, saves without publishing, and reopens
the same draft with the expected images and pixels intact. Record the exact tested
versions, source of media, original action times, and any remaining restrictions.

Current disposition: **unresolved media persistence; bounded recovery exhausted
without a proven root cause**. The draft was retained for handoff. No blanket
platform incompatibility, successful custom-rule save, public post, or repaired
browser capability is claimed. This document does not authorize additional retries.
