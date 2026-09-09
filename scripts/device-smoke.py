#!/usr/bin/env python3
"""On-device PTY smoke checks; prints assertions, never shell configuration values."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("AGENTICOS_STATE", Path.home() / ".local/state/agenticos"))
ENV = {**os.environ, "TERM": "xterm-256color", "PATH": str(STATE / "bin") + ":" + os.environ["PATH"]}


def terminal(name, command, expected, keys, seconds=12, cols=88):
    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe(command[0], command, ENV)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 32, cols, 0, 0))
    output = bytearray()
    start = time.monotonic()
    sent = 0
    ended = False
    while time.monotonic() - start < seconds:
        elapsed = time.monotonic() - start
        if sent < len(keys) and elapsed > keys[sent][0]:
            os.write(fd, keys[sent][1])
            sent += 1
        if select.select([fd], [], [], 0.1)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > 2_000_000:
                break
        child, status = os.waitpid(pid, os.WNOHANG)
        if child:
            ended = True
            break
    if not ended:
        child, status = os.waitpid(pid, os.WNOHANG)
        if not child:
            os.kill(pid, signal.SIGTERM)
            _, status = os.waitpid(pid, 0)
    os.close(fd)
    text = output.decode(errors="replace")
    result = {"test": name, "visible": {word: word in text for word in expected},
              "traceback": "Traceback (most recent call last)" in text,
              "exit": os.waitstatus_to_exitcode(status)}
    print(json.dumps(result), flush=True)
    return all(result["visible"].values()) and not result["traceback"] and result["exit"] == 0


def main():
    results = []
    results.append(terminal("store", ["python", str(ROOT / "scripts/software.py")],
                            ["AgenticOS Software", "Install and configure", "tgpt"],
                            [(1, b"\r"), (3, b"\t\r"), (5, b"\t\r")], cols=48))
    results.append(terminal("tgpt-tui", [str(STATE / "bin/tgpt-tui")],
                            ["TGPT TOOLKIT", "powerbrain"], [(3, b"q")]))
    results.append(terminal("sgpt-tui", [str(STATE / "bin/sgpt-tui")],
                            ["SGPT TOOLKIT"], [(3, b"q")]))
    results.append(terminal("tuipkg", [str(STATE / "bin/tuipkg")],
                            ["TUIPKG"], [(9, b"q")], seconds=30))
    script = '''emit fish_prompt
echo __CHECKS__
type -P tgpt
type -P sgpt
type -P cline
type -P kilo
functions -q fish_command_not_found helpme err __agenticos_install; and echo integrations-ok
'''
    fish = subprocess.run(["fish", "-i", "-c", script], env={**ENV, "MORPHE_OFF": "1"},
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
    checks = fish.stdout.split("__CHECKS__\n", 1)[-1]
    ok = fish.returncode == 0 and "integrations-ok" in checks and checks.count(str(STATE / "bin")) == 4
    results.append(ok)
    print(json.dumps({"test": "fish startup and stable PATH", "passed": ok,
                      "paths": [line for line in checks.splitlines() if line.startswith(str(STATE / "bin"))]}))
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
