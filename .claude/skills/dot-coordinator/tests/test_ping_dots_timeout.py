#!/usr/bin/env python3
"""Compatibility CI entrypoint for the current offline coordinator contracts."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_simple_dot_ping', 'tests.test_coordinator_review_lock'])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
