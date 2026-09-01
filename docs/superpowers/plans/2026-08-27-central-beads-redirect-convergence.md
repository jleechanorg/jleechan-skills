# Central Beads Redirect Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one portable, crash-recoverable Beads redirect-convergence engine that plans many repositories read-only while applying to only one separately authoritative repository at a time.

**Architecture:** `jleechan-skills` provides a Python package, thin CLI,
schemas, fixtures, and operator skill. A host registry supplied from
`user_scope` selects repository-local canonical stores and pinned
`br-sqlite-v1`/Git executables. A fixed per-user control namespace coordinates
canonical locks and journals; repository evidence remains outside repositories.
A separately installed root-owned trust root verifies offline-signed
one-operation approvals.

**Tech Stack:** Python 3.11+, standard library only, `unittest`, JSON Schema
documents enforced by strict Python parsers, POSIX `fcntl`,
directory-descriptor filesystem operations, and descriptor-bound pinned `git`,
`br`, and `ssh-keygen` subprocesses on macOS/Linux.

## Global Constraints

- Centralize portable code only; never centralize repository databases.
- Initial adapter support is exactly `br-sqlite-v1`; legacy `bd`/Dolt is unsupported.
- Default operations are read-only; no `apply-all` or automatic recovery exists.
- Apply requires literal `--apply`; recovery requires literal `--recover`; both
  also require a valid, unexpired, single-use externally signed approval.
- Apply and recovery operate on exactly one `repo_id` and require all operator hash/path bindings.
- DB, WAL, SHM, and JSONL are fingerprint-only and never mutation targets.
- Variable-input subprocesses use `shell=False` and finite timeouts.
- No registry, manifest, plan, applying process, or test flag can mint or bypass
  production approval.
- Real certification is dry-run only; real apply requires separate authorization.
- Implementation begins in a clean worktree from current `jleechan-skills` `origin/main`.

---

## File map

| File | Responsibility |
|---|---|
| `scripts/beads-converge` | Thin executable importing the CLI |
| `scripts/beads_convergence/models.py` | Frozen registry, manifest, plan, journal, and receipt types |
| `scripts/beads_convergence/codec.py` | Strict JSON parsing and canonical serialization |
| `scripts/beads_convergence/registry.py` | Registry validation and duplicate-authority checks |
| `scripts/beads_convergence/adapters.py` | Adapter protocol and `br-sqlite-v1` implementation |
| `scripts/beads_convergence/approval.py` | Root-owned trust and signed approval verification |
| `scripts/beads_convergence/fsafety.py` | Descriptor walks, pinned executables, and safe writes |
| `scripts/beads_convergence/inventory.py` | Bounded Git worktree discovery and manifest production |
| `scripts/beads_convergence/planner.py` | Deterministic one-repo plans and read-only `plan-all` |
| `scripts/beads_convergence/transaction.py` | Lock, journal, apply, rollback, and recovery |
| `scripts/beads_convergence/cli.py` | Argument parsing, JSON receipts, and exit codes |
| `.claude/skills/beads-redirect-convergence/SKILL.md` | Operator contract and examples |
| `.claude/skills/beads-redirect-convergence/references/*.schema.json` | Registry, manifest, plan, approval, journal, and receipt schemas |
| `tests/test_beads_convergence_*.py` | Unit and subprocess fixture certification |

### Task 1: Establish strict models and canonical codecs

**Files:**
- Create: `scripts/beads_convergence/__init__.py`
- Create: `scripts/beads_convergence/models.py`
- Create: `scripts/beads_convergence/codec.py`
- Create: `.claude/skills/beads-redirect-convergence/references/registry-v1.schema.json`
- Create: `.claude/skills/beads-redirect-convergence/references/manifest-v1.schema.json`
- Create: `.claude/skills/beads-redirect-convergence/references/plan-v1.schema.json`
- Test: `tests/test_beads_convergence_codec.py`

**Interfaces:**
- Produces: `Registry`, `RepositoryConfig`, `BinaryBinding`, `ApprovalEnvelope`,
  `Manifest`, `Plan`, `canonical_json_bytes(value) -> bytes`, and
  `sha256_hex(payload) -> str`.
- Consumes: standard-library `dataclasses`, `json`, `hashlib`, and `pathlib` only.

- [ ] **Step 1: Write strict-decoding RED tests**

