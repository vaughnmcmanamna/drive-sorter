"""Preview and safely organize game clips into Organized/<game>/<year>."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm", ".wmv"}
FFPROBE_TIMEOUT_SECONDS = 30
MAX_METADATA_WORKERS = 4
METADATA_CACHE_PATH = Path(__file__).resolve().parent / ".drive-sorter-state" / "metadata-cache.json"
INVALID_FOLDER_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ZERO_WIDTH_CHARACTERS = re.compile(r"[\u200b-\u200d\ufeff]")
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}


@dataclass(frozen=True)
class Clip:
    path: Path
    game: str | None
    year: int | None
    metadata_error: str | None = None


@dataclass(frozen=True)
class PlannedMove:
    clip: Clip
    destination: Path
    status: str


class ScanCancelled(Exception):
    """Raised when a scan is cancelled after active metadata reads finish."""


def sanitize_folder_name(name: str) -> str | None:
    """Return a usable Windows folder name, or None if the name is unusable."""
    cleaned = ZERO_WIDTH_CHARACTERS.sub("", name)
    cleaned = INVALID_FOLDER_CHARACTERS.sub("", cleaned).strip().rstrip(". ")
    reserved_base_name = cleaned.split(".", maxsplit=1)[0].upper()
    if not cleaned or reserved_base_name in WINDOWS_RESERVED_NAMES:
        return None
    return cleaned


def parse_creation_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def path_key(path: Path) -> str:
    """Return a Windows-safe comparison key for planned file destinations."""
    return str(path).casefold()


def _load_metadata_cache(cache_path: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        entries = payload.get("entries", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return entries if isinstance(entries, dict) else {}


def _cached_clip(file: Path, entries: dict[str, dict[str, object]]) -> Clip | None:
    entry = entries.get(str(file.resolve()))
    if not isinstance(entry, dict):
        return None
    stat = file.stat()
    if entry.get("size") != stat.st_size or entry.get("mtime_ns") != stat.st_mtime_ns:
        return None
    game = entry.get("game")
    year = entry.get("year")
    error = entry.get("error")
    if not isinstance(game, str) and game is not None:
        return None
    if not isinstance(year, int) and year is not None:
        return None
    if not isinstance(error, str) and error is not None:
        return None
    return Clip(file, game, year, error)


def _cache_clip(file: Path, clip: Clip, entries: dict[str, dict[str, object]]) -> None:
    if clip.metadata_error not in (None, "no usable game title in metadata"):
        return
    stat = file.stat()
    entries[str(file.resolve())] = {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "game": clip.game,
        "year": clip.year,
        "error": clip.metadata_error,
    }


def _save_metadata_cache(cache_path: Path, entries: dict[str, dict[str, object]]) -> None:
    cache_path.parent.mkdir(exist_ok=True)
    temporary_path = cache_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    temporary_path.replace(cache_path)


def metadata_reader(file: Path) -> tuple[str | None, datetime | None, str | None]:
    """Read Game Bar metadata without allowing one bad file to stop the scan."""
    process_options: dict[str, int] = {}
    if os.name == "nt":
        process_options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(file)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            **process_options,
        )
    except FileNotFoundError:
        return None, None, "ffprobe was not found on PATH"
    except OSError as error:
        return None, None, f"could not run ffprobe: {error}"
    except subprocess.TimeoutExpired:
        return None, None, f"ffprobe timed out after {FFPROBE_TIMEOUT_SECONDS} seconds"
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        return None, None, f"ffprobe failed: {detail}"
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, None, "ffprobe returned invalid JSON"

    format_data = metadata.get("format")
    tags = format_data.get("tags", {}) if isinstance(format_data, dict) else {}
    if not isinstance(tags, dict):
        tags = {}
    title = tags.get("title")
    game = sanitize_folder_name(title) if isinstance(title, str) else None
    error = None if game else "no usable game title in metadata"
    return game, parse_creation_time(tags.get("creation_time")), error


def file_scanner(
    folder: Path,
    output: Path,
    progress: Callable[[int, int, Path], None] | None = None,
    workers: int | None = None,
    cancelled: Callable[[], bool] | None = None,
    cache_path: Path | None = METADATA_CACHE_PATH,
) -> list[Clip]:
    """Read clip metadata concurrently, with caching and cooperative cancellation."""
    clips: list[Clip] = []
    output = output.resolve()
    files = sorted(
        (
            file for file in folder.rglob("*")
            if file.is_file()
            and file.suffix.lower() in VIDEO_EXTENSIONS
            and not file.resolve().is_relative_to(output)
        ),
        key=lambda file: str(file).lower(),
    )
    if not files:
        return clips

    worker_count = workers if workers is not None else min(MAX_METADATA_WORKERS, os.cpu_count() or 1)
    results: list[Clip | None] = [None] * len(files)
    entries = _load_metadata_cache(cache_path) if cache_path else {}
    uncached: list[tuple[int, Path]] = []
    completed = 0
    for index, file in enumerate(files):
        if cancelled and cancelled():
            raise ScanCancelled
        clip = _cached_clip(file, entries) if cache_path else None
        if clip is None:
            uncached.append((index, file))
            continue
        results[index] = clip
        completed += 1
        if progress:
            progress(completed, len(files), file)

    with ThreadPoolExecutor(max_workers=max(1, worker_count)) as executor:
        pending: dict[object, tuple[int, Path]] = {}
        uncached_index = 0

        def submit_next() -> bool:
            nonlocal uncached_index
            if uncached_index >= len(uncached):
                return False
            index, file = uncached[uncached_index]
            uncached_index += 1
            pending[executor.submit(metadata_reader, file)] = (index, file)
            return True

        for _ in range(min(worker_count, len(uncached))):
            submit_next()
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            if cancelled and cancelled():
                for future in pending:
                    future.cancel()
                raise ScanCancelled
            for future in finished:
                index, file = pending.pop(future)
                game, creation_time, error = future.result()
                clip = Clip(file, game, creation_time.year if creation_time else None, error)
                results[index] = clip
                if cache_path:
                    _cache_clip(file, clip, entries)
                completed += 1
                if progress:
                    progress(completed, len(files), file)
                if not (cancelled and cancelled()):
                    submit_next()
    if cache_path:
        _save_metadata_cache(cache_path, entries)
    return [clip for clip in results if clip is not None]


def get_destination(clip: Clip, output: Path) -> Path:
    if clip.game is None:
        return output / "Unsorted" / clip.path.name
    if clip.year is None:
        return output / clip.game / "Unknown Year" / clip.path.name
    return output / clip.game / str(clip.year) / clip.path.name


def build_plan(clips: list[Clip], output: Path, rename_duplicates: bool = False) -> list[PlannedMove]:
    """Mark existing and same-run name conflicts before any file is moved."""
    if rename_duplicates:
        reserved: set[str] = set()
        plan: list[PlannedMove] = []
        for clip in clips:
            destination = get_destination(clip, output)
            if destination.exists():
                plan.append(PlannedMove(clip, destination, "CONFLICT: destination exists"))
                continue
            candidate = destination
            number = 2
            while path_key(candidate) in reserved or candidate.exists():
                candidate = destination.parent / f"{destination.stem} ({number}){destination.suffix}"
                number += 1
            reserved.add(path_key(candidate))
            plan.append(PlannedMove(clip, candidate, "READY"))
        return plan

    destinations: dict[str, int] = {}
    for clip in clips:
        destination = get_destination(clip, output)
        key = path_key(destination)
        destinations[key] = destinations.get(key, 0) + 1
    plan = []
    for clip in clips:
        destination = get_destination(clip, output)
        if destination.exists():
            status = "CONFLICT: destination exists"
        elif destinations[path_key(destination)] > 1:
            status = "CONFLICT: duplicate destination in this run"
        else:
            status = "READY"
        plan.append(PlannedMove(clip, destination, status))
    return plan


def print_plan(plan: list[PlannedMove]) -> None:
    if not plan:
        print("No video files found outside Organized.")
        return
    for move in plan:
        print(f"{move.clip.path} -> {move.destination}")
        print(move.status)
        if move.clip.metadata_error:
            print(f"Metadata note: {move.clip.metadata_error}; sending to Unsorted.")
        print()


def organize_clips(
    plan: list[PlannedMove],
    progress: Callable[[int, int, PlannedMove, str], None] | None = None,
    on_moved: Callable[[Path, Path], None] | None = None,
    echo: bool = True,
) -> list[str]:
    messages = [
        f"SKIPPED: {move.clip.path.name} ({move.status})"
        for move in plan
        if move.status != "READY"
    ]
    ready_moves = [move for move in plan if move.status == "READY"]
    for index, move in enumerate(ready_moves, start=1):
        if move.destination.exists():
            message = f"SKIPPED: {move.clip.path.name} (destination now exists)"
            messages.append(message)
            if progress:
                progress(index, len(ready_moves), move, message)
            continue
        try:
            move.destination.parent.mkdir(parents=True, exist_ok=True)
            if move.destination.exists():
                message = f"SKIPPED: {move.clip.path.name} (destination now exists)"
                messages.append(message)
                if progress:
                    progress(index, len(ready_moves), move, message)
                continue
            shutil.move(str(move.clip.path), str(move.destination))
        except (OSError, shutil.Error) as error:
            message = f"FAILED: {move.clip.path.name} ({error})"
            messages.append(message)
        else:
            message = f"MOVED: {move.clip.path.name}"
            messages.append(message)
            if on_moved:
                on_moved(move.clip.path, move.destination)
        if progress:
            progress(index, len(ready_moves), move, message)
    if echo:
        for message in messages:
            print(message)
    return messages


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize game clips using ffprobe metadata.")
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        help="directory containing clips to organize",
    )
    return parser.parse_args()


def main() -> None:
    directory = parse_arguments().directory
    if directory is None:
        directory = Path(__file__).resolve().parent / "test-videos"
        print(f"Using default directory: {directory}")

    root = directory.expanduser()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")
    output = root / "Organized"
    plan = build_plan(file_scanner(root, output), output)
    print_plan(plan)
    if not plan:
        return
    if input("Organize READY files? (y/n): ").strip().lower() == "y":
        organize_clips(plan)
    else:
        print("No files moved.")


if __name__ == "__main__":
    main()
