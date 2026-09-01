# Central Beads Redirect Convergence Design

## Status and scope

This specification defines a centrally maintained redirect-convergence engine
for multiple repositories while preserving one independent Beads authority per
repository. It does not merge databases, choose DB-versus-JSONL authority,
export tracker state, or authorize a real redirect change.

The portable engine belongs in `jleechanorg/jleechan-skills`. Host-specific
registry data belongs in `jleechanorg/user_scope`. Application repositories
retain their own canonical Beads store, exporter, health policy, and evidence.

## Problem

The recovered tool in
`/Users/jleechan/evidence/beads-canonical-recovery-20260827/` proves that a
redirect-only transaction can be dry-run by default, source-immutable, atomic,
and reversible. It is currently an evidence artifact rather than a reusable
product. It consumes a WorldArchitect audit schema, has no registry producer,
supports one hardcoded Beads adapter shape, and cannot durably recover after
process death between redirect writes.

Copying that tool into every application repository would duplicate security
logic and let fixes drift. Redirecting every repository into one global Beads
database would instead erase repository-local authority and recreate the
split-brain class this work is meant to prevent.

## Assumptions and recommended defaults

1. **Centralize code, not data authority.** One portable engine serves many
   repository-local canonical stores.
2. **Use `jleechan-skills` as the engine owner.** It already exports portable
   skills, scripts, and fixture tests. `user_scope` is a machine-config backup
   repository and owns only host-specific registry entries.
3. **Ship one adapter first: `br-sqlite-v1`.** Repositories using legacy `bd`
   or Dolt are explicitly unsupported until a separate adapter and fixture
   suite exist.
4. **Never provide `apply-all`.** `plan-all` is read-only; every apply or
   recovery names exactly one repository.
5. **Require an external approval capability plus operator bindings.** Apply
   requires a detached, externally signed approval envelope as well as literal
   registry, manifest, recomputed-plan, canonical-target, adapter,
   tracker-binary, and Git-binary bindings. The applying process cannot mint
   the approval, values embedded in an artifact never satisfy the corresponding
   operator argument, and the tool never emits a runnable apply command.
6. **Separate control state from evidence.** Active locks and journals live in
   one non-configurable per-user control namespace keyed by physical canonical
   identity. Manifests, plans, redirect backups, and receipts live in a
   registry-selected evidence directory outside application repositories.
7. **Treat the recovered tool as a donor.** Port its verified invariants and
   tests; do not execute or install the evidence file as production code.
8. **Certification never implies authorization.** Fixture apply and real
   dry-run are sufficient for implementation readiness. Any real apply needs a
   separate, explicit operator instruction against a fresh manifest.

## Considered approaches

### A. Portable engine plus host registry — selected

`jleechan-skills` owns the engine, schemas, skill, and tests. `user_scope` owns
an explicit per-host registry. Each registry entry identifies one repository,
its canonical Beads directory, its Git worktree discovery root, optional extra
clones, the adapter, the pinned tracker binary, and the evidence directory.

This gives one patch surface for security while retaining per-repository
authority and operator-visible configuration.

### B. Engine and configuration copied into every repository — rejected

This makes discovery easy for each repo but duplicates path validation,
journaling, rollback, and binary verification. Security corrections would need
coordinated multi-repository releases and could silently diverge.

### C. One global Beads database — rejected

A global store changes issue authority, prefixes, export lifecycles, and failure
domains. It also makes a central maintenance failure affect unrelated projects.
The convergence engine must never suggest or implement this topology.

## Ownership model

| Concern | Owner | Mutable data |
|---|---|---|
| Portable schemas, engine, CLI, fixtures, skill | `jleechan-skills` | Source code only |
| Per-host repository registry | `user_scope` | Reviewed host configuration |
| Canonical DB and JSONL export | Each application repository | Repository-local tracker state |
| Manifests, plans, backups, receipts | Registry evidence root | Redirect-operation evidence |
| Locks, active journals, nonce ledger | Fixed control namespace | Canonical transaction coordination |
| Approval trust root | Root-owned host installation | Allowed signing identities and verifier binding |
| Apply authorization | Offline human signer | Signed exact operation envelope |

No subagent, scheduled job, `plan-all`, registry entry, or applying user process
may grant apply authority.

## Approval capability

