"""Generate PyInstaller's Windows version resource from version.py."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from version import __version__
parts = [int(part) for part in __version__.split(".")]
if len(parts) != 3:
    raise SystemExit("Drive Sorter versions must use major.minor.patch format.")
numeric = (*parts, 0)
content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric!r},
    prodvers={numeric!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Drive Sorter'),
         StringStruct('FileDescription', 'Drive Sorter game clip organizer'),
         StringStruct('FileVersion', '{__version__}'),
         StringStruct('InternalName', 'Drive Sorter'),
         StringStruct('OriginalFilename', 'Drive Sorter.exe'),
         StringStruct('ProductName', 'Drive Sorter'),
         StringStruct('ProductVersion', '{__version__}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
destination = ROOT / "packaging" / "windows-version-info.txt"
destination.write_text(content, encoding="utf-8")
print(f"Created {destination} for {__version__}")
