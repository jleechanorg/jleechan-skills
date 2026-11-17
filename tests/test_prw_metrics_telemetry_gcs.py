"""PRW window telemetry in GCS: content-addressed upload, index publication, materialising reads.

A fake `gcloud` (directory-backed) and a logging `zstd` wrapper stand in at the process
boundary; git is real and the compression is the real zstd binary.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import prw_metrics as m

REAL_ZSTD = shutil.which("zstd")
BUCKET = "test-bucket"
PREFIX = f"gs://{BUCKET}/prw/telemetry"
WIN = "20261102"
TEL = "dashboards/prw/telemetry"
IDX = "dashboards/prw/telemetry-index"

FAKE_GCLOUD = r"""#!{py}
import json, os, shutil, sys
root = os.environ["FAKE_GCS_ROOT"]
args = sys.argv[1:]
with open(os.path.join(root, "calls.log"), "a") as f:
    f.write(json.dumps(args) + "\n")
def key(uri):
    return os.path.join(root, "objects", uri[5:].replace("/", "__"))
if args[:3] == ["storage", "objects", "describe"]:
    k = key(args[3])
    if not os.path.exists(k + ".bin"):
        sys.stderr.write("ERROR: (gcloud.storage.objects.describe) HTTPError 404: No such object\n")
        sys.exit(1)
    print(json.dumps({{"size": os.path.getsize(k + ".bin"), "custom_fields": json.load(open(k + ".json"))}}))
elif args[:2] == ["storage", "cp"]:
    meta, pos = {{}}, []
    for a in args[2:]:
        if a.startswith("--custom-metadata="):
            name, value = a.split("=", 1)[1].split("=", 1)
            meta[name] = value
        elif not a.startswith("--"):
            pos.append(a)
    src, dst = pos
    if dst.startswith("gs://"):
        n = sum(1 for l in open(os.path.join(root, "calls.log"))
                if json.loads(l)[:2] == ["storage", "cp"] and json.loads(l)[-1].startswith("gs://"))
        if os.environ.get("FAKE_GCS_FAIL_UPLOAD_N") == str(n):
            sys.stderr.write("ERROR: injected upload failure\n")
            sys.exit(1)
        k = key(dst)
        if "--no-clobber" in args and os.path.exists(k + ".bin"):
            sys.exit(0)
        shutil.copy(src, k + ".bin")
        json.dump(meta, open(k + ".json", "w"))
    else:
        k = key(src)
        if not os.path.exists(k + ".bin"):
            sys.stderr.write("ERROR: 404 No such object\n")
            sys.exit(1)
        shutil.copy(k + ".bin", dst)
else:
    sys.exit(2)
