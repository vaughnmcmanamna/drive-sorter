"""Per-user storage paths for Drive Sorter state."""

from __future__ import annotations

import os
from pathlib import Path


APP_DIRECTORY = Path(__file__).resolve().parent
LEGACY_STATE_DIRECTORY = APP_DIRECTORY / ".drive-sorter-state"


def user_state_directory() -> Path:
    """Return a writable per-user state location on Windows and other systems."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "DriveSorter"
    return Path.home() / ".drive-sorter"


STATE_DIRECTORY = user_state_directory()
