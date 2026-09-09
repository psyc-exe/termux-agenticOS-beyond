#!/usr/bin/env python3
"""Termux software store: reviewed selections, isolated tools and patch receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("AGENTICOS_STATE", Path.home() / ".local/state/agenticos"))
PREFIX = Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"))
ISOLATED = os.environ.get("AGENTICOS_ISOLATED_HOST") == "1"
DEFAULTS = ["tuipkg", "tgpt", "tgpt-tui"]
SHELL_FEATURES = ["shell-theme", "shell-aliases", "shell-hints", "shell-fuzzy", "shell-discovery"]
BUILTINS = {
    "tuipkg": ("Package and app launcher; includes tldr examples", "tuipkg"),
    "tgpt": ("Full native tgpt 2.14.0; PowerBrain default; chat via ask", "tgpt"),
    "tgpt-tui": ("Your tgpt menus: chat, shell, code, providers, MCP, tools", "tgpt-tui"),
    "tgpt-mcp": ("Configure a PowerBrain worker for OpenCode; free, no user key", "opencode"),
    "beginner": ("Enable all: Fish, theme, hints, examples, fuzzy finding, shortcuts", "fish"),
    "vanilla": ("Bash login shell; store and stable command PATH remain available", "bash"),
    "fish": ("Fish shell integration; add individual features below", "fish"),
    "shell-theme": ("Configure Cyberdream Starship prompt and Fish colors", "fish"),
    "shell-aliases": ("Configure app/AI shortcuts, eza, bat and directory aliases", "fish"),
    "shell-hints": ("Configure typo/package hints, tldr, error help and AI drafting", "fish"),
    "shell-fuzzy": ("Configure fzf history and fd hidden-file finder with previews", "fish"),
    "shell-discovery": ("Reveal new commands and help examples after installation", "fish"),
    "sgpt": ("shell-gpt 1.5.1 via isolated pipx; provider setup required", "sgpt"),
    "sgpt-tui": ("Your shell-gpt TUI, using the same isolated interpreter", "sgpt-tui"),
    "cline": ("Cline 3.0.61 + glibc/Bash patches; ARM64; update locked", "cline"),
    "kilo": ("Kilo 7.5.14 + glibc launcher patch; ARM64; update locked", "kilo"),
}
VOID = json.loads((ROOT / "config/void-ai.json").read_text(encoding="utf8"))
CATALOG = {key: {"description": value[0], "command": value[1], "kind": "builtin"}
           for key, value in BUILTINS.items()}
CATALOG.update({"void:" + p["id"]: {**p, "kind": "void"} for p in VOID["packages"]})


def run(argv, **kwargs):
    print("+ " + shlex.join(map(str, argv)), flush=True)
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".new")
    temp.write_text(content, encoding="utf8")
    temp.chmod(0o700)
    temp.replace(path)


def wrapper(name, argv, env=None):
    env = env or {}
    write(STATE / "bin" / name, "#!" + str(PREFIX / "bin/bash") + "\n" +
          "exec env " + shlex.join([f"{k}={v}" for k, v in env.items()] + list(map(str, argv))) + ' "$@"\n')


def receipt(name, files, version="local"):
    data = {"id": name, "version": version, "locked": True,
            "files": {str(p.resolve()): digest(p) for p in files}, "created": int(time.time())}
    write(STATE / "receipts" / (name.replace(":", "_") + ".json"), json.dumps(data, indent=2) + "\n")


def status(name):
    if name.startswith("shell-"):
        enabled = Path.home() / ".config/agenticos/fish-enabled"
        if not enabled.exists() or name.removeprefix("shell-") not in enabled.read_text().splitlines():
            return "available"
    file = STATE / "receipts" / (name.replace(":", "_") + ".json")
    if not file.exists():
        return "unmanaged" if shutil.which(CATALOG[name]["command"]) else "available"
    data = json.loads(file.read_text())
    changed = [p for p, sha in data["files"].items() if not Path(p).is_file() or digest(p) != sha]
    return "CHANGED: repair required" if changed else "installed / locked"


def require_termux():
    if not (PREFIX / "bin/pkg").is_file() or not shutil.which("getprop"):
        raise RuntimeError("Install/launch requires native Termux. --list and --plan work on any host.")
    if not STATE.resolve().is_relative_to(Path.home().resolve()) or STATE.resolve() == Path.home().resolve():
        raise RuntimeError("Managed state must be a subdirectory of private Termux HOME")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    (STATE / "bin").mkdir(exist_ok=True)


def activate():
    """Owned entry points; no overwrite of existing package-manager binaries."""
    wrapper("agenticos-software", ["python", ROOT / "scripts/software.py"], {"AGENTICOS_STATE": STATE})
    if ISOLATED:
        wrapper("agenticos-software", ["python", ROOT / "scripts/software.py"],
                {"AGENTICOS_STATE": STATE, "AGENTICOS_ISOLATED_HOST": "1"})
        return
    for name in ("agenticos-software", "agenticos-chat"):
        target = STATE / "bin" / ("ask" if name == "agenticos-chat" else name)
        link = PREFIX / "bin" / name
        if target.exists() and not link.exists() and not link.is_symlink():
            link.symlink_to(target)
    # A single stable facade for npm, pipx, Go and ported tools. No package paths in RC files.
    bashrc = Path.home() / ".bashrc"
    existing = bashrc.read_text() if bashrc.exists() else ""
    begin, end = "# >>> agenticos PATH >>>", "# <<< agenticos PATH <<<"
    block = begin + "\nexport PATH=" + shlex.quote(str(STATE / "bin")) + ':"$PATH"\n' + end
    if begin in existing and end in existing:
        start, stop = existing.index(begin), existing.index(end) + len(end)
        updated = existing[:start] + block + existing[stop:]
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"
    if updated != existing:
        if bashrc.exists():
            backup = STATE / "backups" / ("bashrc." + str(time.time_ns()))
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bashrc, backup)
        write(bashrc, updated)
    # Fish PATH activation is independent of the optional beginner features.
    fishpath = Path.home() / ".config/fish/conf.d/agenticos-path.fish"
    quoted = "'" + str(STATE / "bin").replace("'", "\\'") + "'"
    write(fishpath, "fish_add_path --prepend --move --path " + quoted + "\n")


def install_tgpt():
    binary = STATE / "tgpt/bin/tgpt"
    existing = PREFIX / "bin/tgpt"
    if not binary.exists() and existing.exists():
        result = run([existing, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20)
        if result.stdout.strip() == "tgpt 2.14.0":
            binary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, binary)
            write(STATE / "tgpt/staged.json", json.dumps({"sha256": digest(binary), "origin": str(existing),
                  "version": "2.14.0", "method": "existing native Termux binary snapshot"}) + "\n")
    if not binary.exists():
        candidate = subprocess.run(["apt-cache", "show", "tgpt=2.14.0"], capture_output=True, text=True)
        if candidate.returncode == 0 and "Package: tgpt" in candidate.stdout:
            run(["apt-get", "install", "-y", "tgpt=2.14.0"])
            binary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, binary)
            write(STATE / "tgpt/staged.json", json.dumps({"sha256": digest(binary), "origin": "APT tgpt=2.14.0"}) + "\n")
    # A staged native build is usable only with its catalog receipt.
    if not binary.exists():
        run(["bash", ROOT / "scripts/native-tgpt.sh"], env={**os.environ, "AGENTICOS_STATE": str(STATE)})
    else:
        metadata = STATE / "tgpt/staged.json"
        if not metadata.exists() or json.loads(metadata.read_text()).get("sha256") != digest(binary):
            # setup_tgpt verifies its source/module identity for its own cached builds.
            if not (STATE / "tgpt/module").exists():
                raise RuntimeError("Unverified staged tgpt binary")
            run(["bash", ROOT / "scripts/native-tgpt.sh"], env={**os.environ, "AGENTICOS_STATE": str(STATE)})
    result = run([binary, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    if result.stdout.strip() != "tgpt 2.14.0":
        raise RuntimeError("Unexpected tgpt version")
    config = (STATE / "config/tgpt.conf") if ISOLATED else (Path.home() / ".config/agenticos/tgpt.conf")
    if not config.exists():
        write(config, "AI_PROVIDER=powerbrain\n")
    wrapper("tgpt", ["bash", ROOT / "bin/tgpt.sh", binary], {"AGENTICOS_TGPT_CONFIG": config})
    wrapper("ask", ["bash", ROOT / "bin/chat.sh", binary])
    receipt("tgpt", [binary, STATE / "bin/tgpt", STATE / "bin/ask"], "2.14.0+managed")


def install_sgpt():
    # Isolated pipx home avoids overwriting the user's existing environment.
    run(["bash", ROOT / "scripts/ensure-packages.sh", "python", "python-pip"])
    pipx = shutil.which("pipx")
    if not pipx:
        manager = STATE / "pipx-manager"
        run(["python", "-m", "venv", manager])
        run([manager / "bin/python", "-m", "pip", "install", "pipx==1.8.0"])
        pipx = manager / "bin/pipx"
    env = {**os.environ, "PIPX_HOME": str(STATE / "pipx"), "PIPX_BIN_DIR": str(STATE / "pipx-bin")}
    python = STATE / "pipx/venvs/shell-gpt/bin/python"
    if not python.exists():
        run([pipx, "install", "shell-gpt==1.5.1"], env=env)
    run([python, "-c", "import importlib.metadata; assert importlib.metadata.version('shell-gpt') == '1.5.1'"])
    wrapper("sgpt", [python, "-m", "sgpt"])
    receipt("sgpt", [STATE / "bin/sgpt"], "1.5.1")


def install_agent(name):
    if os.uname().machine != "aarch64":
        raise RuntimeError("These phone-derived patches are tested for ARM64 only.")
    version, package, native = (("3.0.61", "cline", "@cline/cli-linux-arm64") if name == "cline"
                                else ("7.5.14", "@kilocode/cli", "@kilocode/cli-linux-arm64"))
    run(["bash", ROOT / "scripts/ensure-packages.sh", "nodejs-lts", "proot", "glibc-repo"])
    run(["bash", ROOT / "scripts/ensure-packages.sh", "glibc-runner", "bash-glibc"])
    destination = STATE / "agents" / (name + "-" + version)
    # No global npm edits. A failed install stays inactive until verified.
    run(["npm", "install", "--prefix", destination, "--ignore-scripts", "--force", "--save-exact",
         package + "@" + version, native + "@" + version])
    package_dir = destination / "node_modules" / package
    run(["python", ROOT / "scripts/patch-agent.py", name, package_dir, version])
    launcher = package_dir / "bin" / name
    # Explicit binary bypasses any app-managed cached self-update binary.
    env = {(name.upper() + "_BIN_PATH"): destination / "node_modules" / native / "bin" / name}
    wrapper("agenticos-glibc", ["bash", ROOT / "bin/glibc-exec.sh"])
    env["AGENTICOS_GLIBC_RUNNER"] = STATE / "bin/agenticos-glibc"
    if name == "kilo":
        env["KILO_DISABLE_AUTOUPDATE"] = "1"
    wrapper(name, ["bash", ROOT / "bin/agent.sh", name, launcher], env)
    if name == "kilo":
        wrapper("kilocode", ["bash", ROOT / "bin/agent.sh", name, launcher], env)
    result = run([STATE / "bin" / name, "--version"], stdin=subprocess.DEVNULL,
                 capture_output=True, text=True, timeout=45)
    if version not in result.stdout:
        raise RuntimeError("Patched agent version check failed")
    files = [launcher, Path(next(iter(env.values()))), STATE / "bin" / name,
             destination / "package-lock.json"]
    receipt(name, files, version + "+termux.1")


def install_void(name):
    package = CATALOG[name]
    key = ROOT / "config/termuxvoid.gpg"
    if digest(key) != VOID["key_sha256"]:
        raise RuntimeError("TermuxVoid signing-key checksum mismatch")
    # Reuse an existing source. A fresh source uses scoped signed-by, never trusted=yes.
    existing = any("termuxvoid.github.io/repo" in p.read_text(errors="replace")
                   for p in (PREFIX / "etc/apt").rglob("*.list"))
    if not existing:
        dest = PREFIX / "etc/apt/keyrings/agenticos-termuxvoid.gpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(key, dest)
        write(PREFIX / "etc/apt/sources.list.d/agenticos-termuxvoid.list",
              f"deb [arch=all signed-by={dest}] https://termuxvoid.github.io/repo termuxvoid main\n")
    run(["apt-get", "update"])
    # Inspectable version in the plan; fail if that snapshot has left the repository.
    # Maintainer scripts may themselves fetch moving upstream releases (documented).
    run(["apt-get", "install", "-y", package["id"] + "=" + package["version"]])
    run(["apt-mark", "hold", package["id"]])
    command = shutil.which(package["command"])
    receipt(name, [Path(command)] if command else [], package["version"])


def install(name):
    if status(name) == "installed / locked":
        print(name + ": already installed and locked")
        return
    if name == "beginner":
        if ISOLATED:
            raise RuntimeError("Beginner host activation is disabled in isolated test mode")
        for component in ["fish"] + SHELL_FEATURES:
            install(component)
        run(["chsh", "-s", "fish"])
        return
    if name == "vanilla":
        if not ISOLATED:
            run(["chsh", "-s", "bash"])
        activate()
        return
    if name.startswith("shell-"):
        if ISOLATED:
            raise RuntimeError("Shell feature activation is disabled in isolated test mode")
        install("fish")
        run(["bash", ROOT / "scripts/setup-fish.sh", name.removeprefix("shell-")],
            env={**os.environ, "AGENTICOS_STATE": str(STATE)})
        receipt(name, [ROOT / "integrations/fish" / (name.removeprefix("shell-") + ".fish")])
    elif name.startswith("void:"):
        install_void(name)
    elif name == "tgpt":
        install_tgpt()
    elif name == "tgpt-mcp":
        install("tgpt")
        original = PREFIX / "bin/opencode"
        if not original.exists():
            install("void:opencode")
        wrapper("tgpt-mcp", ["python", ROOT / "integrations/tgpt_mcp.py"],
                {"AGENTICOS_TGPT_BIN": STATE / "tgpt/bin/tgpt"})
        wrapper("opencode", ["python", ROOT / "bin/opencode-mcp.py", original, STATE / "bin/tgpt-mcp"])
        receipt(name, [STATE / "bin/tgpt-mcp", STATE / "bin/opencode", ROOT / "integrations/tgpt_mcp.py"])
    elif name == "sgpt":
        install_sgpt()
    elif name in ("cline", "kilo"):
        install_agent(name)
    elif name == "fish":
        if ISOLATED:
            raise RuntimeError("Fish activation is disabled in isolated test mode")
        run(["bash", ROOT / "scripts/setup-fish.sh"], env={**os.environ, "AGENTICOS_STATE": str(STATE)})
        receipt(name, [Path.home() / ".config/fish/conf.d/agenticos.fish"])
    elif name == "tuipkg":
        env = {"PYTHONPATH": ROOT / "integrations"}
        if ISOLATED:
            env["AGENTICOS_TUIPKG_CONFIG"] = STATE / "config/tuipkg"
        wrapper(name, ["python", "-m", "tuipkg"], env)
        receipt(name, [STATE / "bin" / name, ROOT / "integrations/tuipkg/app.py"])
    elif name in ("tgpt-tui", "sgpt-tui"):
        dependency = name.removesuffix("-tui")
        install(dependency)
        python = "python" if dependency == "tgpt" else STATE / "pipx/venvs/shell-gpt/bin/python"
        env = {"PATH": str(STATE / "bin") + os.pathsep + os.environ["PATH"]}
        if dependency == "tgpt":
            env["AGENTICOS_TGPT_CONFIG"] = (STATE / "config/tgpt.conf") if ISOLATED else (Path.home() / ".config/agenticos/tgpt.conf")
        wrapper(name, [python, ROOT / "integrations" / (name + ".py")], env)
        receipt(name, [STATE / "bin" / name, ROOT / "integrations" / (name + ".py")])
    activate()


def launch(name):
    if status(name).startswith("CHANGED"):
        raise RuntimeError("Managed files changed. Inspect and repair before launching.")
    cmd = CATALOG[name]["command"]
    managed = STATE / "bin" / cmd
    argv = [str(managed)] if managed.exists() else [cmd]
    if name == "tgpt":
        argv = [str(STATE / "bin/ask")]
    run(argv)


def dialog(mode, text, values=None):
    size = shutil.get_terminal_size((80, 24))
    height, width = min(22, max(12, size.lines - 2)), min(90, max(30, size.columns - 2))
    cmd = ["dialog", "--stdout", "--title", "AgenticOS Software", "--" + mode, text, str(height), str(width)]
    if values is not None:
        cmd += [str(max(3, height - 9))] + values
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def tui():
    if not shutil.which("dialog"):
        run(["bash", ROOT / "scripts/ensure-packages.sh", "dialog"])
    while True:
        action = dialog("menu", "Select software, review the plan, then install. Cancel exits.",
                        ["install", "Install and configure", "launch", "Launch an installed app", "disable", "Disable a shell feature", "status", "Versions and update locks"])
        if action is None:
            return
        if action == "status":
            dialog("msgbox", "\n".join(k + ": " + status(k) for k in CATALOG))
        elif action == "disable":
            options = [x for k in SHELL_FEATURES for x in (k, CATALOG[k]["description"])]
            selected = dialog("menu", "Disable one component (installed packages are retained)", options)
            if selected:
                disable(selected)
                dialog("msgbox", "Disabled for new Fish sessions. Restart Fish to clear old functions.")
        elif action == "launch":
            options = [x for k, v in CATALOG.items() if status(k) != "available" for x in (k, v["description"])]
            selected = dialog("menu", "Choose an app", options) if options else None
            if selected:
                try:
                    launch(selected)
                except (RuntimeError, subprocess.CalledProcessError) as error:
                    dialog("msgbox", str(error))
        else:
            options = [x for k, v in CATALOG.items() for x in
                       (k, v["description"], "on" if k in DEFAULTS else "off")]
            selected = dialog("checklist", "Space selects; Enter reviews. Select beginner for the whole bundle, or mix individual features.", options)
            if not selected:
                continue
            names = shlex.split(selected)
            if dialog("yesno", plan(names) + "\n\nInstall this selection?") is None:
                continue
            try:
                install_many(names)
                dialog("msgbox", "Installed. Open a new Fish session. Commands: software, apps, tui, ask.")
            except (RuntimeError, subprocess.CalledProcessError) as error:
                dialog("msgbox", "Installation stopped: " + str(error) + "\nCompleted tools remain usable; retry after fixing the error.")


def plan(names):
    if "beginner" in names and "vanilla" in names:
        raise ValueError("Choose beginner or vanilla, not both")
    for name in names:
        if name not in CATALOG:
            raise ValueError("Unknown software: " + name)
    return "\n".join(name + ": " + CATALOG[name]["description"] for name in names) + (
        "\n\nExisting global tools are preserved. Patched tools live in private state. "
        "Managed updates are locked; explicit external npm/pipx operations can bypass this. "
        "TermuxVoid entries use third-party APT scripts; provider accounts may be required.")


def install_many(names):
    # flock releases even after failures; prevents concurrent writers and partial receipts.
    import fcntl
    with (STATE / "software.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name in names:
            install(name)


def disable(name):
    if name not in SHELL_FEATURES:
        raise ValueError("Only optional shell components can be disabled")
    enabled = Path.home() / ".config/agenticos/fish-enabled"
    if enabled.exists():
        lines = [x for x in enabled.read_text().splitlines() if x != name.removeprefix("shell-")]
        write(enabled, "\n".join(lines) + "\n")


def adopt(name):
    """Snapshot exact existing phone builds into the managed location before patching."""
    if name == "sgpt":
        source = Path.home() / ".local/share/pipx/venvs/shell-gpt"
        run([source / "bin/python", "-c", "import importlib.metadata; assert importlib.metadata.version('shell-gpt') == '1.5.1'"])
        destination = STATE / "pipx/venvs/shell-gpt"
        if destination.exists():
            raise RuntimeError("Managed sgpt already exists; use install/repair")
        shutil.copytree(source, destination, symlinks=True)
        wrapper("sgpt", [destination / "bin/python", "-m", "sgpt"])
        files = list((destination / "lib").glob("python*/site-packages/sgpt/**/*.py"))
        receipt(name, [STATE / "bin/sgpt"] + files, "1.5.1+phone-snapshot")
    else:
        version, package, native = (("3.0.61", "cline", "@cline/cli-linux-arm64") if name == "cline"
                                    else ("7.5.14", "@kilocode/cli", "@kilocode/cli-linux-arm64"))
        source = PREFIX / "lib/node_modules" / package
        if json.loads((source / "package.json").read_text())["version"] != version:
            raise RuntimeError("Existing agent version is outside the patch contract")
        destination = STATE / "agents" / (name + "-" + version) / "node_modules"
        main = destination / package
        if main.exists():
            raise RuntimeError("Managed agent already exists; use install/repair")
        shutil.copytree(source, main, symlinks=True)
        native_source = source / "node_modules" / native
        if not native_source.exists():
            native_source = PREFIX / "lib/node_modules" / native
        native_dest = destination / native
        shutil.copytree(native_source, native_dest, symlinks=True)
        run(["python", ROOT / "scripts/patch-agent.py", name, main, version])
        env = {name.upper() + "_BIN_PATH": native_dest / "bin" / name}
        wrapper("agenticos-glibc", ["bash", ROOT / "bin/glibc-exec.sh"])
        env["AGENTICOS_GLIBC_RUNNER"] = STATE / "bin/agenticos-glibc"
        if name == "kilo":
            env["KILO_DISABLE_AUTOUPDATE"] = "1"
        wrapper(name, ["bash", ROOT / "bin/agent.sh", name, main / "bin" / name], env)
        if name == "kilo":
            wrapper("kilocode", ["bash", ROOT / "bin/agent.sh", name, main / "bin" / name], env)
        result = run([STATE / "bin" / name, "--version"], stdin=subprocess.DEVNULL,
                     capture_output=True, text=True, timeout=45)
        if version not in result.stdout:
            raise RuntimeError("Adopted agent failed its version check")
        receipt(name, [STATE / "bin" / name, main / "bin" / name, native_dest / "bin" / name], version + "+phone-snapshot")
    activate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--plan", nargs="*", metavar="TOOL")
    parser.add_argument("--install", nargs="+", metavar="TOOL")
    parser.add_argument("--launch", choices=CATALOG)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--disable", choices=SHELL_FEATURES)
    parser.add_argument("--adopt", nargs="+", choices=["sgpt", "cline", "kilo"])
    args = parser.parse_args()
    if args.list:
        print("\n".join(k + "\t" + v["description"] for k, v in CATALOG.items()))
    elif args.plan is not None:
        print(plan(args.plan or DEFAULTS))
    elif args.status:
        print("\n".join(k + "\t" + status(k) for k in CATALOG))
    else:
        require_termux()
        if args.adopt:
            for name in args.adopt:
                adopt(name)
        elif args.disable:
            disable(args.disable)
        elif args.install:
            print(plan(args.install))
            install_many(args.install)
        elif args.launch:
            launch(args.launch)
        else:
            tui()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print("Software store: " + str(exc), file=sys.stderr)
        sys.exit(1)