```python
def test_registry_rejects_unknown_field():
    payload = valid_registry_dict()
    payload["repositories"][0]["surprise"] = True
    with self.assertRaisesRegex(ContractError, "unknown field"):
        decode_registry(payload)

def test_plan_bytes_ignore_dictionary_insertion_order():
    self.assertEqual(canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')
```

- [ ] **Step 2: Run the RED tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_codec`

Expected: FAIL because the package and strict decoders do not exist.

- [ ] **Step 3: Implement frozen types and exact-field decoders**

Implement `ContractError`, frozen dataclasses, exact schema-string checks,
lowercase 64-hex validation, absolute-path validation, duplicate-field
rejection, and canonical compact UTF-8 JSON serialization. Do not depend on a
third-party JSON Schema package; the schema files document the same contract
and tests keep them aligned.

- [ ] **Step 4: Run codec tests and placeholder scan**

Run: `python3 -m unittest -v tests.test_beads_convergence_codec`

Run: `rg -n 'FIXME|XXX|implement later' scripts/beads_convergence .claude/skills/beads-redirect-convergence tests/test_beads_convergence_codec.py`

Expected: tests PASS and `rg` returns no matches.

- [ ] **Step 5: Commit the contract unit**

```bash
git add scripts/beads_convergence .claude/skills/beads-redirect-convergence/references tests/test_beads_convergence_codec.py
git commit -m "feat(beads): define convergence contracts [codex][gpt-5.6-sol]"
```

### Task 2: Validate registry authority, repository membership, and pinned executables

**Files:**
- Create: `scripts/beads_convergence/registry.py`
- Create: `scripts/beads_convergence/adapters.py`
- Create: `scripts/beads_convergence/fsafety.py`
- Test: `tests/test_beads_convergence_registry.py`
- Test: `tests/test_beads_convergence_adapters.py`

**Interfaces:**
- Consumes: `Registry`, `RepositoryConfig`, and `BinaryBinding` from Task 1.
- Produces: `load_registry(path, expected_sha256) -> Registry`,
  `validate_repository(config) -> ValidatedRepository`,
  `open_trusted_tree(root, path) -> DirectoryHandle`, `VerifiedExecutable`,
  `TrackerAdapter`, and `BrSqliteV1Adapter`.

- [ ] **Step 1: Write registry and binary RED tests**

```python
def test_duplicate_resolved_canonical_directory_is_rejected():
    registry = registry_with_two_ids_same_canonical()
    with self.assertRaisesRegex(RegistryError, "duplicate canonical authority"):
        validate_registry(registry)

def test_binary_same_version_wrong_digest_is_rejected():
    binding = BinaryBinding(path=fake_br, version="0.4.0", sha256="0" * 64)
    with self.assertRaisesRegex(AdapterError, "binary SHA-256"):
        BrSqliteV1Adapter().verify_binary(binding)
```

Also test path traversal, symlink canonical directories, evidence roots inside
worktrees, unsafe fixed-control-root ownership/mode, unknown adapter IDs,
relative paths, duplicate IDs, duplicate managed `.beads` device/inodes across
repo entries, incorrect Git/tracker versions and digests, pathname replacement,
timeouts, exact `br where` and `br sync --status --json` argv, minimal
environments, and descriptor execution.

Assert registry and artifact readers hash and decode one captured descriptor
buffer. Assert path containment is a component-wise descriptor walk rather than
a string prefix. For every Git/`br`/verifier invocation require `run_verified`
to `fchdir` the retained directory before descriptor execution, with a minimal
environment and all `BEADS_*` overrides absent. Pause between validation and
fork, rename/replace every ancestor pathname, and prove the child remains bound
to the retained directory or fails without acting on the replacement.
Construct child environments from an allowlist containing only `LC_ALL=C`,
`LANG=C`, `TZ=UTC`, `GIT_CONFIG_NOSYSTEM=1`,
`GIT_CONFIG_GLOBAL=/dev/null`, and `GIT_TERMINAL_PROMPT=0`. Assert inherited
`HOME`, `PATH`, `GIT_*`, `BEADS_*`, `BD_*`, `BR_*`, Python, loader, and shell
variables never reach the child. Derive the fixed control root only from
`getpwuid(geteuid())`, never `$HOME`.

Add fixtures for hot `beads.db-journal`, unknown SQLite sidecars, hard-linked
source members, mixed SQLite/Dolt state, malformed health output, and a writer
that changes WAL state during fingerprinting. Require a version-specific
read-only `WriterLease`; if the exact pinned `br` implementation cannot prove
that every writer honors the lease, classify real apply as unavailable while
retaining read-only planning.

- [ ] **Step 2: Run the RED tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_registry tests.test_beads_convergence_adapters`

