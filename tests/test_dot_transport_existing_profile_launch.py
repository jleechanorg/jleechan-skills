"""Exercise the Dot existing-profile launcher without starting a browser."""

import hashlib
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
        self.env.pop("BASH_ENV", None)
        self.env.pop("ENV", None)
        self.env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
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
        command_env = dict(env or self.env)
        command_env.pop("BASH_ENV", None)
        command_env.pop("ENV", None)
        command_env["PATH"] = self.env["PATH"]
        return subprocess.run(
            [str(DOT_SH), "existing-profile-only"],
            env=command_env,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )

    def _install_fake_send_playwright(self, initial_composer="", *, usage_limit=False):
        state_path = self.root / "prepared-send-state.json"
        external_composer_path = self.root / "external-composer.txt"
        state_path.unlink(missing_ok=True)
        external_composer_path.unlink(missing_ok=True)
        self.external_composer_path = external_composer_path
        modules = self.root / "node_modules" / "playwright"
        script = r'''const fs = require("node:fs");
const statePath = __STATE_PATH__;
const externalComposerPath = __EXTERNAL_COMPOSER_PATH__;
const state = {composer: __INITIAL_COMPOSER__, clicked: false, userMessages: [], replyClicked: false, replyOpened: false, scrolls: 0, focusClicks: 0};
const replyParent = process.env.DOT_TEST_REPLY_PARENT;
let urlReads = 0, historyReads = 0;
const history = process.env.DOT_TEST_HISTORY;
const changeAt = process.env.DOT_TEST_CHANGE_AT;
const hasOlderRows = () => state.scrolls > 0 && ["grow", "hydrate"].includes(history) && historyReads > 2;
const parentIsLoaded = () => !history || hasOlderRows() || (history === "deep" && state.scrolls >= 7);
const replyPanel = {
  async count() { return Number(state.replyOpened); },
  async isVisible() { return state.replyOpened; },
  async waitFor() { if (!state.replyOpened) throw Error("Reply panel never opened"); },
  locator(selector) {
    if (selector === ".message-list article.message-row[data-message-id]") return {
      first() { return this; },
      async count() { return 1; },
      async getAttribute() {
        if ((process.env.DOT_TEST_REPLY_CHANGED === "focus" && state.replyFocused) ||
            (process.env.DOT_TEST_REPLY_CHANGED === "commit" && globalThis.fixturePrepared) ||
            (process.env.DOT_TEST_REPLY_CHANGED === "receipt" && state.replyClicked)) return "other-parent";
        return replyParent;
      },
    };
    if (selector === ".message-list article.self .message-text") return {
      async allInnerTexts() { return state.userMessages; },
    };
    if (selector.startsWith(".reply-chain-composer [contenteditable=true]")) {
      return {...locator("fixture scoped composer"), async click() { state.replyFocused = true; }};
    }
    if (selector === ".reply-chain-composer") return {
      getByRole(role, options) {
        if (role !== "button" || options.name !== "Send" || !options.exact) throw Error("Unexpected reply control");
        return {
          async count() { return 1; },
          async isEnabled() {
            if (process.env.DOT_TEST_REPLY_CHANGED === "timeout") globalThis.advanceClock(120000);
            return true;
          },
          async click() {
            state.replyClicked = true;
            state.userMessages.push(state.composer);
            state.composer = "";
          },
        };
      },
    };
    throw Error("Unscoped reply read: " + selector);
  },
};
function locator(selector) {
  if (selector === '.reply-chain-container[aria-label="Replies"]') return replyPanel;
  if (selector === '.messages-scroll:visible') return {
    async count() { return 1; },
    async waitFor() {},
    async evaluate(scroll, url) {
      const positions = [];
      const fixture = {isConnected: true, ownerDocument: {URL: process.env.DOT_TEST_RESOLVED_URL},
        set scrollTop(value) { positions.push(value); }};
      if (!await scroll(fixture, url) || positions.join(",") !== "35,0") throw Error("Unexpected history scroll");
      state.scrolls++;
      if (history === "growing_missing") globalThis.advanceClock(5000);
      return true;
    },
    locator(selector) {
      if (selector === 'article.message-row[data-message-id]') return {
        async count() {
          historyReads++;
          if (["deep", "growing_missing"].includes(history)) return 52 + state.scrolls * 8;
          if (history === "hydrate" && historyReads <= 2) return 0;
          return hasOlderRows() ? 84 : 52;
        },
      };
      return locator(selector);
    },
  };
  if (selector.startsWith('article.message-row[data-message-id=')) return {
    filter() { return this; },
    last() { return this; },
    getByRole() {
      return {
        async count() {
          return Number(parentIsLoaded() &&
            selector === `article.message-row[data-message-id="${replyParent}"]`);
        },
        async click() { state.replyOpened = true; },
      };
    },
  };
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
    async focus() { if (changeAt === "cleanup_focus") state.routeChanged = true; },
    async isVisible() {
      if (changeAt === "commit_ready" && globalThis.fixturePrepared) state.routeChanged = true;
      return process.env.DOT_TEST_BUSY === "1";
    },
    async click() {},
  };
}
let activeEditor;
function runExactFixture(fn, binding) {
  const { action, parent } = binding;
  if (action === "fill" && changeAt === "late_fill") state.composer = "Other draft";
  if (action === "clear" && changeAt === "cleanup_focus") activeEditor = {};
  if (action === "submit") {
    if (changeAt === "commit_ready") state.routeChanged = true;
    if (changeAt === "late_submit") state.composer = "Other draft";
    if (process.env.DOT_TEST_REPLY_CHANGED === "timeout") globalThis.advanceClock(120000);
  }
  const visible = () => [{}];
  const editor = {
    isContentEditable: true, get innerText() { return state.composer; },
    getClientRects: visible, contains(node) { return node === "composer"; },
    focus() {
      activeEditor = "composer";
      if (parent) state.replyFocused = true;
      else state.focusClicks++;
      if (changeAt === "after_focus") state.routeChanged = true;
    },
  };
  const send = {getClientRects: visible, matches() { return false; }, click() {
    if (parent) state.replyClicked = true;
    else state.clicked = true;
    state.userMessages.push(state.composer);
    state.composer = "";
    if (changeAt === "submit_error") throw Error("execution context lost after click");
  }};
  const lists = selector => {
    if (selector === binding.composerSelector) return [editor];
    if (selector === binding.userMessageSelector) return state.userMessages.map(text => ({innerText: text}));
    if (selector.includes("stop-button")) return process.env.DOT_TEST_BUSY ? [{getClientRects: visible}] : [];
    if (selector.includes('aria-label="Send"')) return [send];
    throw Error("Unexpected exact selector " + selector);
  };
  const panel = {getClientRects: visible, querySelectorAll: lists, querySelector() {
    const changed = process.env.DOT_TEST_REPLY_CHANGED;
    const moved = (changed === "focus" && state.replyFocused) ||
      (changed === "commit" && globalThis.fixturePrepared) || (changed === "receipt" && state.replyClicked);
    return {dataset: {messageId: moved ? "other-parent" : replyParent}};
  }};
  globalThis.getComputedStyle = element => ({
    visibility: element === send && changeAt === "hidden_submit" ? "hidden" : "visible",
    pointerEvents: "auto",
  });
  globalThis.location = { origin: "https://chatgpt.com", get href() {
    return action === "observe" && state.clicked && changeAt === "receipt_transient"
      ? "https://chatgpt.com/c/00000000-0000-4000-8000-000000000002" : page.url();
  }};
  globalThis.window = {getSelection: () => ({removeAllRanges() {}, addRange() {
    if (changeAt === "cleanup_selection") state.routeChanged = true;
  }})};
  globalThis.document = {
    get activeElement() { return activeEditor; },
    createRange() { return {selectNodeContents() {}}; },
    execCommand(op, _, value) {
      if (op === "delete" && changeAt === "cleanup_persistence") {
        state.persistedComposer = state.composer;
        setTimeout(() => { state.persistedComposer = ""; }, 700);
      }
      if (op === "delete" && changeAt === "cleanup_scope_changed") {
        setTimeout(() => { state.routeChanged = true; }, 700);
      }
      state.composer = op === "insertText" ? value : "";
      return true;
    },
    querySelectorAll(selector) {
      return selector.includes("reply-chain-container") ? [panel] : lists(selector);
    },
  };
  try { return fn(binding); }
  finally { delete globalThis.document; delete globalThis.location; delete globalThis.window; delete globalThis.getComputedStyle; }
}
const page = {
  async goto() {},
  url() {
    if (state.routeChanged) return "https://chatgpt.com/c/00000000-0000-4000-8000-000000000002";
    if (globalThis.fixturePrepared && process.env.DOT_TEST_POST_PREPARED_URL) return process.env.DOT_TEST_POST_PREPARED_URL;
    if (state.clicked && process.env.DOT_TEST_POST_SEND_URL) return process.env.DOT_TEST_POST_SEND_URL;
    if (urlReads++ === 0 && process.env.DOT_TEST_DOT_HOME) return "https://chatgpt.com/dots/home";
    return process.env.DOT_TEST_RESOLVED_URL || process.env.DOT_URL;
  },
  async title() { return "ChatGPT"; },
  locator,
  getByRole() { return {}; },
  async evaluate(fn, binding) {
    if (binding?.action) return runExactFixture(fn, binding);
    if (fn.toString().includes("/api/auth/session")) {
      return {status: 200, hasUser: true, isJson: true, email: "fixture@example.invalid"};
    }
    if (fn.toString().includes("usage limit")) {
      if (changeAt === "before_focus") state.routeChanged = true;
      return __USAGE_LIMIT_ALERT__;
    }
    return "Fixture conversation";
  },
  async click(selector) {
    if (selector.includes("send-button")) {
      state.clicked = true;
      if (process.env.DOT_TEST_HANG_SEND_MS) {
        globalThis.advanceClock(Number(process.env.DOT_TEST_HANG_SEND_MS));
        await new Promise(() => {});
      }
      state.userMessages.push(state.composer);
      state.composer = "";
    } else {
      state.focusClicks++;
      if (changeAt === "after_focus") state.routeChanged = true;
    }
  },
  keyboard: {
    selected: false,
    async press(key) {
      if (key.endsWith("+A")) {
        this.selected = true;
        if (changeAt === "cleanup_selection") state.routeChanged = true;
      } else if (key === "Backspace" && this.selected) state.composer = "";
    },
    async insertText(text) {
      state.composer += process.env.DOT_TEST_MISMATCH_COMPOSER === "1" ? "different fixture" : text;
    },
  },
};
exports.chromium = {
  async launchPersistentContext() {
    if (process.env.DOT_TEST_HANG_LAUNCH === "1") {
      setImmediate(() => globalThis.advanceClock(120000));
      await new Promise(() => {});
    }
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
        alert = "synthetic usage limit" if usage_limit else ""
        script = script.replace("__USAGE_LIMIT_ALERT__", json.dumps(alert))
        (modules / "index.js").write_text(script, encoding="utf-8")
        return state_path

    def _run_clocked_prepared(self, *, decision="commit", advance_ms=120000,
                              initial_composer="", usage_limit=False,
                              mismatched_composer=False, missing_profile=False,
                              hang_launch=False, hang_after_commit=False,
                              send_advance_ms=120000, exact=None, reply=None, copy_only=False):
        state_path = self._install_fake_send_playwright(initial_composer, usage_limit=usage_limit)
        if missing_profile:
            self.profile.rmdir()
        message_path = self.root / "clocked-message.txt"
        message_path.write_text("Synthetic proof")
        preload = self.root / "clock.cjs"
        preload.write_text(r'''const originalSetTimeout = global.setTimeout;
