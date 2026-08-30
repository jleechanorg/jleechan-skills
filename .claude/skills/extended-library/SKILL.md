---
name: extended-library
description: Compatibility routing for the exported extended-library command collection.
---

# Extended-library compatibility

Read only the command-specific file named by the dispatcher under
`references/`. Preserve its workflow and apply the invoking command's
`$ARGUMENTS` unchanged. Do not load the complete reference collection when one
command is requested.
