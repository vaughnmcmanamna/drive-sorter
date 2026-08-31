"""Record a real Drive Sorter demo against temporary hard-linked test clips."""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "demo" / "actual-demo-clips"
VIDEO_SOURCES = list((ROOT / "test-videos").rglob("*.mp4"))
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v"}
OUTPUT = ROOT / "demo" / "drive-sorter-actual-demo.gif"
RECORDING = ROOT / "demo" / "drive-sorter-actual-demo.mp4"

USER32 = __import__("ctypes").windll.user32


def find_window(title: str, timeout: float = 10) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window = USER32.FindWindowW(None, title)
        if window:
            return window
        time.sleep(0.1)
    raise RuntimeError("Drive Sorter window did not open")


def prepare_fixture() -> None:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    FIXTURE.mkdir(parents=True)
    sources = [path for path in VIDEO_SOURCES if path.suffix.lower() in VIDEO_EXTENSIONS]
    if not sources:
        raise RuntimeError("No test videos were found")
    for source in sources:
        target = FIXTURE / "Old clip folders" / "To organize" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.hardlink_to(source)


def main() -> None:
    prepare_fixture()
    demo_title = "Drive Sorter Demo"
    demo_code = textwrap.dedent(f"""
import gui
gui.messagebox.askyesno = lambda *args, **kwargs: True
app = gui.DriveSorterApp()
app.title({demo_title!r})
app.directory.set({str(FIXTURE)!r})
def organize_when_ready():
    if str(app.organize_button['state']) == 'normal':
        app.organize()
    else:
        app.after(250, organize_when_ready)
def scan_after_flatten():
    if app.signal.get() == '[ FLATTEN COMPLETE ]':
        app.after(1200, app.scan)
        app.after(1450, organize_when_ready)
    else:
        app.after(250, scan_after_flatten)
app.after(1000, app.flatten)
app.after(1500, scan_after_flatten)
app.mainloop()
""")
    app = subprocess.Popen(
        ["pythonw", "-c", demo_code],
        cwd=ROOT,
        env=os.environ.copy(),
    )
    recorder = None
    try:
        window = find_window(demo_title)
        recorder = subprocess.Popen(
            [
                "ffmpeg", "-y", "-f", "gdigrab", "-framerate", "10",
                "-i", f"title={demo_title}", "-t", "10", str(RECORDING),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        time.sleep(9)
    finally:
        if recorder:
            recorder.wait(timeout=20)
        USER32.PostMessageW(window if "window" in locals() else 0, 0x0010, 0, 0)
        app.wait(timeout=5)
        if FIXTURE.exists():
            shutil.rmtree(FIXTURE)

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(RECORDING), "-vf", "fps=10,scale=900:-1:flags=lanczos", str(OUTPUT)],
        check=True,
    )
    RECORDING.unlink(missing_ok=True)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
