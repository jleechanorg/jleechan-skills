#!/usr/bin/env python3
"""Compatibility CI entrypoint for the current offline coordinator contracts."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_dot_recovery_prompt', 'tests.test_coordinator_cli'])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
