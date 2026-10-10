"""Dot sessions use an independent persistent profile for every account."""

import json
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
DOT_CHROME = ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot_chrome.mjs"
DOT_SH = ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot.sh"
NODE = shutil.which("node") or "node"


def system_chrome_dir(home):
    if platform.system() == "Darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome"
    return home / ".config" / "google-chrome"


class DotAuthSyncTest(unittest.TestCase):
    def test_source_cannot_import_real_chrome_profiles_or_cookies(self):
        source = DOT_CHROME.read_text(encoding="utf-8")
        self.assertNotIn("syncCookiesFromSource", source)
        self.assertNotIn("DOT_FORCE_SYNC_COOKIES", source)
        self.assertNotIn("rsync", source)
        self.assertNotIn("Local State", source)
        self.assertNotIn(".manual_login", source)

    def test_fresh_and_existing_destinations_are_not_seeded_even_when_forced(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            chrome_root = system_chrome_dir(root)
            real_profile = chrome_root / "Profile 1"
            real_default = real_profile / "Default"
            real_default.mkdir(parents=True)
            (chrome_root / "Local State").write_text(json.dumps({
                "profile": {"info_cache": {"Profile 1": {"email": "owner@example.com"}}}
            }))
            (real_default / "Cookies").write_text("real-browser-cookie-secret")

            destination = root / ".config" / "dot-headless-chrome-work"
            destination_default = destination / "Default"
            destination_default.mkdir(parents=True)
            existing_cookie = destination_default / "Cookies"
            existing_cookie.write_text("dedicated-login-cookie")
            stale_marker = destination_default / ".src_cookies_synced_mtime"
            stale_marker.write_text("stale-marker")
            manual_marker = destination_default / ".manual_login"
            manual_marker.write_text("manual-marker")

            script = root / "verify.mjs"
            script.write_text(f"""
import fs from 'node:fs';
import os from 'node:os';
os.homedir = () => {json.dumps(str(root))};
const {{ ensurePersistentProfile }} = await import({json.dumps(DOT_CHROME.as_uri())});
const target = {json.dumps(str(destination))};
const cookiePath = {json.dumps(str(existing_cookie))};
const before = fs.statSync(cookiePath).mtimeMs;
ensurePersistentProfile({{ matchedKey: 'Profile 1' }}, target);
if (fs.readFileSync(cookiePath, 'utf8') !== 'dedicated-login-cookie' || fs.statSync(cookiePath).mtimeMs !== before)
  throw new Error('existing dedicated session was overwritten');
if (fs.existsSync(target + '/Local State')) throw new Error('real Local State was copied');
if (fs.readFileSync({json.dumps(str(stale_marker))}, 'utf8') !== 'stale-marker')
  throw new Error('old sync marker was modified');
if (fs.readFileSync({json.dumps(str(manual_marker))}, 'utf8') !== 'manual-marker')
  throw new Error('manual login marker was modified');
console.log('DEDICATED_PROFILE_PRESERVED');
""")
            env = dict(os.environ, HOME=tmp, DOT_FORCE_SYNC_COOKIES="1")
            result = subprocess.run([NODE, str(script)], env=env, capture_output=True,
                                    text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DEDICATED_PROFILE_PRESERVED", result.stdout)
            self.assertEqual((real_default / "Cookies").read_text(), "real-browser-cookie-secret")

            fresh = root / ".config" / "dot-headless-chrome-fresh"
            script.write_text(f"""
import fs from 'node:fs';
import os from 'node:os';
os.homedir = () => {json.dumps(str(root))};
const {{ ensurePersistentProfile }} = await import({json.dumps(DOT_CHROME.as_uri())});
const target = {json.dumps(str(fresh))};
ensurePersistentProfile({{ matchedKey: 'Profile 1' }}, target);
if (fs.existsSync(target + '/Local State') || fs.existsSync(target + '/Default/Cookies'))
  throw new Error('fresh profile imported real-browser state');
console.log('FRESH_PROFILE_EMPTY');
""")
            result = subprocess.run([NODE, str(script)], env=env, capture_output=True,
                                    text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("FRESH_PROFILE_EMPTY", result.stdout)

    def test_real_chrome_paths_are_rejected_but_custom_dedicated_path_is_kept(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / ".config" / "dot" / "config.json"
            config.parent.mkdir(parents=True)
            chrome_root = system_chrome_dir(root)
            chrome_profile = chrome_root / "Profile 1"
            dedicated = root / "custom" / "dot-profile"

            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(chrome_profile), "profile_match": "owner@example.com"
            }}}))
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work", DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)
            result = subprocess.run([NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0,
                                result.stderr or "a real Chrome profile must be rejected")

            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated), "profile_match": "owner@example.com"
            }}}))
            result = subprocess.run([NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["profileDir"], str(dedicated))

            config.write_text(json.dumps({"accounts": {
                "work": {"user_data_dir": str(dedicated)},
                "other": {"user_data_dir": str(dedicated)},
            }}))
            result = subprocess.run([NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, "two configured accounts cannot share a profile")

            chrome_root.mkdir(parents=True)
            alias = root / "chrome-alias"
            alias.symlink_to(chrome_root, target_is_directory=True)
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(alias / "Profile 1")
            }}}))
            result = subprocess.run([NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, "symlink aliases to real Chrome must be rejected")

    def test_chrome_subprofile_must_stay_within_account_profile(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work",
                       DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)

            for profile_directory in (
                "",
                False,
                0,
                None,
                "../other/Default",
                "/tmp/foreign-profile",
                r"..\other\Default",
                ".",
                "..",
            ):
                with self.subTest(profile_directory=profile_directory):
                    config.write_text(json.dumps({"accounts": {"work": {
                        "user_data_dir": str(dedicated),
                        "profile_directory": profile_directory,
                    }}}))
                    result = subprocess.run(
                        [NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertNotEqual(
                        result.returncode, 0,
                        f"unsafe configured subprofile was accepted: {profile_directory!r}",
                    )

            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7",
            }}}))
            env["DOT_PROFILE_DIRECTORY"] = "../other/Default"
            result = subprocess.run(
                [NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                capture_output=True, text=True, timeout=15,
            )
            self.assertNotEqual(
                result.returncode, 0,
                "unsafe DOT_PROFILE_DIRECTORY override must be rejected",
            )

    def test_chrome_subprofile_symlink_cannot_escape_account_profile(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            outside = root / "outside-profile"
            outside.mkdir()
            (dedicated / "Profile 7").parent.mkdir(parents=True)
            (dedicated / "Profile 7").symlink_to(outside, target_is_directory=True)
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7",
            }}}))
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work",
                       DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)

            result = subprocess.run(
                [NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                capture_output=True, text=True, timeout=15,
            )
            self.assertNotEqual(
                result.returncode, 0,
                "configured subprofile symlink outside the dedicated directory must be rejected",
            )

    def test_dedicated_profile_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            outside = root / "outside-profile"
            outside.mkdir()
            dedicated_link = root / "dot-profile"
            dedicated_link.symlink_to(outside, target_is_directory=True)
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated_link),
                "profile_directory": "Profile 7",
            }}}))
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work",
                       DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)

            result = subprocess.run(
                [NODE, str(DOT_CHROME), "resolve-profile"], env=env,
                capture_output=True, text=True, timeout=15,
            )
            self.assertNotEqual(
                result.returncode, 0,
                "dedicated user-data root symlink must be rejected",
            )

    def test_profile_operations_reject_root_symlink_added_after_resolution(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            outside = root / "outside-profile"
            dedicated.mkdir()
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7",
            }}}))
            script = root / "root-symlink.mjs"
            script.write_text(f"""
import fs from 'node:fs';
import os from 'node:os';
os.homedir = () => {json.dumps(str(root))};
const {{ markAuthFailed, clearAuthFailed, ensurePersistentProfile }} =
  await import({json.dumps(DOT_CHROME.as_uri())});
const dedicated = {json.dumps(str(dedicated))};
const outside = {json.dumps(str(outside))};
fs.mkdirSync(outside + '/Profile 7', {{ recursive: true }});
const marker = outside + '/Profile 7/.auth_failed';
fs.writeFileSync(marker, 'preserve');
fs.renameSync(dedicated, dedicated + '-original');
fs.symlinkSync(outside, dedicated, 'dir');
markAuthFailed(dedicated);
clearAuthFailed(dedicated);
let rejected = false;
try {{ ensurePersistentProfile({{ profileDirectory: 'Profile 7' }}, dedicated); }}
catch {{ rejected = true; }}
if (!rejected) throw new Error('profile setup accepted a replaced root symlink');
if (fs.readFileSync(marker, 'utf8') !== 'preserve')
  throw new Error('auth marker operation followed a replaced root symlink');
console.log('OUTSIDE_ROOT_PRESERVED');
""")
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work",
                       DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)
            result = subprocess.run(
                [NODE, str(script)], env=env, capture_output=True,
                text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OUTSIDE_ROOT_PRESERVED", result.stdout)

    def test_profile_filesystem_operations_reject_late_subprofile_symlink(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            outside = root / "outside-profile"
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7",
            }}}))
            script = root / "profile-symlink.mjs"
            script.write_text(f"""
import fs from 'node:fs';
import os from 'node:os';
os.homedir = () => {json.dumps(str(root))};
const {{ markAuthFailed, clearAuthFailed, ensurePersistentProfile }} =
  await import({json.dumps(DOT_CHROME.as_uri())});
const dedicated = {json.dumps(str(dedicated))};
const outside = {json.dumps(str(outside))};
fs.mkdirSync(outside, {{ recursive: true }});
fs.mkdirSync(dedicated, {{ recursive: true }});
fs.symlinkSync(outside, dedicated + '/Profile 7', 'dir');
const marker = outside + '/.auth_failed';
fs.writeFileSync(marker, 'preserve');
markAuthFailed(dedicated);
clearAuthFailed(dedicated);
let rejected = false;
try {{ ensurePersistentProfile({{ profileDirectory: 'Profile 7' }}, dedicated); }}
catch {{ rejected = true; }}
if (!rejected) throw new Error('persistent profile setup accepted an outside symlink');
if (fs.readFileSync(marker, 'utf8') !== 'preserve')
  throw new Error('auth marker operation followed an outside symlink');
console.log('OUTSIDE_PROFILE_PRESERVED');
""")
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work",
                       DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)
            result = subprocess.run(
                [NODE, str(script)], env=env, capture_output=True,
                text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OUTSIDE_PROFILE_PRESERVED", result.stdout)

    def test_auth_failure_marker_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            outside_marker = root / "outside-marker"
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7",
            }}}))
            script = root / "auth-marker-symlink.mjs"
            script.write_text(f"""
import fs from 'node:fs';
import os from 'node:os';
os.homedir = () => {json.dumps(str(root))};
const {{ markAuthFailed, ensurePersistentProfile }} =
  await import({json.dumps(DOT_CHROME.as_uri())});
const dedicated = {json.dumps(str(dedicated))};
const outsideMarker = {json.dumps(str(outside_marker))};
ensurePersistentProfile({{ profileDirectory: 'Profile 7' }}, dedicated);
fs.writeFileSync(outsideMarker, 'preserve');
fs.symlinkSync(outsideMarker, dedicated + '/Profile 7/.auth_failed');
markAuthFailed(dedicated);
if (fs.readFileSync(outsideMarker, 'utf8') !== 'preserve')
  throw new Error('auth failure marker write followed a symlink');
console.log('OUTSIDE_MARKER_PRESERVED');
""")
            env = dict(os.environ, HOME=tmp, DOT_ACCOUNT="work",
                       DOT_CONFIG_FILE=str(config))
            env.pop("DOT_CHROME_USER_DATA", None)
            result = subprocess.run(
                [NODE, str(script)], env=env, capture_output=True,
                text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OUTSIDE_MARKER_PRESERVED", result.stdout)

    def test_negative_auth_observations_do_not_clear_auth_failure(self):
        source = DOT_CHROME.read_text(encoding="utf-8")
        self.assertIn("session.status === 200 && session.isJson && session.hasUser", source)
        self.assertIn("if (session.status === 200 && session.isJson && session.hasUser) {\n        clearAuthFailed(USER_DATA_DIR);", source)
        self.assertNotIn("clearAuthFailed(USER_DATA_DIR);\n      if (mode === 'send')", source)
        self.assertNotIn("clearAuthFailed(USER_DATA_DIR);\n    return page;", source)
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            script = root / "auth-marker.mjs"
            marker = root / "profile" / "Default" / ".auth_failed"
            script.write_text(f"""
import fs from 'node:fs';
import {{ markAuthFailed, clearAuthFailed }} from {json.dumps(DOT_CHROME.as_uri())};
const root = {json.dumps(str(root / 'profile'))};
const marker = {json.dumps(str(marker))};
markAuthFailed(root);
if (!fs.existsSync(marker)) throw new Error("negative auth observation cleared auth failure");
clearAuthFailed(root);
if (fs.existsSync(marker)) throw new Error('explicit confirmed login cleanup did not clear auth failure marker');
console.log('AUTH_FAILURE_MARKER_PRESERVED');
""")
            env = dict(os.environ, HOME=tmp)
            result = subprocess.run([NODE, str(script)], env=env, capture_output=True,
                                    text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("AUTH_FAILURE_MARKER_PRESERVED", result.stdout)

    def test_login_and_read_share_the_resolved_dedicated_profile(self):
        shell = DOT_SH.read_text(encoding="utf-8")
        self.assertIn('DOT_CHROME_USER_DATA="$PROFILE_DIR"', shell)
        self.assertIn('DOT_CHROME_USER_DATA="${DOT_CHROME_USER_DATA:-}"', shell)
        self.assertIn('local dir="${DOT_CHROME_USER_DATA:-}"', shell)
        self.assertNotIn("forward_to_mac", shell)
        source = DOT_CHROME.read_text(encoding="utf-8")
        self.assertIn('const USER_DATA_DIR = accountInfo.profileDir;', source)
        self.assertIn('chromium.launchPersistentContext(USER_DATA_DIR', source)

        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7"
            }}}))
            chrome = root / "fake-chrome"
            args_file = root / "login-args"
            chrome.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$DOT_CHROME_ARGS"\n')
            chrome.chmod(0o700)
            env = dict(os.environ, HOME=tmp,
                       PATH=str(Path(NODE).resolve().parent) + os.pathsep + os.environ["PATH"],
                       DOT_CONFIG_FILE=str(config), DOT_CHROME_BIN=str(chrome),
                       DOT_CHROME_ARGS=str(args_file))
            env.pop("DOT_CHROME_USER_DATA", None)
            result = subprocess.run(["bash", str(DOT_SH), "--account", "work", "login"],
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = args_file.read_text().splitlines()
            self.assertIn(f"--user-data-dir={dedicated}", args)
            self.assertIn("--profile-directory=Profile 7", args)

    def test_interactive_login_rejects_root_replaced_after_resolution(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            dedicated.mkdir()
            dedicated_original = root / "dot-profile-original"
            outside = root / "outside-profile"
            outside.mkdir()
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated),
                "profile_directory": "Profile 7",
            }}}))

            race_marker = root / "root-replaced"
            node_wrapper = root / "node-wrapper"
            node_wrapper.write_text(f"""#!/bin/bash
{shlex.quote(str(Path(NODE).resolve()))} "$@"
status=$?
if [[ "$1" == {shlex.quote(str(DOT_CHROME))} && "$2" == "resolve-profile" &&
      ! -e {shlex.quote(str(race_marker))} ]]; then
  mv {shlex.quote(str(dedicated))} {shlex.quote(str(dedicated_original))}
  ln -s {shlex.quote(str(outside))} {shlex.quote(str(dedicated))}
  touch {shlex.quote(str(race_marker))}
fi
exit "$status"
""")
            node_wrapper.chmod(0o700)

            args_file = root / "login-args"
            chrome = root / "fake-chrome"
            chrome.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$DOT_CHROME_ARGS"\n')
            chrome.chmod(0o700)
            env = dict(os.environ, HOME=tmp, DOT_NODE=str(node_wrapper),
                       DOT_CONFIG_FILE=str(config), DOT_CHROME_BIN=str(chrome),
                       DOT_CHROME_ARGS=str(args_file))
            env.pop("DOT_CHROME_USER_DATA", None)

            result = subprocess.run(
                ["bash", str(DOT_SH), "--account", "work", "login"],
                env=env, capture_output=True, text=True, timeout=15,
            )

            self.assertTrue(race_marker.exists(), "test did not replace the root after initial resolution")
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertFalse(args_file.exists(), "Chrome launched after the profile root was replaced")

    def test_canceled_login_preserves_existing_auth_failure_marker(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            dedicated = root / "dot-profile"
            config.write_text(json.dumps({"accounts": {"work": {
                "user_data_dir": str(dedicated)
            }}}))
            marker = dedicated / "Default" / ".auth_failed"
            marker.parent.mkdir(parents=True)
            marker.write_text('{"failedAt":123}')

            chrome = root / "fake-chrome"
            chrome.write_text("#!/bin/sh\nexit 130\n")
            chrome.chmod(0o700)
            env = dict(os.environ, HOME=tmp, DOT_CONFIG_FILE=str(config),
                       DOT_CHROME_BIN=str(chrome))
            env.pop("DOT_CHROME_USER_DATA", None)
            result = subprocess.run(["bash", str(DOT_SH), "--account", "work", "login"],
                                    env=env, capture_output=True, text=True, timeout=15)

            self.assertEqual(result.returncode, 130, result.stderr)
            self.assertEqual(marker.read_text(), '{"failedAt":123}')


if __name__ == "__main__":
    unittest.main()
