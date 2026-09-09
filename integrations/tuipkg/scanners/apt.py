import os
import shutil
from pathlib import Path
import subprocess


def scan_apt():
    apps = []
    # Manual-package filtering is part of the scanner contract. If apt-mark
    # is unavailable, do not silently turn every installed library into an app.
    if not shutil.which("apt-mark") or not shutil.which("dpkg-query"):
        return apps

    try:
        manual_set = set()
        m_res = subprocess.run(["apt-mark", "showmanual"], capture_output=True, text=True, timeout=5)
        if m_res.returncode == 0:
            manual_set = {line.strip() for line in m_res.stdout.splitlines() if line.strip()}

        q_res = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Installed-Size}\n"],
            capture_output=True, text=True, timeout=5
        )
        if q_res.returncode == 0:
            for line in q_res.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                pkg_name = parts[0]
                version = parts[1]

                if manual_set and pkg_name not in manual_set:
                    continue

                # Initial size from dpkg-query tabular output.
                size_bytes = 0
                if len(parts) >= 3 and parts[2].strip():
                    try:
                        size_bytes = int(parts[2]) * 1024
                    except ValueError:
                        size_bytes = 0

                # Resolve binaries from PATH and the package file list.
                # Do not assume Termux's $PREFIX; Debian, Ubuntu, and
                # Termux all expose their executable directories through
                # PATH or standard bin directories.
                bin_path = shutil.which(pkg_name) or ""
                valid_bins = [pkg_name] if bin_path else []
                path_dirs = {
                    Path(entry).resolve()
                    for entry in os.environ.get("PATH", "").split(os.pathsep)
                    if entry
                }
                path_dirs.update({Path("/bin"), Path("/usr/bin"), Path("/usr/local/bin")})

                if not bin_path:
                    try:
                        l_res = subprocess.run(["dpkg", "-L", pkg_name], capture_output=True, text=True, timeout=2)
                        if l_res.returncode == 0:
                            for listed in l_res.stdout.splitlines():
                                candidate = Path(listed)
                                if (candidate.parent.resolve() in path_dirs
                                        and candidate.is_file()
                                        and os.access(candidate, os.X_OK)
                                        and candidate.name not in valid_bins):
                                    valid_bins.append(candidate.name)
                    except Exception:
                        pass

                primary_bin = valid_bins[0] if valid_bins else pkg_name

                # --- Size resolution: three fallback tiers ---
                # Tier 1: dpkg-query -W with explicit format request.
                if size_bytes <= 0:
                    try:
                        sq_res = subprocess.run(
                            ["dpkg-query", "-W", "-f=${Installed-Size}", pkg_name],
                            capture_output=True, text=True, timeout=2,
                        )
                        if sq_res.returncode == 0 and sq_res.stdout.strip():
                            size_bytes = int(sq_res.stdout.strip()) * 1024
                    except Exception:
                        pass

                # Tier 2: dpkg -s — used for meta-packages whose dpkg-query
                # tabular output has no size field (e.g. android-sdk, whose
                # dpkg -L returns only "/./").  dpkg -s prints Installed-Size
                # whenever APT's database has a positive value for it.
                if size_bytes <= 0:
                    try:
                        ds_res = subprocess.run(
                            ["dpkg", "-s", pkg_name],
                            capture_output=True, text=True, timeout=5,
                        )
                        if ds_res.returncode == 0:
                            for sline in ds_res.stdout.splitlines():
                                if sline.startswith("Installed-Size:"):
                                    sval = sline.split(":", 1)[1].strip()
                                    if sval.isdigit():
                                        size_bytes = int(sval) * 1024
                                    break
                    except Exception:
                        pass

                # Tier 3: sum file sizes from dpkg -L (skip the "/." synthetic
                # entry that some meta-packages report).
                if size_bytes <= 0:
                    try:
                        ll_res = subprocess.run(
                            ["dpkg", "-L", pkg_name],
                            capture_output=True, text=True, timeout=5,
                        )
                        if ll_res.returncode == 0:
                            for listed in ll_res.stdout.splitlines():
                                fp = Path(listed)
                                if fp.is_file() and fp != Path("/."):
                                    try:
                                        size_bytes += fp.stat().st_size
                                    except OSError:
                                        pass
                    except Exception:
                        pass

                apps.append({
                    "id": f"apt:{pkg_name}",
                    "name": pkg_name,
                    "store": "APT",
                    "version": version,
                    "size": size_bytes,
                    "bin": primary_bin,
                    "bins": valid_bins,
                    "desc": f"APT package ({pkg_name})"
                })
    except Exception:
        pass
    return apps
