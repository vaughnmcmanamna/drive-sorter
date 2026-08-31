# Issues and Lessons

## Missing game metadata created too many folders

**Symptom:** Clips without a usable title were grouped under folders named after individual filenames.

**Cause:** The first implementation used the filename stem as a fallback game name.

**Resolution:** Removed filename fallback. Clips without a valid metadata title now go directly to `Organized/Unsorted`.

## The interface appeared stuck after a scan

**Symptom:** A long per-file list of `READY` results made the scan look unfinished and buried the confirmation action.

**Cause:** The GUI was rendering every planned move into the text panel.

**Resolution:** Replaced the default output with a progress bar and summary. The confirmation button stays visible beside Scan, and the full plan is available through a toggle.

## GUI could freeze while moving files

**Symptom:** Moving many clips could block the window and delay completion feedback.

**Cause:** File moves ran on Tkinter's main event thread.

**Resolution:** Scans and moves now run in background threads. A queue sends progress and completion events back to the GUI thread.

## Text displayed with corrupted characters

**Symptom:** Some arrows, ellipses, and separators displayed as garbled multi-byte text.

**Cause:** Text encoding differed between the editor, shell, and saved files.

**Resolution:** The user-facing interface and documentation now use plain ASCII punctuation such as `...`, `-`, and `->`.

## `ffprobe` can fail or hang

**Symptom:** A missing executable, bad video, or stalled probe could stop a scan.

**Resolution:** `ffprobe` errors are captured per file, and each call has a 30-second timeout. Affected clips remain visible in the scan result and are sent to `Unsorted`.

## Destination files can change after preview

**Symptom:** A destination may be created after the move plan is built.

**Resolution:** The organizer checks for an existing destination again immediately before each move and skips it if one exists.

## Flatten destinations can also become stale

**Symptom:** A file could appear at a planned flatten destination after confirmation.

**Resolution:** Flattening now performs the same last-second destination check and selects a new numeric suffix rather than risking an overwrite.

## The GUI launcher hid a runtime layout error

**Symptom:** The `.pyw` launcher did not open a window after a layout change.

**Cause:** Tkinter accepts a padding tuple for geometry managers but not for a frame's own `pady` option.

**Resolution:** Replaced the invalid value and added a startup check that constructs and closes the GUI before handoff.
