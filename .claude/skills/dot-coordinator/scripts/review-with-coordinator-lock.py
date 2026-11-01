#!/usr/bin/env python3
"""Retired compatibility entrypoint: reviews use Dot transport profile protection."""
import sys
print('Coordinator review holds are retired; use the existing Dot transport directly. No command executed.', file=sys.stderr)
raise SystemExit(2)
