# Reddit rich-text editing

These are observations from a completed editing session, not promises about
all Reddit versions. Inspect the current UI and runtime capabilities first.

## Preserve the draft and assets

- Read the exact existing draft and latest author edits before changing it.
  Preserve a pre-edit body/link/media backup and compare substantive paragraphs
  and links after each risky mutation. Do not restore a stale full-body backup
  over newer author edits.
- Fetch images from the requested PR/source; retain the original captures.
  Keep full source images and aspect ratios. Do not stretch, crop key content,
  mislabel a new flow as a repair, or substitute unrelated comparisons.
- For side-by-side presentation, compose actual image bytes into one panel;
  two independent Reddit images do not reliably form a horizontal pair. Match
  the requested left/right asset order and nearby rendered panel width. One
  observed final pair was 664 × 752; 664 is not a platform constant. Padding
  can preserve full images of different proportions without stretching them.
- Put each compact panel immediately after its matching explanation. Verify
  actual order, size and meaningful clickable links, including top and bottom
  links when requested. A media count alone does not establish layout.

## Insertion and selection

- In the observed run, FileChooser uploads landed in the top media tray rather
  than the body. A successful chooser or queued gallery is not inline insertion.
- Prefer supported native UI insertion. If it fails and the runtime supports it,
  pasting real image-file bytes with a native ClipboardEvent into the observed
  contenteditable succeeded in that session. This is a UI fallback, not authority
  for a direct API, private endpoint, or hidden service bypass.
- Setting a DOM caret and immediately pasting in the SAME evaluate task used
  stale editor selection and inserted at the top. Establish a clean native caret
  at the exact paragraph end, then let selection synchronize in a separate
  step/snapshot before paste. Native Enter can create a safe empty paragraph.
  Verify the actual resulting order, not just the intended caret.
- Before deleting a staged image, verify the selected DOM range contains only
  that image. A native global page.keyboard.press removed only the selected
  image in the observed session. Locator-targeted Backspace once selected and
  deleted the whole body; immediate native Undo restored it. Never blindly
  Backspace or assume a trash click was accepted. Hover-only delete controls
  can disappear; refresh the snapshot before retrying.
- A reused filename paste showed no insertion once, but filename and caret both
  changed on the later attempt. Cause was not isolated. Do not claim Reddit
  rejects duplicate filenames or require filename changes as a fix. Unique
  revision names are optional traceability.

## Persistence and proof

Reddit explicitly warned that saved drafts do not save images/videos in the
observed flow. Text saving may preserve links while losing image bytes; a
media ID, preview, gallery, upload receipt or saved text is not persisted media.
Do not reload or close the working composer just to verify persistence. Inspect
saved text separately only if that preserves the populated composer, and report
what was actually verified. Keep exact media outside the browser for recovery.

Provide a screenshot and the exact composer URL. Distinguish staged from saved
and published; do not claim foreground visibility. After edits, compare body,
links, image order and placement with the current backup and requested outcome.
