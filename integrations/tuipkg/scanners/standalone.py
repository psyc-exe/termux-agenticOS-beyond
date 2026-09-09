import os
from pathlib import Path

from ..profiles import add_profile_metadata, configured_roots, get_profiles


def scan_standalone(existing_names=None, existing_bins=None, config=None):
    if existing_names is None:
        existing_names = set()
    else:
        existing_names = set(existing_names)
    if existing_bins is None:
        existing_bins = set()
    else:
        existing_bins = set(existing_bins)

    apps = []
    seen_paths = set()
    for profile in get_profiles(config):
        home = profile["home"]
        search_dirs = [home / ".local" / "bin", home / "bin"]
        search_dirs.extend(configured_roots(config, "standalone", home))
        for search_dir in search_dirs:
            try:
                resolved_dir = search_dir.resolve()
            except OSError:
                continue
            if resolved_dir in seen_paths or not search_dir.is_dir():
                continue
            seen_paths.add(resolved_dir)
            for path in search_dir.iterdir():
                if path.name == "tuipkg":
                    continue
                name_lower = path.name.lower()
                if (path.is_file() and os.access(path, os.X_OK)
                        and name_lower not in existing_names
                        and name_lower not in existing_bins):
                    # Skip symlinks that point into other managed directories
                    # (e.g. ~/.local/bin/sgpt -> pipx venv, ~/.local/bin/rtfm -> cargo bin)
                    if path.is_symlink():
                        try:
                            target = path.resolve()
                            managed_prefixes = [
                                Path.home() / ".local" / "share" / "pipx",
                                Path.home() / ".cargo" / "bin",
                                Path.home() / ".bun" / "bin",
                            ]
                            if any(str(target).startswith(str(p)) for p in managed_prefixes):
                                existing_names.add(name_lower)
                                existing_bins.add(name_lower)
                                continue
                        except OSError:
                            pass
                    app = {
                        "id": f"bin:{profile['owner']}:{path.name}",
                        "name": path.name,
                        "store": "BIN",
                        "version": "",
                        "size": path.stat().st_size,
                        "bin": str(path),
                        "managed_root": str(resolved_dir),
                        "desc": f"Custom/Curl binary in {path.parent.name}",
                    }
                    apps.append(add_profile_metadata(app, profile))
                    existing_names.add(name_lower)
                    existing_bins.add(name_lower)
    return apps
