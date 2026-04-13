"""
Port-distribution sync — fetch ports.json from PC 217, apply to in-memory
COMPUTERS, and cache locally so the app starts with the latest mapping.

Schema (ports.json on PC 217 at c:\\dev\\ports.json):

    {
      "PC 217": {
        "Placa 01": {
          "ecu_ports": ["COM25","COM26","COM27","COM28"],
          "reset_port": "COM57",
          "can_selector_port": "COM57"   # optional; defaults to reset_port
        },
        ...
      },
      "PC 218": {...}, "PC 220": {...}, "PC 221": {...}
    }

Only `ecu_ports`, `reset_port`, and `can_selector_port` are overrideable.
`flash_method`, `reset_script`, SSH credentials, etc. stay from lab_config.py.
"""
import os
import json

# Path to the JSON file on PC 217
REMOTE_PORTS_PATH = "c:/dev/ports.json"

# Local cache — mirrors settings.py APPDATA pattern but computed inline
# to avoid a circular import with lab_config.py.
_CACHE_DIR = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~"), "RemoteFlasher"
)
CACHE_FILE = os.path.join(_CACHE_DIR, "ports_cache.json")

_OVERRIDABLE_FIELDS = ("ecu_ports", "reset_port", "can_selector_port")


def _short_pc_key(full_key: str) -> str:
    """Extract 'PC 217' from 'PC 217 (172.20.36.217)'."""
    return full_key.split(" (", 1)[0]


def apply_overrides(computers: dict, data: dict) -> list:
    """Mutate `computers` in place with port overrides from `data`.

    Returns a list of human-readable change descriptions for logging.
    Unknown PCs/boards/fields in the JSON are silently ignored.
    """
    changes = []
    if not isinstance(data, dict):
        return changes
    for full_key, pc_cfg in computers.items():
        short = _short_pc_key(full_key)
        pc_overrides = data.get(short) or data.get(full_key)
        if not isinstance(pc_overrides, dict):
            continue
        boards = pc_cfg.get("boards", {})
        for board_name, board_overrides in pc_overrides.items():
            if board_name not in boards or not isinstance(board_overrides, dict):
                continue
            for field in _OVERRIDABLE_FIELDS:
                if field in board_overrides:
                    new_val = board_overrides[field]
                    old_val = boards[board_name].get(field)
                    if old_val != new_val:
                        boards[board_name][field] = new_val
                        changes.append(f"{short} / {board_name} / {field}: {old_val} -> {new_val}")
    return changes


def load_cache() -> dict:
    """Return the cached JSON, or {} if missing/invalid."""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_cache(data: dict) -> None:
    """Persist the fetched JSON to the local cache file."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
