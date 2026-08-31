# Core Design

```text
Scan files -> Read metadata -> Identify game/year -> Build move plan -> Preview -> Move files
```

## Components

### Scanner

Finds supported video files in the selected directory and excludes its `Organized` output folder. It reports completed video metadata reads to the GUI for progress display.

### Metadata reader

Uses `ffprobe` to read the title and creation time. Each call has a timeout. Metadata failures are stored as per-file notes instead of stopping the scan.

### Detector

Uses a sanitized metadata title as the game name. If the title is unavailable or unusable, the clip remains unsorted; filenames are never used as game-folder names.

### Planner

Calculates destinations and marks both existing files and duplicate destinations in the same run as conflicts before any changes are made.

### Organizer

Rechecks a ready destination immediately before moving. It reports each result and progress event, allowing the GUI to keep responding while files move in a background worker.

### GUI

Uses a Windows 95-inspired native layout with a compact summary by default, destination counts, and conflicts. The complete plan is available by toggle, and folder controls are locked during scans and moves.

## Project files

- `metadata_test.py`: core scan, metadata, planning, and move logic; also provides a command-line workflow.
- `gui.py`: native Tkinter interface.
- `launch_drive_sorter.pyw`: double-click launcher that starts the GUI without a terminal window.
- `dev_flatten_videos.py`: development-only test-folder reset helper.
- `test_metadata.py`: automated unit and filesystem tests.
- `assets/drive-sorter-icon.png`: custom application emblem.