Expected: FAIL because validation and the adapter do not exist.

- [ ] **Step 3: Implement validation and `br-sqlite-v1`**

Walk authority-bearing paths component by component from retained trusted-root
descriptors with `openat`, `O_DIRECTORY|O_NOFOLLOW`, owner/mode validation, and
device/inode binding. Verify the absolute Git and `br` binaries through open
descriptors. Implement one single-threaded `run_verified` primitive: fork,
`fchdir` to the retained worktree/seed dirfd, then `fexecve` the retained
executable where available or exec its inherited `/dev/fd/<n>` descriptor. The
parent supervises bounded pipes, timeout, termination, and status collection,
then rechecks executable identity and digest. Never convert an
authority-bearing dirfd back into string `cwd` or `git -C` input. Probe and test
the exact macOS/Linux capability branch; there is no pathname subprocess
fallback.

- [ ] **Step 4: Run targeted tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_registry tests.test_beads_convergence_adapters`

Expected: PASS.

- [ ] **Step 5: Commit registry and adapter support**

```bash
git add scripts/beads_convergence/registry.py scripts/beads_convergence/adapters.py scripts/beads_convergence/fsafety.py tests/test_beads_convergence_registry.py tests/test_beads_convergence_adapters.py
git commit -m "feat(beads): validate registry authority [codex][gpt-5.6-sol]"
```

### Task 3: Generate bounded topology manifests

**Files:**
- Create: `scripts/beads_convergence/inventory.py`
- Test: `tests/test_beads_convergence_inventory.py`

**Interfaces:**
- Consumes: `ValidatedRepository` and `TrackerAdapter` from Task 2.
- Produces: `discover_worktrees(repository) -> tuple[Path, ...]` and `build_manifest(repository, adapter) -> Manifest`.

- [ ] **Step 1: Write discovery and immutability RED tests**

```python
def test_discovery_uses_git_porcelain_and_explicit_extras_only():
    manifest = build_manifest(validated_repository(), fake_adapter())
    self.assertEqual(manifest.worktrees, expected_bounded_entries())
    self.assertFalse(home_scan_spy.called)

def test_inventory_does_not_change_source_or_redirect_hashes():
    before = fixture_tree_fingerprints(root)
    build_manifest(validated_repository(), fake_adapter())
    self.assertEqual(before, fixture_tree_fingerprints(root))
```

Cover paths with spaces, vanished worktrees, paths outside allowed roots,
symlink/nonregular source members, unexpected redirects, canonical stores,
already-canonical redirects, independent clones, malformed Git output, a repo A
extra listed under repo B, common-dir mismatch, clone-identity mismatch, and
cross-entry duplicate `.beads` identities.

Use the real redirect contract in fixtures: `.beads/redirect` is a regular file,
but its byte base is not guessed. For each exact pinned `br-sqlite-v1` version,
a temporary oracle tries candidate codecs and accepts exactly one only when
descriptor-bound, scrubbed-environment `br where` resolves one hop to the bound
fixture canonical directory. Zero or multiple accepted codecs disable that
adapter version. Bind the codec ID and oracle receipt into registry validation,
manifest, plan, approval, and receipt. Reject NUL/CR, trailing-space,
multiline, symlink, nonregular, and multi-hop variants; record exact prior bytes,
mode, absence, and intended bytes.

- [ ] **Step 2: Run the RED tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_inventory`

Expected: FAIL because inventory functions do not exist.

- [ ] **Step 3: Implement bounded discovery and classification**

Invoke only the verified Git descriptor through `run_verified` after `fchdir`
to the retained seed descriptor, as `git worktree list --porcelain`. Seed worktrees must share the seed's
physical Git common-dir; explicit independent clones must match their
registry-bound repository identity. Merge explicit extras, validate containment
and membership, de-duplicate managed `.beads` identities across the whole
registry, inspect `.beads`, positively attest SQLite-v1 versus legacy/mixed
formats, fingerprint source members through read-only descriptors, and create a
deterministically ordered manifest. Do not recursively scan shared roots.