Real apply and recovery require a canonical JSON approval envelope plus a
detached SSH signature. The envelope binds operation (`apply` or `recover`),
repo ID, registry and manifest hashes, recomputed plan or journal hash,
canonical physical path/device/inode, adapter, tracker and Git bindings, exact
tool-tree hash, target redirect identities, issued-at, expires-at, and a
single-use 256-bit nonce. It never contains a wildcard repository or target.
`tool-tree hash` is the canonical digest of the exact executed engine module and
schema bytes enumerated by the release manifest; files outside that manifest
cannot influence transaction behavior.

The allowed-signers file and pinned `ssh-keygen` verifier binding live at one
compiled, non-overridable platform path:
`/Library/Application Support/Beads Convergence/trust` on macOS and
`/etc/beads-convergence/trust` on Linux. No registry field, CLI option,
environment variable, or symlink can select another trust root. The directory
and every ancestor are root-owned and non-group/world-writable. The engine walks
the platform path by descriptor and rejects unsafe ownership or mode. It verifies the
signature using exact `ssh-keygen -Y verify` arguments, a minimal environment,
`shell=False`, a timeout, and the same descriptor-bound executable rules used
for Git and `br`. It durably consumes the nonce in the canonical control
namespace before the first redirect mutation; an expired, replayed, mismatched,
or unverifiable envelope fails closed.

SSH signature domain separation is constant and not envelope-controlled:
`beads-redirect-convergence-v1@jleechan.org`. Verification feeds the exact
captured canonical envelope bytes on stdin and invokes the retained verifier as
`ssh-keygen -Y verify -f <allowed-signers-fd> -I <signer-principal> -n
beads-redirect-convergence-v1@jleechan.org -s <signature-fd>`. The `-I` value
must equal the envelope's `signer_principal` and an exact principal admitted by
the root-owned allowed-signers file. The envelope cannot choose or override
namespace, identity, signers file, verifier, or signature path semantics.

An allowed signer is necessary but not sufficient operationally: its private credential must
be hardware-held, off-host, or controlled by a separately administered
principal and unavailable to the applying account, process, agents, environment,
filesystem, and SSH agent. The envelope and receipt record the signer principal
and key fingerprint. Private-key custody is an out-of-band provisioning and
certification gate; the CLI can verify signature and root-owned trust but cannot
prove where the private key lives. It must not accept a user-writable
"custody evidence" checkbox or claim technical custody proof.

Fixture transaction tests use an in-process test authority limited to a
temporary root. The production CLI has no approval bypass, environment switch,
or test-only flag. Installing the host trust root and issuing a real signed
envelope are separate operator-governed activities and are not authorized by
this plan.

## Registry contract

The portable schema is
`beads.redirect-convergence.registry.v1`. A host registry contains a stable
`host_id` and a list of entries with these required fields:

```json
{
  "repo_id": "worldarchitect.ai",
  "adapter": "br-sqlite-v1",
  "repository_seed": "/Users/jleechan/projects/worldarchitect.ai",
  "canonical_beads": "/Users/jleechan/projects/worldarchitect.ai/.beads",
  "allowed_worktree_roots": [
    "/Users/jleechan/projects",
    "/Users/jleechan/.ao/data/worktrees/worldarchitect"
  ],
  "additional_worktrees": [],
  "tracker_binary": {
    "path": "/absolute/path/to/br",
    "version": "0.4.0",
    "sha256": "<64 lowercase hex characters>"
  },
  "git_binary": {
    "path": "/absolute/path/to/git",
    "version": "<exact version output>",
    "sha256": "<64 lowercase hex characters>"
  },
  "evidence_root": "/absolute/operator/evidence/worldarchitect.ai"
}
```

All paths are absolute after JSON parsing; environment expansion, shell
expansion, and command substitution are forbidden. `repo_id` matches
`[a-z0-9][a-z0-9._-]{0,63}`. Repository IDs are unique. Canonical directories
must be physical directories, must lie under a declared root or the seed, and
must not resolve through a symlink. Evidence roots must not be inside a
worktree, canonical Beads directory, or the engine control namespace.

Registry, manifest, approval, signature, and journal inputs are opened once by
descriptor. The engine hashes and parses the same captured bytes; it never
hashes a pathname and then reopens that pathname for decoding. Path containment
is descriptor-anchored, component-wise containment beneath a retained physical
root, never a string-prefix or one-shot `realpath` check.

