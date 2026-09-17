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
DEMO_CLIPS_PER_SOURCE = 4

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
        for number in range(1, DEMO_CLIPS_PER_SOURCE + 1):
            target = FIXTURE / "Old clip folders" / "To organize" / f"{source.stem}-{number:02}{source.suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.hardlink_to(source)


def main() -> None:
    prepare_fixture()
    demo_title = "Drive Sorter Demo"
    demo_code = textwrap.dedent(f"""
import gui
import organizer
import time
import ctypes
ctypes.windll.user32.SetProcessDPIAware()
gui.messagebox.askyesno = lambda *args, **kwargs: True
app = gui.DriveSorterApp()
app.title({demo_title!r})
app.directory.set({str(FIXTURE)!r})
app._confirm = lambda *args, **kwargs: True
original_metadata_reader = organizer.metadata_reader
def slower_metadata_reader(path):
    time.sleep(0.45)
    return original_metadata_reader(path)
organizer.metadata_reader = slower_metadata_reader
user32 = ctypes.windll.user32

def glide_to(widget, duration=500):
    app.update_idletasks()
    target_x = widget.winfo_rootx() + widget.winfo_width() // 2
    # gdigrab crops out the native title bar, but Tk includes it in root
    # coordinates. This keeps the recorded pointer visually on its control.
    target_y = widget.winfo_rooty() + widget.winfo_height() // 2 - 40
    class Point(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
    point = Point()
    user32.GetCursorPos(ctypes.byref(point))
    for step in range(1, 17):
        progress = step / 16
        x = round(point.x + (target_x - point.x) * progress)
        y = round(point.y + (target_y - point.y) * progress)
        app.after(round(duration * progress), lambda x=x, y=y: user32.SetCursorPos(x, y))

def organize_when_ready():
    if str(app.organize_button['state']) == 'normal':
        glide_to(app.organize_button)
        app.after(700, app.organize)
    else:
        app.after(250, organize_when_ready)
def scan_after_flatten():
    if app.signal.get() == '[ FLATTEN COMPLETE ]':
        glide_to(app.scan_button)
        app.after(700, app.scan)
        app.after(1000, organize_when_ready)
    else:
        app.after(250, scan_after_flatten)
app.after(600, app._show_tools_panel)
app.after(750, lambda: glide_to(app.flatten_button))
app.after(1450, lambda: (app._hide_tools_panel(), app.flatten()))
app.after(1750, scan_after_flatten)
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
                "-i", f"title={demo_title}", "-t", "18", str(RECORDING),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        time.sleep(17)
    finally:
        if recorder:
            recorder.wait(timeout=20)
        USER32.PostMessageW(window if "window" in locals() else 0, 0x0010, 0, 0)
        app.wait(timeout=5)
        if FIXTURE.exists():
            shutil.rmtree(FIXTURE)

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(RECORDING), "-vf", "fps=6,scale=720:-1:flags=lanczos", str(OUTPUT)],
        check=True,
    )
    RECORDING.unlink(missing_ok=True)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
