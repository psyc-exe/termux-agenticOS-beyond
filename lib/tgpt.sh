#!/usr/bin/env bash
setup_tgpt() {
    if [[ $TGPT != yes ]]; then
        # Remove only this installation's own launchers; retain downloaded/build data.
        if [[ -L $PREFIX/bin/agenticos-chat && $(readlink "$PREFIX/bin/agenticos-chat") == "$STATE_DIR/bin/ask" ]]; then
            rm -- "$PREFIX/bin/agenticos-chat"
        fi
        [[ ! -f $STATE_DIR/bin/ask ]] || rm -- "$STATE_DIR/bin/ask"
        [[ ! -f $STATE_DIR/bin/tgpt ]] || rm -- "$STATE_DIR/bin/tgpt"
        return 0
    fi
    local module binary=$STATE_DIR/tgpt/bin/tgpt
    module=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["ai"]["tgpt"])' "$ROOT_DIR/config/catalog.json")
    [[ $module =~ ^github.com/aandrew-me/tgpt/v2@v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die 'Invalid pinned tgpt module'
    mkdir -p "$STATE_DIR/tgpt/bin"
    local marker="$module|android-cgo1"
    if [[ ! -x $binary && -x $PREFIX/bin/tgpt ]] && [[ $(timeout 20 "$PREFIX/bin/tgpt" --version </dev/null) == 'tgpt 2.14.0' ]]; then
        cp -- "$PREFIX/bin/tgpt" "$binary"
        printf '%s\n' "$marker" > "$STATE_DIR/tgpt/module"
    fi
    # Build with Termux's native Android toolchain, not a downloaded Linux/glibc binary.
    # A too-old Go toolchain fails locally; no incompatible auto-downloaded toolchain.
    if [[ ! -x $binary || ! -f $STATE_DIR/tgpt/module || $(cat "$STATE_DIR/tgpt/module") != "$marker" ]]; then
        bash "$ROOT_DIR/scripts/ensure-packages.sh" golang git clang
        local build_dir
        env GOTOOLCHAIN=local go mod download -json "$module" > "$STATE_DIR/tgpt/source.json"
        build_dir=$(mktemp -d "$STATE_DIR/tgpt/build.XXXXXX")
        python "$ROOT_DIR/scripts/prepare-tgpt.py" "$STATE_DIR/tgpt/source.json" \
            "$ROOT_DIR/config/catalog.json" "$build_dir/source"
        (
            cd -- "$build_dir/source" || exit 1
            env -u GOARCH -u GOFLAGS GOOS=android GOTOOLCHAIN=local CGO_ENABLED=1 \
                go build -mod=readonly -buildvcs=false -trimpath -o "$binary.new" .
        ) 2>&1 | tee "$STATE_DIR/logs/tgpt-install.log"
        mv -- "$binary.new" "$binary"
        printf '%s\n' "$marker" > "$STATE_DIR/tgpt/module"
    fi
    timeout 30 "$binary" --version </dev/null > "$STATE_DIR/logs/tgpt-version.txt"
    {
        printf '#!%s/bin/bash\n' "$PREFIX"
        printf 'exec bash %q %q "$@"\n' "$ROOT_DIR/bin/tgpt.sh" "$binary"
    } > "$STATE_DIR/bin/tgpt"
    chmod 700 "$STATE_DIR/bin/tgpt"
    {
        printf '#!%s/bin/bash\n' "$PREFIX"
        printf 'exec bash %q %q "$@"\n' "$ROOT_DIR/bin/chat.sh" "$binary"
    } > "$STATE_DIR/bin/ask"
    chmod 700 "$STATE_DIR/bin/ask"
    if [[ ${AGENTICOS_ISOLATED_HOST:-0} == 1 ]]; then
        log "Isolated chat ready: $STATE_DIR/bin/ask"
    elif [[ ! -e $PREFIX/bin/agenticos-chat && ! -L $PREFIX/bin/agenticos-chat ]]; then
        ln -s "$STATE_DIR/bin/ask" "$PREFIX/bin/agenticos-chat"
    elif [[ $(readlink "$PREFIX/bin/agenticos-chat" 2>/dev/null || true) != "$STATE_DIR/bin/ask" ]]; then
        log "Existing agenticos-chat preserved; use $STATE_DIR/bin/ask for this installation."
    fi
    log 'Native chat ready: agenticos-chat (interactive), or linux chat "your question". No prompt is sent during installation.'
}
