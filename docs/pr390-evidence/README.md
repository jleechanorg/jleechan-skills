# PR #390 Evidence Bundle: Conversation Titling with `[web advice]`

## Scope note
This evidence bundle provides empirical proof that `/web-advice` formats and titles web model conversations with the prefix `[web advice]`, allowing users to distinguish automated review threads from personal chat histories in ChatGPT, Gemini, Grok, and Perplexity.

## Artifacts in this bundle
1. `gemini_convo_title.png`: Full screenshot of Gemini tab showing conversation titled `[web advice] PR #390` in tab and sidebar.
2. `chatgpt_convo_title.png`: Full screenshot of ChatGPT tab showing conversation titled `[web advice] PR #390 Review` in tab and sidebar.
3. `grok_convo_title.png`: Full screenshot of Grok tab showing conversation in sidebar.
4. `perplexity_convo_title.png`: Full screenshot of Perplexity tab showing conversation titled `[web advice] You are an independent expert advising on PR #390...` in sidebar.
5. `review_synthesis.md`: Detailed breakdown and multi-model synthesis table of all 4 independent model reviews.
6. `test_results.txt`: Test run output confirming 167/167 web-advice and approval contract tests passing.
7. `metadata.json`: Provenance metadata bound to HEAD commit `c3a0d86bf8ac54335fd904e7e718db309774cfc7`.
8. `SHA256SUMS.txt` / `checksums.sha256`: Cryptographic integrity hashes for all bundle artifacts.

## Verification
- Bundle passes `sha256sum -c SHA256SUMS.txt`
- Code changes pass all 167 automated unit and contract tests.
