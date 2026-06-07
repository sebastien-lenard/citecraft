# src/citecraft/utils/paths.py
"""Path and directory utilities for the CiteCraft application."""

import os
import platform
import tempfile
from pathlib import Path

from dotenv import dotenv_values

_ENV = {**dotenv_values(".env"), **os.environ}


def get_app_name() -> str:
    """Get the application folder name, defaulting to project standard."""
    return _ENV.get("APP_NAME", "citecraft").strip("\"'")


def get_app_base_dir() -> Path:
    """Determine the persistent base root directory for the app based on OS."""
    if custom_base := _ENV.get("APP_BASE_DIR"):
        return Path(custom_base.strip("\"'")).resolve()

    system = platform.system()
    home = Path.home()

    if system == "Windows":
        local_app_data = _ENV.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else home / "AppData" / "Local"
        return base / get_app_name()
    if system == "Darwin":
        return home / "Library" / get_app_name()
    xdg_state = _ENV.get("XDG_STATE_HOME")
    base = Path(xdg_state) if xdg_state else home / ".local" / "state"
    return base / get_app_name()


def get_safe_dir(subfolder: str) -> tuple[Path, Path, bool]:
    """Ensure a writable directory.

    Return a writable directory, the original intended path, and a boolean = True
    if it had to resort to a temp directory.
    """
    target_path = get_app_base_dir() / subfolder

    try:
        target_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Fallback to temp directory if persistent directory is locked/read-only
        fallback_path = (
            Path(tempfile.gettempdir()).resolve() / get_app_name() / subfolder
        )
        fallback_path.mkdir(parents=True, exist_ok=True)
        return fallback_path, target_path, True
    else:
        return target_path, target_path, False
