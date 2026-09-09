#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
source "$ROOT_DIR/lib/common.sh"
[[ ${1:-} == --state-dir && -n ${2:-} ]] || die 'Use the generated launcher, or pass --state-dir PATH'
STATE_DIR=$2
shift 2
[[ -f $STATE_DIR/config.sh ]] || die 'No saved configuration; run install.sh first'
source "$STATE_DIR/config.sh"
# shellcheck disable=SC1090
for module in environment privileges distro display; do source "$ROOT_DIR/lib/$module.sh"; done
check_environment
command=${1:-shell}
(($# == 0)) || shift
case "$command" in
    shell) guest_user "$BASE_NAME" /bin/bash -l "$@";;
    tools) if (($#)); then guest_user "$TOOLS_NAME" "$@"; else guest_user "$TOOLS_NAME" /bin/bash -l; fi;;
    exec) (($#)) || die 'exec requires a command'; guest_user "$BASE_NAME" "$@";;
    admin) (($#)) || set -- /bin/bash -l; guest_login "$BASE_NAME" "$@";;
    desktop) start_desktop;;
    chat)
        [[ ${TGPT:-no} == yes ]] || die 'Enable terminal chat with install.sh --tgpt yes'
        exec "$STATE_DIR/bin/ask" "$@";;
    ai)
        case "$AI" in
            native) exec "$STATE_DIR/ai-native/node_modules/.bin/codex-vl" "$@";;
            distro)
                agent=${1:-cline}; (($# == 0)) || shift
                one_of "$agent" cline kilo || die 'Use ai cline or ai kilo'
                guest_user "$BASE_NAME" "/home/dev/.local/share/termux-linux-ai/node_modules/.bin/$agent" "$@";;
            *) die 'AI integration was not selected';;
        esac;;
    doctor)
        printf 'Installer status: '; cat "$STATE_DIR/status"
        proot-distro --version
        guest_login "$BASE_NAME" /bin/bash -c 'cat /etc/os-release; test -x /bin/bash; dpkg --audit; getent hosts deb.debian.org'
        guest_login "$TOOLS_NAME" /bin/bash -c 'cat /var/lib/termux-linux/profile; dpkg --audit'
        printf 'GPU evidence (only created by a desktop launch):\n'
        for report in "$STATE_DIR"/logs/gpu-*.txt; do [[ ! -f $report ]] || cat "$report"; done;;
    *) die 'Commands: shell, tools [command], exec COMMAND, admin [COMMAND], ai, chat, desktop, doctor';;
esac
