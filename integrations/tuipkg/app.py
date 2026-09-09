import curses
import sys
import time
from .config import load_config, save_config, format_size
from .scanners import scan_all_stores
from .ui.theme import STORE_COLORS, STORE_BADGES, init_theme_colors
from .ui.dialogs import show_app_dialog
from .ui.run_modal import show_run_window
from .ui.wizard import show_store_wizard
from .ui.mouse import is_left_click, is_scroll_down, is_scroll_up
from .ui.icons import icon_for_store

TOUCH_DOUBLE_TAP_DELAY = 0.4

class TuiPkgApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.config = load_config()
        self.apps = []
        self.filtered_apps = []
        self.search_query = ""
        self.selected_idx = 0
        self.scroll_offset = 0
        self.search_active = False

        self.touch_buttons = []
        self.card_zones = []
        self.mouse_press = None
        self.touch_tap = None
        self.store_filter = None

        curses.curs_set(0)
        curses.use_default_colors()
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        self.init_colors()

    def init_colors(self):
        init_theme_colors()

    def safe_addstr(self, y, x, text, attr=0):
        try:
            h, w = self.stdscr.getmaxyx()
            if y < 0 or y >= h or x < 0 or x >= w:
                return
            max_len = w - x
            if y == h - 1:
                max_len = max(0, max_len - 1)
            chunk = str(text)[:max_len]
            if chunk:
                self.stdscr.addstr(y, x, chunk, attr)
        except curses.error:
            pass

    def run(self):
        if self.config.get("first_run", True):
            self.show_store_wizard()
            self.config["first_run"] = False
            save_config(self.config)

        self.rescan()

        while True:
            self.filter_apps()
            self.draw()

            try:
                ch = self.stdscr.getch()
            except KeyboardInterrupt:
                break

            if ch == curses.KEY_RESIZE:
                continue

            if self.search_active:
                if ch == 27:
                    self.search_active = False
                elif ch in (curses.KEY_ENTER, 10, 13):
                    self.search_active = False
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    self.search_query = self.search_query[:-1]
                    self.selected_idx = 0
                elif 32 <= ch <= 126:
                    self.search_query += chr(ch)
                    self.selected_idx = 0
                continue

            if ch == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                    self.handle_touch(mx, my, bstate)
                except curses.error:
                    pass
                continue

            # A keyboard action ends a pending touch double-tap sequence.
            self.touch_tap = None
            if ch in (ord('q'), ord('Q')):
                break
            elif ch == ord('/'):
                self.search_active = True
            elif ch in (ord('m'), ord('v')):
                self.config["view_mode"] = "list" if self.config.get("view_mode") == "grid" else "grid"
                save_config(self.config)
            elif ch in (ord('r'), ord('R')):
                self.rescan()
            elif ch in (ord('s'), ord('S')):
                self.show_store_wizard()
                self.rescan()
            elif ch in (curses.KEY_UP, ord('k')):
                if self.config.get("view_mode") == "grid":
                    cols = self.get_grid_cols()
                    if self.selected_idx >= cols:
                        self.selected_idx -= cols
                else:
                    if self.selected_idx > 0:
                        self.selected_idx -= 1
            elif ch in (curses.KEY_DOWN, ord('j')):
                if self.config.get("view_mode") == "grid":
                    cols = self.get_grid_cols()
                    if self.selected_idx + cols < len(self.filtered_apps):
                        self.selected_idx += cols
                else:
                    if self.selected_idx < len(self.filtered_apps) - 1:
                        self.selected_idx += 1
            elif ch in (curses.KEY_LEFT, ord('h')):
                # In grid mode move one column left, not one item back. In
                # list mode horizontal keys are a no-op for dpad/touch users
                # that don't have a meaningful left/right axis.
                if self.config.get("view_mode") == "grid":
                    cols = max(1, self.get_grid_cols())
                    row = self.selected_idx // cols
                    col = self.selected_idx % cols
                    if col > 0 and self.selected_idx > 0:
                        self.selected_idx -= 1
                # list view: ignore LEFT/H on dpad
            elif ch in (curses.KEY_RIGHT, ord('l')):
                if self.config.get("view_mode") == "grid":
                    cols = max(1, self.get_grid_cols())
                    row = self.selected_idx // cols
                    col = self.selected_idx % cols
                    if col < cols - 1 and self.selected_idx < len(self.filtered_apps) - 1:
                        self.selected_idx += 1
                # list view: ignore RIGHT/L on dpad
            elif ch == curses.KEY_HOME:
                if self.filtered_apps:
                    self.selected_idx = 0
            elif ch == curses.KEY_END:
                if self.filtered_apps:
                    self.selected_idx = len(self.filtered_apps) - 1
            elif ch == curses.KEY_PPAGE:
                self.move_selection(-self.visible_step())
            elif ch == curses.KEY_NPAGE:
                self.move_selection(self.visible_step())
            elif ch in (curses.KEY_ENTER, 10, 13, 32):
                if 0 <= self.selected_idx < len(self.filtered_apps):
                    self.show_app_dialog(self.filtered_apps[self.selected_idx])

    def rescan(self):
        h, w = self.stdscr.getmaxyx()
        self.stdscr.clear()
        msg = "⚡ Scanning installed packages across stores..."
        self.safe_addstr(h // 2, max(0, (w - len(msg)) // 2), msg, curses.color_pair(6) | curses.A_BOLD)
        self.stdscr.refresh()
        self.apps = scan_all_stores(self.config)
        self.filter_apps()
        self.selected_idx = 0
        self.scroll_offset = 0

    def filter_apps(self):
        candidates = self.apps
        if self.store_filter:
            candidates = [a for a in candidates if a.get("store") == self.store_filter]
        if not self.search_query.strip():
            self.filtered_apps = list(candidates)
        else:
            q = self.search_query.lower()
            self.filtered_apps = [
                a for a in candidates
                if q in a["name"].lower() or q in a["store"].lower() or q in a.get("desc", "").lower()
            ]
        if self.selected_idx >= len(self.filtered_apps):
            self.selected_idx = max(0, len(self.filtered_apps) - 1)

    def toggle_store_filter(self, store):
        self.store_filter = None if self.store_filter == store else store
        self.selected_idx = 0
        self.scroll_offset = 0
        self.filter_apps()

    def get_grid_cols(self):
        """Use TUIFI-style flowing icon columns instead of fixed cards."""
        _, w = self.stdscr.getmaxyx()
        return max(1, (w - 2) // 16)

    def grid_row_height(self):
        # Four icon rows plus two lines for the package name/metadata.
        return 6

    def visible_step(self):
        """Number of items moved by a page or a touch swipe."""
        h, _ = self.stdscr.getmaxyx()
        content_top = 3
        content_height = max(1, h - content_top - 1)
        if self.config.get("view_mode") == "grid":
            return max(1, content_height // self.grid_row_height()) * self.get_grid_cols()
        return max(1, content_height)

    def move_selection(self, delta):
        if not self.filtered_apps:
            return
        self.selected_idx = max(0, min(len(self.filtered_apps) - 1, self.selected_idx + delta))

    def scroll_touch(self, direction):
        """Move the selected item in response to a wheel or vertical swipe."""
        # Scrolling invalidates any pending touch double-tap so a swipe
        # followed by an accidental tap cannot open the wrong item.
        self.touch_tap = None
        if self.config.get("view_mode") == "grid":
            direction *= self.get_grid_cols()
        self.move_selection(direction)

    def handle_touch(self, mx, my, bstate):
        if is_scroll_up(bstate):
            self.mouse_press = None
            self.touch_tap = None
            self.scroll_touch(-1)
            return
        if is_scroll_down(bstate):
            self.mouse_press = None
            self.touch_tap = None
            self.scroll_touch(1)
            return

        # Do not activate a card on BUTTON1_PRESSED. Terminals emit that
        # event at the beginning of a drag, which used to make scrolling look
        # like a click. A completed click is handled below.
        if bstate & getattr(curses, "BUTTON1_PRESSED", 0):
            self.mouse_press = (mx, my)
            return
        if not is_left_click(bstate):
            return

        if self.mouse_press is not None:
            _, press_y = self.mouse_press
            self.mouse_press = None
            if abs(my - press_y) > 0:
                self.scroll_touch(-1 if my > press_y else 1)
                return

        for b in self.touch_buttons:
            if b["y"] == my and b["x_start"] <= mx <= b["x_end"]:
                act = b["action"]
                self.touch_tap = None
                if act == "filter_store":
                    self.toggle_store_filter(b["store"])
                elif act == "toggle_view":
                    self.config["view_mode"] = "list" if self.config.get("view_mode") == "grid" else "grid"
                    save_config(self.config)
                elif act == "search":
                    self.search_active = True
                elif act == "rescan":
                    self.rescan()
                elif act == "stores":
                    self.show_store_wizard()
                    self.rescan()
                elif act == "quit":
                    sys.exit(0)
                return

        for card in self.card_zones:
            if card["y_top"] <= my <= card["y_bottom"] and card["x_left"] <= mx <= card["x_right"]:
                idx = card["app_idx"]
                if 0 <= idx < len(self.filtered_apps):
                    self.selected_idx = idx
                    now = time.monotonic()
                    previous = self.touch_tap
                    if previous and previous[0] == idx and now - previous[1] <= TOUCH_DOUBLE_TAP_DELAY:
                        self.touch_tap = None
                        self.show_app_dialog(self.filtered_apps[idx])
                    else:
                        # Touch deliberately uses select-then-open. This keeps
                        # a swipe/tap from launching an app accidentally.
                        self.touch_tap = (idx, now)
                return

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self.touch_buttons = []
        self.card_zones = []

        # TUIFI-style reverse information strip.
        filter_text = f"  • {self.store_filter}" if self.store_filter else ""
        header_text = f" ⚡ TUIPKG  {len(self.apps)} apps{filter_text} "
        self.safe_addstr(0, 0, header_text.ljust(w), curses.color_pair(10) | curses.A_BOLD)

        # Store legend is also a filter toolbar. apt and pkg are aliases for
        # the same APT store; tapping the active alias clears the filter.
        legend = [
            ("a:apt", "APT"), ("p:pkg", "APT"), ("n:npm", "NPM"),
            ("y:pip", "PIP"), ("r:cargo", "RUST"), ("g:go", "GO"),
            ("b:bun", "BUN"), ("c:bin", "BIN"),
        ]
        legend_y = 1
        legend_x = 1
        for label, store in legend:
            token = f" {label} "
            if legend_x > 1 and legend_x + len(token) > w:
                legend_y += 1
                legend_x = 1
            active = self.store_filter == store
            attr = (curses.color_pair(11) if active else curses.color_pair(6)) | curses.A_BOLD
            self.safe_addstr(legend_y, legend_x, token, attr)
            self.touch_buttons.append({
                "y": legend_y,
                "x_start": legend_x,
                "x_end": min(w - 1, legend_x + len(token) - 1),
                "action": "filter_store",
                "store": store,
            })
            legend_x += len(token)

        # Compact controls remain below the clickable legend.
        y = legend_y + 1
        btn_view = f" [ {'Grid' if self.config.get('view_mode') == 'grid' else 'List'} ] "
        btn_search = f" [ 🔍 {'Search' if not self.search_query else self.search_query[:8]} ] "
        btn_rescan = " [ 🔄 Rescan ] "
        btn_stores = " [ ⚙ Stores ] "
        btn_quit = " [ ✕ Quit ] "
        x = 0
        for btext, baction in ((btn_view, "toggle_view"), (btn_search, "search"),
                               (btn_rescan, "rescan"), (btn_stores, "stores"),
                               (btn_quit, "quit")):
            if x + len(btext) <= w:
                self.safe_addstr(y, x, btext, curses.color_pair(6) | curses.A_BOLD)
                self.touch_buttons.append({
                    "y": y, "x_start": x, "x_end": x + len(btext) - 1,
                    "action": baction,
                })
                x += len(btext)

        y += 1
        if self.search_active or self.search_query:
            search_prompt = "🔍 Search: "
            query_disp = self.search_query + ("█" if self.search_active else "")
            self.safe_addstr(y, 1, search_prompt, curses.color_pair(3) | curses.A_BOLD)
            self.safe_addstr(y, 1 + len(search_prompt), query_disp, curses.A_BOLD)
            y += 1
        else:
            self.safe_addstr(y, 1, f"Showing {len(self.filtered_apps)} apps • Tap twice to open", curses.A_DIM)
            y += 1

        content_top = y
        content_height = max(1, h - content_top - 1)
        if self.config.get("view_mode") == "grid":
            self.draw_grid(content_top, content_height, w)
        else:
            self.draw_list(content_top, content_height, w)

        status = " [Tap twice]: Open • [Enter]: Open • [Wheel/Swipe]: Scroll • [M]: View • [Q]: Quit"
        self.safe_addstr(h - 1, 0, status.ljust(w - 1), curses.color_pair(10))
        self.stdscr.refresh()

    def draw_grid(self, top_y, max_h, w):
        """Draw a flowing TUIFI-inspired icon canvas."""
        cols = self.get_grid_cols()
        cell_w = max(12, (w - 2) // cols)
        row_h = self.grid_row_height()
        visible_rows = max(1, max_h // row_h)

        selected_row = self.selected_idx // cols
        if selected_row < self.scroll_offset:
            self.scroll_offset = selected_row
        elif selected_row >= self.scroll_offset + visible_rows:
            self.scroll_offset = selected_row - visible_rows + 1

        start_idx = self.scroll_offset * cols
        end_idx = min(len(self.filtered_apps), start_idx + visible_rows * cols)
        icon_width = min(12, cell_w - 2)

        for idx in range(start_idx, end_idx):
            item = self.filtered_apps[idx]
            rel_idx = idx - start_idx
            row = rel_idx // cols
            col = rel_idx % cols
            cy = top_y + row * row_h
            cx = 1 + col * cell_w + max(0, (cell_w - icon_width) // 2)
            is_selected = idx == self.selected_idx
            store = item["store"]
            badge = STORE_BADGES.get(store, store[:1])
            store_color = curses.color_pair(STORE_COLORS.get(store, 7))
            selected_attr = curses.color_pair(11) | curses.A_BOLD if is_selected else store_color

            name_width = max(8, cell_w - 2)
            name = item["name"][:name_width]
            version = item.get("version", "")
            meta = format_size(item.get("size", 0)) or "—"
            self.card_zones.append({
                "y_top": cy,
                "y_bottom": cy + row_h - 1,
                "x_left": 1 + col * cell_w,
                "x_right": min(w - 1, 1 + (col + 1) * cell_w - 1),
                "app_idx": idx,
            })

            icon_lines = icon_for_store(store).split('\n')
            for line_no, line in enumerate(icon_lines):
                line = line[:icon_width].center(icon_width)
                attr = selected_attr if is_selected else store_color
                self.safe_addstr(cy + line_no, cx, line, attr)

            name_x = 1 + col * cell_w
            name_attr = curses.color_pair(11) | curses.A_BOLD if is_selected else curses.A_BOLD
            meta_attr = curses.color_pair(11) | curses.A_DIM if is_selected else curses.A_DIM
            self.safe_addstr(cy + 4, name_x, name.center(name_width)[:name_width], name_attr)
            self.safe_addstr(cy + 5, name_x, meta.center(name_width)[:name_width], meta_attr)

    def draw_list(self, top_y, max_h, w):
        visible_rows = max_h
        if self.selected_idx < self.scroll_offset:
            self.scroll_offset = self.selected_idx
        elif self.selected_idx >= self.scroll_offset + visible_rows:
            self.scroll_offset = self.selected_idx - visible_rows + 1

        start_idx = self.scroll_offset
        end_idx = min(len(self.filtered_apps), start_idx + visible_rows)

        for row_idx, idx in enumerate(range(start_idx, end_idx)):
            item = self.filtered_apps[idx]
            cy = top_y + row_idx
            is_selected = (idx == self.selected_idx)

            store = item["store"]
            store_color = curses.color_pair(STORE_COLORS.get(store, 7))

            self.card_zones.append({
                "y_top": cy,
                "y_bottom": cy,
                "x_left": 0,
                "x_right": w - 1,
                "app_idx": idx
            })

            badge = f"[{store}]".ljust(6)
            name = item["name"]
            ver = item.get("version", "")
            size_str = format_size(item["size"]) if item.get("size") else ""

            line_str = f" {badge} {name:<20} {ver:<10} {size_str:>8}"
            line_str = line_str.ljust(w)[:w]

            if is_selected:
                self.safe_addstr(cy, 0, line_str, curses.color_pair(11) | curses.A_BOLD)
            else:
                self.safe_addstr(cy, 0, f" {badge}", store_color | curses.A_BOLD)
                rest = line_str[len(badge) + 1:]
                self.safe_addstr(cy, len(badge) + 1, rest)

    def show_app_dialog(self, app):
        show_app_dialog(self, app)

    def show_run_window(self, app):
        show_run_window(self, app)

    def show_store_wizard(self):
        show_store_wizard(self)
