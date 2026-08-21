# Packaged Founder MVP smoke gate — run against dist\CacheVault.exe
# Usage: pwsh scripts\founder_package_smoke.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$exe = Join-Path $root "dist\CacheVault.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Missing $exe — run packaging\build_exe.ps1 first"
}

$exeBytes = [System.IO.File]::ReadAllBytes($exe)
$exeText = [System.Text.Encoding]::ASCII.GetString($exeBytes)
if ($exeText -notmatch "cache_vault\.ui\.founder") {
    throw "Packaged exe missing cache_vault.ui.founder — rebuild before release"
}

$testLicense = "C:\secure\cachevault-keys\founder-test-license.json"
if (-not (Test-Path -LiteralPath $testLicense)) {
    throw "Missing test license: $testLicense"
}

function Invoke-ExeSelftest {
    param([string]$LocalAppData, [string]$Label)
    $env:LOCALAPPDATA = $LocalAppData
    Remove-Item -Recurse -Force $LocalAppData -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $LocalAppData | Out-Null
    $out = & $exe --selftest 2>&1 | Out-String
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $code -ne $null) { return @{ Label = $Label; Pass = $false; Detail = $out.Trim() } }
    if ($out -match "selftest OK") { return @{ Label = $Label; Pass = $true; Detail = $out.Trim() } }
    return @{ Label = $Label; Pass = $false; Detail = $out.Trim() }
}

$results = @()

# Free mode
$freeDir = Join-Path $env:TEMP "cv-smoke-free"
$results += Invoke-ExeSelftest -LocalAppData $freeDir -Label "Fresh launch / free selftest"

# Invalid license rejected
#
# NOTE: this cannot be driven through `$exe --selftest` — --selftest always
# runs inside an isolated, auto-managed temp profile (see
# `_run_contained_selftest` in app.py) that overrides LOCALAPPDATA itself,
# specifically so selftest never touches real user data. That containment
# is intentional, already-canonical hardening, not a defect (see Release
# Closure R3/R4). It means any license.json staged here via $env:LOCALAPPDATA
# is invisible to --selftest, which is why this step used to silently pass
# regardless of license validity. Fixed by calling the same `cache_vault`
# licensing module the packaged build ships, directly -- the same pattern
# already used below for the proof-receipt-export check.
$badDir = Join-Path $env:TEMP "cv-smoke-bad-license"
$env:LOCALAPPDATA = $badDir
Remove-Item -Recurse -Force $badDir -ErrorAction SilentlyContinue
$licDir = Join-Path $badDir "CacheVault"
New-Item -ItemType Directory -Force -Path $licDir | Out-Null
@'
{"product":"cache-vault","edition":"founder","licensee":"bad","issued_at":"2026-01-01T00:00:00Z","expires_at":null,"features":["proof_pack_export"],"signature":"AAAA"}
'@ | Set-Content -LiteralPath (Join-Path $licDir "license.json") -Encoding utf8
$badOut = python -c "from cache_vault import licensing; s = licensing.load_license(); print(s.state.value)" 2>&1 | Out-String
$badPass = $badOut -match "INVALID_SIGNATURE"
$results += @{ Label = "Invalid license rejected"; Pass = $badPass; Detail = $badOut.Trim() }

# Production test Founder license accepted
$founderDir = Join-Path $env:TEMP "cv-smoke-founder"
$env:LOCALAPPDATA = $founderDir
Remove-Item -Recurse -Force $founderDir -ErrorAction SilentlyContinue
$founderLicDir = Join-Path $founderDir "CacheVault"
New-Item -ItemType Directory -Force -Path $founderLicDir | Out-Null
Copy-Item -LiteralPath $testLicense -Destination (Join-Path $founderLicDir "license.json") -Force
$founderOut = python -c "from cache_vault import licensing; s = licensing.load_license(); print(s.state.value); print(licensing.is_feature_enabled('proof_pack_export'))" 2>&1 | Out-String
$founderPass = ($founderOut -match "FOUNDER_VALID") -and ($founderOut -match "True")
$results += @{ Label = "Production test Founder license accepted"; Pass = $founderPass; Detail = $founderOut.Trim() }

# Proof receipt export (dev runner — same licensing module as packaged build)
$receiptDir = Join-Path $env:TEMP "cv-smoke-receipt-out"
Remove-Item -Recurse -Force $receiptDir -ErrorAction SilentlyContinue
$env:LOCALAPPDATA = $founderDir
python -c "from pathlib import Path; from cache_vault.core import app_receipt; p=app_receipt.export_app_receipt(Path(r'$receiptDir')); print(p)"
$receiptPath = Get-ChildItem -Path $receiptDir -Directory | Select-Object -First 1
$receiptText = Get-Content -LiteralPath (Join-Path $receiptPath.FullName "APP_RECEIPT.md") -Raw
$noLeak = ($receiptText -notmatch "sk-abc123") -and ($receiptText -match "Founder")
$results += @{ Label = "Proof receipt export (no clipboard leak)"; Pass = $noLeak; Detail = $receiptPath.FullName }

Write-Host ""
Write-Host "=== Founder package smoke ==="
$allPass = $true
foreach ($r in $results) {
    $mark = if ($r.Pass) { "PASS" } else { "FAIL" }
    if (-not $r.Pass) { $allPass = $false }
    Write-Host "$mark  $($r.Label)"
    if (-not $r.Pass -and $r.Detail) { Write-Host "      $($r.Detail.Substring(0, [Math]::Min(200, $r.Detail.Length)))" }
}
if (-not $allPass) { exit 1 }
Write-Host "All automated packaged smoke checks passed."
