"""Filesystem helpers used by scanners."""

import os
from pathlib import Path


def path_size(path):
    """Return a best-effort recursive size in bytes."""
    path = Path(path)
    try:
        if path.is_file():
            return path.stat().st_size
        if not path.is_dir():
            return 0
    except OSError:
        return 0

    total = 0
    for root, _, files in os.walk(path):
        for filename in files:
            try:
                total += (Path(root) / filename).stat().st_size
            except OSError:
                pass
    return total
