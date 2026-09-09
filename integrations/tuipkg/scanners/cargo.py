import os
import shutil
import subprocess

from ..profiles import add_profile_metadata, find_profile_command, get_profiles, scoped_command


def _binary_size(path):
    try:
        return os.path.getsize(path) if path else 0
    except OSError:
        return 0


def scan_cargo(config=None):
    apps = []
    seen = set()
    for profile in get_profiles(config):
        try:
            cargo_command = find_profile_command("cargo", profile)
            if not cargo_command:
                continue
            command = scoped_command([cargo_command, "install", "--list"], profile)
            c_res = subprocess.run(command, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError, RuntimeError):
            continue
        if c_res.returncode != 0:
            continue
        for line in c_res.stdout.splitlines():
            if not line.startswith(" ") and ":" in line:
                parts = line.split(":", 1)
                package = parts[0].strip()
                version = parts[1].strip().lstrip("v")
                if not package or (profile["owner"], package) in seen:
                    continue
                seen.add((profile["owner"], package))
                binary = profile["home"] / ".cargo" / "bin" / package
                binary_path = str(binary) if binary.is_file() else (shutil.which(package) or "")
                app = {
                    "id": f"cargo:{profile['owner']}:{package}",
                    "name": package,
                    "store": "RUST",
                    "version": version,
                    "size": _binary_size(binary_path),
                    "bin": binary_path or package,
                    "managed_root": str(profile["home"] / ".cargo" / "bin"),
                    "desc": f"Rust/Cargo binary ({package})",
                    "manager_command": cargo_command,
                }
                apps.append(add_profile_metadata(app, profile))
    return apps
