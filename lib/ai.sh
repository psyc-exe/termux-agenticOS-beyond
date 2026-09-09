#!/usr/bin/env bash
setup_ai() {
    case "$AI" in
        none) return 0;;
        native)
            pkg install -y nodejs-lts python clang make ripgrep
            local package
            package=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["ai"]["codex-vl"])' "$ROOT_DIR/config/catalog.json")
            mkdir -p "$STATE_DIR/ai-native"
            npm install --prefix "$STATE_DIR/ai-native" --save-exact "$package" 2>&1 | tee "$STATE_DIR/logs/ai-install.log"
            timeout 30 "$STATE_DIR/ai-native/node_modules/.bin/codex-vl" --version > "$STATE_DIR/logs/ai-version.txt"
            {
                printf '#!%s/bin/bash\n' "$PREFIX"
                printf 'exec %q "$@"\n' "$STATE_DIR/ai-native/node_modules/.bin/codex-vl"
            } > "$STATE_DIR/bin/codex-vl"
            chmod 700 "$STATE_DIR/bin/codex-vl"
            # A native Bionic subprocess check catches /bin/bash assumptions without changing Android /bin.
            node -e 'require("child_process").execFileSync(process.env.PREFIX+"/bin/bash",["-c","printf native-shell-ok"],{stdio:"inherit"})'
            ;;
        distro)
            guest_user "$BASE_NAME" /bin/bash -s < "$ROOT_DIR/guest/ai.sh" 2>&1 | tee "$STATE_DIR/logs/ai-install.log"
            ;;
    esac
}
