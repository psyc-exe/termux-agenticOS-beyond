#!/usr/bin/env bash
set -Eeuo pipefail
missing=()
for package in "$@"; do
    if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) != 'install ok installed' ]]; then
        missing+=("$package")
    fi
done
if ((${#missing[@]})); then pkg install -y "${missing[@]}"; fi