The registry is configuration, not apply authorization. Apply receives the
signed approval and
literal `--expected-*` arguments for the registry, canonical path, adapter,
tracker binary, and Git binary. Each is compared independently with the live
object and the hash-bound manifest. Merely repeating a value found inside the
registry does not satisfy the CLI parser; the human-facing session must supply
every argument. The engine may print hashes for review but never constructs or
executes a corresponding apply command.

The control root is not a registry field or CLI option. On supported POSIX
hosts it is `<physical home from getpwuid(geteuid())>/.local/state/beads-convergence/control`.
`HOME` and other environment variables never choose it.
The engine creates and verifies every ancestor as owned by the effective user,
non-symlink, mode `0700`, and bound by device/inode. Control artifacts are mode
`0600`. A changed or unsafe control root is a hard failure.

## Adapter boundary

The engine calls an adapter through this interface:

```python
class TrackerAdapter(Protocol):
    adapter_id: str
    source_names: tuple[str, ...]

    def verify_binary(self, binding: BinaryBinding) -> VerifiedExecutable: ...
    def attest_backend(self, beads_dir: DirectoryHandle) -> BackendAttestation: ...
    def verify_health(self, worktree: DirectoryHandle,
                      executable: VerifiedExecutable) -> HealthAttestation: ...
    def acquire_writer_exclusion(self, beads_dir: DirectoryHandle,
                                 executable: VerifiedExecutable) -> WriterLease: ...
    def fingerprint_sources(self, beads_dir: DirectoryHandle) -> SourceSnapshot: ...
    def resolve_authority(self, worktree: DirectoryHandle,
                          executable: VerifiedExecutable) -> Path: ...
```

`br-sqlite-v1` recognizes only `beads.db`, `beads.db-wal`, `beads.db-shm`, and
`issues.jsonl`. It invokes exactly:

```text
br where --json --no-auto-flush --no-auto-import
```

