#!/usr/bin/env python3
"""Copy the verified pinned tgpt module and apply its Android-only clipboard adapter."""
import argparse
import json
import shutil
from pathlib import Path


def prepare(metadata, catalog, destination, adapter):
    expected = catalog["ai"]
    actual = metadata.get("Path", "") + "@" + metadata.get("Version", "")
    if actual != expected["tgpt"] or metadata.get("Sum") != expected["tgpt_sum"]:
        raise ValueError("tgpt source does not match the pinned version/checksum")
    if destination.exists():
        raise ValueError("Use a fresh tgpt source destination")
    source = Path(metadata["Dir"])
    relative = Path("src/clipboard/clipboard_other.go")
    old = "//go:build !freebsd\n// +build !freebsd"
    original = (source / relative).read_text()
    if original.count(old) != 1:
        raise ValueError("Upstream clipboard constraints changed; re-review the patch")
    # copyfile leaves the Go module cache untouched and creates writable build sources.
    shutil.copytree(source, destination, copy_function=shutil.copyfile)
    (destination / relative).write_text(original.replace(old,
        "//go:build !freebsd && !android\n// +build !freebsd,!android"), newline="\n")
    shutil.copyfile(adapter, destination / "src/clipboard/clipboard_android.go")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(json.loads(args.metadata.read_text(encoding="utf-8-sig")),
            json.loads(args.catalog.read_text()), args.destination,
            Path(__file__).resolve().parents[1] / "patches/tgpt/clipboard_android.go")
