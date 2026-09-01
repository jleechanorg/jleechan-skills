# Learning: Skill Archive Dependency and Migration Closure

**Context / Provenance:** PR [#376](https://github.com/jleechanorg/jleechan-skills/pull/376) and Bead `bd-7nx`.

## Summary
During the historical zero-use skill and command archival (moving 110 recoverable skills and 7 commands to dated archive directories), three critical lifecycle and portability lessons emerged:

1. **Dependency and Caller Closure Scan Before Archiving**:
   - Inactivity and zero-use telemetry alone are insufficient to justify archiving a skill.
   - Candidate selection must comprehensively audit:
     - Active skill-to-command references and caller chains.
     - Inter-skill dependencies (skills required by other active skills).
     - Global operating contracts and CLAUDE.md requirements.
     - Repository test contracts (e.g. Batch 1 portability tuple).
   - In PR #376, 50 skills initially flagged by zero-use filters were properly retained after caller/dependency closure audits.

2. **Transactional and Race-Safe Archive Migration**:
   - Installer migration during `--merge --migrate-archives` must be atomic and race-safe.
   - Acquire an exclusive migration lock with automatic trap cleanup on exit or interrupt.
   - Perform preflight collision checks that fail closed (never overwrite existing target files or directories).
   - Support rollback on partial migration failures.

3. **Cross-Platform Filesystem Node Identity (`stat` Compatibility)**:
   - When verifying filesystem paths and inode identity across operating systems, differences between GNU and BSD utilities must be accommodated:
     - GNU `stat` (Linux) uses `stat -c '%d:%i'` for device and inode numbers.
     - BSD `stat` (macOS / FreeBSD) uses `stat -f '%d:%i'`.
   - The installer helper `path_identity` (`stat -c '%d:%i' "$1" 2>/dev/null || stat -f '%d:%i' "$1"`) guarantees cross-platform reliability for path equivalence checks.
