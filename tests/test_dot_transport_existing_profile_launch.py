"""Exercise the Dot existing-profile launcher without starting a browser."""

import json
import os
import selectors
import shlex
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot_chrome.mjs"
DOT_SH = REPO_ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot.sh"
NVM_NODE22 = Path.home() / ".nvm" / "versions" / "node" / "v22.22.0" / "bin" / "node"
NODE22 = Path(os.environ.get("DOT_NODE") or (
    str(NVM_NODE22) if NVM_NODE22.is_file() else shutil.which("node") or "node"
))


class ExistingProfileLaunchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dot-launch-test-", dir="/tmp")
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
        modules = self.root / "node_modules" / "playwright"
        modules.mkdir(parents=True)
        (self.root / "require-anchor.cjs").touch()
        self.launch_record = self.root / "launch-record.json"
        (modules / "index.js").write_text(
            """
const fs = require("node:fs");
const recordPath = __LOG_PATH__;
exports.chromium = {
  async launchPersistentContext(profileDir, options) {
    fs.writeFileSync(recordPath, JSON.stringify({
      profileDir,
      executablePath: options.executablePath,
      headless: options.headless,
      args: options.args,
      ignoreDefaultArgs: options.ignoreDefaultArgs,
    }));
    return { async close() {
      if (process.env.DOT_TEST_CLOSE_FAIL === "1") throw new Error("fixture close failure");
    } };
  },
};
""".replace("__LOG_PATH__", json.dumps(str(self.launch_record))),
            encoding="utf-8",
        )
        self.env = dict(os.environ)
        self.env.update(
            {
                "HOME": str(self.home),
                "DOT_ACCOUNT": "fixture",
                "DOT_CONFIG_FILE": str(self.config),
                "DOT_CHROME_USER_DATA": str(self.profile),
                "DOT_CHROME_BIN": str(self.chrome),
                "DOT_PW_MODULES": str(self.root / "require-anchor.cjs"),
                "DOT_NODE": str(NODE22),
                "DOT_NO_REMOTE": "1",
            }
        )

    def tearDown(self):
        self.temp.cleanup()

    def _run(self, path=None, env=None):
        command = [str(NODE22), str(SCRIPT), "existing-profile-only"]
        if path is not None:
            command[0] = str(path)
        return subprocess.run(
            command,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def _run_dot_sh(self, env=None):
        return subprocess.run(
            [str(DOT_SH), "existing-profile-only"],
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )

    def _install_fake_send_playwright(self, initial_composer=""):
        state_path = self.root / "prepared-send-state.json"
        external_composer_path = self.root / "external-composer.txt"
        state_path.unlink(missing_ok=True)
        external_composer_path.unlink(missing_ok=True)
        self.external_composer_path = external_composer_path
        modules = self.root / "node_modules" / "playwright"
        script = r'''const fs = require("node:fs");
const statePath = __STATE_PATH__;
const externalComposerPath = __EXTERNAL_COMPOSER_PATH__;
const state = {composer: __INITIAL_COMPOSER__, clicked: false, userMessages: []};
function locator(selector) {
  if (selector.includes("data-message-author-role=user")) {
    return {async allInnerTexts() { return state.userMessages; }};
  }
  return {
    async count() { return 1; },
    first() { return this; },
    async innerText() {
      if (fs.existsSync(externalComposerPath)) return fs.readFileSync(externalComposerPath, "utf8");
      return state.composer;
    },
    async focus() {},
    async click() {},
  };
}
const page = {
  async goto() {},
  async title() { return "ChatGPT"; },
  locator,
  async evaluate(fn) {
    if (fn.toString().includes("/api/auth/session")) {
      return {status: 200, hasUser: true, isJson: true};
    }
    if (fn.toString().includes("usage limit")) return "";
    return "Fixture conversation";
  },
  async click(selector) {
    if (selector.includes("send-button")) {
      state.clicked = true;
      state.userMessages.push(state.composer);
      state.composer = "";
    }
  },
  keyboard: {
    selected: false,
    async press(key) {
      if (key.endsWith("+A")) this.selected = true;
      else if (key === "Backspace" && this.selected) state.composer = "";
    },
    async insertText(text) { state.composer += text; },
  },
};
exports.chromium = {
  async launchPersistentContext() {
    return {
      async newPage() { return page; },
      async close() { fs.writeFileSync(statePath, JSON.stringify(state)); },
    };
  },
};
'''.replace("__STATE_PATH__", json.dumps(str(state_path)))
        script = script.replace(
            "__EXTERNAL_COMPOSER_PATH__", json.dumps(str(external_composer_path))
        )
        script = script.replace("__INITIAL_COMPOSER__", json.dumps(initial_composer))
        (modules / "index.js").write_text(script, encoding="utf-8")
        return state_path

    def _run_prepared_send(self, control):
        message_path = self.root / "prepared-message.txt"
        message_path.write_text("Coordinator-owned fixture message", encoding="utf-8")
        state_path = self._install_fake_send_playwright()
        env = dict(self.env, DOT_PREPARED="1")
        proc = subprocess.Popen(
            [str(NODE22), str(SCRIPT), "send-prepared", str(message_path)],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        output = bytearray()
        nonce = None
        deadline = time.monotonic() + 30
        try:
            while nonce is None:
                remaining = deadline - time.monotonic()
                self.assertGreater(remaining, 0, "Node did not prepare the message")
                self.assertTrue(selector.select(remaining), "Node did not prepare the message")
                output.extend(os.read(proc.stdout.fileno(), 4096))
                for line in output.splitlines():
                    if line.startswith(b"prepared "):
                        tokens = line.decode("utf-8").split()
                        if len(tokens) == 2:
                            nonce = tokens[1]
                            break
            proc.stdin.write((control(nonce) + "\n").encode("utf-8"))
            proc.stdin.flush()
            rest, stderr = proc.communicate(timeout=10)
            output.extend(rest)
            return proc.returncode, output.decode("utf-8"), stderr.decode("utf-8"), json.loads(state_path.read_text())
        finally:
            selector.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    def test_prepared_send_requires_matching_nonce_and_clears_only_its_draft(self):
        for control in (lambda nonce: "commit", lambda nonce: "commit " + "0" * 32):
            with self.subTest(control=control("ignored")):
                rc, stdout, stderr, state = self._run_prepared_send(control)
                self.assertEqual(rc, 0, stderr)
                self.assertNotIn("DOT_SENT_VERIFIED", stdout)
                self.assertFalse(state["clicked"])
                self.assertEqual(state["composer"], "")

    def test_prepared_send_keeps_existing_drafts_untouched(self):
        message = "Coordinator-owned fixture message"
        drafts = (
            ("near_match", "Coordinator-owned fixture messag", [], True),
            ("clear_flag", "Unrelated human draft", [], True),
            ("already_sent", message, [message], False),
        )
        for case, draft, prior_messages, clear_flag in drafts:
            with self.subTest(case=case):
                state_path = self._install_fake_send_playwright(draft)
                (self.root / "node_modules" / "playwright" / "index.js").write_text(
                    (self.root / "node_modules" / "playwright" / "index.js")
                    .read_text(encoding="utf-8")
                    .replace("userMessages: []", f"userMessages: {json.dumps(prior_messages)}"),
                    encoding="utf-8",
                )
                message_path = self.root / "prepared-message-with-draft.txt"
                message_path.write_text(message, encoding="utf-8")
                env = dict(self.env, DOT_PREPARED="1")
                if clear_flag:
                    env["DOT_CLEAR_DRAFT"] = "1"
                proc = subprocess.run(
                    [str(NODE22), str(SCRIPT), "send-prepared", str(message_path)],
                    env=env, capture_output=True, text=True, timeout=30, check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(
                    "DOT_PREPARED_ABORTED reason=composer_not_empty", proc.stdout
                )
                self.assertNotIn(draft[:20], proc.stdout)
                state = json.loads(state_path.read_text())
                self.assertEqual(state["composer"], draft)
                self.assertFalse(state["clicked"])

    def test_prepared_send_does_not_click_after_composer_changes(self):
        def alter_then_commit(nonce):
            self.external_composer_path.write_text("User edited this draft", encoding="utf-8")
            return "commit " + nonce

        rc, stdout, stderr, state = self._run_prepared_send(alter_then_commit)
        self.assertEqual(rc, 0, stderr)
        self.assertNotIn("DOT_SENT_VERIFIED", stdout)
        self.assertFalse(state["clicked"])
        self.assertEqual(state["composer"], "Coordinator-owned fixture message")
        self.assertEqual(
            self.external_composer_path.read_text(encoding="utf-8"),
            "User edited this draft",
        )

    def test_prepared_send_does_not_click_after_whitespace_change(self):
        edited_composers = (
            "Coordinator-owned fixture  message",
            " Coordinator-owned fixture message ",
        )
        for edited_composer in edited_composers:
            with self.subTest(edited_composer=edited_composer):
                def alter_spacing_then_commit(nonce):
                    self.external_composer_path.write_text(
                        edited_composer, encoding="utf-8"
                    )
                    return "commit " + nonce

                rc, stdout, stderr, state = self._run_prepared_send(
                    alter_spacing_then_commit
                )
                self.assertEqual(rc, 0, stderr)
                self.assertIn("DOT_PREPARED_ABORTED reason=composer_changed", stdout)
                self.assertNotIn("DOT_SENT_VERIFIED", stdout)
                self.assertFalse(state["clicked"])
                self.assertEqual(state["composer"], "Coordinator-owned fixture message")
                self.assertEqual(
                    self.external_composer_path.read_text(encoding="utf-8"),
                    edited_composer,
                )

    def test_prepared_send_preserves_whitespace_changes_on_abort(self):
        edited_composers = (
            "Coordinator-owned fixture  message",
            " Coordinator-owned fixture message ",
        )
        for edited_composer in edited_composers:
            with self.subTest(edited_composer=edited_composer):
                def alter_spacing_then_abort(nonce):
                    self.external_composer_path.write_text(
                        edited_composer, encoding="utf-8"
                    )
                    return "abort " + nonce

                rc, stdout, stderr, state = self._run_prepared_send(
                    alter_spacing_then_abort
                )
                self.assertEqual(rc, 0, stderr)
                self.assertIn("aborted ", stdout)
                self.assertNotIn("DOT_SENT_VERIFIED", stdout)
                self.assertFalse(state["clicked"])
                self.assertEqual(state["composer"], "Coordinator-owned fixture message")
                self.assertEqual(
                    self.external_composer_path.read_text(encoding="utf-8"),
                    edited_composer,
                )

    def test_prepared_send_commits_only_matching_nonce(self):
        rc, stdout, stderr, state = self._run_prepared_send(
            lambda nonce: "commit " + nonce
        )
        self.assertEqual(rc, 0, stderr)
        self.assertIn("DOT_SENT_VERIFIED", stdout)
        self.assertTrue(state["clicked"])
        self.assertEqual(state["userMessages"], ["Coordinator-owned fixture message"])
        self.assertEqual(state["composer"], "")

    @staticmethod
    def _result(stdout):
        for line in stdout.splitlines():
            if line.startswith("DOT_PROFILE_LAUNCH_RESULT "):
                return json.loads(line.removeprefix("DOT_PROFILE_LAUNCH_RESULT "))
        return None

    def test_launch_uses_existing_profile_without_seeding(self):
        self.assertTrue(NODE22.is_file(), f"Node 22 not found: {NODE22}")
        before = sorted(str(path.relative_to(self.profile)) for path in self.profile.rglob("*"))

        proc = self._run()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        call = json.loads(self.launch_record.read_text(encoding="utf-8"))
        self.assertEqual(call["profileDir"], str(self.profile))
        self.assertEqual(call["executablePath"], str(self.chrome))
        self.assertIsInstance(call["args"], list)
        self.assertIsInstance(call["ignoreDefaultArgs"], list)
        self.assertFalse((self.profile / "Default").exists())
        after = sorted(str(path.relative_to(self.profile)) for path in self.profile.rglob("*"))
        self.assertEqual(after, before)
        result = self._result(proc.stdout)
        self.assertEqual(
            result,
            {
                "schema_version": 1,
                "launch_state": "started",
                "browser_disposition": "spawned",
                "cleanup_state": "context_close_returned",
            },
        )
        self.assertNotIn(str(self.profile), json.dumps(result))

    def test_missing_profile_blocks_launch_without_creating_it(self):
        self.profile.rmdir()

        proc = self._run()

        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_missing",
            },
        )
        self.assertFalse(self.profile.exists())
        self.assertFalse(self.launch_record.exists())

    def test_context_close_failure_is_not_reported_as_success(self):
        env = dict(self.env)
        env["DOT_TEST_CLOSE_FAIL"] = "1"

        proc = self._run(env=env)

        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "context_cleanup_unverified",
            },
        )

    def test_dot_sh_exposes_redacted_local_mode_without_fallback_banner(self):
        proc = self._run_dot_sh()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNotNone(self._result(proc.stdout))
        self.assertNotIn(str(self.profile), proc.stdout + proc.stderr)
        self.assertNotIn("account=", proc.stderr)

    def test_present_unknown_lock_is_preserved_and_blocks_launch(self):
        lock = self.profile / "SingletonLock"
        lock.symlink_to("unknown-host-12345")

        proc = self._run()

        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {"schema_version": 1, "launch_state": "unavailable", "diagnostic": "profile_lock_present"},
        )
        self.assertFalse(self.launch_record.exists())
        self.assertTrue(lock.is_symlink())

    def test_process_query_failure_blocks_launch(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        fake_ps.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
        fake_ps.chmod(fake_ps.stat().st_mode | stat.S_IXUSR)
        env = dict(self.env)
        env["PATH"] = f"{bin_dir}{os.pathsep}{self.env['PATH']}"

        proc = self._run(env=env)

        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {"schema_version": 1, "launch_state": "unavailable", "diagnostic": "profile_owner_unknown"},
        )
        self.assertFalse(self.launch_record.exists())

    def test_detected_profile_process_blocks_launch(self):
        bin_dir = self.root / "active-bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        fake_ps.write_text(
            "#!/bin/sh\nprintf '%s\\n' "
            + shlex.quote(f"chrome --user-data-dir={self.profile}")
            + "\n",
            encoding="utf-8",
        )
        fake_ps.chmod(fake_ps.stat().st_mode | stat.S_IXUSR)
        env = dict(self.env)
        env["PATH"] = f"{bin_dir}{os.pathsep}{self.env['PATH']}"

        proc = self._run(env=env)

        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {"schema_version": 1, "launch_state": "unavailable", "diagnostic": "profile_owner_present"},
        )
        self.assertFalse(self.launch_record.exists())

    def test_prepared_send_mode_blocks_when_profile_missing_without_seeding(self):
        self.profile.rmdir()
        msg_file = self.root / "msg.txt"
        msg_file.write_text("Hello dot", encoding="utf-8")
        env = dict(self.env)
        env["DOT_PREPARED"] = "1"
        proc = subprocess.run(
            [str(NODE22), str(SCRIPT), "send-prepared", str(msg_file)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_missing",
            },
        )
        self.assertFalse(self.profile.exists())

    def test_dot_sh_prepared_send_mode_blocks_when_lock_present(self):
        lock = self.profile / "SingletonLock"
        lock.symlink_to("unknown-host-12345")
        msg_file = self.root / "msg.txt"
        msg_file.write_text("Hello dot", encoding="utf-8")
        env = dict(self.env)
        env["DOT_PREPARED"] = "1"
        proc = subprocess.run(
            [str(DOT_SH), "send-once", str(msg_file)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 10, proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_lock_present",
            },
        )
        self.assertTrue(lock.is_symlink())


if __name__ == "__main__":
    unittest.main()
