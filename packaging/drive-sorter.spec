# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
ffmpeg_bin = project_root / "vendor" / "ffmpeg" / "bin"
required_tools = [ffmpeg_bin / "ffmpeg.exe", ffmpeg_bin / "ffprobe.exe"]
missing = [str(path) for path in required_tools if not path.is_file()]
if missing:
    raise SystemExit("Run tools/fetch_ffmpeg.ps1 first. Missing: " + ", ".join(missing))

a = Analysis(
    [str(project_root / "launch_drive_sorter.pyw")],
    pathex=[str(project_root)],
    binaries=[(str(path), "tools") for path in required_tools],
    datas=[(str(project_root / "assets" / "drive-sorter-icon.png"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["unittest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Drive Sorter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "drive-sorter-icon.ico"),
    version=str(project_root / "packaging" / "windows-version-info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Drive Sorter",
)
