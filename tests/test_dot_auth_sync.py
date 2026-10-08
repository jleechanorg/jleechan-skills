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

        # Regression check: clearAuthFailed must only be called when auth is confirmed
        self.assertIn("if (session.status === 200 && session.isJson && session.hasUser)", source)
        # Ensure clearAuthFailed is not called unconditionally on indeterminate status 0 or 500
        self.assertNotIn("clearAuthFailed(USER_DATA_DIR);\n      if (mode === 'send')", source)
        self.assertNotIn("clearAuthFailed(USER_DATA_DIR);\n    return page;", source)

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

// 2b. When sync is already recorded, allow a newer source mtime to trigger copying
// even if routine headless runs touched dst to a later timestamp
const routineHeadlessTouch = new Date(Date.now() + 10000);
fs.utimesSync(dstCookies, routineHeadlessTouch, routineHeadlessTouch);

const newerDesktopLogin = new Date(Date.now() + 5000);
fs.writeFileSync(path.join(srcProfilePath, 'Cookies'), 'fresh_desktop_login_v2');
fs.utimesSync(path.join(srcProfilePath, 'Cookies'), newerDesktopLogin, newerDesktopLogin);

const copied2b = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!copied2b) throw new Error("Step 2b failed: newer desktop login should sync over routine dst touch when sync already recorded");
if (fs.readFileSync(dstCookies, 'utf8') !== 'fresh_desktop_login_v2') {{
  throw new Error("Step 2b failed: dstCookies content mismatch after 2b sync");
}}

// 3. REGRESSION TEST: Browser shutdown flush 2 seconds after failedAt without manual login marker
// When auth fails, clearSyncMarker writes .auth_failed.
// Browser shutdown flushes cookies 2s AFTER failedAt.
// syncCookiesFromSource must NOT mistake this routine flush for a manual login.
clearSyncMarker(dstRootDir);
const failedAt = JSON.parse(fs.readFileSync(authFailedMarker, 'utf8')).failedAt;
const flushTime = new Date(failedAt + 2000);
fs.writeFileSync(dstCookies, 'stale_expired_session_flushed_on_shutdown');
fs.utimesSync(dstCookies, flushTime, flushTime);

// Source desktop cookies are older than the shutdown flush
const desktopTime = new Date(failedAt - 5000);
fs.writeFileSync(path.join(srcProfilePath, 'Cookies'), 'authenticated_desktop_cookie');
fs.utimesSync(path.join(srcProfilePath, 'Cookies'), desktopTime, desktopTime);

// Multiple recovery attempts must succeed and update dstCookies
for (let i = 1; i <= 3; i++) {{
  const res = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
  if (i === 1 && !res) {{
    throw new Error("Step 3 failed: recovery attempt 1 failed to sync desktop cookies!");
  }}
  if (fs.readFileSync(dstCookies, 'utf8') !== 'authenticated_desktop_cookie') {{
    throw new Error(`Step 3 failed: dstCookies was left expired on attempt ${{i}}!`);
  }}
}}

// Verify failure state is preserved until explicit confirmation (not deleted merely by copying)
if (!fs.existsSync(authFailedMarker)) {{
  throw new Error("Step 3 failed: .auth_failed should remain until session is confirmed");
}}

// 4. SESSION CHECK CONTRACT: Indeterminate responses (0, 500) must NOT clear .auth_failed
// Only confirmed session (200 with hasUser) clears it
function handleSessionCheck(status, isJson, hasUser) {{
  if (status === 200 && isJson && hasUser) {{
    clearAuthFailed(dstRootDir);
  }}
}}

handleSessionCheck(0, false, false);
if (!fs.existsSync(authFailedMarker)) throw new Error("Step 4 failed: status 0 cleared authFailedMarker");
handleSessionCheck(500, false, false);
if (!fs.existsSync(authFailedMarker)) throw new Error("Step 4 failed: status 500 cleared authFailedMarker");

// Confirmed auth clears it
handleSessionCheck(200, true, true);
if (fs.existsSync(authFailedMarker)) throw new Error("Step 4 failed: confirmed auth did not clear authFailedMarker");

// 5. MANUAL LOGIN PRESERVATION
// An explicit manual login marker (.manual_login) touched via dot.sh login is preserved
clearSyncMarker(dstRootDir); // auth failed again
const manualTime = new Date(Date.now() + 30000);
fs.writeFileSync(dstCookies, 'manual_headless_login_session');
fs.utimesSync(dstCookies, manualTime, manualTime);
fs.writeFileSync(manualLoginMarker, '');
fs.utimesSync(manualLoginMarker, manualTime, manualTime);

const copiedAfterManual = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (copiedAfterManual) {{
  throw new Error("Step 5 failed: syncCookiesFromSource must not overwrite newer manual login!");
}}
if (fs.readFileSync(dstCookies, 'utf8') !== 'manual_headless_login_session') {{
  throw new Error("Step 5 failed: manual login session was overwritten!");
}}

// 6. Desktop Chrome newer login overrides manual login
const newestDesktopTime = new Date(manualTime.getTime() + 10000);
fs.writeFileSync(path.join(srcProfilePath, 'Cookies'), 'newest_desktop_session');
fs.utimesSync(path.join(srcProfilePath, 'Cookies'), newestDesktopTime, newestDesktopTime);

const copied6 = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!copied6) throw new Error("Step 6 failed: newest desktop login should sync");
if (fs.readFileSync(dstCookies, 'utf8') !== 'newest_desktop_session') {{
  throw new Error("Step 6 failed: dstCookies not updated to newest desktop session");
}}

// 7. Independent tracking for Network/Cookies
const srcNetworkCookies = path.join(srcProfilePath, 'Network', 'Cookies');
fs.writeFileSync(srcNetworkCookies, 'network_cookie_data');
const copied7 = syncCookiesFromSource(srcProfilePath, dstDefaultDir);
if (!copied7) throw new Error("Step 7 failed: Network/Cookies sync should succeed");
const markerContent = JSON.parse(fs.readFileSync(syncMarker, 'utf8'));
if (!markerContent['Cookies'] || !markerContent[path.join('Network', 'Cookies')]) {{
  throw new Error("Step 7 failed: marker should independently track Cookies and Network/Cookies");
}}

// 8. Error handling: clearSyncMarker and clearAuthFailed on missing markers handle ENOENT cleanly
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
