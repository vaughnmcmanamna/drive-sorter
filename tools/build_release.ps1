param(
    [string]$CertificateThumbprint = $env:DRIVE_SORTER_SIGNING_THUMBPRINT,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
$pythonPath = (Get-ItemProperty "HKCU:\Software\Python\PythonCore\3.13\InstallPath" -ErrorAction SilentlyContinue).ExecutablePath
if (-not $pythonPath) {
    $pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
}
$version = (& $pythonPath -c "from version import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Could not read the application version."
}

function Reset-ProjectDirectory([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    $fullRoot = [IO.Path]::GetFullPath($projectRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not $fullPath.StartsWith($fullRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset a directory outside the project: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
}

& (Join-Path $PSScriptRoot "fetch_ffmpeg.ps1")

$venvRoot = Join-Path $projectRoot ".build-venv"
if (-not (Test-Path -LiteralPath (Join-Path $venvRoot "Scripts\python.exe"))) {
    & $pythonPath -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw "Could not create the build virtual environment." }
}
$buildPython = Join-Path $venvRoot "Scripts\python.exe"
& $buildPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install build dependencies." }
& $buildPython (Join-Path $PSScriptRoot "create_windows_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Could not generate the Windows icon." }
& $buildPython (Join-Path $PSScriptRoot "create_version_info.py")
if ($LASTEXITCODE -ne 0) { throw "Could not generate Windows version information." }

Reset-ProjectDirectory (Join-Path $projectRoot "build")
Reset-ProjectDirectory (Join-Path $projectRoot "dist")
Reset-ProjectDirectory (Join-Path $projectRoot "release")

& $buildPython -m PyInstaller --noconfirm --clean (Join-Path $projectRoot "packaging\drive-sorter.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed."
}

$appDirectory = Join-Path $projectRoot "dist\Drive Sorter"
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $appDirectory
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $appDirectory
Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination $appDirectory
Copy-Item -LiteralPath (Join-Path $projectRoot "vendor\ffmpeg\licenses") -Destination (Join-Path $appDirectory "licenses") -Recurse -Force

$appExe = Join-Path $appDirectory "Drive Sorter.exe"
$smoke = Start-Process -FilePath $appExe -ArgumentList "--release-smoke-test" -Wait -PassThru -WindowStyle Hidden
if ($smoke.ExitCode -ne 0) {
    throw "The packaged application failed its startup/tool smoke test."
}

if ($CertificateThumbprint) {
    & (Join-Path $PSScriptRoot "sign_release.ps1") -CertificateThumbprint $CertificateThumbprint -Files $appExe
} else {
    Write-Warning "The application is unsigned. Set DRIVE_SORTER_SIGNING_THUMBPRINT for public releases."
}

$portableArchive = Join-Path $projectRoot "release\DriveSorter-Portable-$version-x64.zip"
Compress-Archive -Path (Join-Path $appDirectory "*") -DestinationPath $portableArchive -CompressionLevel Optimal
Copy-Item -LiteralPath (Join-Path $projectRoot "vendor\downloads\ffmpeg-9.0.1.tar.xz") -Destination (Join-Path $projectRoot "release\ffmpeg-9.0.1-source.tar.xz")

if (-not $SkipInstaller) {
    $isccCandidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source,
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $iscc = $isccCandidates | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 was not found. Install it or use -SkipInstaller."
    }
    & $iscc "/DMyAppVersion=$version" (Join-Path $projectRoot "packaging\installer.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed."
    }
    $installer = Join-Path $projectRoot "release\DriveSorter-Setup-$version-x64.exe"
    if ($CertificateThumbprint) {
        & (Join-Path $PSScriptRoot "sign_release.ps1") -CertificateThumbprint $CertificateThumbprint -Files $installer
    }
}

Get-FileHash -Path (Join-Path $projectRoot "release\*") -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($_.Path))" } |
    Set-Content -LiteralPath (Join-Path $projectRoot "release\SHA256SUMS.txt") -Encoding utf8

Write-Host "Release $version is ready in $(Join-Path $projectRoot 'release')"
