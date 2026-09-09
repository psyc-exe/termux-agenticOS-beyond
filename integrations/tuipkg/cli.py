import curses
from .app import TuiPkgApp

def main():
    curses.wrapper(lambda stdscr: TuiPkgApp(stdscr).run())

if __name__ == "__main__":
    main()
