# Core Design

```text
Scan files -> Read metadata -> Identify game/year -> Build move plan -> Preview -> Move files
```

## Components

### Scanner

Finds supported video files in the selected directory and excludes its `Organized` output folder. Up to four metadata reads run at once. A persistent cache reuses metadata for unchanged files, and the scan can be cancelled after active reads finish.

### Metadata reader

Uses `ffprobe` to read the title and creation time. Each call has a timeout. Metadata failures are stored as per-file notes instead of stopping the scan.

### Detector

Uses a sanitized metadata title as the game name. If the title is unavailable or unusable, the clip remains unsorted; filenames are never used as game-folder names.

### Planner

Calculates destinations and marks both existing files and duplicate destinations in the same run as conflicts before any changes are made. Destination keys use Windows-style case-insensitive comparison. The optional duplicate-name mode assigns safe numeric suffixes instead.

### Organizer

Rechecks a ready destination immediately before moving. Successful moves are written to a persistent last-operation journal, allowing a safe Undo action that never overwrites a restored source file.

### GUI

Uses a Windows 95-inspired native layout with a compact summary by default, destination counts, and conflicts. The complete plan is available by toggle, and folder controls are locked during scans and moves.

## Project files

- `organizer.py`: core scan, metadata, planning, and move logic; also provides a command-line workflow.
- `gui.py`: native Tkinter interface.
- `launch_drive_sorter.pyw`: double-click launcher that starts the GUI without a terminal window.
- `dev_flatten_videos.py`: reusable safe flattening logic and command-line helper; the GUI's `Flatten all` action uses the same logic.
- `operation_history.py`: persistent last-operation journal and safe undo logic.
- `test_metadata.py`: automated unit and filesystem tests.
- `assets/drive-sorter-icon.png`: custom application emblem.
