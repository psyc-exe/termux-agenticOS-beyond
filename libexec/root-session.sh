#!/system/bin/sh
# Native backend. Invoked via su; no PRoot rootfs, no persistent/global mount changes.
set -eu
root=$1
shared_tmp=$2
shift 2
case "$root" in /data/local/termux-linux/*) ;; *) exit 64;; esac
case "$root" in *..*|*[!a-zA-Z0-9_./-]*) exit 64;; esac
[ "$(id -u)" = 0 ] || exit 77
[ "$(readlink -f "$root")" = "$root" ] || exit 77
case "$shared_tmp" in /data/data/*/files/usr/tmp|/data/user/0/*/files/usr/tmp) ;; *) exit 64;; esac
[ -d "$shared_tmp" ] && [ ! -L "$shared_tmp" ] || exit 77
check_dir() {
    [ -d "$1" ] && [ ! -L "$1" ] || exit 77
    [ "$(stat -c %u "$1")" = 0 ] || exit 77
    mode=$(stat -c %a "$1")
    [ $((0$mode & 0022)) = 0 ] || exit 77
}
check_dir /data/local/termux-linux
check_dir "$root"
for target in dev proc sys tmp; do
    [ -d "$root/$target" ] && [ ! -L "$root/$target" ] || exit 77
done
[ ! -e "$root/.l2s" ] || exit 77
if [ "${1:-}" = --probe ]; then
    exec /system/bin/unshare -m /system/bin/sh -c '
        set -eu
        /system/bin/mount --make-rprivate /
        /system/bin/chroot "$1" /bin/true
    ' sh "$root"
fi
if [ "${1:-}" != --inside ]; then
    exec /system/bin/unshare -m /system/bin/sh "$0" "$root" "$shared_tmp" --inside "$@"
fi
shift
/system/bin/mount --make-rprivate /
# Namespace destruction releases mounts after the session's last process exits.
/system/bin/mount --bind /dev "$root/dev"
/system/bin/mount -t proc proc "$root/proc"
/system/bin/mount --bind /sys "$root/sys"
/system/bin/mount --bind "$shared_tmp" "$root/tmp"
exec /system/bin/chroot "$root" /usr/bin/env -i HOME=/root USER=root LOGNAME=root \
    TERM=xterm-256color PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 SHELL=/bin/bash "$@"