"""

ZSTD_WRAPPER = r"""#!{py}
import json, os, sys
with open(os.path.join(os.environ["FAKE_GCS_ROOT"], "zstd.log"), "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
level = os.environ.get("ZSTD_WRAP_LEVEL")
args = ["-" + level if a == "-19" else a for a in sys.argv[1:]] if level else sys.argv[1:]
os.execv({real!r}, [{real!r}] + args)
"""


def sha(raw):
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def key_path(prefix, digest):
    return f"{prefix}/sha256/{digest[:2]}/{digest}.zst"


@unittest.skipUnless(REAL_ZSTD, "zstd binary required")
class GcsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prw_gcs_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.gcs, self.bin, self.home = self.tmp / "gcs", self.tmp / "bin", self.tmp / "home"
        for d in (self.gcs / "objects", self.bin, self.home):
            d.mkdir(parents=True)
        for name, body in (("gcloud", FAKE_GCLOUD.format(py=sys.executable)),
                           ("zstd", ZSTD_WRAPPER.format(py=sys.executable, real=REAL_ZSTD))):
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        (self.bin / "git").symlink_to("/usr/bin/git")  # skip the slow user-level git wrapper
        self.minpath = self.tmp / "minbin"  # a PATH with git only: no zstd, no gcloud
        self.minpath.mkdir()
        (self.minpath / "git").symlink_to("/usr/bin/git")
        patcher = mock.patch.dict(os.environ, {
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "PRW_METRICS_GCLOUD": str(self.bin / "gcloud"),
            "FAKE_GCS_ROOT": str(self.gcs), "HOME": str(self.home),
            "PRW_METRICS_TELEMETRY_BUCKET": BUCKET})
        patcher.start()
        self.addCleanup(patcher.stop)
        for var in ("PRW_METRICS_TELEMETRY_REF", "FAKE_GCS_FAIL_UPLOAD_N", "ZSTD_WRAP_LEVEL"):
            os.environ.pop(var, None)
        shard = mock.patch.object(m, "USAGE_SHARD_BYTES", 1500)
        shard.start()
        self.addCleanup(shard.stop)
        self.remote, self.local = self.tmp / "remote.git", self.tmp / "local"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.local)], check=True,
                       stderr=subprocess.PIPE)
        self.git(self.local, "config", "user.name", "T")
        self.git(self.local, "config", "user.email", "t@example.invalid")
        root = self.local / TEL
        root.mkdir(parents=True)
        (self.local / "README.md").write_text("seed\n")
        (root / "pilot_events.jsonl").write_text("{}\n")
        (root / "human_episodes.jsonl").write_text("{}\n")
        (root / "calibration_audit.json").write_text("{}")
        (root / "retention_manifest.json").write_text(json.dumps(
            {"version": "1.0", "retention_days": 90, "last_updated_at": "2000-01-01T00:00:00Z"}))
        self.git(self.local, "add", ".")
        self.git(self.local, "commit", "-qm", "seed")
        self.git(self.local, "push", "-q", "origin", "main")

    # -- helpers ---------------------------------------------------------
    def git(self, repo, *args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True,
                                       stderr=subprocess.PIPE)

    def main_sha(self):
        return self.git(self.remote, "rev-parse", "main").strip()

    def tree(self):
        return self.git(self.remote, "ls-tree", "-r", "--name-only", "main").splitlines()

    def show(self, path, ref="main"):
        return self.git(self.remote, "show", f"{ref}:{path}")

    def rows(self, count, tag="req"):
        return [{"provider": "example", "request_id": f"{tag}-{i}", "session_id": "s",
                 "timestamp": "2026-11-09T00:00:00Z", "model": "model",
                 "raw_usage": {"input_tokens": i, "output_tokens": 2},
                 "usage_conflict": False, "attributions": []} for i in range(count)]

    def summary(self, count):
        return {"w2_bounds": ["2026-11-02T00:00:00Z", "x"],
                "usage_summary": {"events": [{"status": "UNKNOWN", "known_cost_usd": None,
                                              "tokens_by_bucket": {"input": i}}
                                             for i in range(count * 20)]}}

    def publish(self, count=9, **kw):
        return m.publish_dashboard(
            "# Dashboard\n", str(self.local), verify_private_fn=lambda _: True,
            publish_telemetry=True, summary_data=self.summary(count),
            usage_events=m.load_usage_events(self.rows(count)), **kw)

    def calls(self):
        log = self.gcs / "calls.log"
        return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []

    def uploads(self):
        return [c for c in self.calls() if c[:2] == ["storage", "cp"] and c[-1].startswith("gs://")]

    def downloads(self):
        return [c for c in self.calls() if c[:2] == ["storage", "cp"] and c[-2].startswith("gs://")]

    def zstd_calls(self):
        log = self.gcs / "zstd.log"
        return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []

    def obj(self, uri):
        return self.gcs / "objects" / (uri[5:].replace("/", "__") + ".bin")

    def raw_of(self, uri):
        return subprocess.run([REAL_ZSTD, "-d", "-q", "-c", str(self.obj(uri))], check=True,
                              capture_output=True).stdout

    def put(self, uri, raw, meta_sha=None):
        """Place a (possibly wrong) object into the fake bucket."""
        path = self.obj(uri)
        path.write_bytes(subprocess.run([REAL_ZSTD, "-q", "-c"], input=raw, check=True,
                                        capture_output=True).stdout)
        path.with_suffix(".json").write_text(json.dumps({"raw_sha256": meta_sha or sha(raw)}))

    def index(self, window=WIN, ref="main"):
        return json.loads(self.show(f"{IDX}/{window}.json", ref))

    def commit_index(self, window, files):
        """Upload `files` and commit their index through the local clone (test seeding only)."""
        entries = m._upload_window(window, files, PREFIX)
        doc = m._index_document(window, entries, PREFIX, "2026-11-02T00:00:00Z")
        path = self.local / IDX / f"{window}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2) + "\n")
        self.git(self.local, "add", str(path))
        self.git(self.local, "commit", "-qm", f"index {window}")
        self.git(self.local, "push", "-q", "origin", "main")
        self.git(self.local, "fetch", "-q", "origin", "main")

    def seed_legacy(self, window, files):
        d = self.local / TEL / window
        d.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            (d / name).write_text(body)
        self.git(self.local, "add", "-A", str(d))
        self.git(self.local, "commit", "-qm", f"legacy {window}")
        self.git(self.local, "push", "-q", "origin", "main")
        self.git(self.local, "fetch", "-q", "origin", "main")

    def usage_line(self, tag):
        return json.dumps(m._sanitize_usage_event_record(self.rows(1, tag)[0])) + "\n"

    def sid(self, tag):
        return m._sanitize_usage_event_record(self.rows(1, tag)[0])["request_id"]

    def collect_usage_ids(self, **kw):
        loaded = m.Collector().collect_all(roadmap_repo=str(self.local), offline=True, **kw)
        return {e.get("request_id") for e in loaded["usage_events"]}


class UploadTests(GcsCase):
    def test_upload_content_addressed_idempotent_and_hash_authoritative(self):  # T1
        raw = "alpha\nbeta\n"
        entries = m._upload_window(WIN, {"usage_events.jsonl": raw}, PREFIX)
        digest = sha(raw)
        uri = key_path(PREFIX, digest)
        self.assertEqual(entries, [{"name": "usage_events.jsonl", "bytes": len(raw), "sha256": digest,
                                    "zst_bytes": entries[0]["zst_bytes"], "uri": uri}])
        self.assertEqual(self.raw_of(uri), raw.encode())
        self.assertEqual(json.loads(self.obj(uri).with_suffix(".json").read_text()),
                         {"raw_sha256": digest})
        self.assertTrue(any("--no-clobber" in c for c in self.uploads()))
        self.assertEqual(len(self.zstd_calls()), 1)
        before = (len(self.zstd_calls()), len(self.uploads()))
        again = m._upload_window(WIN, {"usage_events.jsonl": raw}, PREFIX)
        self.assertEqual(again[0]["sha256"], digest)
        self.assertEqual((len(self.zstd_calls()), len(self.uploads())), before)  # exists: no zstd, no cp
        # a different zstd encoding of the same raw bytes maps to the same key
        shutil.rmtree(self.gcs / "objects")
        (self.gcs / "objects").mkdir()
        os.environ["ZSTD_WRAP_LEVEL"] = "3"
        other = m._upload_window(WIN, {"usage_events.jsonl": raw}, PREFIX)
        self.assertEqual(other[0]["uri"], uri)
        self.assertEqual(other[0]["sha256"], digest)
        # existing object whose stored raw hash disagrees with its key fails loudly
        wrong = "gamma\n"
        self.put(key_path(PREFIX, sha(wrong)), b"not gamma", meta_sha="0" * 64)
        with self.assertRaises(m.TelemetryStoreError):
            m._upload_window(WIN, {"usage_events.jsonl": wrong}, PREFIX)


class PublishTests(GcsCase):
    def test_publish_with_bucket_swaps_window_blobs_for_index_keeps_root_files(self):  # T2
        result = self.publish()
        self.assertTrue(result["committed"], result)
        tree = self.tree()
        self.assertFalse([p for p in tree if p.startswith(f"{TEL}/{WIN}/")])
        for root_file in ("pilot_events.jsonl", "human_episodes.jsonl", "calibration_audit.json"):
            self.assertIn(f"{TEL}/{root_file}", tree)
        self.assertNotEqual(json.loads(self.show(f"{TEL}/retention_manifest.json"))["last_updated_at"],
                            "2000-01-01T00:00:00Z")
        doc = self.index()
        self.assertEqual((doc["schema"], doc["window"], doc["bucket_prefix"]), (1, WIN, PREFIX))
        self.assertNotIn("export_sha256", doc)
        self.assertGreater(len(doc["files"]), 3)
        for entry in doc["files"]:
            self.assertTrue(self.obj(entry["uri"]).exists(), entry)

    def test_publish_without_bucket_keeps_legacy_layout(self):  # T2c (characterization)
        del os.environ["PRW_METRICS_TELEMETRY_BUCKET"]
        result = self.publish()
        self.assertTrue(result["committed"], result)
        bundle = m.Publisher(str(self.local)).write_telemetry_bundle(
            self.summary(9), usage_events=m.load_usage_events(self.rows(9)))
        tree = self.tree()
        self.assertTrue(all(p in tree for p in bundle))
        self.assertFalse([p for p in tree if p.startswith(IDX)])
        self.assertEqual(self.calls(), [])

    def test_publish_without_bucket_blocks_when_parent_has_index(self):  # T2d
        self.assertTrue(self.publish()["committed"])
        head = self.main_sha()
        del os.environ["PRW_METRICS_TELEMETRY_BUCKET"]
        result = self.publish(count=5)
        self.assertEqual(result["action"], "BLOCKED", result)
        self.assertFalse(result["committed"])
        self.assertIn(f"window {WIN} has an index but no bucket configured", result["reason"])
        self.assertEqual(self.main_sha(), head)

    def test_publish_after_backfill_drops_legacy_blobs_keeps_backfilled_entries(self):  # T7b
        self.seed_legacy(WIN, {"retained_sources.json": "{}",
                               "usage_events.jsonl": self.usage_line("legacy")})
        commit = self.git(self.local, "rev-parse", "HEAD").strip()
        path = self.local / IDX / f"{WIN}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(m.backfill_window_index(str(self.local), commit, WIN, BUCKET))
        self.git(self.local, "add", str(path))
        self.git(self.local, "commit", "-qm", "backfilled index")
        self.git(self.local, "push", "-q", "origin", "main")
        self.assertTrue([p for p in self.tree() if p.startswith(f"{TEL}/{WIN}/")])
        result = self.publish(count=5)
        self.assertTrue(result["committed"], result)
        self.assertFalse([p for p in self.tree() if p.startswith(f"{TEL}/{WIN}/")])
        self.assertIn("retained_sources.json", {e["name"] for e in self.index()["files"]})

    def test_unsanitizable_file_blocks_before_upload(self):  # T2b
        result = m.publish_dashboard(
            "# D\n", str(self.local), verify_private_fn=lambda _: True,
            telemetry_files={f"{TEL}/{WIN}/raw_transcript.txt": "secret"})
        self.assertEqual(result["action"], "BLOCKED")
        self.assertFalse(result["committed"])
        self.assertIn("Unsanitizable telemetry file rejected", result["reason"])
        self.assertEqual((self.calls(), self.zstd_calls()), ([], []))

    def test_publish_upload_failure_returns_blocked_and_commits_nothing(self):  # T3
        self.assertTrue(self.publish(count=5)["committed"])
        head, index_before = self.main_sha(), self.show(f"{IDX}/{WIN}.json")
        before = len(self.uploads())
        os.environ["FAKE_GCS_FAIL_UPLOAD_N"] = str(before + 3)
        result = self.publish(count=9)
        self.assertEqual(result["action"], "BLOCKED", result)
        self.assertFalse(result["committed"])
        self.assertEqual(len(self.uploads()) - before, 3)  # attempted once, never retried
        self.assertEqual(self.main_sha(), head)
        self.assertEqual(self.show(f"{IDX}/{WIN}.json"), index_before)

    def test_private_check_precedes_any_upload(self):  # T3
        result = m.publish_dashboard(
            "# D\n", str(self.local), verify_private_fn=lambda _: False, publish_telemetry=True,
            summary_data=self.summary(5), usage_events=m.load_usage_events(self.rows(5)))
        self.assertEqual(result["action"], "PUBLIC_REPO_REJECTED")
        self.assertEqual(self.calls(), [])

    def test_index_unions_previous_index_for_sticky_files(self):  # T3b
        sticky = {f"{TEL}/{WIN}/retained_handoffs.jsonl": "{}\n",
                  f"{TEL}/{WIN}/retained_sources.json": "{}"}
        self.assertTrue(self.publish(count=9, telemetry_files=sticky)["committed"])
        first = {e["name"]: e for e in self.index()["files"]}
        self.assertTrue({"retained_handoffs.jsonl", "retained_sources.json"} <= set(first))
        self.assertTrue(self.publish(count=5)["committed"])
        second = {e["name"]: e for e in self.index()["files"]}
        self.assertTrue({"retained_handoffs.jsonl", "retained_sources.json"} <= set(second))
        run_two = m.Publisher(str(self.local)).write_telemetry_bundle(
            self.summary(5), usage_events=m.load_usage_events(self.rows(5)))
        fresh = {os.path.basename(p): c for p, c in run_two.items() if f"/{WIN}/" in p}
        self.assertEqual({n for n in second if m._usage_file(n) or m._summary_candidate(n)},
                         {n for n in fresh if m._usage_file(n) or m._summary_candidate(n)})
        self.assertNotEqual(first["summary_snapshot.manifest.json"]["sha256"],
                            second["summary_snapshot.manifest.json"]["sha256"])
        self.assertEqual(second["summary_snapshot.manifest.json"]["sha256"],
                         sha(fresh["summary_snapshot.manifest.json"]))

    def test_cli_exits_nonzero_when_upload_fails(self):  # T3c
        os.environ["PRW_METRICS_GCLOUD"] = "/usr/bin/false"
        head = self.main_sha()
        now = "2026-11-02T01:00:00Z"
        collected = {"prs": [], "timeline": [], "handoff_records": [], "status": "COMPLETE",
                     "sources": {"example/repo": {"status": "COMPLETE", "cutoff": now}}}
        args = ["prw_metrics.py", "--offline", "--publish", "--roadmap-repo", str(self.local),
                "--cutoff", now]
        out = io.StringIO()
        with redirect_stdout(out), \
                mock.patch.object(m.Collector, "collect_all", return_value=collected), \
                mock.patch.object(m.Publisher, "_verify_destination_is_private", return_value=True), \
                mock.patch("sys.argv", args):
            with self.assertRaises(SystemExit) as raised:
                m.main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("BLOCKED", out.getvalue())
        self.assertEqual(self.main_sha(), head)

    def test_legacy_blobs_without_index_fail_closed(self):  # T3d
        self.seed_legacy(WIN, {"usage_events.jsonl": self.usage_line("legacy")})
        head = self.main_sha()
        result = self.publish(count=5)
        self.assertEqual(result["action"], "BLOCKED", result)
        self.assertFalse(result["committed"])
        self.assertIn("run the one-shot backfill", result["reason"])
        self.assertEqual(self.main_sha(), head)

    def test_index_is_rendered_against_the_repinned_parent(self):  # T3d (retry loop)
        self.assertTrue(self.publish(count=9)["committed"])
        other = self.tmp / "other"
        subprocess.run(["git", "clone", "-q", str(self.remote), str(other)], check=True,
                       stderr=subprocess.PIPE)
        self.git(other, "config", "user.name", "O")
        self.git(other, "config", "user.email", "o@example.invalid")
        raced = {"done": False}
        real_run = subprocess.run

        def racing_run(argv, *a, **kw):
            if not raced["done"] and isinstance(argv, list) and "push" in argv and "-C" in argv \
                    and argv[argv.index("-C") + 1] == str(self.local):
                raced["done"] = True
                extra = m._upload_window(WIN, {"retained_sources.json": "{\"raced\": 1}"}, PREFIX)
                doc = json.loads((other / IDX / f"{WIN}.json").read_text())
                doc["files"] = sorted(doc["files"] + extra, key=lambda e: e["name"])
                (other / IDX / f"{WIN}.json").write_text(json.dumps(doc, indent=2) + "\n")
                self.git(other, "pull", "-q", "origin", "main")
                self.git(other, "commit", "-qam", "raced")
                self.git(other, "push", "-q", "origin", "main")
            return real_run(argv, *a, **kw)

        with mock.patch.object(m.subprocess, "run", racing_run):
            result = self.publish(count=5)
        self.assertTrue(result["committed"], result)
        self.assertTrue(raced["done"])
        self.assertIn("retained_sources.json", {e["name"] for e in self.index()["files"]})

    def test_missing_zstd_is_a_clear_prerequisite_error(self):  # T6c
        os.environ["PATH"] = str(self.minpath)
        self.assertIsNone(shutil.which("zstd"))
        with self.assertRaisesRegex(m.TelemetryStoreError, "missing prerequisite: zstd"):
            m._upload_window(WIN, {"usage_events.jsonl": "x\n"}, PREFIX)
        head = self.main_sha()
        result = self.publish(count=5)
        self.assertEqual(result["action"], "BLOCKED", result)
        self.assertIn("missing prerequisite: zstd", result["reason"])
        self.assertEqual(self.main_sha(), head)

    def test_gcloud_resolution_order(self):  # T6
        explicit = self.tmp / "explicit-gcloud"
        explicit.write_text("#!/bin/sh\n")
        explicit.chmod(0o755)
        os.environ["PRW_METRICS_GCLOUD"] = str(explicit)
        self.assertEqual(m._gcloud_bin(), str(explicit))
        del os.environ["PRW_METRICS_GCLOUD"]
        self.assertEqual(m._gcloud_bin(), str(self.bin / "gcloud"))  # PATH
        os.environ["PATH"] = str(self.minpath)
        with self.assertRaisesRegex(m.TelemetryStoreError, "missing prerequisite: gcloud"):
            m._gcloud_bin()
        sdk = self.home / "google-cloud-sdk" / "bin"
        sdk.mkdir(parents=True)
        (sdk / "gcloud").write_text("#!/bin/sh\n")
        (sdk / "gcloud").chmod(0o755)
        self.assertEqual(m._gcloud_bin(), str(sdk / "gcloud"))


class ReadTests(GcsCase):
    def published(self, count=9):
        self.assertTrue(self.publish(count=count)["committed"])
        return self.index()["files"]

    def test_export_materialises_index_with_cache_and_deletes_tempdir(self):  # T4
        entries = self.published()
        dest = self.tmp / "export"
        self.assertTrue(m.export_published_telemetry(str(self.local), str(dest)))
        expected = m.Publisher(str(self.local)).write_telemetry_bundle(
            self.summary(9), usage_events=m.load_usage_events(self.rows(9)))
        for entry in entries:
            got = (dest / WIN / entry["name"]).read_bytes()
            self.assertEqual(sha(got), entry["sha256"])
            if f"{TEL}/{WIN}/{entry['name']}" in expected:
                self.assertEqual(got, expected[f"{TEL}/{WIN}/{entry['name']}"].encode())
            cached = self.home / ".cache" / "prw-metrics" / "telemetry" / f"{entry['sha256']}.zst"
            self.assertTrue(cached.read_bytes().startswith(b"\x28\xb5\x2f\xfd"))  # compressed, not raw
        self.assertTrue((dest / "pilot_events.jsonl").exists())  # root files still come from git
        fetched = len(self.downloads())
        m.export_published_telemetry(str(self.local), str(self.tmp / "export2"))
        self.assertEqual(len(self.downloads()), fetched)  # warm cache: zero fetches
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        with mock.patch.object(tempfile, "tempdir", str(scratch)):
            m.Collector().collect_all(roadmap_repo=str(self.local), offline=True)
        self.assertEqual(list(scratch.iterdir()), [])

    def test_materialisation_peak_temp_is_about_one_window(self):  # T4c
        sizes = {"20261102": 200, "20261103": 400, "20261104": 800}
        for window, count in sizes.items():
            self.commit_index(window, {"usage_events.jsonl": "".join(
                self.usage_line(f"{window}-{i}") for i in range(count))})
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        peaks, real = [], m._materialise_window

        def watching(*a, **kw):
            real(*a, **kw)
            peaks.append(sum(p.stat().st_size for p in scratch.rglob("*") if p.is_file()))

        with mock.patch.object(tempfile, "tempdir", str(scratch)), \
                mock.patch.object(m, "_materialise_window", watching):
            lazy = m.Collector().collect_all(roadmap_repo=str(self.local), offline=True)
        sizes_on_disk = [len(self.usage_line("20261104-0")) * n for n in sizes.values()]
        self.assertEqual(len(peaks), 3)
        self.assertLessEqual(max(peaks), max(sizes_on_disk) + 20_000)
        self.assertLess(max(peaks), sum(sizes_on_disk))
        self.assertEqual(list(scratch.iterdir()), [])
        # equals an all-in-one-directory load of the same files, in window order
        whole = self.tmp / "whole"
        m.export_published_telemetry(str(self.local), str(whole))
        merged = m.Collector().load_retained_telemetry(telemetry_dir=str(whole))
        self.assertEqual([e["request_id"] for e in lazy["usage_events"]],
                         [e["request_id"] for e in merged["usage_events"]])

    def test_mixed_layouts_load_oldest_first_so_newer_sources_win(self):  # T4d
        def sources(day):
            return json.dumps({"example/repo": {"status": "COMPLETE", "cutoff": f"2026-11-{day}T00:00:00Z"}})
        self.commit_index("20261102", {"retained_sources.json": sources("02")})
        self.seed_legacy("20261103", {"retained_sources.json": sources("03")})
        loaded = m.Collector(repos=["example/repo"]).collect_all(roadmap_repo=str(self.local), offline=True)
        self.assertEqual(loaded["sources"]["example/repo"]["cutoff"], "2026-11-03T00:00:00Z")

    def test_materialisation_failure_is_not_swallowed_and_does_not_fall_back_to_stale_copy(self):  # T4b
        self.published(count=5)
        stale = self.local / TEL / WIN
        stale.mkdir(parents=True)
        (stale / "usage_events.jsonl").write_text(self.usage_line("STALE-sentinel"))
        self.assertFalse(issubclass(m.TelemetryStoreError, (OSError, subprocess.SubprocessError)))
        for label, env in (("gcloud failing", {"PRW_METRICS_GCLOUD": "/usr/bin/false"}),
                           ("gcloud missing", {"PRW_METRICS_GCLOUD": str(self.tmp / "nope")}),
                           ("zstd missing", {"PATH": str(self.minpath)})):
            with self.subTest(label), mock.patch.dict(os.environ, env):
                with self.assertRaises(m.TelemetryStoreError):
                    m.Collector().collect_all(roadmap_repo=str(self.local), offline=True)

    def test_materialise_rejects_hash_mismatch_and_leaves_nothing_partial(self):  # T5
        entries = self.published(count=5)
        bad = next(e for e in entries if e["name"].startswith("usage_events.part-")
                   or e["name"] == "usage_events.jsonl")
        self.put(bad["uri"], b"corrupt", meta_sha=bad["sha256"])
        dest = self.tmp / "export"
        with self.assertRaises(ValueError):
            m.export_published_telemetry(str(self.local), str(dest))
        self.assertFalse((dest / WIN).exists())
        # a corrupted cache entry is dropped and refetched once; a second mismatch fails
        raw = m._upload_window(WIN, {"usage_events.jsonl": "alpha\n"}, PREFIX)[0]
        doc = m._index_document(WIN, [raw], PREFIX, "2026-11-02T00:00:00Z")
        self.put(raw["uri"], b"alpha\n")
        m._materialise_window(doc, str(self.tmp / "ok"))
        cache = self.home / ".cache" / "prw-metrics" / "telemetry" / f"{raw['sha256']}.zst"
        self.assertTrue(cache.exists())
        cache.write_bytes(subprocess.run([REAL_ZSTD, "-q", "-c"], input=b"tampered", check=True,
                                         capture_output=True).stdout)
        before = len(self.downloads())
        m._materialise_window(doc, str(self.tmp / "ok2"))
        self.assertEqual((self.tmp / "ok2" / "usage_events.jsonl").read_bytes(), b"alpha\n")
        self.assertEqual(len(self.downloads()), before + 1)
        cache.write_bytes(subprocess.run([REAL_ZSTD, "-q", "-c"], input=b"tampered", check=True,
                                         capture_output=True).stdout)
        self.put(raw["uri"], b"also tampered", meta_sha=raw["sha256"])
        with self.assertRaises(ValueError):
            m._materialise_window(doc, str(self.tmp / "ok3"))
        self.assertFalse((self.tmp / "ok3").exists())

    def doc(self, name="usage_events.jsonl", digest="a" * 64, window=WIN, prefix=PREFIX, uri=None):
        return {"schema": 1, "window": window, "bucket_prefix": prefix, "cutoff": "x",
                "files": [{"name": name, "bytes": 1, "sha256": digest, "zst_bytes": 1,
                           "uri": uri or key_path(prefix, digest)}]}

    def assert_rejected(self, doc):
        dest = self.tmp / "dest"
        with self.assertRaises(ValueError):
            m._materialise_window(doc, str(dest))
        self.assertFalse(dest.exists())
        self.assertEqual(self.calls(), [])

    def test_materialise_rejects_unsafe_entry_names(self):  # T5b
        for name in ("../x", "raw_transcript.txt", "a/b.jsonl", "usage_events./../x"):
            with self.subTest(name=name):
                self.assert_rejected(self.doc(name=name))
        for window in ("../w", "a/b", ""):
            with self.subTest(window=window):
                self.assert_rejected(self.doc(window=window))

    def test_materialise_rejects_bad_sha_prefix_and_mismatched_uri(self):  # T5c
        self.assert_rejected(self.doc(digest="XYZ", uri=f"{PREFIX}/sha256/XY/XYZ.zst"))
        self.assert_rejected(self.doc(digest="A" * 64))
        for prefix in ("http://test-bucket/prw/telemetry", "gs://Test-Bucket/prw/telemetry",
                       f"{PREFIX}/extra", f"{PREFIX}/"):
            with self.subTest(prefix=prefix):
                self.assert_rejected(self.doc(prefix=prefix, uri="gs://x/y"))
        self.assert_rejected(self.doc(uri=f"{PREFIX}/sha256/bb/{'a' * 64}.zst"))
        self.assert_rejected(self.doc(uri=f"gs://elsewhere/prw/telemetry/sha256/aa/{'a' * 64}.zst"))
        os.environ["PRW_METRICS_TELEMETRY_BUCKET"] = "other"  # reads use the bucket the index names
        with self.assertRaises(ValueError):  # passes validation, then fails fetching (nothing uploaded)
            m._materialise_window(self.doc(), str(self.tmp / "dest2"))
        self.assertTrue(self.downloads())

    def test_telemetry_ref_option_selects_legacy_commit(self):  # T6d
        self.seed_legacy(WIN, {"usage_events.jsonl": self.usage_line("legacy")})
        legacy_commit = self.git(self.local, "rev-parse", "HEAD").strip()
        self.git(self.local, "rm", "-rq", f"{TEL}/{WIN}")
        self.git(self.local, "commit", "-qm", "drop legacy")
        self.git(self.local, "push", "-q", "origin", "main")
        self.git(self.local, "fetch", "-q", "origin", "main")
        current = self.tmp / "current"
        self.assertTrue(m.export_published_telemetry(str(self.local), str(current)))
        self.assertFalse((current / WIN).exists())
        pinned = self.tmp / "pinned"
        self.assertTrue(m.export_published_telemetry(str(self.local), str(pinned), ref=legacy_commit))
        self.assertTrue((pinned / WIN / "usage_events.jsonl").exists())
        os.environ["PRW_METRICS_TELEMETRY_REF"] = legacy_commit
        via_env = self.tmp / "env"
        self.assertTrue(m.export_published_telemetry(str(self.local), str(via_env)))
        self.assertTrue((via_env / WIN / "usage_events.jsonl").exists())
        self.assertIn(self.sid("legacy"), self.collect_usage_ids(telemetry_ref=legacy_commit))

    def test_index_covered_window_is_read_from_index_only(self):  # T6b
        legacy = {"usage_events.jsonl": self.usage_line("LEGACY-sentinel")}
        self.seed_legacy(WIN, legacy)
        self.seed_legacy("20261103", {"usage_events.jsonl": self.usage_line("UNCOVERED-sentinel")})
        self.commit_index(WIN, {"usage_events.jsonl": self.usage_line("INDEX-sentinel")})
        # (a) legacy blobs and an index for one window in a single export: the index wins
        ids = self.collect_usage_ids()
        self.assertIn(self.sid("INDEX-sentinel"), ids)
        self.assertNotIn(self.sid("LEGACY-sentinel"), ids)
        # (c) a window no index covers still loads from git, and root files still load
        self.assertIn(self.sid("UNCOVERED-sentinel"), ids)
        loaded = m.Collector().collect_all(roadmap_repo=str(self.local), offline=True)
        self.assertIsNotNone(loaded.get("pilot_events"))
        # (b) an explicit --telemetry-dir wins and its window is not duplicated from the index
        explicit = self.tmp / "frozen"
        (explicit / WIN).mkdir(parents=True)
        (explicit / WIN / "usage_events.jsonl").write_text(self.usage_line("EXPLICIT-sentinel"))
        fetched = len(self.downloads())
        ids = self.collect_usage_ids(telemetry_dir=str(explicit))
        self.assertIn(self.sid("EXPLICIT-sentinel"), ids)
        self.assertNotIn(self.sid("INDEX-sentinel"), ids)
        self.assertEqual(len(self.downloads()), fetched)


class BackfillTests(GcsCase):
    def test_backfill_builds_index_from_git_blobs(self):  # T7
        files = {"usage_events.jsonl": self.usage_line("legacy"),
                 "retained_sources.json": "{}", "pilot_events.jsonl": "{}\n"}
        self.seed_legacy(WIN, files)
        commit = self.git(self.local, "rev-parse", "HEAD").strip()
        self.seed_legacy("20261103", {"usage_events.jsonl": self.usage_line("other")})
        expected_cutoff = self.git(self.local, "log", "-1", "--format=%cI", commit, "--",
                                   f"{TEL}/{WIN}").strip()
        with mock.patch.object(m.Publisher, "publish", side_effect=AssertionError("publish used")), \
                mock.patch.object(m, "_summary_parts", side_effect=AssertionError("summary rebuilt")):
            text = m.backfill_window_index(str(self.local), commit, WIN, BUCKET)
        doc = json.loads(text)
        names = self.git(self.local, "ls-tree", "--name-only", commit, f"{TEL}/{WIN}/").split()
        self.assertEqual([e["name"] for e in doc["files"]], sorted(os.path.basename(n) for n in names))
        self.assertEqual(doc["cutoff"], expected_cutoff)
        for entry in doc["files"]:
            exact = subprocess.check_output(
                ["git", "-C", str(self.local), "show", f"{commit}:{TEL}/{WIN}/{entry['name']}"])
            self.assertEqual(self.raw_of(entry["uri"]), exact)
            self.assertEqual(entry["sha256"], sha(exact))
        m._validate_index(doc)  # the same validator publish() and the reader use


if __name__ == "__main__":
    unittest.main()
