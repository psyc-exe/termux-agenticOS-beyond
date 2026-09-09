#!/usr/bin/env bash
set -Eeuo pipefail
XDG_RUNTIME_DIR=/tmp/tl-runtime-$(id -u)
export XDG_RUNTIME_DIR
if [[ -L $XDG_RUNTIME_DIR ]]; then echo 'Unsafe runtime directory' >&2; exit 1; fi
mkdir -p "$XDG_RUNTIME_DIR"
[[ $(stat -c %u "$XDG_RUNTIME_DIR") == "$(id -u)" ]] || exit 1
chmod 700 "$XDG_RUNTIME_DIR"
# D-Bus owns the entire desktop lifecycle. No systemctl, daemonized desktop, or system bus required.
dbus-run-session -- /bin/bash -c '
    set -eu
    printf "Xft.dpi: %s\n" "$TL_DPI" | xrdb -merge
    xfconf-query -c xsettings -p /Xft/DPI -n -t int -s "$TL_DPI" ||
        xfconf-query -c xsettings -p /Xft/DPI -s "$TL_DPI"
    xfconf-query -c xfwm4 -p /general/use_compositing -n -t bool -s false ||
        xfconf-query -c xfwm4 -p /general/use_compositing -s false
    exec xfce4-session
'
