#!/usr/bin/env bash
setup_display() {
    [[ $DESKTOP == xfce ]] || return 0
    pkg install -y x11-repo
    pkg install -y termux-x11-nightly xorg-xauth
    if one_of "$GPU" auto virgl; then
        if ! pkg install -y virglrenderer-android; then
            log 'VirGL package unavailable; runtime will test Zink/software fallback.'
        fi
    fi
    log 'Install the official Termux:X11 Android APK as well as its companion package. Run linux desktop to verify the display.'
}
renderer_is_hardware() {
    local output=$1
    [[ $output == *'OpenGL renderer string:'* ]] || return 1
    ! grep -Eiq 'llvmpipe|softpipe|swrast|software rasterizer|lavapipe' <<< "$output"
}
graphics_env() {
    # Explicit per-process environment; never write driver variables to shell startup files.
    case "$1" in
        software) printf '%s\n' LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe;;
        virgl) printf '%s\n' GALLIUM_DRIVER=virpipe LIBGL_ALWAYS_SOFTWARE=0;;
        zink) printf '%s\n' MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink LIBGL_ALWAYS_SOFTWARE=0;;
    esac
}
select_renderer() {
    local candidate output
    local -a candidates=() vars=()
    case "$GPU" in
        auto) candidates=(virgl zink software);;
        virgl) candidates=(virgl software);;
        zink) candidates=(zink software);;
        software) candidates=(software);;
    esac
    for candidate in "${candidates[@]}"; do
        [[ $candidate != virgl || -n ${VIRGL_PID:-} ]] || continue
        mapfile -t vars < <(graphics_env "$candidate")
        if output=$(guest_user "$BASE_NAME" /usr/bin/timeout 20 /usr/bin/env \
            -u LD_PRELOAD -u LD_LIBRARY_PATH -u VK_ICD_FILENAMES -u VK_DRIVER_FILES \
            -u MESA_LOADER_DRIVER_OVERRIDE -u GALLIUM_DRIVER -u LIBGL_ALWAYS_SOFTWARE \
            DISPLAY=:1 XAUTHORITY=/home/dev/.Xauthority "${vars[@]}" glxinfo -B 2>&1); then
            printf '%s\n' "$output" > "$STATE_DIR/logs/gpu-$candidate.txt"
            if [[ $candidate == software ]]; then
                grep -Eiq 'OpenGL renderer string:.*(llvmpipe|softpipe)' <<< "$output" || continue
            else
                renderer_is_hardware "$output" || continue
            fi
            RENDERER=$candidate
            log "Renderer accepted: $candidate (see logs/gpu-$candidate.txt)"
            return 0
        else
            printf '%s\n' "$output" > "$STATE_DIR/logs/gpu-$candidate.txt"
        fi
    done
    die 'No working renderer, including software. Check X11 connection and GPU logs.'
}
desktop_cleanup() {
    local pid
    for pid in "${VIRGL_PID:-}" "${X11_PID:-}"; do
        [[ -z $pid ]] || { kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
    done
}
start_desktop() {
    [[ $DESKTOP == xfce ]] || die 'XFCE was not selected for this installation'
    exec 8>"$STATE_DIR/desktop.lock"
    flock -n 8 || die 'Desktop already running for this installation'
    [[ ! -S $PREFIX/tmp/.X11-unix/X1 ]] || die 'Display :1 already exists. Exit its owning session before launching this one.'
    local cookie n
    local -a render_vars
    X11_PID='' VIRGL_PID=''
    trap desktop_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    cookie=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
    xauth -f "$STATE_DIR/Xauthority" add :1 MIT-MAGIC-COOKIE-1 "$cookie"
    termux-x11 :1 -nolisten tcp -auth "$STATE_DIR/Xauthority" >"$STATE_DIR/logs/x11.log" 2>&1 &
    X11_PID=$!
    # The APK launch is a documented Android component, not a fabricated executable.
    /system/bin/am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >"$STATE_DIR/logs/x11-activity.log" 2>&1 || true
    for ((n=0;n<30;n++)); do
        kill -0 "$X11_PID" 2>/dev/null || die 'Termux:X11 companion exited; inspect logs/x11.log'
        [[ ! -S $PREFIX/tmp/.X11-unix/X1 ]] || break
        sleep 1
    done
    [[ -S $PREFIX/tmp/.X11-unix/X1 ]] || die 'X11 socket did not appear; install/open the Termux:X11 APK'
    # FamilyWild avoids host/guest hostname differences while retaining cookie authentication.
    xauth -f "$STATE_DIR/Xauthority" nlist :1 | sed 's/^..../ffff/' |
        guest_user "$BASE_NAME" xauth -f /home/dev/.Xauthority nmerge -
    if [[ ${AGENTICOS_ISOLATED_HOST:-0} != 1 ]] && has termux-x11-preference; then
        termux-x11-preference 'displayResolutionMode:native' 'forceOrientation:auto' \
            >"$STATE_DIR/logs/x11-preferences.log" 2>&1 || log 'Set Native resolution and Auto orientation in the X11 app preferences.'
    fi
    if one_of "$GPU" auto virgl && has virgl_test_server_android; then
        if [[ -S $PREFIX/tmp/.virgl_test ]]; then
            log 'Existing VirGL socket belongs to another session; skipping this backend.'
        else
            TMPDIR=$PREFIX/tmp virgl_test_server_android >"$STATE_DIR/logs/virgl.log" 2>&1 &
            VIRGL_PID=$!
            for ((n=0;n<10;n++)); do
                [[ ! -S $PREFIX/tmp/.virgl_test ]] || break
                kill -0 "$VIRGL_PID" 2>/dev/null || { VIRGL_PID=; break; }
                sleep 1
            done
        fi
    fi
    select_renderer
    mapfile -t render_vars < <(graphics_env "$RENDERER")
    guest_user "$BASE_NAME" /usr/bin/env -u LD_PRELOAD -u LD_LIBRARY_PATH \
        -u VK_ICD_FILENAMES -u VK_DRIVER_FILES -u MESA_LOADER_DRIVER_OVERRIDE \
        -u GALLIUM_DRIVER -u LIBGL_ALWAYS_SOFTWARE DISPLAY=:1 XAUTHORITY=/home/dev/.Xauthority \
        TL_DPI="$DPI" "${render_vars[@]}" /bin/bash -s < "$ROOT_DIR/guest/desktop.sh"
}
