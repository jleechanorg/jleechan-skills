# Clean Claude launcher and comparison

- Outcome: expose `claudea` as the native safe-mode Claude counterpart to the clean Codex launcher; default to Fable 5.2. Add `/claudea-bench` with distinct balanced work by default and duplicate tasks only with `--strict`.
- Non-goals: changing normal Claude settings, copying credentials, isolated account/history storage, modifying Codexa, or silently replacing unavailable models.
- Acceptance: the shell helper calls the external Claude CLI with safe mode, permission bypass, and `claude-fable-5-2`; preserves argument boundaries and caller overrides; installer selects the helper with the skill. Actual model availability and benchmark outcomes must be reported honestly.
- User stories: source the installed helper to start clean customization sessions; invoke the benchmark from a normal agent session to compare bounded matched-model work without sharing arm outputs.
- Proof plan: shell argument/exit-code checks against an executable fixture, installer in an isolated target, help/version checks on both hosts, and a bounded real-model probe followed by comparison when quota allows. An explicit quota denial stops retries.
- Mock exemption: no rendered UI changes. Executable fixtures prove shell forwarding only; they cannot prove model availability or isolation inside Claude. Native help documents safe-mode boundaries.
- Risks: permission bypass requires authorized scope; admin policy and built-in plugins remain; normal history/auth are preserved. Older CLI versions may lack safe mode. Shared-profile continuation can load prior non-clean sessions. Caller flags may override defaults. Fable quota/access can prevent real comparison.
