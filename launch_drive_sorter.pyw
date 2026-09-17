"""Double-click launcher for Drive Sorter; Windows runs .pyw files without a console."""

import sys

from gui import DriveSorterApp
from media_tools import verify_media_tools


if "--release-smoke-test" in sys.argv:
    app = DriveSorterApp()
    app.update_idletasks()
    app.destroy()
    raise SystemExit(1 if verify_media_tools() else 0)

DriveSorterApp().mainloop()
