#!/usr/bin/env bash
check.root() {
    has su || return 1
    [[ $(timeout 15 su -c 'id -u' 2>/dev/null) == 0 ]]
}
select_privilege() {
    [[ $MODE == auto ]] || return 0
    log 'Checking su; Android may show a root authorization prompt.'
    if check.root; then choose MODE 'Privilege: root is available' root proot
    else MODE=proot; log 'Root unavailable; using non-root PRoot.'; fi
}
fallback_privilege() {
    log "$*"
    [[ $FALLBACK == proot ]] || die 'Privilege setup failed (--fallback abort)'
    MODE=proot
    log 'Continuing with standard PRoot.'
}
root_preflight() {
    [[ $ROOTFS == /data/local/termux-linux/* && $ROOTFS != *[!a-zA-Z0-9_./-]* && $ROOTFS != *..* ]] || return 1
    # Root-owned provisioning is separate from PRoot's app-owned, link2symlink filesystem.
    local command
    command="/system/bin/sh $(shell_quote "$ROOT_DIR/libexec/root-session.sh") $(shell_quote "$ROOTFS") $(shell_quote "$PREFIX/tmp") --probe"
    timeout 15 su -c "$command" >"$STATE_DIR/logs/root-probe.log" 2>&1
}
resolve_privilege() {
    case "$MODE" in
        proot) ;;
        root)
            if ! check.root; then fallback_privilege 'Root access was denied or timed out.'
            elif ! root_preflight; then fallback_privilege 'Native rootfs/capability probe failed. See docs/ROOT.md and logs/root-probe.log.'
            fi ;;
    esac
}
