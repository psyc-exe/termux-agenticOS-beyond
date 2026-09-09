from .apt import scan_apt
from .npm import scan_npm
from .pip import scan_pip
from .cargo import scan_cargo
from .go import scan_go
from .standalone import scan_standalone
from .bun import scan_bun


def scan_all_stores(config):
    enabled = config.get("enabled_stores", {})
    apps = []

    if enabled.get("apt", True):
        apps.extend(scan_apt())
    if enabled.get("npm", True):
        apps.extend(scan_npm(config))
    if enabled.get("pip", True):
        apps.extend(scan_pip(config))
    if enabled.get("cargo", True):
        apps.extend(scan_cargo(config))
    if enabled.get("go", True):
        apps.extend(scan_go(config))
    if enabled.get("bun", True):
        apps.extend(scan_bun(config))

    # Deduplicate: collect all known binary names and package names before
    # scanning standalone, so that standalone entries that shadow a package
    # manager binary (e.g. sgpt from pip + sgpt symlink in ~/.local/bin)
    # are suppressed.
    known_names = set()
    known_bins = set()
    for a in apps:
        known_names.add(a["name"].lower())
        for b in a.get("bins", [a.get("bin", "")]):
            if b:
                known_bins.add(b.lower())

    if enabled.get("standalone", True):
        apps.extend(scan_standalone(known_names, known_bins, config))

    # Cross-store dedup: packages appearing in multiple stores (e.g. APT + PIP).
    # Prefer the more specific/modern source when names collide.
    # PIP > APT for Python packages (pip install is more likely intentional).
    deduped = {}
    for a in apps:
        key = a["name"].lower()
        if key in deduped:
            existing = deduped[key]
            # Prefer PIP over APT for Python packages
            if existing.get("store") == "APT" and a.get("store") == "PIP":
                deduped[key] = a
            # Otherwise keep the first one encountered (APT usually listed first)
        else:
            deduped[key] = a

    result = list(deduped.values())
    result.sort(key=lambda x: (x["name"].lower(), x.get("owner", "").lower()))
    return result
