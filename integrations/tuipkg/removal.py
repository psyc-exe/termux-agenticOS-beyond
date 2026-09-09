"""Build and execute safe uninstall plans for discovered applications."""

import os
import shutil
import subprocess
from pathlib import Path

from .profiles import scoped_command


class RemovalPlanError(ValueError):
    """Raised when an app cannot be mapped to a safe uninstall operation."""


def _command_exists(command, command_exists):
    return bool(command_exists(command))


def _path_inside(path, roots):
    candidate = Path(path).expanduser().resolve()
    for root in roots:
        try:
            candidate.relative_to(root.expanduser().resolve())
            return candidate
        except ValueError:
            continue
    raise RemovalPlanError(f"Refusing to remove a file outside managed bin directories: {path}")


def _managed_bin_path(app):
    raw_path = app.get("bin")
    if not raw_path:
        raise RemovalPlanError("This binary has no recorded path")

    home = Path(app.get("home", Path.home()))
    roots = [
        home / ".local" / "bin",
        home / "bin",
        home / "go" / "bin",
        home / ".bun" / "bin",
        home / ".cargo" / "bin",
    ]
    if app.get("managed_root"):
        roots.append(Path(app["managed_root"]))
    path = _path_inside(raw_path, roots)
    if not path.is_file():
        raise RemovalPlanError(f"Managed binary does not exist: {path}")
    return path


def _profile_for_app(app):
    if app.get("scope") != "user" or not app.get("owner") or not app.get("home"):
        return None
    return {"owner": app["owner"], "home": Path(app["home"]), "current": False}


def _scoped(command, app):
    profile = _profile_for_app(app)
    executable = app.get("manager_command")
    if executable:
        command = [executable, *command[1:]]
    if not profile:
        return list(command)
    try:
        return scoped_command(command, profile)
    except RuntimeError as exc:
        raise RemovalPlanError(str(exc)) from exc


def build_removal_plan(app, command_exists=shutil.which):
    """Return ``(commands, dependency_note)`` for an app.

    Commands are argv lists, so package names and paths are never interpreted
    by a shell. APT's autoremove is deliberately a second command and is only
    run if the package uninstall succeeds. Foreign-profile commands are
    wrapped with ``runuser`` when TUIPKG itself is running as root.
    """
    store = app.get("store")
    name = app.get("name", "")
    if not name:
        raise RemovalPlanError("Application has no package name")

    if store == "APT":
        if _command_exists("pkg", command_exists):
            return ([
                ["pkg", "uninstall", "-y", name],
                ["pkg", "autoremove", "-y"],
            ], "orphaned APT dependencies are cleaned with autoremove")
        if _command_exists("apt-get", command_exists):
            return ([
                ["apt-get", "remove", "-y", name],
                ["apt-get", "autoremove", "-y"],
            ], "orphaned APT dependencies are cleaned with autoremove")
        raise RemovalPlanError("Neither pkg nor apt-get is available")

    if store == "NPM":
        return ([_scoped(["npm", "uninstall", "--global", name], app)],
                "NPM removes dependencies owned only by this global package")

    if store == "PIP":
        manager = app.get("manager")
        if manager == "pipx":
            return ([_scoped(["pipx", "uninstall", name], app)],
                    "the pipx virtual environment and its dependencies are removed")
        if app.get("pip_root") and not app.get("manager_command"):
            raise RemovalPlanError(
                "Configured Python root has no matching pip executable; refusing an ambiguous uninstall"
            )
        if _command_exists("pip-autoremove", command_exists):
            return ([_scoped(["pip-autoremove", name, "-y"], app)],
                    "pip-autoremove removes dependencies no longer needed by other packages")
        return ([_scoped(["pip", "uninstall", "-y", name], app)],
                "direct package removed; pip alone does not safely remove dependencies")

    if store == "RUST":
        return ([_scoped(["cargo", "uninstall", name], app)],
                "Cargo uninstall removes the installed binaries; build-cache files remain")

    if store == "BUN":
        return ([_scoped(["bun", "remove", "--global", name], app)],
                "Bun removes dependencies owned only by this global package")

    if store in {"BIN", "GO"}:
        path = _managed_bin_path(app)
        return ([["__remove_file__", str(path)]], "only the managed binary is removed")

    raise RemovalPlanError(f"Unknown application store: {store}")


def run_removal_plan(commands, runner=subprocess.run, unlink=Path.unlink):
    """Run a removal plan and return ``(success, failed_command, result)``."""
    for command in commands:
        if command and command[0] == "__remove_file__":
            try:
                unlink(Path(command[1]))
                continue
            except OSError:
                return False, command, None

        try:
            result = runner(command, check=False)
        except OSError:
            return False, command, None
        if result.returncode != 0:
            return False, command, result
    return True, None, None
