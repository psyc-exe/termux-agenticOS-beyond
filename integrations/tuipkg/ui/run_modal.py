import curses
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from ..profiles import scoped_command
from ..utils.tldr import fetch_tldr_and_flags
from .dialogs import draw_popup_box
from .mouse import is_left_click

def show_run_window(app_instance, app):
    stdscr = app_instance.stdscr
    safe_addstr = app_instance.safe_addstr

    # Choose primary binary
    primary_bin = app.get("bin") or app["name"]
    bins_available = app.get("bins", [primary_bin])
    if not bins_available:
        bins_available = [primary_bin]

    selected_bin = primary_bin
    cmd_input = selected_bin

    examples, flags = fetch_tldr_and_flags(selected_bin)

    focused_button = 0  # 0 = "Run Here", 1 = "Run in New Tab"

    while True:
        h, w = stdscr.getmaxyx()
        dw = min(58, w - 2)
        dh = min(24, h - 2)
        dy = max(1, (h - dh) // 2)
        dx = max(1, (w - dw) // 2)

        draw_popup_box(stdscr, safe_addstr, dy, dx, dh, dw, f"▶ Launch: {app['name']}")

        # Multiple binaries selector if more than 1
        curr_y = dy + 2
        bin_touch = []
        if len(bins_available) > 1:
            safe_addstr(curr_y, dx + 2, "Binary: ", curses.A_BOLD)
            bx = dx + 10
            for b_name in bins_available[:4]:
                is_cur = (b_name == selected_bin)
                b_badge = f" [{b_name}] "
                if bx + len(b_badge) <= dx + dw - 2:
                    col = curses.color_pair(10) if is_cur else curses.color_pair(7)
                    safe_addstr(curr_y, bx, b_badge, col | curses.A_BOLD)
                    bin_touch.append({"y": curr_y, "x1": bx, "x2": bx + len(b_badge) - 1, "bin": b_name})
                    bx += len(b_badge) + 1
            curr_y += 1

        # Command text box
        safe_addstr(curr_y, dx + 2, "Command line:", curses.A_BOLD)
        curr_y += 1
        box_w = dw - 4
        input_box = f" {cmd_input}".ljust(box_w)[:box_w]
        safe_addstr(curr_y, dx + 2, input_box, curses.color_pair(11) | curses.A_BOLD)
        curr_y += 2

        # Two Action Run Buttons. The focused button is highlighted so a
        # dpad/touch user can press Tab to swap between Run Here and Run
        # in New Tab, then Enter to launch.
        btn_y = curr_y
        btn_here = " [ ▶ Run Here ] "
        btn_new = " [ ⧉ Run in New Tab ] "

        here_attr = (curses.color_pair(12) if focused_button == 0
                     else curses.color_pair(7))
        safe_addstr(btn_y, dx + 2, btn_here, here_attr | curses.A_BOLD)
        here_bounds = (dx + 2, dx + 2 + len(btn_here) - 1)

        new_x = dx + 2 + len(btn_here) + 1
        new_bounds = None
        if new_x + len(btn_new) <= dx + dw - 1:
            new_attr = (curses.color_pair(10) if focused_button == 1
                        else curses.color_pair(7))
            safe_addstr(btn_y, new_x, btn_new, new_attr | curses.A_BOLD)
            new_bounds = (new_x, new_x + len(btn_new) - 1)

        # Tiny hint so dpad users know how to switch focus.
        hint = " [Tab] switch • [Enter] run "
        if new_bounds is not None and (new_x + len(btn_new) + 1 + len(hint)) < (dx + dw - 1):
            safe_addstr(btn_y, new_x + len(btn_new) + 1, hint, curses.A_DIM)
        elif (dx + 2 + len(btn_here) + 1 + len(hint)) < (dx + dw - 1):
            safe_addstr(btn_y, dx + 2 + len(btn_here) + 1, hint, curses.A_DIM)

        curr_y += 2

        # Flag chips section
        chip_touch = []
        if flags:
            safe_addstr(curr_y, dx + 2, "Quick Flags (Tap to add):", curses.color_pair(6) | curses.A_BOLD)
            curr_y += 1
            cx = dx + 2
            for flg in flags[:8]:
                c_text = f" {flg} "
                if cx + len(c_text) <= dx + dw - 2:
                    safe_addstr(curr_y, cx, c_text, curses.color_pair(10))
                    chip_touch.append({"y": curr_y, "x1": cx, "x2": cx + len(c_text) - 1, "flag": flg})
                    cx += len(c_text) + 1
            curr_y += 1

        # TLDR Examples Section
        example_touch = []
        if examples and curr_y + 3 < dy + dh:
            safe_addstr(curr_y, dx + 2, "TLDR Examples (Tap to use):", curses.color_pair(3) | curses.A_BOLD)
            curr_y += 1
            for ex in examples[:3]:
                if curr_y >= dy + dh - 2:
                    break
                desc_line = f"• {ex['desc']}"[:dw - 4]
                cmd_line = f"  {ex['cmd']}"[:dw - 4]
                safe_addstr(curr_y, dx + 2, desc_line, curses.A_DIM)
                curr_y += 1
                if curr_y >= dy + dh - 1:
                    break
                safe_addstr(curr_y, dx + 2, cmd_line, curses.color_pair(6))
                example_touch.append({"y": curr_y, "x1": dx + 2, "x2": dx + dw - 2, "cmd": ex["cmd"]})
                curr_y += 1

        stdscr.refresh()

        ch = stdscr.getch()
        if ch == 27:
            break
        elif ch in (curses.KEY_ENTER, 10, 13):
            # Enter on the focused button. 0 = "Run Here", 1 = "Run in New Tab".
            execute_command(
                app_instance, cmd_input,
                in_active=(focused_button == 0),
                app=app,
            )
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            cmd_input = cmd_input[:-1]
        elif ch == ord('\t'):
            # Tab swaps between the two action buttons for dpad users.
            focused_button = 1 - focused_button
        elif 32 <= ch <= 126:
            cmd_input += chr(ch)
        elif ch == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if not is_left_click(bstate):
                    continue
                if my == btn_y:
                    if here_bounds[0] <= mx <= here_bounds[1]:
                        focused_button = 0
                        execute_command(app_instance, cmd_input, in_active=True, app=app)
                        break
                    elif new_bounds and new_bounds[0] <= mx <= new_bounds[1]:
                        focused_button = 1
                        execute_command(app_instance, cmd_input, in_active=False, app=app)
                        break
                # Check binary switcher chips
                for bt in bin_touch:
                    if bt["y"] == my and bt["x1"] <= mx <= bt["x2"]:
                        selected_bin = bt["bin"]
                        cmd_input = selected_bin
                        examples, flags = fetch_tldr_and_flags(selected_bin)
                        break
                # Flag chips
                for c in chip_touch:
                    if c["y"] == my and c["x1"] <= mx <= c["x2"]:
                        cmd_input = f"{cmd_input.strip()} {c['flag']}"
                        break
                # TLDR examples
                for ex in example_touch:
                    if ex["y"] == my and ex["x1"] <= mx <= ex["x2"]:
                        cmd_input = ex["cmd"]
                        break
                if not (dy <= my < dy + dh and dx <= mx < dx + dw):
                    break
            except curses.error:
                pass

def _scoped_shell_command(cmd_str, app):
    """Return a root-safe shell invocation for a foreign profile."""
    if app and app.get("scope") == "user" and app.get("owner") and app.get("home"):
        profile = {"owner": app["owner"], "home": Path(app["home"]), "current": False}
        return scoped_command(["sh", "-lc", cmd_str], profile)
    return None


def execute_command(app_instance, cmd_str, in_active=True, app=None):
    if not cmd_str.strip():
        return

    try:
        scoped_argv = _scoped_shell_command(cmd_str, app)
    except RuntimeError as exc:
        print(f"\033[1;31mExecution refused: {exc}\033[0m")
        return

    if in_active:
        curses.endwin()
        print("\033[2J\033[H", end="")
        print(f"\033[1;36m▶ Executing:\033[0m \033[1;37m{cmd_str}\033[0m\n" + "─" * 45)

        try:
            ret = subprocess.call(scoped_argv if scoped_argv else cmd_str,
                                  shell=scoped_argv is None)
        except Exception as e:
            print(f"\033[1;31mExecution error: {e}\033[0m")
            ret = -1

        print("\n" + "─" * 45)
        print(f"\033[1;32m✓ Process finished (exit code {ret})\033[0m")
        # Removed blocking input() - return immediately to TUI

        app_instance.stdscr.clear()
        curses.curs_set(0)
        app_instance.init_colors()
    else:
        launched = False
        target_argv = list(scoped_argv) if scoped_argv else None
        target_cmd = shlex.join(target_argv) if target_argv else cmd_str
        label = cmd_str.split()[0] if cmd_str.split() else "tuipkg"

        # 1) Inside an existing tmux session, open a brand-new window so the
        #    user can keep the current TUI visible while the command runs.
        if "TMUX" in os.environ and shutil.which("tmux"):
            try:
                subprocess.Popen(
                    ["tmux", "new-window", "-n", label[:32], f"{target_cmd}; echo; read"],
                )
                launched = True
            except Exception:
                launched = False

        # 2) tmux is installed but we are not inside a session (typical over
        #    SSH without a wrapping tmux). Detach a brand-new tmux server so
        #    the user can later `tmux attach -t tuipkg` to see the output.
        if not launched and shutil.which("tmux"):
            session = "tuipkg"
            try:
                subprocess.Popen(
                    ["tmux", "new-session", "-d", "-s", session, "-n", label[:32],
                     f"{target_cmd}; echo; read"],
                )
                launched = True
            except Exception:
                launched = False

        # 3) Termux without tmux: use the modern RUN_COMMAND intent which is
        #    still shipped in current Termux. The deprecated service_execute
        #    path is removed; this is the supported equivalent.
        if not launched and scoped_argv is None and shutil.which("am"):
            try:
                bash_path = shutil.which("bash") or shutil.which("sh") or "sh"
                subprocess.Popen([
                    "am", "start", "--user", "0",
                    "-n", "com.termux/com.termux.app.RunCommandService",
                    "-a", "com.termux.RUN_COMMAND",
                    "--es", "com.termux.execute.path", bash_path,
                    "--esa", "com.termux.execute.arguments", f"-c,{cmd_str}; echo",
                ])
                launched = True
            except Exception:
                launched = False

        # 4) Last-resort: detach the command via setsid so it survives the
        #    TUI exiting and capture its stdout/stderr to a temp log file we
        #    can show to the user. No shell interpolation is performed.
        if not launched:
            try:
                log_path = Path("/tmp") / f"tuipkg-{os.getpid()}-{int(time.time())}.log"
                if scoped_argv:
                    subprocess.Popen(
                        ["setsid"] + target_argv,
                        stdout=open(log_path, "ab"),
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                    )
                else:
                    # Even for the non-scoped path, avoid shell=True and
                    # tokenize via shlex so injection is impossible.
                    argv = shlex.split(cmd_str)
                    if argv:
                        subprocess.Popen(
                            ["setsid"] + argv,
                            stdout=open(log_path, "ab"),
                            stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                        )
                launched = True
            except Exception:
                launched = False

        # Show confirmation notification popup. The text reflects the actual
        # path that was taken so the user can debug "did it launch?" without
        # guessing. We freeze the screen for a moment so the message is
        # readable instead of being clobbered by the next draw tick.
        h, w = app_instance.stdscr.getmaxyx()
        if launched:
            if "TMUX" in os.environ:
                how = "tmux window"
            elif shutil.which("tmux"):
                how = "tmux session (attach with: tmux attach -t tuipkg)"
            elif shutil.which("am"):
                how = "Termux service"
            else:
                how = "detached process (see /tmp/tuipkg-*.log)"
            msg = f"✓ Launched in {how}: {cmd_str[:max(0, w - 32 - len(how))]}"
        else:
            msg = f"✗ Failed to launch: {cmd_str}"
        attr = curses.color_pair(12) if launched else curses.color_pair(13)
        app_instance.safe_addstr(h - 2, max(0, (w - len(msg)) // 2), msg, attr | curses.A_BOLD)
        app_instance.stdscr.refresh()
        time.sleep(0.8)
