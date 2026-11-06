# Specification: retire factory tooling from the shared skill catalog

- **Outcome:** Remove the retired dark-factory and auto-factory commands, skills, callpath profile, local-retention entries, and live consumer pointers from the exported Claude and Hermes catalogs. Preserve the separate Hermes `agento` `/f` alias to `finish-the-job`, plus historical and archived records.
- **Non-goals:** Rebuilding or replacing the retired pipeline; changing user-wide agent policy or another repository; deleting archived/history/data references; changing the behavior of `finish-the-job` or other surviving workflows.
- **Acceptance:**
  - The live command/skill catalogs and installer no longer expose the retired factory entries or retain removed local packages.
  - `finish-the-job` owns the `agento` `/f` alias, while no surviving live command dispatches to the deleted factory skills.
  - Historical references, archived snapshots, and unrelated AO project data remain intact.
  - The focused command-discovery, installer, dispatcher, and history suite passes: `python3 -m unittest tests.test_command_archive_migration tests.test_command_closure tests.test_command_skill_usage_audit tests.test_installer tests.test_thin_command_dispatchers tests.test_history_search -q`.
- **User stories:** A skill-catalog maintainer no longer sees retired factory commands as available tools. An `agento` user can still invoke `/f` for `finish-the-job`.
- **Proof plan:** Inspect the live command closure and retained callers against current `main`; run the focused unittest command above and `git diff --check`; confirm the installer excludes the retired local-retention entries and that `/f` still points to `finish-the-job`. The six focused modules passed at code SHA `c6e1e4215d61e534f8d7b6479bc7e477331f4858` (139 tests, 3 skipped); only this Markdown specification is added afterward, so no runtime test rerun is needed for it.
- **Mock:** Exempt. This catalog and command retirement has no application UI or service behavior to mock; the existing installer and command-discovery tests are the relevant proof.
- **Risk:** Medium. A broad removal could leave a live caller broken or remove a similarly named surviving command. Keep the deletion list scoped to the retired factory tools, verify references and installer behavior, and preserve the independent Hermes `/f` alias and historical records.
