# Releasing Drive Sorter

## What the release contains

- `DriveSorter-Setup-<version>-x64.exe`: per-user Windows installer with shortcuts and uninstall support.
- `DriveSorter-Portable-<version>-x64.zip`: portable application folder.
- `ffmpeg-9.0.1-source.tar.xz`: corresponding source for the bundled GPLv3 FFmpeg build.
- `SHA256SUMS.txt`: checksums for every release artifact.

Python, Tkinter, FFmpeg, and FFprobe are bundled. End users do not install them separately.

## Local release build

Run from PowerShell on 64-bit Windows:

```powershell
.\tools\build_release.ps1
```

The script:

1. Downloads the pinned FFmpeg 9.0.1 Essentials binary and corresponding source.
2. Verifies both SHA-256 hashes.
3. Creates an isolated `.build-venv` and installs pinned build dependencies.
4. Generates the Windows icon and version resource.
5. Builds the PyInstaller `onedir` application.
6. Runs the packaged GUI/tool smoke test.
7. Produces the portable ZIP and Inno Setup installer under `release`.
8. Writes `SHA256SUMS.txt`.

Inno Setup 6 is required for the installer. Use `-SkipInstaller` only when intentionally building the portable package by itself.

## Versioning

Change `__version__` in `version.py`. Windows executable metadata, installer version, filenames, and GitHub release artifacts derive from it.

Use tags such as `v0.1.0`. The tag version must match `version.py` before publishing.

## Signing

For a certificate already installed in the Windows certificate store:

```powershell
$env:DRIVE_SORTER_SIGNING_THUMBPRINT = "CERTIFICATE_THUMBPRINT"
.\tools\build_release.ps1
```

The build signs and verifies the application before creating the installer, then signs and verifies the installer. FFmpeg's third-party binaries are not modified.

Do not publish a production installer until a trusted code-signing certificate or Microsoft signing service has been configured. Unsigned beta builds will normally produce a Windows SmartScreen warning.

## GitHub

`.github/workflows/release.yml` builds artifacts on demand and publishes them when a `v*` tag is pushed. CI artifacts are unsigned, so the workflow marks the GitHub release as a pre-release and includes a SmartScreen warning. Promote it to a normal release only after replacing the artifacts with signed builds.

Before pushing a release tag:

1. Run all tests.
2. Build locally.
3. Test install, startup, Organize, manual review, Undo, and uninstall on a clean Windows VM.
4. Confirm the checksums and FFmpeg source archive are present.
5. Confirm the release notes and that the MIT and FFmpeg notices are included.
6. Configure signing for a public production release.

## Clean-machine test

Use a Windows 10 or Windows 11 x64 virtual machine without Python or FFmpeg installed. Confirm:

- Installation succeeds without administrator rights.
- The folder field starts empty.
- Scan metadata and manual preview both work, proving bundled FFprobe and FFmpeg are used.
- Application state is written below `%LOCALAPPDATA%\DriveSorter`.
- An upgrade preserves state.
- Uninstall removes program files while leaving user-created clips untouched.
