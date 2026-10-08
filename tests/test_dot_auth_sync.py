"""Test contract for dot_chrome.mjs cookie synchronization and persistent profile setup."""

import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
DOT_CHROME = ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot_chrome.mjs"


class DotAuthSyncTest(unittest.TestCase):
    def test_syntax_and_lock_ordering(self):
        source = DOT_CHROME.read_text(encoding="utf-8")
        self.assertIn("const preferences = path.join(defaultDir, 'Preferences');", source)
        self.assertIn("function syncCookiesFromSource(", source)
        self.assertIn("function clearSyncMarker(", source)
        self.assertIn("function clearAuthFailed(", source)

        # Regression check: Singleton lock must be checked before profile synchronization
        lock_call = "await waitAndCleanSingletonLock(USER_DATA_DIR);"
        sync_call = "ensurePersistentProfile(accountInfo, USER_DATA_DIR);"
        self.assertIn(lock_call, source)
        self.assertIn(sync_call, source)

        lock_pos = source.find(lock_call)
        sync_pos = source.find(sync_call)
        self.assertLess(
            lock_pos,
            sync_pos,
            "waitAndCleanSingletonLock must precede ensurePersistentProfile in launch()",
        )

    def test_production_sync_cookies_and_failed_auth_recovery(self):
        # Run isolated Node test importing actual production functions from dot_chrome.mjs
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            src_dir = temp_path / "src_profile"
            src_network = src_dir / "Network"
            dst_root = temp_path / "dst_profile"
            dst_default = dst_root / "Default"

            src_network.mkdir(parents=True)
            dst_default.mkdir(parents=True)

            src_cookies = src_dir / "Cookies"
            src_cookies.write_text("src_cookie_v1")

            test_script = temp_path / "test_runner.mjs"
            test_script.write_text(f"""
import fs from 'fs';
import path from 'path';
import {{ syncCookiesFromSource, clearSyncMarker, clearAuthFailed }} from {repr(DOT_CHROME.as_uri())};

const srcProfilePath = {repr(str(src_dir))};
const dstRootDir = {repr(str(dst_root))};
const dstDefaultDir = {repr(str(dst_default))};
const dstCookies = path.join(dstDefaultDir, 'Cookies');
const syncMarker = path.join(dstDefaultDir, '.src_cookies_synced_mtime');
const authFailedMarker = path.join(dstDefaultDir, '.auth_failed');
const manualLoginMarker = path.join(dstDefaultDir, '.manual_login');

// 1. Initial sync copies from src to dst and creates JSON sync marker
const copied1 = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!copied1) throw new Error("Step 1 failed: initial sync should return true");
if (fs.readFileSync(dstCookies, 'utf8') !== 'src_cookie_v1') {{
  throw new Error("Step 1 failed: dstCookies content mismatch");
}}
if (!fs.existsSync(syncMarker)) {{
  throw new Error("Step 1 failed: syncMarker not created in dst Default dir");
}}

// 2. Second sync with unchanged source should return false
const copied2 = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (copied2) throw new Error("Step 2 failed: second sync without changes should return false");

// 3. REGRESSION TEST: Failed-auth recovery
// Headless Chrome launches, touches dstCookies (routine touch), and fails auth.
// Desktop Chrome has valid cookies that are OLDER than the routine touch.
// clearSyncMarker clears syncMarker and records .auth_failed.
const touchTime = new Date();
fs.writeFileSync(dstCookies, 'unauthenticated_stale_data');
fs.utimesSync(dstCookies, touchTime, touchTime);

clearSyncMarker(dstRootDir);
if (fs.existsSync(syncMarker)) {{
  throw new Error("Step 3 failed: clearSyncMarker did not remove marker");
}}
if (!fs.existsSync(authFailedMarker)) {{
  throw new Error("Step 3 failed: clearSyncMarker did not write .auth_failed");
}}

// srcCookies mtime is older than the unauthenticated routine touch (e.g. 5s before touch)
const desktopTime = new Date(touchTime.getTime() - 5000);
fs.writeFileSync(path.join(srcProfilePath, 'Cookies'), 'authenticated_desktop_cookie');
fs.utimesSync(path.join(srcProfilePath, 'Cookies'), desktopTime, desktopTime);

// syncCookiesFromSource MUST recover by syncing srcCookies despite dst being touched more recently
const recovered = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!recovered) {{
  throw new Error("Step 3 failed: failed-auth recovery was blocked by destination routine touch mtime!");
}}
if (fs.readFileSync(dstCookies, 'utf8') !== 'authenticated_desktop_cookie') {{
  throw new Error("Step 3 failed: dstCookies was not updated with authenticated desktop cookies");
}}
if (fs.existsSync(authFailedMarker)) {{
  throw new Error("Step 3 failed: successful recovery should remove .auth_failed marker");
}}

// 4. MANUAL LOGIN PRESERVATION
// If the user performs a manual login on dst after an auth failure, it must NOT be overwritten.
clearSyncMarker(dstRootDir); // auth failed again
const manualTime = new Date(Date.now() + 20000);
fs.writeFileSync(dstCookies, 'manual_headless_login_session');
fs.utimesSync(dstCookies, manualTime, manualTime);
fs.writeFileSync(manualLoginMarker, '');
fs.utimesSync(manualLoginMarker, manualTime, manualTime);

const copiedAfterManual = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (copiedAfterManual) {{
  throw new Error("Step 4 failed: syncCookiesFromSource must not overwrite newer manual login!");
}}
if (fs.readFileSync(dstCookies, 'utf8') !== 'manual_headless_login_session') {{
  throw new Error("Step 4 failed: manual login session was overwritten!");
}}

// 5. Desktop Chrome newer login overrides manual login
const newestDesktopTime = new Date(manualTime.getTime() + 10000);
fs.writeFileSync(path.join(srcProfilePath, 'Cookies'), 'newest_desktop_session');
fs.utimesSync(path.join(srcProfilePath, 'Cookies'), newestDesktopTime, newestDesktopTime);

const copied5 = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!copied5) throw new Error("Step 5 failed: newest desktop login should sync");
if (fs.readFileSync(dstCookies, 'utf8') !== 'newest_desktop_session') {{
  throw new Error("Step 5 failed: dstCookies not updated to newest desktop session");
}}

// 6. Independent tracking for Network/Cookies
const srcNetworkCookies = path.join(srcProfilePath, 'Network', 'Cookies');
fs.writeFileSync(srcNetworkCookies, 'network_cookie_data');
const copied6 = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!copied6) throw new Error("Step 6 failed: Network/Cookies sync should succeed");
const markerContent = JSON.parse(fs.readFileSync(syncMarker, 'utf8'));
if (!markerContent['Cookies'] || !markerContent[path.join('Network', 'Cookies')]) {{
  throw new Error("Step 6 failed: marker should independently track Cookies and Network/Cookies");
}}

// 7. Error handling: clearSyncMarker and clearAuthFailed on missing markers handle ENOENT cleanly
clearSyncMarker(dstRootDir);
clearAuthFailed(dstRootDir);
clearAuthFailed(dstRootDir);

console.log("ALL_AUTH_SYNC_TESTS_PASSED");
""")

            result = subprocess.run(["node", str(test_script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ALL_AUTH_SYNC_TESTS_PASSED", result.stdout)


if __name__ == "__main__":
    unittest.main()