- [ ] **Step 4: Run inventory tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_inventory`

Expected: PASS.

- [ ] **Step 5: Commit inventory generation**

```bash
git add scripts/beads_convergence/inventory.py tests/test_beads_convergence_inventory.py
git commit -m "feat(beads): build bounded topology manifests [codex][gpt-5.6-sol]"
```

### Task 4: Build deterministic plans and structurally read-only `plan-all`

**Files:**
- Create: `scripts/beads_convergence/planner.py`
- Test: `tests/test_beads_convergence_planner.py`

**Interfaces:**
- Consumes: `Registry` and per-repository `Manifest`.
- Produces: `build_plan(manifest) -> Plan` and `plan_all(registry) -> PlanAllReceipt`.

- [ ] **Step 1: Write planning RED tests**

```python
def test_plan_is_deterministic_across_two_runs():
    first = build_plan(manifest_fixture())
    second = build_plan(manifest_fixture())
    self.assertEqual(first.sha256, second.sha256)

def test_plan_all_has_no_apply_parameter_or_mutation_calls():
    signature = inspect.signature(plan_all)
    self.assertNotIn("apply", signature.parameters)
    before = fixture_tree_fingerprints(multi_repo_root)
    plan_all(registry_fixture())
    self.assertEqual(before, fixture_tree_fingerprints(multi_repo_root))
```

Cover missing, unsupported, incomplete, newly appeared, and vanished entries;
prove separate plan hashes and nonzero aggregate status on any repository error.

- [ ] **Step 2: Run the RED tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_planner`

Expected: FAIL because planning functions do not exist.

- [ ] **Step 3: Implement canonical planning**

Select only complete, healthy, positively attested noncanonical physical
stores, sort by resolved worktree path, bind every source/redirect fingerprint,
and exclude volatile metadata from the plan hash. Keep aggregate plan results
independent. Apply deterministically recomputes this plan from the bound
manifest and live state; it does not accept a mutable plan file.

- [ ] **Step 4: Run planner tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_planner`

Expected: PASS.

- [ ] **Step 5: Commit deterministic planning**

```bash
git add scripts/beads_convergence/planner.py tests/test_beads_convergence_planner.py
git commit -m "feat(beads): add deterministic multi-repo planning [codex][gpt-5.6-sol]"
```

### Task 5: Implement journaled one-repo apply and explicit recovery

**Files:**
- Create: `scripts/beads_convergence/transaction.py`
- Create: `scripts/beads_convergence/approval.py`
- Create: `.claude/skills/beads-redirect-convergence/references/approval-v1.schema.json`
- Create: `.claude/skills/beads-redirect-convergence/references/journal-v1.schema.json`
- Create: `.claude/skills/beads-redirect-convergence/references/receipt-v1.schema.json`
- Test: `tests/test_beads_convergence_transaction.py`
- Test: `tests/test_beads_convergence_crash_recovery.py`

**Interfaces:**
- Consumes: validated registry, manifest, recomputed plan, adapter, root-owned
  trust root, signed approval, and exact operator bindings.
- Produces: `apply_plan(request) -> ApplyReceipt`, `recover_run(request) -> RecoveryReceipt`, and durable journal transitions `PREPARED -> APPLYING -> COMMITTED|ROLLED_BACK|NEEDS_OPERATOR`.

- [ ] **Step 1: Write transaction RED tests**

```python
def test_apply_requires_literal_flag_and_all_bindings():
    with self.assertRaisesRegex(TransactionError, "explicit --apply"):
        apply_plan(request_without_apply())

def test_apply_one_repo_cannot_change_neighbor_repo():
    before_neighbor = fixture_tree_fingerprints(repo_b)
    apply_plan(valid_fixture_request(repo_id="repo-a"))
    self.assertEqual(before_neighbor, fixture_tree_fingerprints(repo_b))

def test_readable_artifacts_cannot_self_authorize_apply():
    request = request_with_every_computable_hash_but_no_external_signature()
    with self.assertRaisesRegex(ApprovalError, "external approval"):
        apply_plan(request)
