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

## Next

- Add an undo log for an organization run
- Offer a conflict-resolution choice such as skip or rename
- Package the application with `ffprobe` availability checks for Windows distribution
- Add a small integration test that exercises a full scan-to-move workflow with mocked metadata
