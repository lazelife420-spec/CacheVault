# Package a built Cache Vault executable into release artifacts.
#   pwsh packaging\package_release.ps1 -Tag v0.1.2
#
# Output:
#   dist\release\<tag>\CacheVault-<tag>-windows.zip
#   dist\release\<tag>\SHA256SUMS.txt

param(
    [Parameter(Mandatory = $true)]
    [string]$Tag,
    [string]$NotesPath = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$tagName = $Tag
if ($tagName.StartsWith("refs/tags/")) {
    $tagName = $tagName.Substring("refs/tags/".Length)
}

$exePath = Join-Path $root "dist\CacheVault.exe"
if ($NotesPath) {
    $notesPath = if ([System.IO.Path]::IsPathRooted($NotesPath)) { $NotesPath } else { Join-Path $root $NotesPath }
} else {
    $notesPath = Join-Path $root "RELEASE_NOTES.md"
}
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Missing built executable: $exePath"
}

# Stale-exe guard: refuse to package if source changed after the exe was built.
$exeTime = (Get-Item -LiteralPath $exePath).LastWriteTimeUtc
$newerSource = Get-ChildItem -Path (Join-Path $root "cache_vault") -Recurse -Include *.py |
    Where-Object { $_.LastWriteTimeUtc -gt $exeTime }
if ($newerSource) {
    $count = $newerSource.Count
    $example = $newerSource | Select-Object -First 3 | ForEach-Object { $_.Name }
    throw "Stale executable: $count source file(s) newer than dist\CacheVault.exe ($exeTime). " +
          "Example: $($example -join ', '). Run packaging\build_exe.ps1 first."
}

# Version truth: pyproject.toml version must match tag.
$pyproject = Join-Path $root "pyproject.toml"
$pyText = Get-Content -LiteralPath $pyproject -Raw
if ($pyText -match 'version\s*=\s*"([^"]+)"') {
    $pyVersion = $Matches[1]
    $cleanTag = $tagName -replace '^v', ''
    if ($cleanTag -ne $pyVersion) {
        throw "Version mismatch: tag '$tagName' -> '$cleanTag' but pyproject.toml has '$pyVersion'"
    }
} elseif ($pyText -match "version\s*=\s*'([^']+)'") {
    $pyVersion = $Matches[1]
    $cleanTag = $tagName -replace '^v', ''
    if ($cleanTag -ne $pyVersion) {
        throw "Version mismatch: tag '$tagName' -> '$cleanTag' but pyproject.toml has '$pyVersion'"
    }
} else {
    throw "Could not find version in pyproject.toml"
}

# Verify the built exe contains the correct version string.
# The PE resource block stores version info as UTF-16LE; ASCII search alone is insufficient.
$exeBytes = [System.IO.File]::ReadAllBytes($exePath)
$exeTextAscii = [System.Text.Encoding]::ASCII.GetString($exeBytes)
$exeTextUtf16 = [System.Text.Encoding]::Unicode.GetString($exeBytes)
if ($exeTextAscii -notmatch "cache_vault\.ui\.founder") {
    throw "Built exe missing cache_vault.ui.founder — run packaging\build_exe.ps1 from current source"
}
$escapedVer = [regex]::Escape($pyVersion)
if (($exeTextAscii -notmatch $escapedVer) -and ($exeTextUtf16 -notmatch $escapedVer)) {
    throw "Built exe version ($pyVersion expected) not found in binary — may be stale"
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
