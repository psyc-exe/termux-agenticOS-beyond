#!/usr/bin/env python3
"""Apply version-bounded phone-derived launchers, without temporary-file dependencies."""
import json
import os
from pathlib import Path
import re
import sys


def patch(name, package, version):
    expected = {"cline": "3.0.61", "kilo": "7.5.14"}
    if expected.get(name) != version or json.loads((package / "package.json").read_text())["version"] != version:
        raise ValueError("Patch is restricted to its tested package version")
    root = Path(__file__).resolve().parents[1]
    launcher = package / "bin" / name
    launcher.write_text((root / "patches/agents" / (name + "-launcher.cjs")).read_text(), encoding="utf8")
    launcher.chmod(0o700)
    # PRoot binds are applied only to Cline's process, never system-wide /bin symlinks.
    # FHS binds cover the compiled binary; JS shell resolvers use the native Bash path.
    if name == "cline":
        pattern = re.compile(r'function\s+([\w$]+)\s*\(\s*([\w$]+)\s*\)\s*\{\s*return\s+\2\s*===\s*"win32"\s*\?\s*"powershell"\s*:\s*"/bin/bash"\s*\}')
        count = 0
        def replace(match):
            fname, arg = match.groups()
            return ('function ' + fname + '(' + arg + '){if(' + arg + '==="win32")return"powershell";'
                    'try{if(process.env.PREFIX)return process.env.PREFIX+"/bin/bash"}catch{}return"/bin/bash"}')
        for directory in (package / "node_modules/@cline", package.parent / "@cline"):
            if not directory.exists():
                continue
            for path in directory.rglob("*.js"):
                if path.stat().st_size > 30_000_000:
                    continue
                content = path.read_text(encoding="utf8")
                updated, hits = pattern.subn(replace, content)
                if hits:
                    path.write_text(updated, encoding="utf8")
                    count += hits
        print(f"Cline JS shell resolvers patched: {count}; compiled binary uses FHS binds")
    print(name + " launcher patched; explicit native package bypasses postinstall/cache")


if __name__ == "__main__":
    patch(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
