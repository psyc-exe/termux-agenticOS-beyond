"""
TUIFI-style box-drawing icons for TUIPKG package tiles.

Mirrors the art style of TUIFIManager's TUIFIProfile system:
- 4-line tall box-drawing icons with block shading (█ ▓ ▒ ░) and
  box-drawing characters (┏━┓┗┛┃┇╋┳┻┣┫)
- Each store gets a distinct icon matching its identity
- All icons have consistent character width per icon (9 or 11 chars per line)
- Folder-style icons for directories (like :folder, :empty_folder in TUIFI)
"""

# ---------------------------------------------------------------------------
# Store icons — TUIFI-style 4-line box drawings, 11 chars per line
# ---------------------------------------------------------------------------

APT_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█A▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

NPM_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█N▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

PIP_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█P▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

BIN_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█C▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

RUST_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█R▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

GO_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█G▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

BUN_ICON = (
    " ┏━━━━━━━━┓\n"
    " ┃░▒█B▒█▒▒┃\n"
    " ┃▒▒┏━━┓▒▒┃\n"
    " ┗━━┻━━┻━━┛"
)

# "All / generic" tile icon — mirrors TUIFI's :all profile icon (9 chars)
ALL_ICON = (
    " ┏━━━━━┳┓\n"
    " ┃▀┇▀┇╋╋┫\n"
    " ┃▀┇┇╋╋╋┫\n"
    " ┗━┻┻┻┻┻┛"
)

# Folder icon — mirrors TUIFI's :folder profile icon (8 chars)
FOLDER_ICON = (
    "█████▒⎫⎫\n"
    "█████▒▐┇\n"
    "█████▒▐┃\n"
    "▀▀▀▀▀  ┘"
)

# Empty folder icon — mirrors TUIFI's :empty_folder profile icon (8 chars)
EMPTY_FOLDER_ICON = (
    "█████ ⎫⎫\n"
    "█████ ┇┇\n"
    "█████ ┃┃\n"
    "▀▀▀▀▀  ┘"
)

# File icon — mirrors TUIFI's :file profile icon (8 chars)
FILE_ICON = (
    "┏┏━━━━┓┓\n"
    "┇┛FILE ┃\n"
    "┃┋┇┃┃┇┋┃\n"
    "┗━━━━━━┛"
)

# Generic binary / executable icon (9 chars)
BINARY_ICON = (
    " ┏━━━━━━┓\n"
    " ┃░BIN░░┃\n"
    " ┃▒▒┏━┓▒┃\n"
    " ┗━━━━━━┛"
)

# Default fallback icon (9 chars)
DEFAULT_ICON = (
    " ┏━━━━━━┓\n"
    " ┃░░░░░░┃\n"
    " ┃▒▒┏━┓▒┃\n"
    " ┗━━━━━━┛"
)


def icon_for_store(store: str) -> str:
    """Return a TUIFI-style 4-line icon string for a store key."""
    return {
        "APT": APT_ICON,
        "NPM": NPM_ICON,
        "PIP": PIP_ICON,
        "BIN": BIN_ICON,
        "RUST": RUST_ICON,
        "GO": GO_ICON,
        "BUN": BUN_ICON,
    }.get(store, DEFAULT_ICON)


def icon_for_store_name(store: str, name: str = "") -> str:
    """Return a TUIFI-style icon with the store badge letter embedded."""
    letter = {
        "APT": "A", "NPM": "N", "PIP": "P",
        "BIN": "C", "RUST": "R", "GO": "G", "BUN": "B",
    }.get(store, "?")

    return (
        " ┏━━━━━━━━┓\n"
        f" ┃░▒█{letter}▒█▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    )


# ---------------------------------------------------------------------------
# Directory / folder icons (TUIFI-style) — 11 chars per line
# ---------------------------------------------------------------------------

DIR_ICONS = {
    "apt": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
    "npm": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
    "pip": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
    "cargo": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
    "go": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
    "bun": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
    "standalone": (
        " ┏━━━━━━━━┓\n"
        " ┃░▒▒▒▒▒▒▒┃\n"
        " ┃▒▒┏━━┓▒▒┃\n"
        " ┗━━┻━━┻━━┛"
    ),
}
