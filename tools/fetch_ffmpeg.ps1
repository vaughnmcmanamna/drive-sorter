param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vendorRoot = Join-Path $projectRoot "vendor\ffmpeg"
$downloadRoot = Join-Path $projectRoot "vendor\downloads"
$archivePath = Join-Path $downloadRoot "ffmpeg-9.0.1-essentials_build.zip"
$sourcePath = Join-Path $downloadRoot "ffmpeg-9.0.1.tar.xz"
$archiveUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.1-essentials_build.zip"
$sourceUrl = "https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz"
$archiveSha256 = "fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9"
$sourceSha256 = "cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635"

New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null

function Download-File([string]$Url, [string]$Destination) {
    $partial = $Destination + ".download"
    Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
    & curl.exe --location --fail --retry 3 --output $partial $Url
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $Url"
    }
    Move-Item -LiteralPath $partial -Destination $Destination -Force
}

if ($Force -or -not (Test-Path -LiteralPath $archivePath)) {
    Download-File $archiveUrl $archivePath
}
$actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $archiveSha256) {
    throw "FFmpeg archive checksum mismatch. Expected $archiveSha256 but received $actualHash."
}

$extractRoot = Join-Path $downloadRoot "ffmpeg-extracted"
$fullExtractRoot = [IO.Path]::GetFullPath($extractRoot)
$fullProjectRoot = [IO.Path]::GetFullPath($projectRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
if (-not $fullExtractRoot.StartsWith($fullProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to reset an extraction path outside the project: $fullExtractRoot"
}
if (Test-Path -LiteralPath $fullExtractRoot) {
    Remove-Item -LiteralPath $fullExtractRoot -Recurse -Force
}
Expand-Archive -LiteralPath $archivePath -DestinationPath $fullExtractRoot
$packageRoot = Get-ChildItem -LiteralPath $fullExtractRoot -Directory | Select-Object -First 1
if ($null -eq $packageRoot) {
    throw "The FFmpeg archive did not contain its expected root directory."
}

New-Item -ItemType Directory -Force -Path (Join-Path $vendorRoot "bin") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $vendorRoot "licenses") | Out-Null
Copy-Item -LiteralPath (Join-Path $packageRoot.FullName "bin\ffmpeg.exe") -Destination (Join-Path $vendorRoot "bin\ffmpeg.exe") -Force
Copy-Item -LiteralPath (Join-Path $packageRoot.FullName "bin\ffprobe.exe") -Destination (Join-Path $vendorRoot "bin\ffprobe.exe") -Force
Copy-Item -LiteralPath (Join-Path $packageRoot.FullName "LICENSE") -Destination (Join-Path $vendorRoot "licenses\FFmpeg-GPLv3.txt") -Force
Copy-Item -LiteralPath (Join-Path $packageRoot.FullName "README.txt") -Destination (Join-Path $vendorRoot "licenses\FFmpeg-build-README.txt") -Force
Remove-Item -LiteralPath $fullExtractRoot -Recurse -Force

if ($Force -or -not (Test-Path -LiteralPath $sourcePath)) {
    Download-File $sourceUrl $sourcePath
}
$actualSourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSourceHash -ne $sourceSha256) {
    throw "FFmpeg source checksum mismatch. Expected $sourceSha256 but received $actualSourceHash."
}

Write-Host "Prepared pinned FFmpeg tools in $vendorRoot"
Write-Host "Corresponding source archive: $sourcePath"
