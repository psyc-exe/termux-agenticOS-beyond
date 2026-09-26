#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")/.."
ROOT_DIR=$PWD
source lib/common.sh
source lib/privileges.sh
source lib/distro.sh
source lib/display.sh
passed=0
assert() { "$@" || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; ((passed+=1)); }
reject() { if "$@"; then printf 'Unexpected success: %s\n' "$*" >&2; exit 1; fi; ((passed+=1)); }

# Root false positives and failed/denied su.
su() { printf '2000\n'; }
timeout() { shift; "$@"; }
reject check.root
su() { printf '0\n'; }
assert check.root
su() { return 1; }
reject check.root
unset -f su timeout

MODE=root FALLBACK=proot
fallback_privilege 'test: unavailable native root'
assert test "$MODE" = proot
reject bash -c 'source lib/common.sh; source lib/privileges.sh; FALLBACK=abort; fallback_privilege unavailable'

# A renderer that silently fell back to LLVMpipe is not hardware acceleration.
reject renderer_is_hardware 'OpenGL renderer string: llvmpipe (LLVM 19)'
reject renderer_is_hardware 'OpenGL renderer string: zink (llvmpipe)'
reject renderer_is_hardware 'error: display unavailable'
assert renderer_is_hardware 'OpenGL renderer string: virgl (Adreno (TM) 740)'

# Quote arbitrary CLI arguments safely across su's /system/bin/sh boundary.
payload='space and apostrophe '\'' with $(touch BAD) ; *'
quoted=$(shell_quote "$payload")
result=$(sh -c "printf '%s' $quoted")
assert test "$result" = "$payload"
assert test ! -e BAD

testdir=$(mktemp -d)
trap 'rm -rf -- "$testdir"' EXIT
STATE_DIR=$testdir BASE_NAME=test-base
mkdir -p "$STATE_DIR/logs"
# End-to-end renderer selection: rejected fake hardware then actual software.
guest_user() {
    if [[ " $* " == *GALLIUM_DRIVER=llvmpipe* ]]; then
        printf 'OpenGL renderer string: llvmpipe (LLVM)\n'
    else
        printf 'OpenGL renderer string: zink (llvmpipe)\n'
    fi
}
GPU=auto VIRGL_PID=123
select_renderer
assert test "$RENDERER" = software
guest_user() { return 1; }
reject bash -c 'source lib/common.sh; source lib/display.sh; guest_user() { return 1; }; GPU=software; STATE_DIR="$1"; BASE_NAME=test; select_renderer' sh "$STATE_DIR"

# PRoot argv keeps paths/commands separate and binds only explicitly selected storage.
MODE=proot STORAGE=0 PREFIX=/test/prefix
proot-distro() { printf '%s\n' "$@" > "$testdir/argv"; }
# shellcheck disable=SC2218
guest_login test-base /bin/echo 'two words'
assert grep -Fxq -- --isolated "$testdir/argv"
assert grep -Fxq -- --shared-tmp "$testdir/argv"
assert grep -Fxq 'two words' "$testdir/argv"
reject grep -Fxq -- --shared-home "$testdir/argv"
guest_user() { :; } # Remove graphics stub; load the actual user boundary.
source lib/distro.sh
guest_user test-base /bin/echo 'two words'
assert grep -Fxq dev "$testdir/argv"

# Argument validation occurs before any platform probes or mutation.
reject bash install.sh --plan --dpi '100;touch BAD'
reject bash install.sh --plan --base fedora
reject bash install.sh --plan --state-dir /
reject bash install.sh --plan --mode shizuku
reject bash install.sh --plan --tgpt invalid
assert bash install.sh --plan --mode proot --base ubuntu --tools parrot --footprint full --ai distro --tgpt yes --desktop xfce

# Native tgpt does not use PRoot, reinterpret question flags, or inherit provider rotation.
printf '#!%s\n' "$(command -v bash)" > "$testdir/fake-tgpt"
cat >> "$testdir/fake-tgpt" <<'EOF'
printf '%s\n' "$@" > "$CHAT_TEST_ARGS"
printf '%s\n' "${AI_ROTATE_PROVIDERS-unset}" > "$CHAT_TEST_ENV"
EOF
chmod +x "$testdir/fake-tgpt"
export CHAT_TEST_ARGS=$testdir/chat-args CHAT_TEST_ENV=$testdir/chat-env
export AI_ROTATE_PROVIDERS=another-provider
bash bin/chat.sh "$testdir/fake-tgpt" '--config=untrusted' '--shell' 'two words'
assert grep -Fxq powerbrain "$CHAT_TEST_ARGS"
assert grep -Fxq 'Question: --config=untrusted --shell two words' "$CHAT_TEST_ARGS"
assert grep -Fxq unset "$CHAT_TEST_ENV"
reject grep -Fxq -- --shell "$CHAT_TEST_ARGS"
bash bin/chat.sh "$testdir/fake-tgpt"
assert grep -Fxq -- --interactive "$CHAT_TEST_ARGS"
assert grep -Fxq /dev/null "$CHAT_TEST_ARGS"
export AGENTICOS_TGPT_CONFIG=$testdir/nonexistent
bash bin/tgpt.sh "$testdir/fake-tgpt" --provider ollama --code 'write hello'
assert grep -Fxq powerbrain "$CHAT_TEST_ARGS"
assert grep -Fxq ollama "$CHAT_TEST_ARGS"
assert grep -Fxq -- --code "$CHAT_TEST_ARGS"
reject bash bin/tgpt.sh "$testdir/fake-tgpt" --provider powerbrain --update
reject bash install.sh --plan --profile broken
assert bash install.sh --plan --profile beginner
assert bash install.sh --plan --profile vanilla --isolated-host
# glibc execution keeps command payloads as a single argument.
mkdir -p "$testdir/prefix/glibc/lib"
cp "$testdir/fake-tgpt" "$testdir/prefix/glibc/lib/ld-linux-aarch64.so.1"
PREFIX=$testdir/prefix bash bin/glibc-exec.sh /test/bash -c 'printf "%s" "two words *"'
assert grep -Fxq 'printf "%s" "two words *"' "$CHAT_TEST_ARGS"
printf 'PASS: %d shell checks\n' "$passed"
