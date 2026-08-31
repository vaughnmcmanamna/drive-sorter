# Decisions

## Getting the game from a video

Game Bar clips store the game name in the `title` metadata tag, which is more reliable than a user-renamed filename. The application uses only a valid metadata title; clips without one go to `Unsorted`. Filenames are never used as game-folder names.

**Why:** An earlier filename fallback created a separate game folder for each renamed or improperly formatted clip. Sending those clips to `Unsorted` is predictable and makes them easy to review.

## Getting the year from a video

The organizer uses the metadata `creation_time` year. If the value is absent or invalid, the clip goes to `<Game>/Unknown Year` rather than guessing from its filename or filesystem timestamp.

**Why:** A guessed date can silently put a clip in the wrong folder. `Unknown Year` preserves the known game grouping without claiming false precision.

## Safety

The application builds and displays a complete move plan before changing files. It never intentionally overwrites an existing destination: existing and duplicate destinations are skipped, and ready destinations are checked a second time when a move begins. Metadata and move failures are reported without halting the remaining files.

**Why:** A destination can change between scanning and confirmation. The second check protects clips even when the folder changes while the preview is open.

## Metadata failures

`ffprobe` is run once per video with UTF-8 decoding and a 30-second timeout. A missing executable, invalid JSON, unsupported clip, or timeout becomes a per-file note instead of ending the entire scan.

**Why:** Video folders can contain incomplete or unusual files. One bad file should not prevent the remaining clips from being organized.

## User interface

The GUI uses a Windows 95-inspired native Tkinter design: classic gray panels, raised controls, a blue title bar, and a custom app emblem. It favors a concise summary by default; the complete move plan is optional.

**Why:** Listing every ready file made scans feel endless and obscured the important information. The summary shows ready, unsorted, conflict, and destination counts immediately, while the full plan remains available for review.

## Development workflow

`dev_flatten_videos.py` provides shared flattening logic that moves nested videos back to the selected folder's root after confirmation. It prevents overwrites by adding a numeric suffix when necessary and reports whether all moves succeeded. The same behavior is available through the GUI's `Flatten all` button.

**Why:** It makes it quick to rebuild a deliberately disorganized test folder without manually moving clips or deleting folders, while also giving users a safe way to undo the folder nesting created by an organization run.

## Recovery and repeated scans

Successful Organize and Flatten moves are recorded as the most recent operation and can be undone from the GUI. The metadata cache keys each entry to a file's absolute path, size, and modified timestamp; changed files are probed again.

**Why:** File moves need a recovery route, while repeated scans should not repeatedly launch `ffprobe` for unchanged clips.

## Visual hierarchy and advanced actions

The normal workflow exposes only Browse, Scan, and Organize. Destination folders are the default scan result, while the full text plan is optional. Flattening, undo, and duplicate-name behavior are placed in a compact top-right flyout rather than competing with the main workflow.

**Why:** The app is used for one repeated task. Giving every feature equal visual weight made the interface feel crowded and obscured the result users needed to review before organizing.