```

Cover wrong registry/manifest/plan/adapter/Git/tracker/tool/canonical bindings,
unsigned/self-signed/expired/replayed/wrong-operation approvals, source drift,
every ancestor replacement, redirect symlinks, lock-path replacement, lock
contention, two registries with different evidence roots for one canonical,
unsafe trust/control ownership or modes, a second physical path to the same
canonical `(st_dev, st_ino)`, mixed/legacy backend state, unhealthy
canonical state, interrupted ordinary errors, and DB-family byte identity.
Require signer principal/fingerprint in approval and receipt. Compile the only
trust roots as `/Library/Application Support/Beads Convergence/trust` on macOS
and `/etc/beads-convergence/trust` on Linux; reject every registry/CLI/env
override and every unsafe ancestor. Signer custody must be independently
certified as hardware-held, off-host, or separately administered and unavailable
to the apply principal, but state honestly that this is an out-of-band
provisioning gate rather than a verifier-readable checkbox.
Fix the SSH signature namespace to
`beads-redirect-convergence-v1@jleechan.org`. Feed the exact captured canonical
envelope bytes on stdin; bind `ssh-keygen -Y verify -I` to the envelope's exact
`signer_principal` and the root-owned allowed-signers principal. Add negative
tests for a valid other-namespace signature, mismatched principal/identity, and
any envelope attempt to choose namespace, identity, signers file, or verifier.
Add exact redirect tests for same-directory `renameat`, `br where` verification
from the target worktree with scrubbed `BEADS_*`, mode/umask preservation, temp
collision/symlink attacks, and `unlinkat` of only `redirect` when restoring a
recorded absent pre-state.

- [ ] **Step 2: Write crash-recovery RED tests**

Use a fixture-only injected exit strategy unavailable from the production CLI.
Launch a subprocess that exits at every durability boundary: before/after
PREPARED creation and directory fsync, before/after every redirect temp fsync,
rename, target-directory fsync, and journal progress update, around COMMITTED
and receipt creation, and during every rollback/recovery target. For each point,
assert that the next invocation deterministically refuses, resumes idempotent
recovery, recognizes committed-without-receipt, or records `NEEDS_OPERATOR`
without overwriting third-party bytes. Kill recovery again midway and prove a
second recovery completes safely.

- [ ] **Step 3: Run the RED transaction tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_transaction tests.test_beads_convergence_crash_recovery`

Expected: FAIL because transaction and recovery functions do not exist.

- [ ] **Step 4: Implement safe directory operations, locking, journals, apply, rollback, and recovery**

Verify the compiled root-owned allowed-signers/verifier trust root and detached
SSH signature, then durably reserve the approval nonce in the fixed canonical-keyed
control namespace. Retain trusted-root descriptor walks for all path operations.
Key the lock and active journal only by canonical `(st_dev, st_ino)`; record
physical paths for diagnostics but never include them in serialization identity.
Acquire and retain the adapter's proven writer-exclusion lease, then require two
identical whole-family descriptor snapshots before proceeding.
Durably write journal temp + file fsync + same-directory rename + directory
fsync before mutation. For every target, record pending state durably, fsync the
redirect temp, rename with `dir_fd`, fsync the target directory, verify, then
record applied state durably. Terminal states use the same protocol. Recovery
restores only recorded pre-state from a known intended target state and records
restartable per-target progress. Transaction code receives write capabilities
only for fixed control/evidence artifacts and exact redirect basenames; a path
spy test rejects every other create/write/rename/unlink target.
Use `F_FULLFSYNC` at durability points on macOS and ordinary file/directory
`fsync` on Linux; a missing capability or sync failure is fatal. Document that
cooperative engine concurrency is covered, while malicious same-UID replacement
in the final instruction window is outside the claim and cannot be hidden by a
test assertion.

Recovery repeats descriptor-bound discovery, backend and canonical-health
attestation, acquires and holds the same writer-exclusion lease, and collects a
coherent two-pass source snapshot before its first redirect mutation. A changed
WAL/source family, unhealthy store, missing lease, or topology mismatch records
`NEEDS_OPERATOR` and leaves redirects untouched. Add recovery-time live-writer
and changed-WAL races.

- [ ] **Step 5: Run transaction tests repeatedly**

Run: `for i in 1 2 3; do python3 -m unittest -v tests.test_beads_convergence_transaction tests.test_beads_convergence_crash_recovery || exit 1; done`

Expected: all three passes succeed with identical fixture receipts except run IDs.

- [ ] **Step 6: Commit journaled transactions**

```bash
git add scripts/beads_convergence/approval.py scripts/beads_convergence/transaction.py .claude/skills/beads-redirect-convergence/references tests/test_beads_convergence_transaction.py tests/test_beads_convergence_crash_recovery.py
git commit -m "feat(beads): journal redirect transactions [codex][gpt-5.6-sol]"
```

