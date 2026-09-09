import json
import shutil
import subprocess
from pathlib import Path

from ..profiles import (add_profile_metadata, configured_roots, find_profile_command,
                         get_profiles, scoped_command)
from ..utils.files import path_size


def _bin_available(name, profile):
    if shutil.which(name):
        return True
    for root in (profile["home"] / ".npm-global" / "bin",
                 profile["home"] / ".local" / "bin",
                 profile["home"] / ".local" / "share" / "npm" / "bin"):
        if (root / name).is_file():
            return True
    return False


def get_node_modules_dirs(config=None, profile=None, manager_command=None):
    profile = profile or get_profiles(config)[0]
    dirs = []
    try:
        res = subprocess.run(
            scoped_command([manager_command or "npm", "root", "-g"], profile),
            capture_output=True, text=True, timeout=3,
        )
        if res.returncode == 0:
            root = Path(res.stdout.strip())
            if root.is_dir():
                dirs.append(root)
    except (OSError, subprocess.SubprocessError, RuntimeError):
        pass

    home = profile["home"]
    defaults = [
        home / ".npm-global" / "lib" / "node_modules",
        home / ".local" / "lib" / "node_modules",
        home / ".local" / "share" / "npm" / "node_modules",
    ]
    # System-global NPM belongs to the current/system profile. Adding it once
    # avoids presenting the same package as every user in a root aggregate.
    if profile.get("current"):
        defaults.extend([Path("/usr/local/lib/node_modules"), Path("/usr/lib/node_modules")])
    for root in defaults + configured_roots(config, "npm", home):
        if root.is_dir() and root not in dirs:
            dirs.append(root)
    return dirs


def scan_npm(config=None):
    apps = []
    seen = set()
    for profile in get_profiles(config):
        manager_command = find_profile_command("npm", profile)
        if not manager_command:
            continue
        for nm_dir in get_node_modules_dirs(config, profile, manager_command):
            for item in nm_dir.iterdir():
                package_dirs = []
                if item.is_dir() and item.name.startswith("@"):
                    package_dirs.extend(
                        (sub, f"{item.name}/{sub.name}")
                        for sub in item.iterdir() if sub.is_dir()
                    )
                elif item.is_dir():
                    package_dirs.append((item, item.name))

                for pkg_dir, pkg_name in package_dirs:
                    key = str(pkg_dir.resolve())
                    if key in seen or pkg_name == "npm":
                        continue
                    pkg_json = pkg_dir / "package.json"
                    if not pkg_json.is_file():
                        continue
                    try:
                        with pkg_json.open(encoding="utf-8", errors="ignore") as stream:
                            data = json.load(stream)
                    except (OSError, ValueError):
                        continue

                    bin_field = data.get("bin")
                    if isinstance(bin_field, str):
                        bin_names = [pkg_name.rsplit("/", 1)[-1]]
                    elif isinstance(bin_field, dict):
                        bin_names = list(bin_field)
                    else:
                        continue
                    valid_bins = [name for name in bin_names if _bin_available(name, profile)]
                    app = {
                        "id": f"npm:{profile['owner']}:{pkg_name}",
                        "name": pkg_name,
                        "store": "NPM",
                        "version": data.get("version", ""),
                        "size": path_size(pkg_dir),
                        "bin": (valid_bins or bin_names)[0],
                        "bins": valid_bins or bin_names,
                        "desc": data.get("description", f"NPM global package ({pkg_name})"),
                        "manager_command": manager_command,
                    }
                    apps.append(add_profile_metadata(app, profile))
                    seen.add(key)
    return apps
