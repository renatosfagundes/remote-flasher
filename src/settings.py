"""
Application settings — persistence, paths, constants.
"""
import sys
import os
import json
import base64

from lab_config import REMOTE_USER_DIR

# App directory — project root (one level up from src/)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# User settings — stored in AppData so the exe can live anywhere
_SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", APP_DIR), "RemoteFlasher")
os.makedirs(_SETTINGS_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")


def load_settings() -> dict:
    """Load saved user settings from the local settings.json file."""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "vpn_password" in data:
            data["vpn_password"] = base64.b64decode(data["vpn_password"]).decode("utf-8")
        return data
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return {}


def save_settings(**kwargs):
    """Save settings to the local settings.json file (merges with existing)."""
    data = load_settings()
    if "vpn_password" in data:
        data["vpn_password"] = base64.b64encode(data["vpn_password"].encode("utf-8")).decode("ascii")
    for k, v in kwargs.items():
        if k == "vpn_password":
            data[k] = base64.b64encode(v.encode("utf-8")).decode("ascii")
        else:
            data[k] = v
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_remote_user_dir() -> str:
    """Get the user's remote folder, falling back to lab_config default."""
    settings = load_settings()
    return settings.get("remote_user_dir", REMOTE_USER_DIR)


def load_credentials() -> dict:
    return load_settings()


def save_credentials(username: str, password: str):
    save_settings(vpn_username=username, vpn_password=password)


def clear_credentials():
    """Remove just the VPN credentials from settings."""
    settings = load_settings()
    if "vpn_password" in settings:
        settings.pop("vpn_password")
    settings.pop("vpn_username", None)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def clear_all_settings():
    """Remove the entire settings file (full reset)."""
    try:
        os.remove(SETTINGS_FILE)
    except FileNotFoundError:
        pass
