"""Test path setup: put scripts/ on sys.path so tests can `import config`,
`import feature_coverage_judge`, etc. exactly as the CLI entrypoints do
(sibling-module imports, no installed package required).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
