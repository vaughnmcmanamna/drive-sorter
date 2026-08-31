# Requirements

## Functional requirements

- The user selects a directory in the GUI or supplies one to the command-line tool.
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

## Safety requirements

- Existing destination files must never be overwritten.
- Duplicate destinations within one run must be skipped.
- Destinations are checked again immediately before each move.
- Flatten destinations are also checked again immediately before each move.
- Destination comparisons account for Windows' case-insensitive filenames.
- A failure reading or moving one clip must not stop other clips from being processed.
- `ffprobe` must time out rather than block a scan indefinitely.
- The `Organized` output folder must not be scanned again.
- Undo never overwrites a file that has reappeared at its original location.

## V1 flow

```text
Select directory -> Scan clips -> Read metadata -> Build plan -> Preview -> Confirm -> Move ready files
```
