"""Preview and safely remove empty folders beneath a selected root."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable


def _is_reparse_point(entry: os.DirEntry[str]) -> bool:
    """Return True for symlinks and Windows junction/reparse entries."""
    if entry.is_symlink():
        return True
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def build_empty_folder_plan(root: Path) -> list[Path]:
    """Return removable folders bottom-up without following links or junctions."""
    root = root.resolve()
    removable: list[Path] = []

    def inspect(folder: Path) -> bool:
        try:
            entries = list(os.scandir(folder))
        except OSError:
            return False

        empty_after_cleanup = True
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False) or _is_reparse_point(entry):
                empty_after_cleanup = False
                continue
            if not inspect(Path(entry.path)):
                empty_after_cleanup = False

        if folder != root and empty_after_cleanup:
            removable.append(folder)
        return empty_after_cleanup

    inspect(root)
    return removable


def remove_empty_folders(
    root: Path,
    plan: list[Path],
    progress: Callable[[int, int, Path, str], None] | None = None,
) -> list[str]:
    """Remove planned folders only if they are still empty and beneath root."""
    root = root.resolve()
    messages: list[str] = []
    for index, folder in enumerate(plan, start=1):
        try:
            resolved = folder.resolve()
            if resolved == root or not resolved.is_relative_to(root):
                message = f"SKIPPED: {folder} is outside the selected folder"
            elif folder.is_symlink() or (
                hasattr(folder, "is_junction") and folder.is_junction()
            ):
                message = f"SKIPPED: {folder} is a link or junction"
            else:
                folder.rmdir()
                message = f"REMOVED: {folder}"
        except FileNotFoundError:
            message = f"SKIPPED: {folder} no longer exists"
        except OSError as error:
            message = f"SKIPPED: {folder} is not empty or accessible ({error})"
        messages.append(message)
        if progress:
            progress(index, len(plan), folder, message)
    return messages