### Task 6: Expose the fail-closed CLI

**Files:**
- Create: `scripts/beads_convergence/cli.py`
- Create: `scripts/beads-converge`
- Test: `tests/test_beads_convergence_cli.py`

**Interfaces:**
- Consumes: Tasks 1–5 public functions.
- Produces: `main(argv: Sequence[str]) -> int` and executable `scripts/beads-converge`.

- [ ] **Step 1: Write CLI RED tests**

```python
def test_plan_all_parser_has_no_apply_flag():
    result = run_cli("plan-all", "--apply")
    self.assertNotEqual(result.returncode, 0)

def test_apply_requires_one_repo_and_literal_apply():
    result = run_cli("apply", "--repo", "repo-a", *all_hash_args())
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("--apply", result.stderr)
```

Cover JSON stdout, diagnostic stderr, exit codes, missing/malformed bindings,
missing approval/signature paths, unknown commands, unknown repo IDs, and
recovery arguments. Assert there is no CLI test-authority or approval-bypass
switch and `plan-all` has no mutation-capable call path.

- [ ] **Step 2: Run the RED CLI tests**

Run: `python3 -m unittest -v tests.test_beads_convergence_cli`

Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement subcommands and thin executable**

The executable imports `scripts.beads_convergence.cli.main` and contains no
business logic. Parsers expose `--apply` only on `apply` and `--recover` only on
`recover`.

- [ ] **Step 4: Run CLI and complete focused suite**

Run: `python3 -m unittest discover -v -s tests -p 'test_beads_convergence_*.py'`

Run: `python3 -m py_compile scripts/beads-converge scripts/beads_convergence/*.py tests/test_beads_convergence_*.py`

Expected: all focused tests and compilation PASS.

- [ ] **Step 5: Commit the CLI**

```bash
git add scripts/beads-converge scripts/beads_convergence/cli.py tests/test_beads_convergence_cli.py
git commit -m "feat(beads): expose convergence CLI [codex][gpt-5.6-sol]"
```

### Task 7: Publish the portable operator skill

**Files:**
- Create: `.claude/skills/beads-redirect-convergence/SKILL.md`
- Create: `.claude/commands/beads-converge.md`
- Modify: `README.md`
- Test: `tests/test_beads_redirect_convergence_skill.py`

**Interfaces:**
- Consumes: exact CLI contracts and schemas from Tasks 1–6.
- Produces: portable discovery metadata, command pointer, operator examples, and explicit no-apply certification boundary.

- [ ] **Step 1: Write documentation contract RED tests**

Assert the skill names every binding, bans `apply-all`, distinguishes portable
engine from per-repo authority, and makes real apply a separately authorized
operation. Assert the command is a thin pointer to the skill.

- [ ] **Step 2: Run documentation RED tests**

Run: `python3 -m unittest -v tests.test_beads_redirect_convergence_skill`

Expected: FAIL because the skill and command do not exist.

- [ ] **Step 3: Write the skill, pointer command, and README entry**

Include copy-paste commands for registry validation, inventory, plan, and
`plan-all`. Document the shape of one-repo apply and recovery without embedding
a reusable approval or real repository hash. Label fixture apply, real dry-run,
trust-root provisioning, offline approval issuance, and real apply as separate
authority classes.
State that signer custody is an operational security boundary: the allowed
private key is never installed in the applying account or its SSH agent. The
CLI verifies root-owned trust and signatures but does not pretend a user-writable
file proves custody; independent certification owns that gate.

- [ ] **Step 4: Run skill and portability validation**

Run: `python3 -m unittest -v tests.test_beads_redirect_convergence_skill tests.test_skill_portability_scan`

Run: `python3 scripts/skill_portability_scan.py .claude/skills/beads-redirect-convergence`

Expected: PASS with no personal absolute paths in portable files.

- [ ] **Step 5: Commit the portable operator surface**

```bash
git add .claude/skills/beads-redirect-convergence .claude/commands/beads-converge.md README.md tests/test_beads_redirect_convergence_skill.py
git commit -m "docs(beads): add convergence operator skill [codex][gpt-5.6-sol]"
```

### Task 8: Add the host registry in `user_scope`

**Files:**
- Create in `user_scope`: `config/beads-convergence/hosts/<normalized-hostname>.json`
- Create in `user_scope`: `tests/test_beads_convergence_registry_config.py`
- Modify in `user_scope`: `docs/new-machine-setup.md`

