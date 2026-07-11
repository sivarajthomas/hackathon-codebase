"""Shared pytest fixtures for the Invoice server (path setup)."""

from __future__ import annotations

import os
import sys

_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_SERVER_DIR)

for path in (_SERVER_DIR, _REPO_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)
