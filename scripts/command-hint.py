#!/usr/bin/env python3
"""Local-only command spelling hints and post-install command discovery."""
import difflib
import os
from pathlib import Path
import sys


def commands():
    result = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        try:
            result.update(p.name for p in Path(directory).iterdir() if p.is_file() and os.access(p, os.X_OK))
        except OSError:
            pass
    return sorted(result)


def main():
    available = commands()
    if sys.argv[1:] == ["--snapshot"]:
        print("\n".join(available))
    elif sys.argv[1:2] == ["--new"]:
        old = set(Path(sys.argv[2]).read_text().splitlines())
        new = sorted(set(available) - old)
        if new:
            print("New commands: " + ", ".join(new[:40]))
            print("Examples: tldr " + new[0] + " | " + new[0] + " --help")
    elif len(sys.argv) == 2:
        word = sys.argv[1]
        print(f"Unknown command: {word}", file=sys.stderr)
        near = difflib.get_close_matches(word, available, n=3, cutoff=0.65)
        if near:
            print("Possible spelling: " + ", ".join(near), file=sys.stderr)


if __name__ == "__main__":
    main()
