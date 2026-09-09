#!/usr/bin/env bash
log() { printf '[linux] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }
one_of() { local value=$1; shift; local item; for item in "$@"; do [[ $value != "$item" ]] || return 0; done; return 1; }
validate_options() {
    one_of "$MODE" auto proot root || die 'Invalid mode: choose root or proot (Shizuku was removed)'
    one_of "$BASE" debian ubuntu || die 'Invalid base'
    one_of "$TOOLCHAIN" kali parrot || die 'Invalid toolchain'
    one_of "$FOOTPRINT" minimal top10 full || die 'Invalid footprint'
    one_of "$AI" none native distro || die 'Invalid AI runtime'
    one_of "$TGPT" yes no || die 'Invalid tgpt option: use yes or no'
    one_of "${PROFILE:-vanilla}" beginner vanilla || die 'Invalid profile: use beginner or vanilla'
    one_of "$DESKTOP" cli xfce || die 'Invalid desktop'
    one_of "$GPU" auto software virgl zink || die 'Invalid GPU'
    one_of "$FALLBACK" proot abort || die 'Invalid fallback'
    [[ $DPI =~ ^[0-9]{2,3}$ ]] && ((10#$DPI >= 96 && 10#$DPI <= 240)) || die 'DPI must be 96..240'
    [[ $STATE_DIR == /* && $STATE_DIR != / && $STATE_DIR != *:* && $STATE_DIR != *$'\n'* ]] || die 'State path must be absolute, non-root, without colon/newline'
}
choose() {
    local variable=$1 title=$2 reply; shift 2
    local -a choices=("$@")
    [[ -t 0 ]] || die 'Interactive setup needs a terminal; use --yes'
    printf '\n%s\n' "$title" >&2
    local i=1 item
    for item in "${choices[@]}"; do printf '  %d) %s\n' "$i" "$item" >&2; ((i+=1)); done
    while true; do
        read -r -p 'Choice: ' reply || die 'Input closed'
        if [[ $reply =~ ^[1-9]$ ]] && ((reply <= ${#choices[@]})); then
            printf -v "$variable" '%s' "${choices[reply-1]}"; return
        fi
    done
}
show_plan() {
    cat <<EOF
Base: $BASE; security environment: $TOOLCHAIN ($FOOTPRINT)
Requested mode: $MODE; fallback: $FALLBACK
AI: $AI; native tgpt/PowerBrain: $TGPT; desktop: $DESKTOP; GPU: $GPU; DPI: $DPI
State: $STATE_DIR
Shell profile: ${PROFILE:-vanilla}; all optional components remain available in the software store.
Isolated host configuration: ${AGENTICOS_ISOLATED_HOST:-0} (required Termux packages are still shared).
Kali/Parrot repositories stay in their own rootfs. Modes: root or non-root PRoot.
Root backend needs --rootfs; security environment always uses PRoot.
Images: config/catalog.json; current tags resolved to an architecture-specific lock.
EOF
}
init_state() {
    umask 077
    mkdir -p "$STATE_DIR"
    STATE_DIR=$(cd -- "$STATE_DIR" && pwd -P)
    case "$STATE_DIR/" in "$HOME/"*) ;; *) die 'State must be in Termux private HOME';; esac
    mkdir -p "$STATE_DIR"/{logs,locks,bin}
    exec 9>"$STATE_DIR/install.lock"
    flock -n 9 || die 'Another installer holds this state lock'
    local suffix
    suffix=$(printf '%s' "$STATE_DIR" | sha256sum); suffix=${suffix:0:10}
    BASE_NAME=tl-$suffix-$BASE TOOLS_NAME=tl-$suffix-$TOOLCHAIN
    export STATE_DIR BASE_NAME TOOLS_NAME
    printf 'installing\n' > "$STATE_DIR/status"
}
on_error() {
    local status=$1 line=$2
    printf 'failed: line=%s exit=%s\n' "$line" "$status" > "$STATE_DIR/status"
    log "Installation failed at line $line (exit $status). Re-run with the same options; inspect $STATE_DIR/logs."
    exit "$status"
}
save_config() {
    local target=$STATE_DIR/config.sh variable
    # Immutable setup identity; never silently repurpose an existing rootfs.
    local identity="$BASE|$TOOLCHAIN|$MODE|$ROOTFS|$FOOTPRINT|$AI|$DESKTOP|$GPU|$DPI|$STORAGE"
    if [[ -f $STATE_DIR/identity && $(cat "$STATE_DIR/identity") != "$identity" ]]; then
        die 'Options differ from this installation. Use a new --state-dir.'
    fi
    # tgpt is an optional host add-on; toggling it does not change rootfs identity.
    printf '%s\n' "$identity" > "$STATE_DIR/identity"
    : > "$target.tmp"
    for variable in ROOT_DIR STATE_DIR BASE_NAME TOOLS_NAME BASE TOOLCHAIN FOOTPRINT MODE ROOTFS AI TGPT DESKTOP GPU DPI STORAGE AGENTICOS_ISOLATED_HOST; do
        [[ $variable != AGENTICOS_ISOLATED_HOST ]] || AGENTICOS_ISOLATED_HOST=${AGENTICOS_ISOLATED_HOST:-0}
        printf '%s=%q\n' "$variable" "${!variable}" >> "$target.tmp"
    done
    mv -- "$target.tmp" "$target"
}
write_launcher() {
    {
        printf '#!%s/bin/bash\n' "$PREFIX"
        printf 'exec bash %q --state-dir %q "$@"\n' "$ROOT_DIR/bin/linux.sh" "$STATE_DIR"
    } > "$STATE_DIR/bin/linux"
    chmod 700 "$STATE_DIR/bin/linux"
}
