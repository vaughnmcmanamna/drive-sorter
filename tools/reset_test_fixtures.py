"""Restore disposable video samples from the repository's canonical fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "test-fixtures" / "manual-review-samples"
DESTINATION = ROOT / "test-videos" / "manual-review-samples"
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm", ".wmv"}


def reset_test_fixtures() -> list[Path]:
    """Copy canonical samples into the disposable test folder."""
    sources = sorted(
        file for file in FIXTURES.iterdir()
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not sources:
        raise RuntimeError(f"No canonical video fixtures found in {FIXTURES}")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    restored = []
    for source in sources:
        destination = DESTINATION / source.name
        shutil.copy2(source, destination)
        restored.append(destination)
    return restored


def main() -> None:
    restored = reset_test_fixtures()
    print(f"Restored {len(restored)} test clip(s) to {DESTINATION}")


if __name__ == "__main__":
    main()
