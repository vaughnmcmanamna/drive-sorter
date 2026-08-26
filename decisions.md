## Getting the game from a video

**Problem:** Filenames aren't reliable because some clips have been renamed.

**Investigation:** Used `ffprobe` to look at Game Bar metadata and found that the `title` field contains the game name. Tested this on a folder of clips and it worked for all of them.

**Decision:** Use the metadata title to identify the game. Fall back to the filename if the metadata isn't available.