#!/usr/bin/env bash
ensure_image() {
    local image=$1 name=$2 reference arch
    [[ $MODE != root || $name != "$BASE_NAME" ]] || return 0
    arch=arm64; [[ $(uname -m) != x86_64 ]] || arch=amd64
    reference=$(python "$ROOT_DIR/scripts/resolve-image.py" "$ROOT_DIR/config/catalog.json" "$image" "$arch" "$STATE_DIR/locks/$name.json")
    if [[ ! -f $STATE_DIR/$name.installed ]]; then
        if proot-distro list --quiet | grep -Fxq "$name"; then
            die "Container $name exists without ownership marker. Inspect it; use a new state directory."
        fi
        mkdir -p "$STATE_DIR/cache"
        local archive=$STATE_DIR/cache/$name.oci.tar
        python "$ROOT_DIR/scripts/resolve-image.py" "$ROOT_DIR/config/catalog.json" "$image" "$arch" \
            "$STATE_DIR/locks/$name.json" --archive "$archive"
        proot-distro install "$archive" --name "$name" --architecture "linux/$arch" 2>&1 | tee "$STATE_DIR/logs/$name-install.log"
        printf '%s\n' "$reference" > "$STATE_DIR/$name.installed"
    fi
}
shell_quote() { printf "'%s'" "${1//\'/\'\\\'\'}"; }
root_login() {
    local command arg
    command="/system/bin/sh $(shell_quote "$ROOT_DIR/libexec/root-session.sh") $(shell_quote "$ROOTFS") $(shell_quote "$PREFIX/tmp")"
    for arg in "$@"; do command+=" $(shell_quote "$arg")"; done
    su -c "$command"
}
guest_login() {
    local name=$1; shift
    if [[ $MODE == root && $name == "$BASE_NAME" ]]; then
        root_login "$@"
    else
        local -a options=(--isolated --shared-tmp)
        if ((STORAGE)) && [[ -d $HOME/storage/shared ]]; then options+=(--bind "$HOME/storage/shared:/mnt/shared"); fi
        proot-distro login "$name" "${options[@]}" -- "$@"
    fi
}
guest_user() {
    local name=$1; shift
    if [[ $MODE == root && $name == "$BASE_NAME" ]]; then
        root_login /usr/sbin/runuser -u dev -- /usr/bin/env HOME=/home/dev USER=dev LOGNAME=dev SHELL=/bin/bash "$@"
    else
        local -a options=(--isolated --shared-tmp --user dev)
        if ((STORAGE)) && [[ -d $HOME/storage/shared ]]; then options+=(--bind "$HOME/storage/shared:/mnt/shared"); fi
        proot-distro login "$name" "${options[@]}" -- /usr/bin/env HOME=/home/dev USER=dev LOGNAME=dev SHELL=/bin/bash "$@"
    fi
}
configure_guest() {
    local name=$1 role=$2 expected=$BASE version
    [[ $role != tools ]] || expected=$TOOLCHAIN
    version=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["images"][sys.argv[2]]["version"])' "$ROOT_DIR/config/catalog.json" "$expected")
    guest_login "$name" /bin/bash -s -- "$role" "$expected" "$version" "$FOOTPRINT" "$DESKTOP" "$AI" \
        < "$ROOT_DIR/guest/provision.sh" 2>&1 | tee "$STATE_DIR/logs/$name-configure.log"
    printf 'configured\n' > "$STATE_DIR/$name.configured"
}
