import curses
from ..config import save_config
from .dialogs import draw_popup_box
from .mouse import is_left_click

def show_store_wizard(app_instance):
    stdscr = app_instance.stdscr
    safe_addstr = app_instance.safe_addstr
    config = app_instance.config

    stores = [
        ("apt", "APT / Termux pkg (Manual apps only)"),
        ("npm", "NPM Global Packages"),
        ("pip", "Python CLI (pipx / pip manual)"),
        ("standalone", "Custom / Curl Binaries (~/.local/bin)"),
        ("cargo", "Rust / Cargo Binaries"),
        ("go", "Go Binaries"),
        ("bun", "Bun Global Packages")
    ]

    cfg_stores = config.get("enabled_stores", {})

    while True:
        h, w = stdscr.getmaxyx()
        dw = min(54, w - 2)
        dh = len(stores) + 7
        dy = max(1, (h - dh) // 2)
        dx = max(1, (w - dw) // 2)

        draw_popup_box(stdscr, safe_addstr, dy, dx, dh, dw, "⚙ Enabled Package Sources")
        safe_addstr(dy + 2, dx + 2, "Tap source to toggle on/off:", curses.A_BOLD)

        item_touch = []
        for i, (s_key, s_label) in enumerate(stores):
            is_on = cfg_stores.get(s_key, True)
            box = "[✓]" if is_on else "[ ]"
            col = curses.color_pair(2) if is_on else curses.color_pair(7)
            iy = dy + 4 + i
            safe_addstr(iy, dx + 2, f"{box} {s_label}"[:dw - 4], col | curses.A_BOLD)
            item_touch.append({"y": iy, "key": s_key})

        btn_y = dy + dh - 2
        btn_save = " [ Save & Scan ] "
        safe_addstr(btn_y, dx + (dw - len(btn_save)) // 2, btn_save, curses.color_pair(12) | curses.A_BOLD)
        save_bounds = (dx + (dw - len(btn_save)) // 2, dx + (dw - len(btn_save)) // 2 + len(btn_save) - 1)

        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (curses.KEY_ENTER, 10, 13, 27, ord('q')):
            config["enabled_stores"] = cfg_stores
            save_config(config)
            break
        elif ch == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if not is_left_click(bstate):
                    continue
                if my == btn_y and save_bounds[0] <= mx <= save_bounds[1]:
                    config["enabled_stores"] = cfg_stores
                    save_config(config)
                    break
                for itm in item_touch:
                    if itm["y"] == my and dx + 2 <= mx <= dx + dw - 2:
                        k = itm["key"]
                        cfg_stores[k] = not cfg_stores.get(k, True)
                        break
            except curses.error:
                pass
