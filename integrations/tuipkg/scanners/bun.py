import json
import shutil
from pathlib import Path

from ..profiles import add_profile_metadata, configured_roots, get_profiles
from ..utils.files import path_size


def _package_dirs(root):
    if not root.is_dir():
        return
    for item in root.iterdir():
        if item.is_dir() and item.name.startswith("@"):
            for child in item.iterdir():
                if child.is_dir():
                    yield child, f"{item.name}/{child.name}"
        elif item.is_dir():
            yield item, item.name


def scan_bun(config=None):
    """Scan Bun global packages from each visible user profile."""
    apps = []
    seen = set()
    for profile in get_profiles(config):
        home = profile["home"]
        roots = [home / ".bun" / "install" / "global" / "node_modules"]
        roots.extend(configured_roots(config, "bun", home))
        for root in roots:
            try:
                resolved_root = root.resolve()
            except OSError:
                continue
            if resolved_root in seen:
                continue
            seen.add(resolved_root)
            for package_dir, package_name in _package_dirs(root):
                package_json = package_dir / "package.json"
                try:
                    with package_json.open(encoding="utf-8", errors="ignore") as stream:
                        data = json.load(stream)
                except (OSError, ValueError):
                    continue
                bin_field = data.get("bin")
                if isinstance(bin_field, str):
                    bin_names = [package_name.rsplit("/", 1)[-1]]
                elif isinstance(bin_field, dict):
                    bin_names = list(bin_field)
                else:
                    continue
                profile_bin = home / ".bun" / "bin"
                valid_bins = [
                    name for name in bin_names
                    if (profile_bin / name).is_file() or shutil.which(name)
                ]
                app = {
                    "id": f"bun:{profile['owner']}:{package_name}",
                    "name": package_name,
                    "store": "BUN",
                    "version": data.get("version", ""),
                    "size": path_size(package_dir),
                    "bin": str(profile_bin / (valid_bins or bin_names)[0])
                    if (profile_bin / (valid_bins or bin_names)[0]).exists()
                    else (valid_bins or bin_names)[0],
                    "bins": valid_bins or bin_names,
                    "desc": data.get("description", f"Bun global package ({package_name})"),
                }
                apps.append(add_profile_metadata(app, profile))
    return apps
