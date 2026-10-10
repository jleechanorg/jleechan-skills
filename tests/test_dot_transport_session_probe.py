"""Exercise the read-only Dot session probe through its Node entrypoint."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOT_SH = REPO_ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot.sh"
NVM_NODE22 = Path.home() / ".nvm" / "versions" / "node" / "v22.22.0" / "bin" / "node"
NODE22 = Path(
    os.environ.get("DOT_NODE")
    or (str(NVM_NODE22) if NVM_NODE22.is_file() else shutil.which("node") or "node")
)
SESSION_EMAIL = "dot-session-user@example.invalid"


class DotSessionProbeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dot-session-probe-", dir="/tmp")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir(mode=0o700)
        self.config = self.root / "dot-config.json"
        self.config.write_text(
            json.dumps(
                {
                    "default_account": "fixture",
                    "accounts": {
                        "fixture": {
                            "url": "https://chatgpt.com/dots/fixture",
                            "slug": "fixture",
                            "user_data_dir": str(self.profile),
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.chrome = self.root / "fake-chrome"
        self.chrome.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        self.chrome.chmod(self.chrome.stat().st_mode | stat.S_IXUSR)
        self.modules = self.root / "node_modules" / "playwright"
        self.modules.mkdir(parents=True)
        self.require_anchor = self.root / "require-anchor.cjs"
        self.require_anchor.touch()
        self.state_path = self.root / "probe-state.json"
        self.audit_path = self.root / "profile-access-audit.json"
        self.env = {
            name: os.environ[name]
            for name in ("PATH", "TMPDIR", "LANG", "LC_ALL")
            if name in os.environ
        }
        self.env.update(
            {
                "HOME": str(self.home),
                "DOT_ACCOUNT": "fixture",
                "DOT_CONFIG_FILE": str(self.config),
                "DOT_CHROME_USER_DATA": str(self.profile),
                "DOT_CHROME_BIN": str(self.chrome),
                "DOT_PW_MODULES": str(self.require_anchor),
                "DOT_NODE": str(NODE22),
                "DOT_NO_REMOTE": "1",
            }
        )
        self._install_fake_playwright()

    def tearDown(self):
        self.temp.cleanup()

    def _install_fake_playwright(
        self,
        *,
        status=200,
        is_json=True,
        email=SESSION_EMAIL,
        composer_available=True,
        title="ChatGPT",
        close_fails=False,
        raw_body=None,
        composer_visible=True,
        hang_evaluate=False,
        hang_fetch=False,
        hang_launch=False,
        close_hangs=False,
        browser_missing=False,
        delay_composer_count_ms=0,
        close_delay_ms=0,
    ):
        state = {
            "launch": None,
            "close_count": 0,
            "goto_count": 0,
            "composer_count": 0,
            "composer_count_resolved": False,
            "composer_visibility_read": False,
            "composer_reads": 0,
            "composer_mutations": 0,
            "fetch_abort_seen": False,
            "launch_timeout": None,
            "launch_timeout_fired": False,
            "late_launch_resolved": False,
            "browser_close_count": 0,
        }
        if raw_body is None:
            raw_body = (
                json.dumps({"user": {"email": email}} if email else {})
                if is_json
                else "not json"
            )
        script = r"""const fs = require("node:fs");
