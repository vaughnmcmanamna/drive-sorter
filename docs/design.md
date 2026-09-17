# Core Design

```text
Scan files -> Read metadata -> Identify game/year -> Build move plan -> Preview -> Move files
```

## Components

### Scanner

Finds supported video files in the selected directory and excludes its `Organized` output folder. Up to four metadata reads run at once. A persistent cache reuses metadata for unchanged files, and the scan can be cancelled after active reads finish. Cache reads and writes are best-effort optimizations; cache failures do not fail the scan.

### Metadata reader

Uses `ffprobe` to read the title and creation time. Each call has a timeout. Metadata failures are stored as per-file notes instead of stopping the scan.

### Detector

Uses a sanitized metadata title as the game name. If the title is unavailable or unusable, the clip remains unsorted; filenames are never used as game-folder names.

### Planner

Calculates destinations and marks both existing files and duplicate destinations in the same run as conflicts before any changes are made. Destination keys use Windows-style case-insensitive comparison. The optional duplicate-name mode assigns safe numeric suffixes for same-run duplicates and existing destinations.

### Organizer

Rechecks a ready destination immediately before moving. Successful moves are written to a persistent last-operation journal, allowing a safe Undo action that never overwrites a restored source file.

### GUI

Uses a Windows 95-inspired native layout with a compact summary by default, destination counts, and conflicts. The complete plan is available by toggle, and folder controls are locked during scans and moves.

### Manual sorter

Clips headed to `Unsorted` can be reviewed before any files move or after they are placed in `Organized/Unsorted`. A modal Windows 95-style workspace extracts a still frame with FFmpeg and lets the user drag it onto a known game or use a keyboard-first flow. The window waits until it is visible before forcing initial focus to the game list. Up/Down chooses a game, Enter assigns it, and starting to type automatically moves focus to the filter field. The clip's known year is preserved when available and the normal planner is rebuilt after review.

Preview extraction runs outside Tkinter's event thread. At most one FFmpeg process is active and only the newest pending preview is retained when the user navigates quickly.

The review count combines unknown clips in the current scan with videos physically present in `Organized/Unsorted`. Assignments from that folder become a new move plan, so they still pass through conflict checks, confirmation, and undo rather than being moved directly by the review window.

Before opening persistent Unsorted clips, the GUI refreshes missing creation years with concurrent FFprobe reads in a background worker. This preserves year folders across application restarts without blocking the interface.

### Empty-folder cleanup

The advanced cleanup tool builds a bottom-up preview without following links or Windows junctions. After confirmation, every planned directory is checked again with the operating system's empty-directory removal operation. The selected root and paths outside it are always skipped. Cleanup does not replace the last move operation in the undo journal because it changes no file contents and has its own confirmation step.

## Project files

- `organizer.py`: core scan, metadata, planning, and move logic; also provides a command-line workflow.
- `app_paths.py`: per-user state location and legacy project-state location.
- `gui.py`: native Tkinter interface.
- `manual_sorter.py`: still-frame extraction and manual drag-to-game review window.
- `empty_folders.py`: bottom-up empty-folder preview and guarded removal logic.
- `tools/reset_test_fixtures.py`: restores disposable working clips from canonical test fixtures.
- `launch_drive_sorter.pyw`: double-click launcher that starts the GUI without a terminal window.
- `flatten_videos.py`: reusable safe flattening logic and command-line helper; the GUI's `Flatten all` action uses the same logic.
- `operation_history.py`: persistent last-operation journal and safe undo logic.
- `test_metadata.py`: automated unit and filesystem tests.
- `test-fixtures/`: canonical small video fixtures that are never used as move sources directly.
- `assets/drive-sorter-icon.png`: custom application emblem.
- `media_tools.py`: bundled-first FFmpeg and FFprobe discovery and release verification.
- `packaging/`: PyInstaller and Inno Setup release definitions.
- `tools/build_release.ps1`: reproducible portable ZIP and installer build.
