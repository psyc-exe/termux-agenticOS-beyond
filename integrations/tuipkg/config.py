import copy
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("AGENTICOS_TUIPKG_CONFIG", Path.home() / ".config" / "tuipkg"))
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "first_run": True,
    "view_mode": "grid",  # "grid" or "list"
    "show_size": True,
    "root_aggregate_profiles": True,
    "custom_roots": {
        "npm": [],
        "bun": [],
        "pip": [],
        "cargo": [],
        "go": [],
        "standalone": [],
    },
    "enabled_stores": {
        "apt": True,
        "npm": True,
        "pip": True,
        "standalone": True,
        "cargo": True,
        "go": True,
        "bun": True
    }
}

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                for key, value in DEFAULT_CONFIG.items():
                    if key not in cfg:
                        cfg[key] = copy.deepcopy(value)
                    elif isinstance(value, dict) and isinstance(cfg[key], dict):
                        for child_key, child_value in value.items():
                            cfg[key].setdefault(child_key, copy.deepcopy(child_value))
                return cfg
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def format_size(bytes_size):
    """Format bytes with compact human-readable binary units."""
    if bytes_size <= 0:
        return ""
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(bytes_size)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)}B"
    rendered = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{rendered}{unit}"