const statePath = __STATE_PATH__;
const state = __STATE__;
const rawBody = __RAW_BODY__;
const responseStatus = __STATUS__;
const composerAvailable = __COMPOSER_AVAILABLE__;
const composerVisible = __COMPOSER_VISIBLE__;
const pageTitle = __TITLE__;
const closeFails = __CLOSE_FAILS__;
const hangEvaluate = __HANG_EVALUATE__;
const hangFetch = __HANG_FETCH__;
const hangLaunch = __HANG_LAUNCH__;
const closeHangs = __CLOSE_HANGS__;
const browserMissing = __BROWSER_MISSING__;
const delayComposerCountMs = __DELAY_COMPOSER_COUNT_MS__;
const closeDelayMs = __CLOSE_DELAY_MS__;
function save() { fs.writeFileSync(statePath, JSON.stringify(state)); }
const composerSelector = [
  '[contenteditable=true]',
  '#prompt-textarea',
  'textarea[placeholder*="Message"]',
].join(', ');
const composer = {
  async count() {
    state.composer_count += 1;
    save();
    if (delayComposerCountMs > 0) {
      await new Promise(resolve => setTimeout(resolve, delayComposerCountMs));
    }
    state.composer_count_resolved = true;
    save();
    return composerAvailable ? 1 : 0;
  },
  async isVisible() {
    state.composer_visibility_read = true;
    save();
    return composerVisible;
  },
  first() { return this; },
  async innerText() {
    state.composer_reads += 1;
    save();
    throw new Error("composer read forbidden");
  },
  async focus() {
    state.composer_mutations += 1;
    save();
    throw new Error("composer mutation forbidden");
  },
  async click() {
    state.composer_mutations += 1;
    save();
    throw new Error("composer mutation forbidden");
  },
};
const page = {
  async goto() { state.goto_count += 1; save(); },
  async title() { return pageTitle; },
  locator(selector) {
    if (selector === composerSelector) return composer;
    throw new Error("unexpected locator");
  },
  async evaluate(fn, arg) {
    if (fn.toString().includes("/api/auth/session")) {
      if (hangEvaluate) return new Promise(() => {});
      const previousFetch = global.fetch;
      global.fetch = async (url, options) => {
        if (url !== '/api/auth/session' || options?.credentials !== 'include') {
          throw new Error('unexpected session request');
        }
        if (hangFetch) {
          return new Promise((resolve, reject) => {
            options.signal.addEventListener('abort', () => {
              state.fetch_abort_seen = true;
              save();
              reject(new Error('fetch aborted'));
            }, { once: true });
          });
        }
        return { status: responseStatus, async text() { return rawBody; } };
      };
      try { return await fn(arg); } finally { global.fetch = previousFetch; }
    }
    throw new Error("unexpected page evaluation");
  },
  async click() {
    state.composer_mutations += 1;
    save();
    throw new Error("page click forbidden");
  },
};
exports.chromium = {
  async launchPersistentContext(profileDir, options) {
    state.launch = {
      profileDir,
      optionKeys: Object.keys(options).sort(),
      executablePath: options.executablePath,
      headless: options.headless,
      args: options.args,
      ignoreDefaultArgs: options.ignoreDefaultArgs,
      userAgent: options.userAgent,
    };
    save();
    const browserListeners = [];
    let browserConnected = true;
    const browser = {
      once(event, listener) {
        if (event === 'disconnected') browserListeners.push(listener);
        return this;
      },
      isConnected() { return browserConnected; },
      async close() {
        state.browser_close_count += 1;
        browserConnected = false;
        save();
        for (const listener of browserListeners) listener(this);
      },
    };
    const context = {
      async newPage() { return page; },
      browser() { return browserMissing ? null : browser; },
      async close() {
        state.close_count += 1;
        save();
        if (closeHangs) return new Promise(() => {});
        if (closeDelayMs > 0) {
          await new Promise(resolve => setTimeout(resolve, closeDelayMs));
        }
        if (closeFails) throw new Error("fixture close failure");
      },
    };
    if (hangLaunch) {
      if (Number.isFinite(options.timeout)) {
        state.launch_timeout = options.timeout;
        save();
        return new Promise((resolve, reject) => setTimeout(() => {
          state.launch_timeout_fired = true;
          save();
          reject(new Error('fixture launch timeout'));
        }, 15));
      }
      return new Promise(resolve => setTimeout(() => {
        state.late_launch_resolved = true;
        save();
        resolve(context);
      }, 80));
    }
    return context;
  },
};
""".replace("__STATE_PATH__", json.dumps(str(self.state_path)))
        script = script.replace("__STATE__", json.dumps(state))
        script = script.replace("__RAW_BODY__", json.dumps(raw_body))
        script = script.replace("__STATUS__", json.dumps(status))
        script = script.replace(
            "__COMPOSER_AVAILABLE__", json.dumps(composer_available)
        )
        script = script.replace("__TITLE__", json.dumps(title))
        script = script.replace("__CLOSE_FAILS__", json.dumps(close_fails))
        script = script.replace("__COMPOSER_VISIBLE__", json.dumps(composer_visible))
        script = script.replace("__HANG_EVALUATE__", json.dumps(hang_evaluate))
        script = script.replace("__HANG_FETCH__", json.dumps(hang_fetch))
        script = script.replace("__HANG_LAUNCH__", json.dumps(hang_launch))
        script = script.replace("__CLOSE_HANGS__", json.dumps(close_hangs))
        script = script.replace("__BROWSER_MISSING__", json.dumps(browser_missing))
        script = script.replace(
            "__DELAY_COMPOSER_COUNT_MS__", json.dumps(delay_composer_count_ms)
        )
        script = script.replace("__CLOSE_DELAY_MS__", json.dumps(close_delay_ms))
        (self.modules / "index.js").write_text(script, encoding="utf-8")

    def _run_probe(self, expected_digest=None):
        command = [str(DOT_SH), "--account", "fixture", "probe"]
        if expected_digest is not None:
            command.append(expected_digest)
        return subprocess.run(
            command,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )

    @staticmethod
    def _result(stdout):
        for line in stdout.splitlines():
            if line.startswith("DOT_SESSION_PROBE "):
                return json.loads(line.removeprefix("DOT_SESSION_PROBE "))
        return None

    def _state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def test_authenticated_probe_compares_exact_email_digest_without_disclosing_it(
        self,
    ):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        wrong = hashlib.sha256(b"different@example.invalid").hexdigest()

        for digest, match in ((expected, True), (wrong, False)):
            with self.subTest(match=match):
                self._install_fake_playwright()
                proc = self._run_probe(digest)

                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = self._result(proc.stdout)
                self.assertIsNotNone(result, proc.stdout)
                self.assertEqual(result["status"], "authenticated")
                self.assertEqual(result["endpoint_status"], 200)
                self.assertEqual(result["identity_match"], match)
                self.assertTrue(result["composer_available"])
                self.assertTrue(result["profile_slot"].startswith("slot_"))
                self.assertNotIn(str(self.profile), json.dumps(result))
                self.assertNotIn(SESSION_EMAIL, proc.stdout)
                self.assertNotIn(expected, proc.stdout)
                self.assertNotIn("token", proc.stdout.lower())
                self.assertTrue(result["probe_id"])
                self.assertTrue(result["timestamp"].endswith("Z"))

                state = self._state()
                self.assertEqual(state["launch"]["profileDir"], str(self.profile))
                self.assertEqual(state["launch"]["executablePath"], str(self.chrome))
                self.assertIsInstance(state["launch"]["args"], list)
                self.assertIn("--no-first-run", state["launch"]["args"])
                self.assertIsInstance(state["launch"]["ignoreDefaultArgs"], list)
                self.assertIn(
                    "--enable-automation", state["launch"]["ignoreDefaultArgs"]
                )
                self.assertTrue(state["launch"]["userAgent"].startswith("Mozilla/5.0 "))
                self.assertEqual(
                    state["launch"]["optionKeys"],
                    [
                        "args",
                        "executablePath",
                        "headless",
                        "ignoreDefaultArgs",
                        "timeout",
                        "userAgent",
                    ],
                )
                self.assertEqual(result["cleanup_state"], "context_closed")
                self.assertEqual(state["close_count"], 1)
                self.assertEqual(state["goto_count"], 1)

    def test_unknown_challenge_and_genuine_logout_are_distinct(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        cases = (
            (500, True, SESSION_EMAIL, True, "ChatGPT", "unknown", 500),
            (0, False, "", False, "ChatGPT", "unknown", None),
            (403, False, "", False, "Just a moment...", "challenge", 403),
            (200, True, "", False, "ChatGPT", "logged_out", 200),
        )
        for (
            status,
            is_json,
            email,
            composer,
            title,
            want_status,
            endpoint_status,
        ) in cases:
            with self.subTest(status=status, want_status=want_status):
                self._install_fake_playwright(
                    status=status,
                    is_json=is_json,
                    email=email,
                    composer_available=composer,
                    title=title,
                )
                proc = self._run_probe(expected)

                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = self._result(proc.stdout)
                self.assertIsNotNone(result, proc.stdout)
                self.assertEqual(result["status"], want_status)
                self.assertEqual(result["endpoint_status"], endpoint_status)
                self.assertIsNone(result["identity_match"])

    def test_locked_profile_is_unavailable_without_launch_or_lock_cleanup(self):
        lock = self.profile / "SingletonLock"
        lock.symlink_to("unknown-host-12345")
        before = sorted(path.name for path in self.profile.iterdir())
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()

        proc = self._run_probe(expected)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = self._result(proc.stdout)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["endpoint_status"])
        self.assertIsNone(result["identity_match"])
        self.assertFalse(self.state_path.exists())
        self.assertTrue(lock.is_symlink())
        self.assertEqual(sorted(path.name for path in self.profile.iterdir()), before)

    def test_existing_profile_launch_options_remain_unchanged(self):
        proc = subprocess.run(
            [str(DOT_SH), "--account", "fixture", "existing-profile-only"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = self._state()
        self.assertEqual(
            state["launch"]["optionKeys"],
            ["args", "executablePath", "headless", "ignoreDefaultArgs", "userAgent"],
        )

    def test_context_close_failure_falls_back_to_verified_browser_close(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(close_fails=True)

        proc = self._run_probe(expected)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = self._result(proc.stdout)
        self.assertEqual(result["status"], "authenticated")
        self.assertEqual(result["endpoint_status"], 200)
        self.assertTrue(result["identity_match"])
        self.assertTrue(result["composer_available"])
        self.assertEqual(result["cleanup_state"], "browser_disconnected")
        state = self._state()
        self.assertEqual(state["close_count"], 1)
        self.assertEqual(state["browser_close_count"], 1)

    def test_hung_context_close_uses_browser_close_and_verifies_disconnect(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(close_hangs=True)
        self._install_fast_probe_timeout()
        proc = self._run_probe(expected)
        result = self._result(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["cleanup_state"], "browser_disconnected")
        self.assertEqual(result["status"], "authenticated")
        state = self._state()
        self.assertEqual(state["close_count"], 1)
        self.assertEqual(state["browser_close_count"], 1)

    def test_unverifiable_cleanup_is_reported_unavailable(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(close_hangs=True, browser_missing=True)
        self._install_fast_probe_timeout()
        proc = self._run_probe(expected)
        result = self._result(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["cleanup_state"], "unresolved")
        self.assertIsNone(result["identity_match"])
        self.assertEqual(self._state()["browser_close_count"], 0)

    def test_late_launch_is_bounded_by_playwright_and_never_detaches_context(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(hang_launch=True)
        self._install_fast_probe_timeout()
        proc = self._run_probe(expected)
        result = self._result(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["cleanup_state"], "unresolved")
        state = self._state()
        self.assertIsInstance(state["launch_timeout"], int)
        self.assertGreater(state["launch_timeout"], 0)
        self.assertTrue(state["launch_timeout_fired"])
        self.assertFalse(state["late_launch_resolved"])
        self.assertEqual(state["close_count"], 0)

    def _install_fast_probe_timeout(self):
        clamp = self.root / "fast-timeout.cjs"
        clamp.write_text(
            "const original = global.setTimeout; "
            "global.setTimeout = (fn, ms, ...args) => original("
            "fn, ms >= 1000 ? 40 : ms, ...args);\n",
            encoding="utf-8",
        )
        self.env["NODE_OPTIONS"] = f"--require {clamp}"

    def test_probe_does_not_seed_or_read_cookies_or_mutate_composer(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        cookies = self.profile / "Default" / "Network" / "Cookies"
        cookies.parent.mkdir(parents=True)
        cookies.write_bytes(b"fixture cookie bytes")
        target_mtime = cookies.stat().st_mtime - 10
        os.utime(cookies, (target_mtime, target_mtime))
        source_profile = (
            self.home
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Default"
        )
        source_cookies = source_profile / "Network" / "Cookies"
        source_cookies.parent.mkdir(parents=True)
        source_cookies.write_bytes(b"newer fixture cookie bytes")
        local_state = source_profile.parent / "Local State"
        local_state.write_text(
            json.dumps(
                {
                    "profile": {
                        "info_cache": {
                            "Default": {
                                "email": SESSION_EMAIL,
                                "name": "fixture",
                                "hosted_domain": "no_hosted_domain",
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        audit = self.root / "profile-access-attempt.txt"
        preload = self.root / "audit-profile-access.cjs"
        preload.write_text(
            """const fs = require('node:fs');
