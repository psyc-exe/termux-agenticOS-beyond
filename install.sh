#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
export ROOT_DIR
for module in common environment privileges distro ai tgpt display; do
    # shellcheck disable=SC1090
    source "$ROOT_DIR/lib/$module.sh"
done

usage() {
    cat <<'EOF'
Usage: bash install.sh [--plan|--yes] [options]
  --mode auto|proot|root          --base debian|ubuntu
  --tools kali|parrot            --footprint minimal|top10|full
  --ai none|native|distro        --desktop cli|xfce
  --gpu auto|software|virgl|zink  --dpi 96..240
  --storage                     Request Android shared-storage access
  --tgpt yes|no                 Optional native PowerBrain terminal chat
  --profile beginner|vanilla    Final shell setup; defaults to vanilla Bash
  --isolated-host               Preserve host shell/PATH/config; use state/bin commands
  --rootfs PATH                  Pre-provisioned, root-owned native base rootfs
  --state-dir PATH               Separate named installation (private storage)
  --fallback proot|abort         Unsupported privilege fallback (default proot)
  --plan                        Read-only plan; no downloads or privilege probes
  --yes                         Use defaults/noninteractive configuration
Defaults: proot, Debian, Kali minimal, no AI, CLI, auto GPU, 144 DPI.
No Android APK is silently installed. See docs/ARCHITECTURE.md.
EOF
}

main() {
    MODE=auto BASE=debian TOOLCHAIN=kali FOOTPRINT=minimal AI=none DESKTOP=cli
    GPU=auto DPI=144 STORAGE=0 TGPT=no PROFILE=vanilla ROOTFS='' FALLBACK=proot YES=0 PLAN=0
    AGENTICOS_ISOLATED_HOST=0
    STATE_DIR=${XDG_STATE_HOME:-$HOME/.local/state}/termux-linux
    while (($#)); do
        case "$1" in
            --help|-h) usage; return 0 ;;
            --plan) PLAN=1; YES=1; shift ;;
            --yes) YES=1; shift ;;
            --storage) STORAGE=1; shift ;;
            --isolated-host) AGENTICOS_ISOLATED_HOST=1; shift ;;
            --mode|--base|--tools|--footprint|--ai|--desktop|--gpu|--dpi|--tgpt|--profile|--rootfs|--state-dir|--fallback)
                (($# >= 2)) || die "Missing value for $1"
                case "$1" in
                    --mode) MODE=$2;; --base) BASE=$2;; --tools) TOOLCHAIN=$2;;
                    --footprint) FOOTPRINT=$2;; --ai) AI=$2;; --desktop) DESKTOP=$2;;
                    --gpu) GPU=$2;; --dpi) DPI=$2;; --tgpt) TGPT=$2;;
                    --profile) PROFILE=$2;;
                    --rootfs) ROOTFS=$2;; --state-dir) STATE_DIR=$2;; --fallback) FALLBACK=$2;;
                esac
                shift 2 ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
    validate_options
    export AGENTICOS_ISOLATED_HOST
    if ((PLAN)); then show_plan; return; fi
    check_environment
    if ((!YES)); then
        select_privilege
        choose BASE '1. Base OS' debian ubuntu
        choose TOOLCHAIN '2. Separate security environment' kali parrot
        choose FOOTPRINT '3. Security installation footprint' minimal top10 full
        choose AI '4. AI CLI runtime (native = Codex VL; distro = glibc Node/Python)' none native distro
        choose TGPT 'Optional native tgpt chat: PowerBrain, online, no user API key (questions sent to the provider)' no yes
        choose DESKTOP '5. Display' cli xfce
        if [[ $DESKTOP == xfce ]]; then choose GPU 'Graphics backend' auto software virgl zink; fi
        choose PROFILE 'Final step: beginner = Fish, theme, typo/error hints, tldr, fuzzy finding and shortcuts; vanilla = Bash. Mix and match later in the software store.' beginner vanilla
    fi
    [[ $MODE != auto ]] || MODE=proot
    init_state
    trap 'on_error "$?" "$LINENO"' ERR
    trap 'exit 130' INT
    trap 'exit 143' TERM
    install_host
    resolve_privilege
    show_plan
    save_config
    ensure_image "$BASE" "$BASE_NAME"
    configure_guest "$BASE_NAME" base
    ensure_image "$TOOLCHAIN" "$TOOLS_NAME"
    configure_guest "$TOOLS_NAME" tools
    setup_ai
    setup_tgpt
    setup_display
    write_launcher
    # Separate store lock; both frontends share the stable command directory.
    local -a software=(tuipkg "$PROFILE")
    if [[ $TGPT == yes ]]; then software+=(tgpt-tui); fi
    AGENTICOS_STATE=$STATE_DIR python "$ROOT_DIR/scripts/software.py" --install "${software[@]}"
    printf 'complete\n' > "$STATE_DIR/status"
    log "Ready: $STATE_DIR/bin/linux shell | tools | desktop | doctor"
}
main "$@"
