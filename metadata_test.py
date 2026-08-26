import subprocess
import json
from pathlib import Path

folder = Path(__file__).parent
for file in folder.glob("*.mp4"):
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

    title = metadata["format"]["tags"]["title"]
    clean_title = title.replace("\u200b", "")
    print(clean_title)
