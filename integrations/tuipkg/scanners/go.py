import os
from pathlib import Path

from ..profiles import add_profile_metadata, configured_roots, get_profiles


def scan_go(config=None):
    apps = []
    seen = set()
    for profile in get_profiles(config):
        home = profile["home"]
        roots = [home / "go" / "bin"]
        if profile.get("current"):
            for value in os.environ.get("GOBIN", "").split(os.pathsep):
                if value:
                    roots.append(Path(value).expanduser())
            for value in os.environ.get("GOPATH", "").split(os.pathsep):
                if value:
                    roots.append(Path(value).expanduser() / "bin")
        roots.extend(configured_roots(config, "go", home))
        for root in roots:
            try:
                resolved_root = root.resolve()
            except OSError:
                continue
            if resolved_root in seen or not root.is_dir():
                continue
            seen.add(resolved_root)
            for path in root.iterdir():
                if path.is_file() and os.access(path, os.X_OK):
                    app = {
                        "id": f"go:{profile['owner']}:{path.name}",
                        "name": path.name,
                        "store": "GO",
                        "version": "",
                        "size": path.stat().st_size,
                        "bin": str(path),
                        "managed_root": str(resolved_root),
                        "desc": f"Go compiled binary ({path.name})",
                    }
                    apps.append(add_profile_metadata(app, profile))
    return apps
