# Core Design

## Program Flow

```text
Scan files
    ↓
Read metadata
    ↓
Identify game/year
    ↓
Build move plan
    ↓
Preview
    ↓
Move files
```

## Components

### Scanner

* Finds video files in the selected directory.

### Metadata Reader

* Extracts the title.
* Extracts the creation date.

### Detector

* Determines the game from the available metadata.
* Determines the year.

### Planner

* Determines the proposed destination for each clip.
* Checks for conflicts at the destination.

### Organizer

* Moves files to their proposed destinations after confirmation.