const originalClearTimeout = global.clearTimeout;
let now = 1000000;
const timers = new Map();
Date.now = () => now;
global.setTimeout = (callback, ms, ...args) => {
  if (ms < 10000) return originalSetTimeout(() => { now += ms; callback(...args); }, 0);
  const id = {};
  timers.set(id, {at: now + ms, callback: () => callback(...args)});
  return id;
};
global.clearTimeout = (id) => { timers.delete(id); originalClearTimeout(id); };
global.advanceClock = (ms) => {
  now += ms;
  for (const [id, timer] of [...timers]) {
    if (timer.at <= now) { timers.delete(id); timer.callback(); }
  }
};
const write = process.stdout.write.bind(process.stdout);
process.stdout.write = (chunk, ...args) => {
  const result = write(chunk, ...args);
  const match = /^prepared(?:-exact)? ([a-f0-9]{32})\n$/.exec(String(chunk));
  if (match) setImmediate(() => {
    globalThis.fixturePrepared = true;
    global.advanceClock(__ADVANCE__);
    setImmediate(() => process.stdin.emit('data', Buffer.from('__DECISION__ ' + match[1] + '\n')));
  });
  return result;
};
'''.replace("__ADVANCE__", str(advance_ms)).replace("__DECISION__", decision))
        entry = SCRIPT
        if copy_only:
            entry = self.root / SCRIPT.name
            shutil.copyfile(SCRIPT, entry)
        command = [str(NODE22), "--require", str(preload), str(entry), "send-prepared", str(message_path)]
        env = dict(
            self.env, DOT_PREPARED="1",
            DOT_TEST_MISMATCH_COMPOSER="1" if mismatched_composer else "",
            DOT_TEST_HANG_LAUNCH="1" if hang_launch else "",
            DOT_TEST_HANG_SEND_MS=str(send_advance_ms) if hang_after_commit else "",
        )
        if exact is not None:
            exact = dict(exact)
            email = exact.pop("expected_email", "fixture@example.invalid")
            command.extend(("--exact-destination", hashlib.sha256(email.encode()).hexdigest()))
            env.update(exact)
        if reply is not None:
            seat, target, parent, observations = reply
            config = json.loads(self.config.read_text())
            config["accounts"]["fixture"]["url"] = f"https://chatgpt.com/dots/{seat}"
            self.config.write_text(json.dumps(config))
            command.extend(("--exact-dot-reply", hashlib.sha256(b"fixture@example.invalid").hexdigest(),
                            target, parent, seat))
            env.update(DOT_TEST_RESOLVED_URL=target, DOT_TEST_REPLY_PARENT=parent)
            env.update(observations)
        with subprocess.Popen(command, env=env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as child:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                raise
            stdout, stderr = child.communicate()
            proc = subprocess.CompletedProcess(command, child.returncode, stdout, stderr)
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        return proc, state

    def test_exact_prepared_send_rejects_redirect_and_busy_destination(self):
        url = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000001"
        for flags, clicked in [
            ({}, True), ({"DOT_TEST_RESOLVED_URL": "https://chatgpt.com/"}, False),
            ({"DOT_TEST_BUSY": "1"}, False), ({"expected_email": "other@example.invalid"}, False),
        ]:
            with self.subTest(flags=flags):
                result, state = self._run_clocked_prepared(exact={"DOT_URL": url, **flags})
                self.assertEqual(state["clicked"], clicked)
                self.assertEqual("prepared-exact " in result.stdout, clicked)
                self.assertEqual("DOT_SENT_VERIFIED" in result.stdout, clicked)

    def test_private_chat_receipt_rejects_destination_switch_after_click(self):
        chat = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000001"
        other = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000002"
        result, state = self._run_clocked_prepared(exact={"DOT_URL": chat, "DOT_TEST_POST_SEND_URL": other})
        self.assertTrue(state["clicked"])
        self.assertEqual(state["userMessages"], ["Synthetic proof"])
        self.assertNotIn("DOT_SENT_VERIFIED", result.stdout)
        self.assertIn("DOT_SEND_UNVERIFIED", result.stdout)

    def test_private_chat_abort_clears_identical_draft_only_at_bound_destination(self):
        chat = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000001"
        other = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000002"
        for current, draft in ((chat, ""), (other, "Synthetic proof")):
            with self.subTest(current=current):
                result, state = self._run_clocked_prepared(
                    decision="abort", exact={"DOT_URL": chat, "DOT_TEST_POST_PREPARED_URL": current},
                )
                self.assertFalse(state["clicked"])
                self.assertIn("aborted ", result.stdout)
                self.assertEqual(state["composer"], draft)
                cleanup = "refused" if draft else "empty_in_context"
                self.assertIn(f"DOT_DRAFT_CLEANUP {cleanup}", result.stderr)

    def test_dot_reply_abort_waits_for_owned_draft_cleanup_before_close(self):
        seat = "00000000-0000-4000-8000-000000000001"
        target = "https://chatgpt.com/dots/00000000-0000-4000-8000-000000000002~" + "1" * 32
        parent = "~".join(("2" * 32, "2" * 32, "CalpicoMessage", "Sentinel_" + "3" * 32))
        cases = (("cleanup_persistence", "empty_in_context"), ("cleanup_scope_changed", "unverified"))
        for behavior, diagnostic in cases:
            with self.subTest(behavior=behavior):
                result, state = self._run_clocked_prepared(
                    decision="abort", reply=(seat, target, parent, {"DOT_TEST_CHANGE_AT": behavior}),
                )
                self.assertFalse(state["replyClicked"])
                self.assertEqual(state["composer"], "")
                if behavior == "cleanup_persistence":
                    self.assertEqual(state["persistedComposer"], "")
                self.assertRegex(result.stdout.splitlines()[-1], r"^aborted [0-9a-f]{32}$")
                self.assertIn(f"DOT_DRAFT_CLEANUP {diagnostic}", result.stderr)

    def test_private_chat_prepared_edits_stop_when_destination_changes(self):
        url = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000001"
        cases = [
            ("before_focus", "commit", 0, ""),
            ("after_focus", "commit", 1, ""),
            ("late_fill", "commit", 1, "Other draft"),
            ("late_submit", "commit", 1, "Other draft"),
            ("hidden_submit", "commit", 1, "Synthetic proof"),
            ("cleanup_focus", "abort", 1, "Synthetic proof"),
            ("cleanup_selection", "abort", 1, "Synthetic proof"),
            ("commit_ready", "commit", 1, "Synthetic proof"),
        ]
        for phase, decision, focus_clicks, draft in cases:
            with self.subTest(phase=phase):
                result, state = self._run_clocked_prepared(
                    decision=decision, exact={"DOT_URL": url, "DOT_TEST_CHANGE_AT": phase},
                )
                self.assertEqual(state["focusClicks"], focus_clicks)
                self.assertFalse(state["clicked"])
                self.assertEqual(state["composer"], draft)
                self.assertNotIn("DOT_SENT_VERIFIED", result.stdout)
                if phase in {"late_submit", "hidden_submit"}:
                    self.assertIn("aborted ", result.stdout)

    def test_private_chat_disconnect_after_click_remains_unverified(self):
        url = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000001"
        result, state = self._run_clocked_prepared(exact={"DOT_URL": url, "DOT_TEST_CHANGE_AT": "submit_error"})
        self.assertTrue(state["clicked"])
        self.assertIn("DOT_SEND_UNVERIFIED", result.stdout)
        self.assertNotIn("aborted ", result.stdout)

    def test_legacy_prepared_send_supports_a_standalone_entrypoint(self):
        result, state = self._run_clocked_prepared(copy_only=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(state["clicked"])
        self.assertIn("DOT_SENT_VERIFIED", result.stdout)

    def test_private_chat_receipt_cannot_use_an_intermediate_conversation(self):
        url = "https://chatgpt.com/c/00000000-0000-4000-8000-000000000001"
        result, state = self._run_clocked_prepared(exact={"DOT_URL": url, "DOT_TEST_CHANGE_AT": "receipt_transient"})
        self.assertTrue(state["clicked"])
        self.assertEqual(state["userMessages"], ["Synthetic proof"])
        self.assertNotIn("DOT_SENT_VERIFIED", result.stdout)

    def test_dot_reply_delivery_is_bound_to_the_parent_panel(self):
        seat = "00000000-0000-4000-8000-000000000001"
        target = "https://chatgpt.com/dots/00000000-0000-4000-8000-000000000002~" + "1" * 32
        parent = "~".join(("2" * 32, "2" * 32, "CalpicoMessage", "Sentinel_" + "3" * 32))
        cases = [
            ({}, True, True, True),
            ({"DOT_TEST_DOT_HOME": "1", "DOT_TEST_HISTORY": "grow"}, True, True, True),
            ({"DOT_TEST_HISTORY": "hydrate"}, True, True, True),
            ({"DOT_TEST_HISTORY": "deep"}, True, True, True),
            ({"DOT_TEST_HISTORY": "growing_missing"}, False, False, False),
            ({"DOT_TEST_HISTORY": "end"}, False, False, False),
            ({"DOT_TEST_REPLY_CHANGED": "focus"}, True, False, False),
            ({"DOT_TEST_REPLY_CHANGED": "commit"}, True, False, False),
            ({"DOT_TEST_CHANGE_AT": "late_submit"}, True, False, False),
            ({"DOT_TEST_CHANGE_AT": "hidden_submit"}, True, False, False),
            ({"DOT_TEST_CHANGE_AT": "submit_error"}, True, True, False),
            ({"DOT_TEST_CHANGE_AT": "late_fill"}, True, False, False),
            ({"DOT_TEST_REPLY_CHANGED": "timeout"}, True, False, False),
            ({"DOT_TEST_REPLY_CHANGED": "receipt"}, True, True, False),
            ({"DOT_TEST_RESOLVED_URL": "https://chatgpt.com/"}, False, False, False),
            ({"DOT_TEST_REPLY_PARENT": "absent-parent"}, False, False, False),
        ]
        for observations, opened, sent, verified in cases:
            with self.subTest(observations=observations):
                result, state = self._run_clocked_prepared(reply=(seat, target, parent, observations))
                self.assertFalse(state["clicked"], "the feed composer must never submit")
                self.assertEqual(state["replyOpened"], opened)
                self.assertEqual(state["replyClicked"], sent)
                if observations.get("DOT_TEST_CHANGE_AT") in {"late_submit", "hidden_submit"}:
                    self.assertIn("aborted ", result.stdout)
                if observations.get("DOT_TEST_CHANGE_AT") == "submit_error":
                    self.assertIn("DOT_SEND_UNVERIFIED", result.stdout)
                    self.assertNotIn("aborted ", result.stdout)
                if observations.get("DOT_TEST_CHANGE_AT") in {"late_fill", "late_submit"}:
                    self.assertEqual(state["composer"], "Other draft")
                if observations.get("DOT_TEST_REPLY_CHANGED") == "focus":
                    self.assertEqual(state["composer"], "")
                    self.assertNotIn("prepared-exact ", result.stdout)
                history = observations.get("DOT_TEST_HISTORY")
                if history in {"deep", "growing_missing"}:
                    self.assertEqual(state["scrolls"], 7)
                elif history:
                    self.assertEqual(state["scrolls"], 1)
                self.assertEqual("DOT_SENT_VERIFIED" in result.stdout, verified)

    def test_prepared_callback_can_outlast_launch_deadline(self):
        proc, state = self._run_clocked_prepared()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("DOT_SENT_VERIFIED", proc.stdout)
        self.assertTrue(state["clicked"])

    def test_prepared_delayed_abort_clears_only_owned_draft(self):
        proc, state = self._run_clocked_prepared(decision="abort")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("aborted ", proc.stdout)
        self.assertFalse(state["clicked"])
        self.assertEqual(state["composer"], "")

    def test_prepared_absolute_timeout_never_clicks(self):
        proc, state = self._run_clocked_prepared(advance_ms=600000)
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertNotIn("DOT_SENT_VERIFIED", proc.stdout)
        self.assertFalse(state["clicked"])

    def test_prepared_readiness_still_has_launch_timeout(self):
        proc, state = self._run_clocked_prepared(hang_launch=True)
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertIn("timeout", proc.stdout)
        self.assertIsNone(state)

    def test_prepared_postcommit_work_has_a_phase_timeout(self):
        proc, state = self._run_clocked_prepared(hang_after_commit=True)
        self.assertIn("DOT_SEND_UNVERIFIED", proc.stdout)
        self.assertNotIn("DOT_SENT_VERIFIED", proc.stdout)
        self.assertNotIn("DOT_PRECOMMIT_NO_SEND", proc.stdout)
        self.assertTrue(state["clicked"])

    def test_prepared_commit_cannot_extend_absolute_operation_budget(self):
        proc, state = self._run_clocked_prepared(
            advance_ms=590000, hang_after_commit=True, send_advance_ms=20000,
        )
        self.assertIn("DOT_SEND_UNVERIFIED", proc.stdout)
        self.assertNotIn("DOT_SENT_VERIFIED", proc.stdout)
        self.assertTrue(state["clicked"])

    def test_prepared_known_failures_emit_message_bound_no_send_proof(self):
        cases = (("usage_limit", {"usage_limit": True}),
                 ("composer_not_empty", {"initial_composer": "Existing draft"}),
                 ("composer_mismatch", {"mismatched_composer": True}),
                 ("profile_unavailable", {"missing_profile": True}))
        for reason, options in cases:
            with self.subTest(reason=reason):
                proc, state = self._run_clocked_prepared(**options)
                frames = [json.loads(line.removeprefix("DOT_PRECOMMIT_NO_SEND "))
                          for line in proc.stdout.splitlines()
                          if line.startswith("DOT_PRECOMMIT_NO_SEND ")]
                self.assertEqual(frames, [{"schema_version": 1, "phase": "precommit",
                                          "reason": reason,
                                          "message_sha256": hashlib.sha256(b"Synthetic proof").hexdigest()}])
                self.assertEqual(proc.returncode, 10 if reason == "profile_unavailable" else 0)
                if state:
                    self.assertFalse(state["clicked"])
                    if reason == "composer_not_empty":
                        self.assertEqual(state["composer"], "Existing draft")

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
                    '"reason":"composer_not_empty"', proc.stdout
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
        startup_script = self.root / "benign-startup-env.sh"
        startup_script.write_text(
            "DOT_ACCOUNT=contaminated\nexport DOT_ACCOUNT\n",
            encoding="utf-8",
        )
        env = dict(self.env)
        env["BASH_ENV"] = str(startup_script)
        env["ENV"] = str(startup_script)

        proc = self._run_dot_sh(env=env)

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

    def test_ignores_only_ancestor_owned_exact_profile_lock_holder(self):
        self.profile.rename(self.root / "profile with spaces")
        self.profile = self.root / "profile with spaces"
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["accounts"]["fixture"]["user_data_dir"] = str(self.profile)
        self.config.write_text(json.dumps(config), encoding="utf-8")
        self.env["DOT_CHROME_USER_DATA"] = str(self.profile)
        bin_dir = self.root / "lock-holder-bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        lock_holder = (
            f"python3 - {self.profile}/.dot-profile.lock "
            f"{self.profile}/.dot-profile.lock.ready.ABC123"
        )
        fake_ps.write_text(
            "#!/bin/sh\n"
            'node_pid="$PPID"\n'
            'parent_pid=$(/bin/ps -o ppid= -p "$node_pid" | tr -d "[:space:]")\n'
            '/bin/ps -o pid=,ppid=,command= -p "$parent_pid"\n'
            "printf '%s %s %s\\n' 987654 \"$parent_pid\" "
            + shlex.quote(lock_holder)
            + "\n",
            encoding="utf-8",
        )
        fake_ps.chmod(fake_ps.stat().st_mode | stat.S_IXUSR)
        env = dict(self.env)
        env["PATH"] = f"{bin_dir}{os.pathsep}{self.env['PATH']}"

        proc = self._run(env=env)

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(self.launch_record.exists())
        self.assertEqual(
            self._result(proc.stdout),
            {
                "schema_version": 1,
                "launch_state": "started",
                "browser_disposition": "spawned",
                "cleanup_state": "context_close_returned",
            },
        )

    def test_ancestor_process_with_extra_lock_arguments_still_blocks_launch(self):
        bin_dir = self.root / "lookalike-lock-holder-bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        lock_path = f"{self.profile}/.dot-profile.lock"
        lock_holder_lookalike = (
            f"python3 - unrelated-helper {lock_path} {lock_path}.ready.ABC123"
        )
        fake_ps.write_text(
            "#!/bin/sh\n"
            'node_pid="$PPID"\n'
            'parent_pid=$(/bin/ps -o ppid= -p "$node_pid" | tr -d "[:space:]")\n'
            '/bin/ps -o pid=,ppid=,command= -p "$parent_pid"\n'
            "printf '%s %s %s\\n' 987654 \"$parent_pid\" "
            + shlex.quote(lock_holder_lookalike)
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
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_owner_present",
            },
        )
        self.assertFalse(self.launch_record.exists())

    def test_ancestor_python_prefix_with_embedded_arguments_still_blocks_launch(self):
        bin_dir = self.root / "embedded-python-prefix-bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        lock_path = f"{self.profile}/.dot-profile.lock"
        lock_holder_lookalike = (
            f"/usr/bin/python3 -c /tmp/python3 - {lock_path} "
            f"{lock_path}.ready.ABC123"
        )
        fake_ps.write_text(
            "#!/bin/sh\n"
            'node_pid="$PPID"\n'
            'parent_pid=$(/bin/ps -o ppid= -p "$node_pid" | tr -d "[:space:]")\n'
            '/bin/ps -o pid=,ppid=,command= -p "$parent_pid"\n'
            "printf '%s %s %s\\n' 987654 \"$parent_pid\" "
            + shlex.quote(lock_holder_lookalike)
            + "\n",
            encoding="utf-8",
        )
        fake_ps.chmod(fake_ps.stat().st_mode | stat.S_IXUSR)
        env = dict(self.env)
        env["PATH"] = f"{bin_dir}{os.pathsep}{self.env['PATH']}"

        proc = self._run(env=env)

        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertEqual(
            self._result(proc.stdout),
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_owner_present",
            },
        )
        self.assertFalse(self.launch_record.exists())

    def test_same_ancestor_non_lock_process_still_blocks_launch(self):
        bin_dir = self.root / "same-parent-bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        fake_ps.write_text(
            "#!/bin/sh\n"
            'node_pid="$PPID"\n'
            'parent_pid=$(/bin/ps -o ppid= -p "$node_pid" | tr -d "[:space:]")\n'
            '/bin/ps -o pid=,ppid=,command= -p "$parent_pid"\n'
            "printf '%s %s %s\\n' 987654 \"$parent_pid\" "
            + shlex.quote(f"python3 - {self.profile}/unrelated-helper")
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
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_owner_present",
            },
        )
        self.assertFalse(self.launch_record.exists())

    def test_non_ancestor_profile_lock_holder_still_blocks_launch(self):
        bin_dir = self.root / "foreign-lock-holder-bin"
        bin_dir.mkdir()
        fake_ps = bin_dir / "ps"
        lock_holder = (
            f"python3 - {self.profile}/.dot-profile.lock "
            f"{self.profile}/.dot-profile.lock.ready.ABC123"
        )
        fake_ps.write_text(
            "#!/bin/sh\n"
            'node_pid="$PPID"\n'
            'parent_pid=$(/bin/ps -o ppid= -p "$node_pid" | tr -d "[:space:]")\n'
            '/bin/ps -o pid=,ppid=,command= -p "$parent_pid"\n'
            "printf '%s %s %s\\n' 987654 1 "
            + shlex.quote(lock_holder)
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
            {
                "schema_version": 1,
                "launch_state": "unavailable",
                "diagnostic": "profile_owner_present",
            },
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
            json.loads(proc.stdout.removeprefix("DOT_PRECOMMIT_NO_SEND ")),
            {"schema_version": 1, "phase": "precommit", "reason": "profile_unavailable",
             "message_sha256": hashlib.sha256(b"Hello dot").hexdigest()},
        )
        self.assertFalse(self.profile.exists())

    def _fixture_xvfb_path(self):
        xvfb = self.root / "xvfb-run"
        xvfb.write_text('#!/bin/bash\n[[ "$1" == -a ]] || exit 1\nshift\nexport DISPLAY=:99\nexec 3>&-\nexec "$@" 2>&1\n')
        xvfb.chmod(0o700)
        return f"{self.root}:{self.env['PATH']}"

    @unittest.skipUnless(os.uname().sysname == "Linux", "Linux keyring contract")
    def test_dot_sh_prepared_streams_with_same_linux_keyring_environment(self):
        msg = self.root / "fixture-message.txt"
        msg.write_text("Hello dot")
        node = self.root / "fixture-node"
        node.write_text(
            '#!/bin/bash\n'
            'if [[ "${2:-}" == send-prepared ]]; then\n'
            '  printf "%s|%s|%s\\n" "$XDG_RUNTIME_DIR" "$DBUS_SESSION_BUS_ADDRESS" "$DISPLAY" >&2\n'
            '  printf "prepared-exact 00000000000000000000000000000000\\n"\n'
            '  IFS= read -r decision && printf "%s\\n" "$decision"\n'
            'else\n'
            f'  exec {shlex.quote(str(NODE22))} "$@"\n'
            'fi\n'
        )
        node.chmod(0o700)
        path = self._fixture_xvfb_path()
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                env = dict(self.env, DOT_NODE=str(node), PATH=path)
                env.pop("XDG_RUNTIME_DIR", None)
                env.pop("DBUS_SESSION_BUS_ADDRESS", None)
                runtime = f"/run/user/{os.getuid()}"
                bus = f"unix:path={runtime}/bus"
                if explicit:
                    runtime, bus = "/fixture/runtime", "unix:path=/fixture/custom-bus"
                    env.update(XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS=bus)
                with subprocess.Popen([str(DOT_SH), "send-prepared", str(msg)], env=env,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) as child:
                    with selectors.DefaultSelector() as output_ready:
                        output_ready.register(child.stdout, selectors.EVENT_READ)
                        self.assertTrue(output_ready.select(timeout=5), "prepared output was buffered")
                        self.assertEqual(child.stdout.readline().strip(), "prepared-exact " + "0" * 32)
                    stdout, stderr = child.communicate("commit fixture\n", timeout=5)
                    self.assertEqual(child.returncode, 0, stderr)
                    self.assertEqual(stdout.strip(), "commit fixture")
                    self.assertEqual(stderr.strip(), f"{runtime}|{bus}|:99")

    def test_dot_sh_prepared_send_mode_blocks_when_lock_present(self):
        lock = self.profile / "SingletonLock"
        lock.symlink_to("unknown-host-12345")
        msg_file = self.root / "msg.txt"
        msg_file.write_text("Hello dot", encoding="utf-8")
        env = dict(self.env, DOT_PREPARED="1", PATH=self._fixture_xvfb_path())
        proc = subprocess.run(
            [str(DOT_SH), "send-once", str(msg_file)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout.removeprefix("DOT_PRECOMMIT_NO_SEND ")),
            {"schema_version": 1, "phase": "precommit", "reason": "profile_unavailable",
             "message_sha256": hashlib.sha256(b"Hello dot").hexdigest()},
        )
        self.assertTrue(lock.is_symlink())
        self.assertFalse(self.launch_record.exists())


if __name__ == "__main__":
    unittest.main()