**Interfaces:**
- Consumes: committed registry schema and registry-validator CLI from Tasks 1–7.
- Produces: reviewed host mappings only; no canonical DB, manifest, plan, or receipt.

- [ ] **Step 1: Create a fresh `user_scope` worktree and write validation RED tests**

The test loads the host registry with the portable CLI, asserts unique repo IDs,
canonical paths, Git/tracker bindings, repository identities, and managed
`.beads` identities, and rejects evidence roots inside worktrees. Use
placeholder fixture paths in tests; never mutate live redirects.

- [ ] **Step 2: Add the actual host registry with independently collected binary bindings**

Resolve each Git and `br` path, version, and SHA-256 read-only. Register only
repos that positively attest as `br-sqlite-v1`; omit legacy, mixed, and
unhealthy repositories. Do not create or install approval trust in this task.

- [ ] **Step 3: Validate the registry and machine setup documentation**

Run: `python3 -m unittest -v tests.test_beads_convergence_registry_config`

Run: `<jleechan-skills-worktree>/scripts/beads-converge registry validate --registry config/beads-convergence/hosts/<normalized-hostname>.json --expected-registry-sha256 <reviewed-sha256>`

Expected: PASS without source, redirect, Git, or tracker mutation.

- [ ] **Step 4: Commit host configuration separately**

```bash
git add config/beads-convergence/hosts tests/test_beads_convergence_registry_config.py docs/new-machine-setup.md
git commit -m "ops(beads): register convergence authorities [codex][gpt-5.6-sol]"
```

### Task 9: Certify fixtures and two real repositories read-only

**Files:**
- Create in `jleechan-skills`: `tests/test_beads_convergence_multirepo.py`
- Create in operator evidence root: immutable manifests, plans, receipts, and before/after hash reports only

**Interfaces:**
- Consumes: installed CLI and reviewed host registry.
- Produces: fixture certification and per-repository real dry-run evidence; no apply authorization.

- [ ] **Step 1: Build two independent fixture repositories**

One fixture has two noncanonical physical stores and one already-canonical
redirect; the other has one noncanonical store. Prove `plan-all` leaves every
source and redirect byte unchanged, then fixture-apply each repo separately and
prove the neighbor is untouched. Add a hostile cross-registration fixture and
prove membership/identity validation prevents repo A targets entering repo B.

- [ ] **Step 2: Run the complete focused suite three times**

Run: `for i in 1 2 3; do python3 -m unittest discover -v -s tests -p 'test_beads_convergence_*.py' || exit 1; done`

Expected: all runs PASS.

- [ ] **Step 3: Produce repeated real plans for WorldArchitect and one second registered `br-sqlite-v1` repository**

Run `inventory` and `plan` twice per repo without `--apply`. Fingerprint each
manifest, canonical DB family, eligible physical DB family, and redirect before
and after. Assert per-repo plans are deterministic and every monitored path is
unchanged.

- [ ] **Step 4: Get independent verification**

Give the exact tool commit, registry commit, commands, and evidence paths to a
read-only verifier. PASS requires independent reproduction of the fixture suite,
kill matrix, two real plan hashes, Git/tracker bindings, backend/health
attestations, and unchanged source fingerprints. Real fixture apply is not
evidence that a live repo supports apply; that claim additionally requires the
exact adapter's writer-exclusion proof.

- [ ] **Step 5: Commit only the portable multi-repo fixture**

```bash
git add tests/test_beads_convergence_multirepo.py
git commit -m "test(beads): certify multi-repo isolation [codex][gpt-5.6-sol]"
```

Do not commit host evidence into `jleechan-skills`. Do not run real `apply` or
`recover`. Open any real convergence operation as a separate operator-governed
task after canonical health is independently verified.

## Self-review result

- Every design requirement maps to Tasks 1–9.
- Public names and signatures are consistent across tasks.
- All code-producing tasks start with executable RED tests and end with focused GREEN tests.
- The plan contains no unresolved design decision, automatic apply path, or real-apply authorization.
- The two-repository certification explicitly proves central-engine reuse without centralizing data authority.
- Production apply remains fail-closed until an independently provisioned,
  root-owned trust root verifies an offline-signed one-operation approval and
  the exact tracker adapter proves non-mutating writer exclusion.
