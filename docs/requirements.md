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

## Safety requirements

- Existing destination files must never be overwritten.
- Duplicate destinations within one run must be skipped.
- Destinations are checked again immediately before each move.
- A failure reading or moving one clip must not stop other clips from being processed.
- `ffprobe` must time out rather than block a scan indefinitely.
- The `Organized` output folder must not be scanned again.

## V1 flow

```text
Select directory -> Scan clips -> Read metadata -> Build plan -> Preview -> Confirm -> Move ready files
```
