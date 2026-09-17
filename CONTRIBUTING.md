# Contributing to Drive Sorter

Thanks for helping improve Drive Sorter.

## Development setup

1. Install Python 3.11 or newer with Tkinter.
2. Install FFmpeg and FFprobe and make both commands available on `PATH`.
3. Clone the repository and run `python -m unittest -v`.
4. Start the app with `python gui.py`.

Use `python tools/reset_test_fixtures.py` to create disposable manual-review clips under the ignored `test-videos` directory.

## Submitting changes

- Keep file operations previewed, confirmed, and non-overwriting.
- Add or update tests for behavior changes.
- Run the complete test suite before opening a pull request.
- Keep unrelated changes in separate pull requests.
- Explain user-visible changes and any filesystem safety implications.

By submitting a contribution, you agree that it may be distributed under the project's MIT License.
