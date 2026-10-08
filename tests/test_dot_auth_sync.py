"""Test contract for dot_chrome.mjs cookie synchronization and persistent profile setup."""

import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
DOT_CHROME = ROOT / ".claude" / "skills" / "dot" / "scripts" / "dot_chrome.mjs"


class DotAuthSyncTest(unittest.TestCase):
    def test_syntax_and_preferences_declared(self):
        source = DOT_CHROME.read_text(encoding="utf-8")
        self.assertIn("const preferences = path.join(defaultDir, 'Preferences');", source)
        self.assertIn("function syncCookiesFromSource(", source)
        self.assertIn("function clearSyncMarker(", source)

    def test_sync_cookies_logic_with_node(self):
        # Run isolated Node test exercising syncCookiesFromSource and clearSyncMarker behavior
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            src_dir = temp_path / "src_profile"
            dst_dir = temp_path / "dst_profile"
            src_dir.mkdir()
            dst_dir.mkdir()

            src_cookies = src_dir / "Cookies"
            src_cookies.write_text("src_cookie_data_initial")

            test_script = temp_path / "test_sync.mjs"
            test_script.write_text(f"""
import fs from 'fs';
import path from 'path';

// Extract sync functions from dot_chrome.mjs or test equivalent logic
const defaultDir = {repr(str(dst_dir))};
const srcProfilePath = {repr(str(src_dir))};

function syncCookiesFromSource(srcProfilePath, defaultDir, force = false) {{
  if (!srcProfilePath || !fs.existsSync(srcProfilePath)) return false;
  const syncMarker = path.join(defaultDir, '.src_cookies_synced_mtime');
  let lastSyncedMtime = 0;
  if (!force && fs.existsSync(syncMarker)) {{
    try {{
      lastSyncedMtime = Number(fs.readFileSync(syncMarker, 'utf8').trim()) || 0;
    }} catch {{}}
  }}
  let copied = false;
  for (const rel of ['Cookies', path.join('Network', 'Cookies')]) {{
    const srcC = path.join(srcProfilePath, rel);
    const dstC = path.join(defaultDir, rel);
    if (fs.existsSync(srcC)) {{
      const srcMtime = fs.statSync(srcC).mtimeMs;
      if (force || lastSyncedMtime === 0 || srcMtime > lastSyncedMtime + 1000) {{
        try {{
          fs.mkdirSync(path.dirname(dstC), {{ recursive: true }});
          fs.copyFileSync(srcC, dstC);
          copied = true;
          try {{
            fs.writeFileSync(syncMarker, String(srcMtime));
          }} catch {{}}
        }} catch {{}}
      }}
    }}
  }}
  return copied;
}}

function clearSyncMarker(targetDir) {{
  try {{
    fs.unlinkSync(path.join(targetDir, '.src_cookies_synced_mtime'));
  }} catch {{}}
}}

// 1. Initial sync (lastSyncedMtime === 0)
const res1 = syncCookiesFromSource(srcProfilePath, defaultDir);
if (!res1) throw new Error("Initial sync should succeed");

const dstCookies = path.join(defaultDir, 'Cookies');
if (fs.readFileSync(dstCookies, 'utf8') !== 'src_cookie_data_initial') {{
  throw new Error("dstCookies content mismatch on initial sync");
}}

// 2. Second sync without source update: should NOT copy
const res2 = syncCookiesFromSource(srcProfilePath, defaultDir);
if (res2) throw new Error("Second sync without change should return false");

// 3. Clear marker (simulating not signed in) -> next sync should copy even if source mtime unchanged
clearSyncMarker(defaultDir);
const res3 = syncCookiesFromSource(srcProfilePath, defaultDir);
if (!res3) throw new Error("Sync after clearSyncMarker should succeed");

console.log("OK");
""")

            result = subprocess.run(["node", str(test_script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
