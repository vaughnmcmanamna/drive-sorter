# Requirements

## Functional Requirements

- User can select a directory to organize.
- Application scans the selected directory for video files.
- Application identifies the game and year for each clip.
- Clips are organized into `Game / Year`.
- Application shows the proposed file moves before changing anything.
- User must confirm before files are moved.
- Clips where the game cannot be identified are placed in an `Unsorted` folder.
- If the game is known but the year isn't, place the clip in `Game / Unknown Year`.

## Non-Functional Requirements

- The application should not overwrite existing files.
- The application should not delete clips.
- File organization should be predictable and repeatable.


# V1
Select directory
      ↓
Find video files
      ↓
Determine game + year
      ↓
Determine destination
      ↓
Check for conflicts
      ↓
Show preview
      ↓
User confirms
      ↓
Move files