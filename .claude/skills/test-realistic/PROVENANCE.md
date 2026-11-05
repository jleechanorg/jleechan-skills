# Provenance

This package is a portable generalized `test-realistic` skill. Its original
versioned upstream lineage is unknown: the source repository initially tracked
only `SKILL.md`, while the active installed package contained the executable
scripts, tests, and example configuration. Those files were imported into
this source package as the byte-for-byte baseline before the cleanup work.

The import manifest and baseline hashes are retained in the task's scratch
evidence, not in this package. No project-specific names, paths, credentials,
or personal identifiers are part of the package. Future changes should update
this document only when provenance becomes verifiable from a versioned source;
do not infer lineage from the installed copy alone.

## Seven-element cleanup scope

1. Pool completeness is checked against the emitted agent pool before judging.
2. Every emitted agent capture must contain a parsed, non-empty JSON object.
3. Capture validation remains schema-generic and rejects malformed records honestly.
4. PR targets carry a pinned head SHA and actual patch context, or fail loudly.
5. Adapter probes reuse the configured actor/persona pool shape.
6. Model-call counts, independent summaries, and the allowed model default remain explicit.
7. Provenance, portability, native-evidence labels, real-service boundaries, and hard model errors remain preserved.
