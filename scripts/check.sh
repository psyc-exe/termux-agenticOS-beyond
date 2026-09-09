#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")/.."
for file in install.sh software.sh bootstrap.sh lib/*.sh libexec/*.sh bin/*.sh guest/*.sh scripts/*.sh tests/*.sh; do bash -n "$file"; done
bash tests/test-shell.sh
python -m unittest discover -s tests -p 'test_*.py' -v
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck -S warning -e SC1091,SC2034,SC2016 install.sh bootstrap.sh lib/*.sh bin/*.sh guest/*.sh scripts/*.sh tests/*.sh
else
    printf 'ShellCheck unavailable; syntax and behavior checks completed.\n'
fi
