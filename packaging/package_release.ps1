# Package a built Cache Vault executable into release artifacts.
#   pwsh packaging\package_release.ps1 -Tag v0.1.1
#
# Output:
#   dist\release\<tag>\CacheVault-<tag>-windows.zip
#   dist\release\<tag>\SHA256SUMS.txt

param(
    [Parameter(Mandatory = $true)]
    [string]$Tag
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$tagName = $Tag
if ($tagName.StartsWith("refs/tags/")) {
    $tagName = $tagName.Substring("refs/tags/".Length)
}

$exePath = Join-Path $root "dist\CacheVault.exe"
$notesPath = Join-Path $root "RELEASE_NOTES.md"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Missing built executable: $exePath"
}
if (-not (Test-Path -LiteralPath $notesPath)) {
    throw "Missing release notes file: $notesPath"
}

$releaseDir = Join-Path $root "dist\release\$tagName"
$stageDir = Join-Path $releaseDir "package"
$zipName = "CacheVault-$tagName-windows.zip"
$zipPath = Join-Path $releaseDir $zipName
$sumPath = Join-Path $releaseDir "SHA256SUMS.txt"

New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
Copy-Item -LiteralPath $exePath -Destination (Join-Path $stageDir "CacheVault.exe") -Force
Copy-Item -LiteralPath $notesPath -Destination (Join-Path $stageDir "RELEASE_NOTES.md") -Force

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -CompressionLevel Optimal

$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath $sumPath -Value "$zipHash  $zipName" -Encoding ascii

Remove-Item -LiteralPath $stageDir -Recurse -Force

Write-Host "Packaged: $zipPath"
Write-Host "Checksums: $sumPath"