from the retained target-worktree descriptor, with a finite timeout and a newly
constructed environment containing only `LC_ALL=C`, `LANG=C`, `TZ=UTC`,
`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and
`GIT_TERMINAL_PROMPT=0`. No inherited `HOME`, `PATH`, `GIT_*`, `BEADS_*`,
`BD_*`, `BR_*`, Python, loader, or shell variable reaches a child. It uses the verified
executable object. The engine never converts an authority-bearing directory
descriptor back into a pathname for child `cwd` or `git -C` resolution.

One single-threaded `run_verified` primitive forks a child, calls `fchdir` on
the retained worktree descriptor, then `fexecve`s the retained executable where
available or executes its inherited `/dev/fd/<n>` descriptor. The parent owns
bounded pipes, timeout, termination, and status collection. Capability probes
and tests must prove the exact branch on macOS and Linux; `subprocess` pathname
fallback is forbidden. The engine opens a binary with `O_NOFOLLOW`, binds
device/inode, hashes its open descriptor, and executes that descriptor through
`/dev/fd` with `pass_fds`; it rechecks identity and digest after execution.
The same rule applies to the pinned Git binary. A platform without the required
descriptor-exec and directory-descriptor primitives is unsupported.

`br-sqlite-v1` positively attests the backend before planning: expected SQLite
source members must be regular files, the database header must be SQLite, and
the adapter rejects every known Dolt/legacy backend marker, hot
`beads.db-journal`, unknown SQLite sidecar, hard-linked source member,
`.beads/dolt`, `.beads/embeddeddolt`, metadata-declared Dolt state, and every
mixed backend state. It also invokes exact read-only `br sync --status --json`
arguments with `--no-auto-flush`, `--no-auto-import`, and `--no-daemon`, and
requires `dirty_count=0`, `db_newer=false`, `jsonl_newer=false`, and
`workspace_health=healthy` before apply. Missing or unknown format/health fields
fail closed.

Real apply additionally requires a version-specific, read-only writer-exclusion
lease that the pinned tracker honors for all DB/WAL/SHM/JSONL writes. The lease
must be acquired without creating or modifying tracker source members and held
from the first coherent fingerprint through COMMITTED or completed rollback.
The adapter collects the source family twice under the lease and requires
identical device/inode/size/digest sets. Until `br` exposes or its implementation
proves that contract, the adapter is plan-only on real repositories; only
temporary fixture stores may exercise apply. A status command, `lsof` snapshot,
or two unleased hash passes is not a quiescence proof. Unknown adapters fail
closed. The initial release has no generic command adapter and no `bd-dolt`
implementation.

## Discovery and manifest generation

Discovery is bounded by registry data:

1. Run the verified Git descriptor from the retained seed-directory descriptor
   as `git worktree list --porcelain` through `run_verified`, with a minimal
   explicit environment and a timeout. String `git -C <path>` is forbidden.
2. Add explicit `additional_worktrees`.
3. Canonicalize, deduplicate, and reject any path outside
   `allowed_worktree_roots`.
4. Inspect only `<worktree>/.beads`, its redirect, and the adapter source names.
5. Classify entries as `canonical`, `redirected_canonical`, `noncanonical`,
   `unresolved_noncanonical`, `missing`, or `unsupported`.

The manifest schema is `beads.redirect-convergence.manifest.v1`. It binds the
registry SHA, repo ID, adapter ID, binary binding, canonical path, all observed
source fingerprints, redirect bytes and modes, physical directory identities,
and discovered worktrees. Volatile timestamps live in a metadata envelope and
are excluded from the canonical plan serialization.

The generator never scans `$HOME`, `/Users`, or a workspace root recursively.
It never runs tracker sync, import, export, doctor repair, or Git mutation.

## Planning

`plan --repo <id>` produces deterministic canonical JSON and a SHA-256. It
selects only physical noncanonical stores whose live manifest entry is complete.
Dry-run may report vanished worktrees as skipped; apply rejects every skipped,
missing, unsupported, or newly discovered entry until a fresh manifest and plan
are produced.

`plan-all` iterates registry entries read-only and emits one independent result
per repository. It has no `--apply` option, returns nonzero when any repo cannot
be safely planned, and never combines multiple repositories into one plan hash.
Planning is read-only with respect to repositories, redirects, and tracker
state; writing hash-bound evidence beneath `evidence_root` is allowed.

There is no mutable plan input to apply. Apply parses the operator-bound
manifest, performs fresh discovery and validation, deterministically recomputes
the executable plan, and compares its digest with
`--expected-plan-sha256`.

## Redirect representation

The only application-repository mutation is the regular file
`<worktree>/.beads/redirect`. Its byte encoding is owned by the exact
`br-sqlite-v1` adapter/binary pair, not hardcoded as `.beads`-relative or
worktree-relative prose. Before the adapter can plan a real target, a temporary
fixture oracle writes each candidate encoding and runs the pinned `br where`
through `run_verified` from the retained fixture-worktree descriptor with the
exact child environment. The adapter accepts exactly one encoding only if it
resolves in one hop to the bound fixture canonical directory; zero or multiple
accepted encodings disable that adapter version. The selected codec ID and
oracle receipt are hash-bound into registry validation, manifest, plan,
approval, and receipt. NUL, CR, trailing space, multiple lines, symlinks,
nonregular files, and multi-hop resolution are always rejected. Planning
records exact prior bytes, mode, absence, parent device/inode, codec ID, and
exact intended bytes.

Apply replaces only that basename using a same-directory exclusive temp and
`renameat` under the retained `.beads` descriptor. Rollback/recovery may
`unlinkat` only that basename when restoring a recorded absent pre-state. The
ban on deletes applies to tracker sources and other paths, not this exact
absence restoration. Post-write verification runs the pinned `br where` from
the target worktree with the scrubbed environment and requires one-hop
resolution to the bound canonical directory.

## Apply transaction

Apply is an explicit subcommand and names one repo:

```text
beads-converge apply \
  --repo worldarchitect.ai \
  --registry <absolute-path> \
  --expected-registry-sha256 <sha> \
  --manifest <absolute-path> \
  --expected-manifest-sha256 <sha> \
  --expected-plan-sha256 <sha> \
  --expected-canonical <absolute-path> \
  --expected-adapter br-sqlite-v1 \
  --expected-tracker-path <absolute-path> \
  --expected-tracker-version 0.4.0 \
  --expected-tracker-sha256 <sha> \
  --expected-git-path <absolute-path> \
  --expected-git-version <exact-version> \
  --expected-git-sha256 <sha> \
  --approval <absolute-envelope-path> \
  --approval-signature <absolute-signature-path> \
  --apply
