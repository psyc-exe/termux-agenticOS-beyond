"""Small helpers for dealing with ncurses mouse event bitmasks."""

import curses


def _flag(name):
    return getattr(curses, name, 0)


def is_scroll_up(bstate):
    return bool(bstate & (_flag("BUTTON4_PRESSED") | _flag("BUTTON4_CLICKED")))


def is_scroll_down(bstate):
    return bool(bstate & (_flag("BUTTON5_PRESSED") | _flag("BUTTON5_CLICKED")))


def is_left_click(bstate):
    """Return true for a completed left click, never for the press event.

    Some terminals report a release instead of CLICKED.  Accepting release
    keeps touch input working, while ignoring PRESSED prevents a drag from
    opening/toggling the item under the finger.
    """
    clicked = _flag("BUTTON1_CLICKED")
    released = _flag("BUTTON1_RELEASED")
    return bool(bstate & (clicked | released))
