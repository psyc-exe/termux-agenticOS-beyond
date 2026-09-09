#!/usr/bin/env bash
# The upstream runner's unquoted $@ splits prompts and bash -c payloads.
set -Eeuo pipefail
: "${PREFIX:?Run inside native Termux}"
loader=$PREFIX/glibc/lib/ld-linux-aarch64.so.1
[[ -x $loader && $# -gt 0 ]] || { echo 'ARM64 glibc loader/target missing' >&2; exit 1; }
unset LD_PRELOAD
export PATH="$PREFIX/glibc/bin:$PATH"
exec "$loader" --library-path "$PREFIX/glibc/lib" "$@"
