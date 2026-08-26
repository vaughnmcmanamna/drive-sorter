import subprocess
import json
from pathlib import Path
from datetime import datetime

#Scanner
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".wmv",
    ".m4v",
}

folder = Path("test-videos")

def metadata_reader(file):
    result = subprocess.run(
                [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                file
                ],
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
    metadata = json.loads(result.stdout)

    game = metadata["format"]["tags"]["title"].replace("\u200b", "")

    time = datetime.fromisoformat(metadata["format"]["tags"]["creation_time"])

    return (game,time)

for file in folder.rglob("*"):
    if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS:
        result = metadata_reader(file)
        print(result)