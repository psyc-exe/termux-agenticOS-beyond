#!/usr/bin/env bash
check_environment() {
    [[ -n ${PREFIX:-} && -x ${PREFIX}/bin/pkg && -x /system/bin/getprop ]] || die 'Run inside native Termux on Android, not inside PRoot or a desktop shell'
    [[ $(id -u) != 0 ]] || die 'Start as the Termux app user; root commands are explicitly brokered via su'
    [[ ! -e /etc/os-release ]] || die 'A Linux guest was detected; return to the native Termux shell'
    [[ $PREFIX == /data/data/*/files/usr || $PREFIX == /data/user/0/*/files/usr ]] || die 'Unsupported Termux prefix'
    case "$HOME" in /data/data/*/files/home|/data/user/0/*/files/home) ;; *) die 'Private Termux HOME required';; esac
    local sdk
    sdk=$(/system/bin/getprop ro.build.version.sdk)
    [[ $sdk =~ ^[0-9]+$ ]] && ((sdk >= 31)) || die 'This installer targets Android 12 (API 31) or newer'
    case $(uname -m) in aarch64|x86_64) ;; *) die 'Initial support is native arm64/amd64 only; no implicit emulation';; esac
    for cmd in bash flock timeout sha256sum; do has "$cmd" || die "Missing $cmd; install Termux coreutils/util-linux first"; done
    export TERMUX__PREFIX=$PREFIX TERMUX__HOME=$HOME
    export TERMUX_APP__PACKAGE_NAME=${TERMUX_APP__PACKAGE_NAME:-${TERMUX_APP_PACKAGE_NAME:-com.termux}}
}
install_host() {
    pkg update -y
    pkg install -y proot-distro python curl ca-certificates git coreutils util-linux
    local help
    help=$(proot-distro install --help)
    [[ $help == *--name* && $help == *--architecture* ]] || die 'OCI-capable PRoot-Distro required. Update Termux packages; legacy alias plugins are unsupported.'
    proot-distro --version > "$STATE_DIR/logs/proot-distro.version"
    if ((STORAGE)); then
        termux-setup-storage
        local n
        for ((n=0;n<30;n++)); do [[ ! -d $HOME/storage/shared ]] || break; sleep 1; done
        [[ -d $HOME/storage/shared && -r $HOME/storage/shared ]] || die 'Shared storage permission not granted; grant in Android settings and rerun'
    fi
    local available required=4194304
    [[ $FOOTPRINT != top10 ]] || required=12582912
    [[ $FOOTPRINT != full ]] || required=41943040
    available=$(df -Pk "$STATE_DIR" | awk 'NR==2 {print $4}')
    [[ $available =~ ^[0-9]+$ ]] && ((available >= required)) || die "Insufficient private-storage space; need at least $((required/1048576)) GiB free (planning floor, not a guarantee)"
}
