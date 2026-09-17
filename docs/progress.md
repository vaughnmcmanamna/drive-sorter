# Current Progress

## Complete

- Recursive video scanning with `Organized` exclusion
- Concurrent FFprobe metadata reads with timeout handling
- Persistent metadata cache for unchanged clips
- Cooperative scan cancellation
- Metadata-based game and creation-year detection
- Safe Windows folder-name sanitization
- Preview plans with destination summaries and optional full details
- Case-insensitive duplicate detection
- Optional safe numeric renaming for same-run and existing-file collisions
- Background Organize and Flatten operations with progress reporting
- Last-second destination checks before every move
- Persistent undo journal for the latest successful Organize or Flatten operation
- Windows 95-inspired Tkinter interface and custom application icon
- Persistent `Organized/Unsorted` discovery after organizing or reopening a folder
- Still-frame manual review with drag, buttons, typing, and keyboard-first Up/Down/Enter controls
- Serialized FFmpeg preview extraction during rapid navigation
- Canonical metadata-free fixtures and a disposable-fixture reset utility
- Nonfatal handling for metadata-cache, individual metadata-reader, and unreadable-history failures
- Confirmed, guarded removal of empty folders without replacing move history
- Folder-change plan invalidation and guarded closing during active operations
- Persistent Unsorted year refresh and final regular-file checks for all move workflows
- Per-user cache and Undo storage with legacy-state migration
- Empty production folder field with explicit selection required before scanning
- Bundled-first FFmpeg/FFprobe discovery with missing-tool warnings
- Reproducible PyInstaller portable build, Inno Setup installer, checksums, and GitHub release workflow
- Automated suite of 43 unit and filesystem tests
- Real Tkinter startup, initial-focus, keyboard-assignment, preview-throttling, and persistent-review smoke checks

## Next candidates

- Persist the selected source folder between launches
- Add user-defined aliases for metadata titles that refer to the same game
- Add an optional scrubber or multiple preview frames for clips whose first frame is not identifiable
- Expand automated GUI coverage around the manual sorter and operation-history warnings