const audit = __AUDIT__;
const readFileSync = fs.readFileSync.bind(fs);
const copyFileSync = fs.copyFileSync.bind(fs);
const note = kind => fs.appendFileSync(audit, kind + '\\n');
fs.readFileSync = (file, ...args) => {
  if (String(file).includes('Cookies') || String(file).includes('Local State')) {
    note('read:' + (String(file).includes('Local State') ? 'local-state' : 'cookies'));
    throw new Error('profile data read blocked');
  }
  return readFileSync(file, ...args);
};
fs.copyFileSync = (source, destination, ...args) => {
  const files = String(source) + String(destination);
  if (files.includes('Cookies') || files.includes('Local State')) {
    note('copy');
    throw new Error('profile data copy blocked');
  }
  return copyFileSync(source, destination, ...args);
};
""".replace("__AUDIT__", json.dumps(str(audit))),
            encoding="utf-8",
        )
        self.env["NODE_OPTIONS"] = f"--require {preload}"
        before = sorted(
            str(path.relative_to(self.profile)) for path in self.profile.rglob("*")
        )

        proc = self._run_probe(expected)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = self._result(proc.stdout)
        self.assertEqual(result["status"], "authenticated")
        self.assertEqual(result["endpoint_status"], 200)
        self.assertEqual(result["identity_match"], True)
        self.assertFalse(
            audit.exists(), audit.read_text(encoding="utf-8") if audit.exists() else ""
        )
        after = sorted(
            str(path.relative_to(self.profile)) for path in self.profile.rglob("*")
        )
        self.assertEqual(after, before)
        state = self._state()
        self.assertEqual(state["composer_reads"], 0)
        self.assertEqual(state["composer_mutations"], 0)
        self.assertGreater(state["composer_count"], 0)

    def test_probe_requires_an_explicit_lowercase_sha256_digest(self):
        for digest in (None, "not-a-digest", "A" * 64):
            with self.subTest(digest=digest):
                proc = self._run_probe(digest)
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertIn("usage:", proc.stderr.lower())
                self.assertFalse(self.state_path.exists())

    def test_malformed_or_unsupported_session_bodies_remain_unknown(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        for body in ("[]", '"signed-in"', "null", '{"user":false}', '{"user":{}}'):
            with self.subTest(body=body):
                self._install_fake_playwright(raw_body=body, composer_available=False)
                proc = self._run_probe(expected)
                result = self._result(proc.stdout)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["identity_match"])

    def test_hidden_composer_does_not_block_logged_out_classification(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(
            raw_body='{"user":null}', composer_available=True, composer_visible=False
        )
        proc = self._run_probe(expected)
        result = self._result(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["status"], "logged_out")
        self.assertFalse(result["composer_available"])

    def test_hung_session_evaluate_is_bounded_and_closes_context(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(hang_evaluate=True)
        self._install_fast_probe_timeout()
        proc = self._run_probe(expected)
        result = self._result(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(self._state()["close_count"], 1)

    def test_success_finishing_during_delayed_cleanup_cannot_override_timeout(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(
            delay_composer_count_ms=60,
            close_delay_ms=80,
        )
        self._install_fast_probe_timeout()

        proc = self._run_probe(expected)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = self._result(proc.stdout)
        self.assertIsNotNone(result, proc.stdout)
        self.assertTrue(self._state()["composer_count_resolved"])
        self.assertTrue(self._state()["composer_visibility_read"])
        self.assertEqual(result["cleanup_state"], "browser_disconnected")
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["identity_match"])
        self.assertIsNone(result["composer_available"])
        self.assertIsNone(result["endpoint_status"])

    def test_hung_session_fetch_is_aborted_and_closes_context(self):
        expected = hashlib.sha256(SESSION_EMAIL.encode("utf-8")).hexdigest()
        self._install_fake_playwright(hang_fetch=True)
        self._install_fast_probe_timeout()
        proc = self._run_probe(expected)
        result = self._result(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["status"], "unknown")
        state = self._state()
        self.assertTrue(state["fetch_abort_seen"])
        self.assertEqual(state["close_count"], 1)


if __name__ == "__main__":
    unittest.main()
