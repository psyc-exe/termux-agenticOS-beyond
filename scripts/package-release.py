#!/usr/bin/env python3
"""Build a source-only installer release, excluding workspace/user/runtime files."""
import argparse
import hashlib
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
roots = ["install.sh", "software.sh", "bootstrap.sh", "README.md", "LICENSE", "integrations", "lib", "libexec", "bin", "guest",
         "config", "scripts", "docs", "dependencies", "patches", "tests"]
files = []
for name in roots:
    path = root / name
    files.extend(path.rglob("*") if path.is_dir() else [path])
args.output.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(args.output, "w:gz") as archive:
    for path in sorted(files):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise SystemExit("Release source symlinks are unsupported: " + str(path))
        if path.is_file():
            archive.add(path, arcname="termux-linux/" + path.relative_to(root).as_posix(), recursive=False)
with args.output.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
args.output.with_suffix(args.output.suffix + ".sha256").write_text(f"{digest}  {args.output.name}\n")
print(f"{digest}  {args.output}")
