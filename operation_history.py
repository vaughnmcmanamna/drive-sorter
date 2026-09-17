"""Persistent, reversible history for the most recent Drive Sorter operation."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app_paths import LEGACY_STATE_DIRECTORY, STATE_DIRECTORY

LAST_OPERATION_PATH = STATE_DIRECTORY / "last-operation.json"
DEFAULT_LAST_OPERATION_PATH = LAST_OPERATION_PATH
LEGACY_LAST_OPERATION_PATH = LEGACY_STATE_DIRECTORY / "last-operation.json"


@dataclass(frozen=True)
class MoveRecord:
    source: Path
    destination: Path


@dataclass(frozen=True)
class OperationHistory:
    operation: str
    moves: list[MoveRecord]


def save_last_operation(operation: str, moves: list[MoveRecord]) -> None:
    """Atomically save successful moves so the user can undo them later."""
    STATE_DIRECTORY.mkdir(exist_ok=True)
    payload = {
        "operation": operation,
        "moves": [{"source": str(move.source), "destination": str(move.destination)} for move in moves],
    }
    temporary_path = LAST_OPERATION_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(LAST_OPERATION_PATH)
    if LAST_OPERATION_PATH == DEFAULT_LAST_OPERATION_PATH:
        try:
            LEGACY_LAST_OPERATION_PATH.unlink(missing_ok=True)
        except OSError:
            # The old application directory may be read-only after installation.
            pass


def _available_history_path() -> Path:
    if LAST_OPERATION_PATH.exists():
        return LAST_OPERATION_PATH
    if LAST_OPERATION_PATH == DEFAULT_LAST_OPERATION_PATH and LEGACY_LAST_OPERATION_PATH.exists():
        return LEGACY_LAST_OPERATION_PATH
    return LAST_OPERATION_PATH


def load_last_operation() -> OperationHistory | None:
    """Return valid recorded history, treating a missing/corrupt record as unavailable."""
    try:
        payload = json.loads(_available_history_path().read_text(encoding="utf-8"))
        operation = payload["operation"]
        moves = [MoveRecord(Path(move["source"]), Path(move["destination"])) for move in payload["moves"]]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(operation, str) or not moves:
        return None
    return OperationHistory(operation, moves)


def undo_last_operation() -> tuple[list[str], OperationHistory | None]:
    """Move recorded files back without overwriting anything at their original paths."""
    history_path = _available_history_path()
    history = load_last_operation()
    if history is None:
        return ["No undoable operation was found."], None

    messages: list[str] = []
    remaining: list[MoveRecord] = []
    for move in reversed(history.moves):
        if not move.destination.exists():
            messages.append(f"SKIPPED: {move.destination.name} is no longer at its recorded destination")
            remaining.append(move)
            continue
        if not move.destination.is_file() or move.destination.is_symlink():
            messages.append(
                f"SKIPPED: {move.destination.name} is no longer a regular file"
            )
            remaining.append(move)
            continue
        if move.source.exists():
            messages.append(f"SKIPPED: {move.source.name} already exists at its original location")
            remaining.append(move)
            continue
        try:
            move.source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.destination), str(move.source))
        except (OSError, shutil.Error) as error:
            messages.append(f"FAILED: {move.destination.name} ({error})")
            remaining.append(move)
        else:
            messages.append(f"UNDONE: {move.destination.name} -> {move.source.name}")

    if remaining:
        save_last_operation(history.operation, list(reversed(remaining)))
        if history_path != LAST_OPERATION_PATH:
            try:
                history_path.unlink(missing_ok=True)
            except OSError:
                pass
        return messages, OperationHistory(history.operation, list(reversed(remaining)))
    try:
        history_path.unlink(missing_ok=True)
    except OSError:
        if history_path != LAST_OPERATION_PATH:
            # A new empty marker takes precedence over an undeletable legacy record.
            STATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
            LAST_OPERATION_PATH.write_text(
                json.dumps({"operation": history.operation, "moves": []}),
                encoding="utf-8",
            )
        else:
            raise
    return messages, None
