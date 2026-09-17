# Requirements

## Functional requirements

- The user selects a directory in the GUI or supplies one to the command-line tool.
- The GUI starts with an empty folder field and cannot scan until the user explicitly selects a valid directory.
- The application scans that directory for supported video files.
- It reads a game title and creation year from video metadata when available.
- It organizes clips into `Organized/<Game>/<Year>`.
- It previews a summary before moving and can show the complete move plan on request.
- The user must confirm before files are moved.
- Clips without a usable game title go to `Organized/Unsorted`.
- Clips with a game but no creation year go to `Organized/<Game>/Unknown Year`.
- The user can flatten nested video files back to the selected folder's top level after confirmation.
- Flattening never overwrites a file; name collisions receive a numeric suffix and empty folders remain.
- The user can undo the most recent successful Organize or Flatten operation.
- The user can cancel a scan after active metadata reads finish.
- The user can opt in to safely renaming duplicate clip filenames instead of skipping them.
- The user can review clips missing a game title before or after organizing, see a still frame, and assign each to a known or new game folder.
- Manual review supports a mouse-free flow: typing filters games, Up/Down changes the selection, and Enter assigns it.
- A newly typed game name must be assigned as typed unless the user explicitly chooses a filtered result.
- The next clip keeps the previously assigned game selected, and one Up/Down press immediately moves to the adjacent game.
- Clips already moved to `Organized/Unsorted` remain available after organizing and after the source folder is selected again on future launches.
- Persistent Unsorted clips have their metadata year refreshed before manual review so assignments do not unnecessarily fall back to `Unknown Year`.
- Manual assignments remain part of the preview plan and receive the same conflict and overwrite checks as metadata-based assignments.
- The user can preview and confirm removal of empty folders beneath the selected folder.

## Safety requirements

- Existing destination files must never be overwritten.
- Duplicate destinations within one run must be skipped unless safe duplicate renaming is enabled.
- Destinations are checked again immediately before each move.
- Flatten destinations are also checked again immediately before each move.
- Destination comparisons account for Windows' case-insensitive filenames.
- A failure reading or moving one clip must not stop other clips from being processed.
- `ffprobe` must time out rather than block a scan indefinitely.
- Normal scans must exclude `Organized`; only `Organized/Unsorted` is inspected for persistent manual-review candidates.
- A metadata-cache failure must not turn a successful scan into a failure.
- If undo history cannot be saved, the GUI must warn the user and must not offer a misleading Undo action.
- Undo never overwrites a file that has reappeared at its original location.
- Empty-folder cleanup never removes the selected root, files, non-empty folders, links, or junctions, and rechecks emptiness immediately before each removal.
- Changing the selected folder invalidates every plan built for the previous folder.
- Organize, Flatten, and Undo recheck that each source is still a regular file immediately before moving it.
- The application cannot close while a background file operation is active.

## V1 flow

```text
Select directory -> Scan clips -> Read metadata -> Build plan -> Optional manual review -> Preview -> Confirm -> Move ready files

Organized/Unsorted -> Manual review -> Build follow-up plan -> Confirm -> Move classified files
```
