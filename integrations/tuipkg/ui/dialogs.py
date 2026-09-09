import curses
import subprocess
from ..config import format_size
from ..removal import RemovalPlanError, build_removal_plan, run_removal_plan
from .mouse import is_left_click
from .theme import STORE_COLORS


def draw_popup_box(stdscr, safe_addstr, y, x, h, w, title=""):
    stdscr.attron(curses.color_pair(11))
    for iy in range(y, y + h):
        safe_addstr(iy, x, " " * w)

    safe_addstr(y, x, f"┌{'─' * max(0, w - 2)}┐")
    for iy in range(y + 1, y + h - 1):
        safe_addstr(iy, x, "│")
        safe_addstr(iy, x + w - 1, "│")
    safe_addstr(y + h - 1, x, f"└{'─' * max(0, w - 2)}┘")

    if title:
        t_disp = f" {title} "[:w - 4]
        safe_addstr(y, x + 2, t_disp, curses.color_pair(10) | curses.A_BOLD)
    stdscr.attroff(curses.color_pair(11))


def show_app_dialog(app_instance, app):
    stdscr = app_instance.stdscr
    safe_addstr = app_instance.safe_addstr

    while True:
        h, w = stdscr.getmaxyx()
        dw = min(50, w - 2)
        dh = 12
        dy = max(1, (h - dh) // 2)
        dx = max(1, (w - dw) // 2)

        draw_popup_box(stdscr, safe_addstr, dy, dx, dh, dw, f"⚡ {app['name']}")

        store_col = STORE_COLORS.get(app["store"], 7)
        safe_addstr(dy + 2, dx + 2, f"Store:   [{app['store']}]", curses.color_pair(store_col) | curses.A_BOLD)
        safe_addstr(dy + 3, dx + 2, f"Version: {app.get('version', 'latest')}")
        if app.get("size"):
            safe_addstr(dy + 4, dx + 2, f"Size:    {format_size(app['size'])}")
        safe_addstr(dy + 5, dx + 2, f"Binary:  {app.get('bin', app['name'])}")
        if app.get("scope") == "user" and app.get("owner"):
            safe_addstr(dy + 6, dx + 2, f"Owner:   {app['owner']}")

        buttons = [
            (" [ ▶ RUN ] ", "run", 12),
            (" [ 🗑 REMOVE ] ", "remove", 13),
            (" [ ✕ CLOSE ] ", "close", 11),
        ]

        bx = dx + 2
        btn_y = dy + dh - 3
        btn_touch = []

        for btext, baction, bcolor in buttons:
            if bx + len(btext) <= dx + dw:
                safe_addstr(btn_y, bx, btext, curses.color_pair(bcolor) | curses.A_BOLD)
                btn_touch.append({
                    "x_start": bx,
                    "x_end": bx + len(btext) - 1,
                    "action": baction,
                })
                bx += len(btext) + 1

        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (ord('q'), ord('Q'), 27):
            break
        elif ch == ord('r'):
            app_instance.show_run_window(app)
            break
        elif ch in (ord('d'), ord('x')):
            confirm_remove(app_instance, app)
            break
        elif ch == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if not is_left_click(bstate):
                    continue
                if my == btn_y:
                    for b in btn_touch:
                        if b["x_start"] <= mx <= b["x_end"]:
                            if b["action"] == "run":
                                app_instance.show_run_window(app)
                                return
                            if b["action"] == "remove":
                                confirm_remove(app_instance, app)
                                return
                            if b["action"] == "close":
                                return
                elif not (dy <= my < dy + dh and dx <= mx < dx + dw):
                    return
            except curses.error:
                pass


def confirm_remove(app_instance, app):
    stdscr = app_instance.stdscr
    safe_addstr = app_instance.safe_addstr

    try:
        commands, dependency_note = build_removal_plan(app)
        plan_error = None
    except RemovalPlanError as exc:
        commands = None
        dependency_note = str(exc)
        plan_error = str(exc)

    h, w = stdscr.getmaxyx()
    dw = min(58, w - 2)
    dh = 9
    dy = max(1, (h - dh) // 2)
    dx = max(1, (w - dw) // 2)

    draw_popup_box(stdscr, safe_addstr, dy, dx, dh, dw, "🗑 Uninstall Package")
    safe_addstr(dy + 2, dx + 2, f"Remove {app['name']} from {app['store']}?", curses.A_BOLD)
    note = f"Cleanup: {dependency_note}"[:dw - 4]
    safe_addstr(dy + 3, dx + 2, note, curses.A_DIM)
    if plan_error:
        safe_addstr(dy + 4, dx + 2, "Removal is unavailable for this item.", curses.color_pair(13) | curses.A_BOLD)

    btn_y = dy + 6
    btn_yes = " [ 🗑 UNINSTALL ] "
    btn_no = " [ ✕ CANCEL ] "

    safe_addstr(btn_y, dx + 2, btn_yes, curses.color_pair(13) | curses.A_BOLD)
    safe_addstr(btn_y, dx + 2 + len(btn_yes) + 2, btn_no, curses.color_pair(11) | curses.A_BOLD)
    stdscr.refresh()

    yes_bounds = (dx + 2, dx + 2 + len(btn_yes) - 1)
    no_bounds = (dx + 2 + len(btn_yes) + 2, dx + 2 + len(btn_yes) + 2 + len(btn_no) - 1)

    confirmed = False
    while True:
        ch = stdscr.getch()
        if ch in (ord('y'), ord('Y'), ord('d')):
            confirmed = True
            break
        if ch in (ord('n'), ord('N'), ord('q'), 27):
            break
        if ch == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if not is_left_click(bstate):
                    continue
                if my == btn_y:
                    if yes_bounds[0] <= mx <= yes_bounds[1]:
                        confirmed = True
                        break
                    if no_bounds[0] <= mx <= no_bounds[1]:
                        break
                elif not (dy <= my < dy + dh and dx <= mx < dx + dw):
                    break
            except curses.error:
                pass

    if not confirmed or commands is None:
        return

    curses.endwin()
    print("\033[2J\033[H", end="")
    print(f"\033[1;31m🗑 Uninstalling {app['name']} ({app['store']})...\033[0m\n")
    success, failed_command, result = run_removal_plan(commands)

    if success:
        print("\n\033[1;32m✓ Uninstallation complete.\033[0m")
    else:
        code = result.returncode if result is not None else "file operation failed"
        print(f"\n\033[1;31m✗ Uninstallation failed (exit: {code}).\033[0m")
        print(f"Failed operation: {' '.join(failed_command)}")
    input("Press [Enter] to return...")
    stdscr.clear()
    app_instance.init_colors()
    app_instance.rescan()