```

Before the first redirect write, the engine:

- verifies the external approval and durably reserves its single-use nonce;
- verifies every supplied hash and both pinned executables by descriptor;
- re-discovers the named repo and rejects topology drift;
- reopens directories with `O_DIRECTORY|O_NOFOLLOW` and binds device/inode;
- positively attests `br-sqlite-v1` and revalidates canonical health;
- acquires and retains the adapter's proven writer-exclusion lease;
- re-fingerprints all adapter source members;
- acquires the control-namespace lock keyed only by canonical device/inode;
- refuses when an incomplete journal already exists;
- durably creates a `PREPARED` journal containing every prior redirect state.

The journal is an exclusive same-directory temp-write, complete write,
file-`fsync`, rename, and parent-directory `fsync`. On macOS, durability points
also use `F_FULLFSYNC`; inability to provide the selected durability level is a
hard failure. Before each target, it durably records that target as pending with
its prior bytes and intended bytes. It then writes and `fsync`s the redirect temp,
renames through a verified directory descriptor, `fsync`s the target `.beads`
directory, verifies resolution, and durably records that target as applied.
After all targets and source fingerprints verify, it durably writes `COMMITTED`
before creating the receipt. Ordinary exceptions roll back in reverse order
using the same per-target durability sequence and end in durable `ROLLED_BACK`.

The engine never deletes, moves, chmods, imports, exports, reconciles, or writes
DB, WAL, SHM, journal, or JSONL members. Its only repository unlink is the exact
`redirect` absence restoration defined above.

## Crash recovery

Process death can bypass in-memory exception handlers. Every redirect backup
therefore exists in the fsynced journal before its corresponding write.

On startup, `apply` refuses when the canonical control key has a `PREPARED`,
`APPLYING`, or recovery-in-progress journal. Recovery is a separate one-repo
command requiring a separately signed recovery approval, the registry SHA, run
ID, journal SHA, expected canonical path, expected adapter, all expected
executable bindings, and literal `--recover`. It may only
restore the recorded redirect bytes or absence after verifying current bytes
are either the recorded pre-state or this run's intended target. Any third
state becomes `NEEDS_OPERATOR` and is not overwritten.

Before its first redirect mutation, recovery repeats descriptor-bound discovery,
backend and health attestation, acquires and retains the same proven
writer-exclusion lease, and captures the same coherent two-pass source-family
snapshot as apply. It compares that snapshot with the journal's permitted
recovery condition. Any topology, health, source, or lease mismatch durably
becomes `NEEDS_OPERATOR`; recovery does not mutate a redirect.

Recovery records per-target progress durably and is idempotent. A second
recovery after process death resumes from current bytes plus the journal rather
than trusting an in-memory index. `COMMITTED` without a receipt is a successful
apply whose receipt may be regenerated; it is never rolled back.

There is no automatic recovery daemon and no cross-repository recovery command.

## Locking and concurrency

The lock and active-journal directory is the fixed control namespace, never an
`evidence_root`. Keys hash only canonical device and inode; physical path is
recorded for humans but never participates in serialization identity. Lock
files are durable and never unlinked by the engine. Opening uses `O_NOFOLLOW`;
`fstat` verifies a regular file, link count, device/inode, and expected owner.
The engine verifies the directory and lock identities before every redirect
mutation. Cooperative engine processes serialize with `fcntl`; deletion or
replacement by an external same-UID process is detected and fails closed.

The threat model covers stale inputs, accidental automation, cooperative engine
concurrency, symlinks, pathname replacement before retained-descriptor binding,
process death, and power-loss durability at documented sync points. It does not
claim atomic compare-and-swap protection against a malicious same-UID process
that replaces an already validated redirect or lock pathname in the final
instruction window. Real operations therefore require the external approval,
private control root, tracker writer lease, and a trusted host session. This
limitation is explicit; tests must not claim stronger hostile-same-UID safety.

Read-only planning may run concurrently across repositories. Apply and recovery
serialize per canonical store. Two registry entries resolving to the same
canonical directory are rejected during registry validation.

## Command surface

```text
beads-converge registry validate ...
beads-converge inventory --repo <id> ...
beads-converge plan --repo <id> ...
beads-converge plan-all ...
beads-converge apply --repo <id> ... --apply
beads-converge recover --repo <id> ... --recover
```

Machine-readable JSON goes to stdout. Diagnostics go to stderr. Success and
failure receipts include schema, tool version, repo ID, adapter, hashes, and
explicit `applied` or `recovered` booleans. Secret values and raw environment
variables are never captured.

## Failure policy

The following always fail before mutation: malformed/unknown schema, missing
operator binding, binary hash/version mismatch, duplicate canonical authority,
path outside allowed roots, symlink/nonregular source or redirect, topology or
source drift, missing worktree, lock contention, unfinished journal, unhealthy
canonical state, unknown/mixed backend, unknown adapter, unsafe control root,
invalid/expired/replayed approval, or nonzero/malformed adapter verification.

A failed `plan-all` does not suppress healthy repository results, but its
process exit remains nonzero. A failed apply either proves full rollback or
leaves a durable `NEEDS_OPERATOR` journal and a nonzero exit.

## Testing strategy

Layer 1 fixtures cover registry/schema parsing, path containment, binary
pinning, deterministic plan serialization, and command construction.

Layer 2 subprocess fixtures create two independent fake repositories and prove:

- `plan-all` never writes either source or redirect;
- apply can affect only the selected repo;
- DB/WAL/SHM/JSONL hashes remain identical;
- symlink, nonregular, changed-source, changed-canonical, and lock attacks fail;
- injected exceptions roll back all redirects;
- process death at every durability boundary leaves a recoverable state;
- recovery restores all prior redirect states and can itself resume after death;
- third-party redirect changes force `NEEDS_OPERATOR` without overwrite.
- two registries with different evidence roots still share one canonical lock;
- mixed SQLite/Dolt and legacy-only fixtures are unsupported;
- hot rollback journals, unknown sidecars, hard links, unstable two-pass
  snapshots, and absent writer-exclusion leases make real apply unavailable;
- wrong Git/tracker digest, inode replacement, and environment injection fail;
- unsigned, self-signed, expired, replayed, wrong-operation, wrong-tool, and
  wrong-target approval envelopes fail before mutation;
- a valid signature under another SSH namespace, a mismatched `-I` principal,
  or an envelope attempting to choose namespace/identity is rejected;
- the production CLI exposes no custody-evidence file, approval bypass, or test
  authority; missing/unsafe compiled trust or a bad signature fails closed;
- a write-surface spy proves only control/evidence artifacts and the exact
  redirect basenames are reachable through write-capable APIs.

Layer 3 uses the existing WorldArchitect topology and a second `br-sqlite-v1`
repository in read-only mode. Both must produce deterministic repeated plans
with unchanged source hashes. No real apply is part of certification.

## Implementation preconditions

- Begin implementation from a clean `jleechan-skills` worktree based on current
  `origin/main`; the present checkout contains unrelated Beads and documentation
  changes.
- Create the host registry only after the portable registry schema is committed.
- Production apply/recovery remains disabled until the root-owned approval
  trust installation and off-host/hardware/separate-principal signer custody are
  independently provisioned and verified.
- A real repository must have a healthy canonical tracker state before apply:
  `dirty_count=0`, `db_newer=false`, `jsonl_newer=false`, and
  `workspace_health=healthy`.
- The initial implementation supports macOS and Linux POSIX hosts only. It must
  prove descriptor execution, `O_NOFOLLOW`, directory `fsync`, and `fcntl`
  behavior on each supported platform, plus `F_FULLFSYNC` on macOS, before
  claiming portability.
- Real apply or recovery requires a new explicit operator instruction and is
  outside this design/planning authorization.

## Acceptance criteria

1. One portable engine serves at least two fixture repositories without
   repository-specific source changes.
2. Every apply/recovery is externally approved, one-repo, registry-bound, manifest-bound,
   recomputed-plan-bound, canonical-bound, adapter-bound, tracker-and-Git-bound,
   journaled, and explicitly authorized.
3. No command can mutate tracker source members or merge repository authorities.
4. `plan-all` is structurally incapable of apply.
5. Process-death recovery is independently reproduced from a durable journal.
6. Two real repositories pass repeated read-only plan certification with all
   monitored hashes unchanged.
7. A real apply path remains disabled unless the exact tracker adapter proves a
   retained, non-mutating writer-exclusion lease.
8. No unresolved placeholder, implicit path discovery, ambient executable, or
   automatic recovery/apply behavior remains.

## Review iteration

The first `/wa` review requested changes. This revision incorporates its
substantive findings: a fixed canonical-keyed control namespace, durable
per-target journal ordering, kill-point and recovery-kill coverage, explicit
tracker/Git bindings, descriptor-bound execution, positive backend and health
attestation, recomputed plans, and a capability-limited write surface. These
changes are design requirements; they are not implementation evidence or real
apply authorization.
