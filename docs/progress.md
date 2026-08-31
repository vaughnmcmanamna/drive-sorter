# Current Progress

- Core scanner, metadata reader, planner, and organizer are implemented
- The GUI supports folder selection, scan and move progress, summaries, conflicts, and explicit completion states
- Clips without usable metadata are sent to `Unsorted`
- Destination conflicts and post-preview destination changes are skipped
- `ffprobe` failures and timeouts are handled per file
- Development flattening helper is available for rebuilding test scenarios
- Automated tests cover metadata parsing, `ffprobe` timeout handling, scanner exclusion, planning conflicts, successful moves, progress reporting, and last-minute destination conflicts
- A `.pyw` launcher starts the GUI without a terminal window
- Custom Windows 95-style GUI emblem is included
- GUI can safely flatten nested videos to the selected folder's top level, with confirmation and collision renaming
- Scans use a four-worker metadata pool, persistent unchanged-file cache, and Cancel scan control
- The latest Organize or Flatten operation can be undone safely from the GUI
- Duplicate destination checks are Windows case-insensitive; optional safe renaming handles same-run duplicates
- Production core module is named `organizer.py`
- Move destinations are summarized as game folders with year subfolders and live per-folder progress
- Large-folder movement animation is grouped by destination rather than playing once per clip
- The interface now keeps Browse, Scan, and Organize as the primary workflow; advanced actions live in a compact top-right flyout
- The complete text plan is hidden by default and can be opened with `+ Details`
- The automated suite contains 20 tests, including cache, cancellation, stale-destination, rename, and undo flows

## Next

- Package the application with `ffprobe` availability checks for Windows distribution
- Add a small GUI integration test that exercises scan, move, and undo with mocked metadata
