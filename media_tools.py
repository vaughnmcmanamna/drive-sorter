"""Locate bundled or system-installed FFmpeg command-line tools."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


RESOURCE_DIRECTORY = Path(__file__).resolve().parent


def media_tool_path(name: str) -> Path | None:
    """Return a bundled media tool first, then fall back to the system PATH."""
    executable = f"{name}.exe" if os.name == "nt" else name
    candidates = [
        RESOURCE_DIRECTORY / "tools" / executable,
        RESOURCE_DIRECTORY / "vendor" / "ffmpeg" / "bin" / executable,
        Path(sys.executable).resolve().parent / "tools" / executable,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which(executable)
    return Path(found) if found else None


def missing_media_tools() -> list[str]:
    """Return names of required executables that cannot be located."""
    return [name for name in ("ffmpeg", "ffprobe") if media_tool_path(name) is None]


def verify_media_tools(timeout: int = 10) -> dict[str, str]:
    """Run each required tool and return user-readable failures by tool name."""
    failures: dict[str, str] = {}
    process_options: dict[str, int] = {}
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NO_WINDOW
    for name in ("ffmpeg", "ffprobe"):
        path = media_tool_path(name)
        if path is None:
            failures[name] = "not found"
            continue
        try:
            result = subprocess.run(
                [str(path), "-version"], capture_output=True, check=False,
                timeout=timeout, **process_options,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            failures[name] = str(error)
        else:
            if result.returncode != 0:
                failures[name] = f"exited with code {result.returncode}"
    return failures
