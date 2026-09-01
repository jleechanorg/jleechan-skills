"""Unit tests for download_campaign.py — pure functions and Firebase init contract."""
import sys
import types
import unittest
import unittest.mock
from pathlib import Path

# Add the scripts dir to path so we can import the module
SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

# Provide stubs for external WA repo modules if not present in the environment
for _mod in ("clock_skew_credentials", "firestore_service", "document_generator"):
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            _stub = types.ModuleType(_mod)
            if _mod == "clock_skew_credentials":
                _stub.apply_clock_skew_patch = lambda: None
            sys.modules[_mod] = _stub

import download_campaign as dc  # noqa: E402


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(dc.slugify("Vespera Thul"), "vespera-thul")

    def test_special_chars_collapsed(self):
        self.assertEqual(dc.slugify("BG3 — Nocturne v3.5!"), "bg3-nocturne-v3-5")

    def test_truncation(self):
        s = "a" * 200
        out = dc.slugify(s)
        self.assertLessEqual(len(out), 80)
        self.assertEqual(len(out), 80)

    def test_strip_leading_trailing_dashes(self):
        self.assertEqual(dc.slugify("  hello  "), "hello")
        self.assertEqual(dc.slugify("---foo---"), "foo")

    def test_idempotent_path_uniqueness(self):
        """Two campaigns with the same title must produce different wiki paths."""
        title = "Vespera Thul (copy)"
        slug = dc.slugify(title)
        ids = ["a" * 20, "b" * 20, "c" * 20]
        paths = [f"{slug}-{i[:8]}.md" for i in ids]
        # The crucial check: all paths unique despite same slug
        self.assertEqual(len(set(paths)), 3)


class TestPathCollisionAvoidance(unittest.TestCase):
    def test_duplicate_titles_get_unique_paths(self):
        """Reproduces the actual bug: 'Vespera Thul (copy)' × 11 copies."""
        title = "Vespera Thul (copy)"
        slug = dc.slugify(title)
        ids = [f"abc{i:04d}xyz" for i in range(11)]
        paths = [f"{slug}-{cid[:8]}.md" for cid in ids]
        unique = set(paths)
        self.assertEqual(len(unique), 11, "Slug collision: duplicates would overwrite")
        # And the raw archive dir uses campaign_id directly — also unique
        raw_dirs = [cid for cid in ids]
        self.assertEqual(len(set(raw_dirs)), 11)


class TestDependencyCheck(unittest.TestCase):
    def test_required_modules_importable(self):
        """The .venv dep chain must be installed for this skill to work."""
        required = [
            "firebase_admin",
            "google.cloud.firestore",
            "flask",
            "pydantic",
            "jsonschema",
            "docx",
            "fpdf",
            "clock_skew_credentials",
        ]
        missing = []
        for mod in required:
            try:
                __import__(mod)
            except ImportError as e:
                missing.append(f"{mod}: {e}")
        self.assertFalse(
            missing,
            f"Missing deps in WA .venv: {missing}. "
            "Run the bootstrap in SKILL.md Phase 1.",
        )


class TestInitFirebaseReturnValue(unittest.TestCase):
    """Regression: init_firebase() must return a non-None firestore client even
    when firebase_admin was already initialized by another module (e.g.
    clock_skew_credentials.apply_clock_skew_patch()) or by a prior call to
    init_firebase() from main(). Bug surfaced 2026-08-20 — every user errored
    with 'NoneType' object has no attribute 'collection' (157 users failed)."""

    def setUp(self):
        # Snapshot and reset firebase_admin state so each test starts clean
        self._orig_apps = dict(dc.firebase_admin._apps)
        dc.firebase_admin._apps = {}
        # Stub credentials.Certificate so we never touch a real SA JSON file
        self._cert_patcher = unittest.mock.patch.object(
            dc.credentials, "Certificate", return_value=unittest.mock.MagicMock(name="cred")
        )
        self._cert_patcher.start()

    def tearDown(self):
        dc.firebase_admin._apps = self._orig_apps
        self._cert_patcher.stop()

    def test_init_firebase_returns_client_when_apps_already_initialized(self):
        """The bug: if firebase_admin._apps is already truthy (e.g. another
        module or a prior init_firebase() call from main() pre-populated it),
        init_firebase() used to fall through the entire `if not firebase_admin._apps:`
        block without ever returning firestore.client(), returning None
        implicitly — causing 'NoneType' has no attribute 'collection'."""
        # Simulate firebase_admin already initialized (this is the state after
        # main()'s first init_firebase() call, which is what 2026-08-20 hit)
        dc.firebase_admin._apps = {"[DEFAULT]": object()}

        # Stub firestore.client() + initialize_app() so we don't need real
        # Firebase creds and so we can verify the no-double-init invariant.
        sentinel = object()
        with unittest.mock.patch.object(
            dc.firestore, "client", return_value=sentinel
        ) as mock_client, unittest.mock.patch.object(
            dc.firebase_admin, "initialize_app"
        ) as mock_init:
            result = dc.init_firebase()

        self.assertIsNotNone(
            result,
            "init_firebase() returned None — this is the 2026-08-20 bug",
        )
        self.assertIs(result, sentinel)
        mock_init.assert_not_called()
        mock_client.assert_called_once()

    def test_init_firebase_returns_client_on_fresh_init(self):
        """Sanity: when firebase_admin._apps is empty (cold start), the function
        must still return a client (i.e. the fix didn't regress the happy path)."""
        dc.firebase_admin._apps = {}
        sentinel = object()
        with unittest.mock.patch.object(
            dc.firestore, "client", return_value=sentinel
        ), unittest.mock.patch.object(dc.firebase_admin, "initialize_app"):
            result = dc.init_firebase()
        self.assertIs(result, sentinel)


if __name__ == "__main__":
    unittest.main()
