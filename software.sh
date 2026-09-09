#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if ! command -v python >/dev/null 2>&1; then
    command -v pkg >/dev/null 2>&1 || { echo 'Python 3 is required.' >&2; exit 1; }
    pkg install -y python
fi
exec python "$ROOT_DIR/scripts/software.py" "$@"
