import curses

STORE_COLORS = {
    "APT": 6,   # Cyan
    "NPM": 2,   # Green
    "PIP": 3,   # Yellow
    "BIN": 5,   # Magenta
    "RUST": 1,  # Red
    "GO": 4,    # Blue
    "BUN": 8,   # Aqua (distinct from PIP yellow)
}

STORE_BADGES = {
    "APT": "A",
    "NPM": "N",
    "PIP": "P",
    "BIN": "C",
    "RUST": "R",
    "GO": "G",
    "BUN": "B",
}


def init_theme_colors():
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_BLUE, -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_CYAN, -1)
    curses.init_pair(7, curses.COLOR_WHITE, -1)
    curses.init_pair(8, curses.COLOR_CYAN, curses.COLOR_BLACK)  # Aqua/light cyan for BUN

    curses.init_pair(10, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(11, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(13, curses.COLOR_BLACK, curses.COLOR_RED)
    curses.init_pair(14, curses.COLOR_WHITE, curses.COLOR_BLUE)
