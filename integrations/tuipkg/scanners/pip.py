import importlib.metadata
import json
import os
import shutil
import subprocess
from pathlib import Path

from ..profiles import (add_profile_metadata, configured_roots, find_profile_command,
                         get_profiles, scoped_command)


def _distribution_size(dist):
    total = 0
    for file_path in dist.files or ():
        try:
            total += dist.locate_file(file_path).stat().st_size
        except OSError:
            pass
    return total


def _run(manager, args, profile):
    try:
        executable = find_profile_command(manager, profile)
        if not executable:
            return None
        command = scoped_command([executable, *args], profile)
        return subprocess.run(command, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError, RuntimeError):
        return None


def _command_available(name, profile):
    return bool(find_profile_command(name, profile))


def scan_pip(config=None):
    apps = []
    for profile in get_profiles(config):
        seen = set()

        # pipx applications are isolated per profile.
        if _command_available("pipx", profile):
            px_res = _run("pipx", ["list", "--json"], profile)
            if px_res and px_res.returncode == 0:
                try:
                    px_data = json.loads(px_res.stdout)
                except ValueError:
                    px_data = {}
                venvs = px_data.get("venvs", {})
                if isinstance(venvs, list):
                    venvs = {v.get("package", v.get("name", "")): v for v in venvs if isinstance(v, dict)}
                for app_name, app_info in venvs.items():
                    metadata = app_info.get("metadata", {}).get("main_package", {})
                    # Try to get actual size from pipx venv directory
                    venv_path = app_info.get("venv", {}).get("path")
                    size_bytes = 0
                    if venv_path:
                        venv_dir = Path(venv_path)
                        if venv_dir.exists():
                            size_bytes = sum(f.stat().st_size for f in venv_dir.rglob('*') if f.is_file())

                    # For pipx apps, resolve the real binary names from the venv.
                    # pipx names can differ from the package name (e.g. shell-gpt
                    # package provides the sgpt binary). Check the venv bin dir and
                    # pipx metadata to find the correct primary binary.
                    # pipx stores venvs at ~/.local/share/pipx/venvs/<name>/
                    pipx_bin_names = [app_name]
                    pipx_venv = Path.home() / ".local" / "share" / "pipx" / "venvs" / app_name
                    metadata_apps = metadata.get("apps", [])
                    if pipx_venv.is_dir():
                        venv_bin = pipx_venv / "bin"
                        if venv_bin.is_dir():
                            # Look for pipx metadata "apps" first (the canonical list),
                            # then fall back to scanning the venv bin directory.
                            if metadata_apps:
                                pipx_bin_names = [
                                    name for name in metadata_apps
                                    if (venv_bin / name).is_file()
                                    and os.access(venv_bin / name, os.X_OK)
                                ]
                            if not pipx_bin_names:
                                pipx_bin_names = sorted(
                                    f.name for f in venv_bin.iterdir()
                                    if f.is_file() and os.access(f, os.X_OK)
                                    and f.name not in ("pip", "activate", "activate.csh",
                                                         "activate.fish", "activate.ps1",
                                                         "activate_this.py")
                                    and not f.name.startswith("python")
                                    and not f.name.startswith("python3")
                                )
                            # If we found real binaries, use the first one as the name.
                            if pipx_bin_names:
                                primary_bin_name = pipx_bin_names[0]
                                # Only override if the binary name differs from package name
                                # (e.g. shell-gpt package -> sgpt binary)
                                if primary_bin_name != app_name:
                                    app_name = primary_bin_name

                    app = {
                        "id": f"pip:{profile['owner']}:{app_name}",
                        "name": app_name,
                        "store": "PIP",
                        "version": metadata.get("package_version", ""),
                        "size": size_bytes,
                        "bin": app_name,
                        "bins": pipx_bin_names,
                        "manager": "pipx",
                        "desc": f"Pipx application ({app_name})",
                        "manager_command": find_profile_command("pipx", profile),
                    }
                    apps.append(add_profile_metadata(app, profile))
                    seen.add(app_name.lower())

        # Standard pip packages: list the profile's environment, not root's.
        if _command_available("pip", profile):
            p_res = _run("pip", ["list", "--not-required", "--format=json"], profile)
            if p_res and p_res.returncode == 0:
                try:
                    p_data = json.loads(p_res.stdout)
                except ValueError:
                    p_data = []
                for item in p_data:
                    name = item.get("name", "")
                    if not name or name.lower() in seen or name.lower() in {"pip", "setuptools", "wheel"}:
                        continue
                    version = item.get("version", "")
                    console_scripts = []
                    package_size = 0
                    # importlib.metadata is reliable for the current interpreter;
                    # foreign profiles still get correct inventory, with unknown size.
                    if profile.get("current"):
                        try:
                            dist = importlib.metadata.distribution(name)
                            console_scripts = [
                                ep.name for ep in dist.entry_points
                                if ep.group == "console_scripts"
                            ]
                            package_size = _distribution_size(dist)
                        except Exception:
                            pass
                    valid_bins = [cs for cs in console_scripts if shutil.which(cs)]
                    # Skip packages with no executable binaries (libraries without CLI)
                    if not valid_bins and not console_scripts:
                        continue
                    primary_bin = valid_bins[0] if valid_bins else (name if shutil.which(name) else "")
                    app = {
                        "id": f"pip:{profile['owner']}:{name}",
                        "name": name,
                        "store": "PIP",
                        "version": version,
                        "size": package_size,
                        "bin": primary_bin or name,
                        "bins": valid_bins or console_scripts or [name],
                        "manager": "pip",
                        "desc": f"Python CLI package ({name})",
                        "manager_command": find_profile_command("pip", profile),
                    }
                    apps.append(add_profile_metadata(app, profile))
                    seen.add(name.lower())

        # Optional virtualenv/site-packages roots. These are inventory-only
        # unless a matching venv pip executable exists, so removal cannot
        # accidentally target a different Python environment.
        for custom_root in configured_roots(config, "pip", profile["home"]):
            metadata_paths = [custom_root]
            metadata_paths.extend(custom_root.glob("lib/python*/site-packages"))
            metadata_paths.extend(custom_root.glob("Lib/site-packages"))
            manager_command = None
            for candidate in (custom_root / "bin" / "pip", custom_root / "Scripts" / "pip.exe"):
                if candidate.is_file() and candidate.stat().st_mode & 0o111:
                    manager_command = str(candidate)
                    break
            for metadata_path in metadata_paths:
                if not metadata_path.is_dir():
                    continue
                try:
                    distributions = importlib.metadata.distributions(path=[str(metadata_path)])
                except Exception:
                    continue
                for dist in distributions:
                    name = dist.metadata.get("Name", "")
                    if not name or name.lower() in seen or name.lower() in {"pip", "setuptools", "wheel"}:
                        continue
                    console_scripts = [
                        ep.name for ep in dist.entry_points
                        if ep.group == "console_scripts"
                    ]
                    valid_bins = [cs for cs in console_scripts if shutil.which(cs)]
                    # Skip packages with no executables (libraries without CLI)
                    if not valid_bins and not console_scripts:
                        continue
                    app = {
                        "id": f"pip:{profile['owner']}:{name}",
                        "name": name,
                        "store": "PIP",
                        "version": dist.version or "",
                        "size": _distribution_size(dist),
                        "bin": valid_bins[0] if valid_bins else (console_scripts[0] if console_scripts else name),
                        "bins": valid_bins or console_scripts or [name],
                        "manager": "pip",
                        "manager_command": manager_command,
                        "pip_root": str(custom_root),
                        "desc": f"Python CLI package ({name}) from configured root",
                    }
                    apps.append(add_profile_metadata(app, profile))
                    seen.add(name.lower())
    return apps
