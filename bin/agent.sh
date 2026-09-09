#!/usr/bin/env bash
set -Eeuo pipefail
name=$1
launcher=$2
shift 2
case ${1:-} in
    update|upgrade|self-update|--update|--upgrade)
        printf '%s is pinned with Termux patches. Use the software store for a tested update.\n' "$name" >&2
        exit 2;;
esac
exec node "$launcher" "$@"
