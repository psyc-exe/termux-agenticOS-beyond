"""User-profile discovery and command scoping for multi-user scans."""

import os
import shutil
from pathlib import Path

try:
    import pwd
except ImportError:  # pragma: no cover - Windows has no passwd database
    pwd = None


class ProfileCommandError(RuntimeError):
    """Raised when a foreign profile cannot be safely entered."""


def _effective_uid():
    return getattr(os, "geteuid", os.getuid)()


def _current_profile():
    home = Path.home().resolve()
    try:
        username = pwd.getpwuid(os.getuid()).pw_name if pwd else None
    except (KeyError, ImportError):
        username = None
    return {
        "owner": username or os.environ.get("USER", "unknown"),
        "home": home,
        "current": True,
    }


def get_profiles(config=None):
    """Return profiles visible to this process.

    Normal users get only their own profile. Root gets existing passwd homes
    when aggregation is enabled, which is an explicit opt-in policy defaulted
    on for the root account.
    """
    current = _current_profile()
    if _effective_uid() != 0 or (config or {}).get("root_aggregate_profiles", True) is False:
        return [current]

    profiles = []
    seen = set()
    try:
        entries = pwd.getpwall() if pwd else []
    except (AttributeError, ImportError):
        entries = []
    for entry in entries:
        home = Path(entry.pw_dir).expanduser()
        if not home.is_dir():
            continue
        resolved = home.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        profiles.append({
            "owner": entry.pw_name,
            "home": resolved,
            "current": resolved == current["home"] and entry.pw_uid == os.getuid(),
        })

    if current["home"] not in seen and current["home"].is_dir():
        profiles.insert(0, current)
    return profiles or [current]


def find_profile_command(name, profile):
    """Find a manager in the profile's common user-local locations."""
    if profile.get("current"):
        return shutil.which(name)
    candidates = [
        profile["home"] / ".local" / "bin" / name,
        profile["home"] / "bin" / name,
        profile["home"] / ".bun" / "bin" / name,
        profile["home"] / ".cargo" / "bin" / name,
        profile["home"] / "go" / "bin" / name,
        profile["home"] / ".volta" / "bin" / name,
        profile["home"] / ".asdf" / "shims" / name,
    ]
    nvm_bin = profile["home"] / ".nvm" / "versions" / "node"
    if nvm_bin.is_dir():
        candidates.extend(path / "bin" / name for path in sorted(nvm_bin.iterdir(), reverse=True))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def configured_roots(config, store, home):
    """Expand configured roots for a store, supporting ``{home}``."""
    result = []
    values = (config or {}).get("custom_roots", {}).get(store, [])
    for value in values:
        path_text = str(value).replace("{home}", str(home))
        path = Path(path_text).expanduser()
        if not path.is_absolute():
            path = home / path
        result.append(path)
    return result


def scoped_command(command, profile):
    """Run a package-manager command as a foreign profile when root scans it.

    Falling back to a root command would mix root's HOME and package database
    with another user's data, and could make a later uninstall destructive.
    """
    if profile.get("current") or _effective_uid() != 0:
        return list(command)
    runuser = shutil.which("runuser")
    if not runuser:
        raise ProfileCommandError(
            f"Cannot safely run a command for profile {profile['owner']}: runuser is unavailable"
        )
    home = str(profile["home"])
    path = os.environ.get("PATH", "")
    user_path = ":".join((f"{home}/.local/bin", f"{home}/bin", f"{home}/.bun/bin", path))
    return [runuser, "-u", profile["owner"], "--", "env", f"HOME={home}",
            f"USER={profile['owner']}", f"PATH={user_path}", *command]


def add_profile_metadata(app, profile):
    """Annotate a discovered app without changing its existing identity."""
    app["owner"] = profile["owner"]
    app["home"] = str(profile["home"])
    app["scope"] = "current" if profile.get("current") else "user"
    return app
