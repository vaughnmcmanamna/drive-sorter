"""Development helper: move nested videos back to the top of a test folder."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Callable

from organizer import VIDEO_EXTENSIONS, path_key


def available_destination(source: Path, root: Path, reserved: set[str]) -> Path:
    """Return a root-level destination without overwriting any file."""
    candidate = root / source.name
    number = 2
    while candidate.exists() or path_key(candidate) in reserved:
        candidate = root / f"{source.stem} ({number}){source.suffix}"
        number += 1
    reserved.add(path_key(candidate))
    return candidate


def build_flatten_plan(root: Path) -> list[tuple[Path, Path]]:
    """Plan moves for videos below root, leaving root-level files untouched."""
    plan: list[tuple[Path, Path]] = []
    reserved: set[str] = set()
    for source in root.rglob("*"):
        if not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if source.parent == root:
            continue
        plan.append((source, available_destination(source, root, reserved)))
    return plan


def flatten_videos(
    plan: list[tuple[Path, Path]],
    progress: Callable[[int, int, Path, Path, str], None] | None = None,
    on_moved: Callable[[Path, Path], None] | None = None,
    echo: bool = True,
) -> list[str]:
    """Move planned nested videos to the root folder without overwriting files."""
    messages = []
    reserved = {path_key(destination) for _source, destination in plan}
    for index, (source, destination) in enumerate(plan, start=1):
        if destination.exists():
            destination = available_destination(source, destination.parent, reserved)
        try:
            shutil.move(str(source), str(destination))
        except (OSError, shutil.Error) as error:
            message = f"FAILED: {source.name} ({error})"
        else:
            message = f"MOVED: {source.name} -> {destination.name}"
            if on_moved:
                on_moved(source, destination)
        messages.append(message)
        if progress:
            progress(index, len(plan), source, destination, message)
    if echo:
        for message in messages:
            print(message)
    return messages


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(
        description="DEV ONLY: move nested video files to the top of a folder."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "test-videos",
        help="test folder to flatten (defaults to this project's test-videos folder)",
    )
    root = parser.parse_args().directory.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    plan = build_flatten_plan(root)
    if not plan:
        print("No nested video files found.")
        return

    print(f"DEV FLATTEN: {len(plan)} video file(s) will move to {root}\n")
    for source, destination in plan:
        print(f"{source.relative_to(root)} -> {destination.name}")

    if input("Flatten these videos? (y/n): ").strip().lower() != "y":
        print("No files moved.")
        return

    messages = flatten_videos(plan, echo=True)
    moved = sum(message.startswith("MOVED") for message in messages)
    failed = sum(message.startswith("FAILED") for message in messages)

    if failed:
        print(f"\nFLATTEN PARTIALLY COMPLETE: {moved} moved, {failed} failed.")
    else:
        print(f"\nFLATTEN COMPLETE: all {moved} video file(s) moved successfully.")


if __name__ == "__main__":
    main()
