param(
    [Parameter(Mandatory = $true)]
    [string]$CertificateThumbprint,
    [Parameter(Mandatory = $true)]
    [string[]]$Files
)

$ErrorActionPreference = "Stop"
$signTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if ($null -eq $signTool) {
    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    $signTool = Get-ChildItem -Path $kitsRoot -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object FullName -Match "\\x64\\signtool.exe$" |
        Sort-Object FullName -Descending |
        Select-Object -First 1
}
if ($null -eq $signTool) {
    throw "signtool.exe was not found. Install the Windows SDK signing tools."
}
$signToolPath = if ($signTool.Source) { $signTool.Source } else { $signTool.FullName }

foreach ($file in $Files) {
    $resolved = (Resolve-Path -LiteralPath $file).Path
    & $signToolPath sign /sha1 $CertificateThumbprint /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com $resolved
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed for $resolved"
    }
    & $signToolPath verify /pa /v $resolved
    if ($LASTEXITCODE -ne 0) {
        throw "Signature verification failed for $resolved"
    }
}
