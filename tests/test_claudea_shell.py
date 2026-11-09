import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ClaudeaShellTests(unittest.TestCase):
    def test_external_cli_arguments_override_and_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli = Path(tmp) / "claude"
            cli.write_text("#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(7)\n")
            cli.chmod(0o755)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"])
            env.pop("BASH_ENV", None)
            script = 'source "$1"; claude() { return 99; }; claudea --model override "two words"'
            run = subprocess.run(["bash", "--noprofile", "--norc", "-c", script, "bash", str(ROOT / ".claude/scripts/claudea.sh")], env=env, capture_output=True, text=True)
            self.assertEqual(run.returncode, 7)
            self.assertEqual(json.loads(run.stdout), ["--safe-mode", "--dangerously-skip-permissions", "--model", "claude-fable-5-2", "--model", "override", "two words"])


if __name__ == "__main__":
    unittest.main()
