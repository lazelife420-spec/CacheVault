#!/usr/bin/env pwsh
# ============================================================================
# Cache Vault — canonical one-command local release-confidence gate.
#
#   pwsh scripts/ci_local_full.ps1            # run the full gate
#   pwsh scripts/ci_local_full.ps1 -Build     # also rebuild the packaged .exe first
#
# Honesty rules baked in:
#   * Refuses to claim PASS if required runtime deps are missing (preflight).
#   * Never hides skips — prints skip count + reasons.
#   * Exit code 0 only when every required gate passed.
# ============================================================================
[CmdletBinding()]
param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Resolve interpreter: prefer the project venv, fall back to PATH python.
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$TmpDir = Join-Path $env:TEMP "cv_ci_logs"
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

$gates = [ordered]@{}     # gate name -> $true/$false
$detail = [ordered]@{}    # gate name -> human detail string

function Write-Head($t) { Write-Host "`n===== $t =====" -ForegroundColor Cyan }

function Invoke-Pytest($name, [string[]]$targets) {
    Write-Head "pytest: $name"
    $log = Join-Path $TmpDir ("pytest_" + ($name -replace '\W', '_') + ".txt")
    & $Py -m pytest -rs --color=no @targets *> $log
    $ok = ($LASTEXITCODE -eq 0)
    $summary = (Get-Content $log | Select-String -Pattern '\d+ (passed|failed|skipped|error)' |
        Select-Object -Last 1).Line
    if (-not $summary) { $summary = "(no summary parsed)" }
    Write-Host $summary
    $gates[$name] = $ok
    $detail[$name] = $summary.Trim()
    return $log
}

# --- Preflight: required runtime deps must import ---------------------------
Write-Head "Preflight: required dependencies"
$pf = & $Py -c @'
import importlib.util, sys
req = ["cryptography", "customtkinter", "PIL", "zeroconf"]
if sys.platform.startswith("win"):
    req.append("win32api")
missing = [m for m in req if importlib.util.find_spec(m) is None]
print("python " + sys.version.split()[0])
print("missing=" + (",".join(missing) if missing else "none"))
sys.exit(1 if missing else 0)
'@
$preflightOk = ($LASTEXITCODE -eq 0)
Write-Host $pf
if (-not $preflightOk) {
    Write-Host "`nRequired dependencies missing. Install: $Py -m pip install -r requirements.txt" -ForegroundColor Red
    Write-Host "`nCACHE VAULT LOCAL CI: ENVIRONMENT INCOMPLETE" -ForegroundColor Red
    Write-Host "Cannot claim PASS without the full required environment." -ForegroundColor Red
    exit 2
}

# --- Full suite (authoritative pass/skip counts) ----------------------------
$fullLog = Invoke-Pytest "full" @()

# Parse skip count + reasons from the full run (the authoritative source).
$skipCount = 0
if ($detail["full"] -match '(\d+) skipped') { $skipCount = [int]$Matches[1] }
$skipReasons = @(Get-Content $fullLog | Select-String -Pattern '^SKIPPED \[\d+\]' |
    ForEach-Object { ($_.Line -replace '^SKIPPED \[\d+\]\s*', '').Trim() } |
    Sort-Object -Unique)

# --- Targeted subsets (named gates the team cares about) --------------------
Invoke-Pytest "founder-critical" @("tests/test_licensing.py", "tests/test_feature_gate.py", "tests/test_app_receipt.py", "tests/test_proof_exports.py") | Out-Null
Invoke-Pytest "command-center" @("tests/test_command_center.py", "tests/test_command_center_ui.py", "tests/test_command_center_app.py") | Out-Null
Invoke-Pytest "quick-paste" @("tests/test_quick_paste.py") | Out-Null
Invoke-Pytest "receipts-export" @("tests/test_app_receipt.py", "tests/test_export.py", "tests/test_proof_exports.py", "tests/test_receipt_ledger.py", "tests/test_html_bundles.py", "tests/test_drag_export.py", "tests/test_editable_copies.py") | Out-Null

# --- compileall -------------------------------------------------------------
Write-Head "compileall cache_vault"
& $Py -m compileall -q cache_vault
$gates["compileall"] = ($LASTEXITCODE -eq 0)

# --- selftest (source pipeline) ---------------------------------------------
Write-Head "selftest (app.py --selftest)"
& $Py app.py --selftest
$gates["selftest"] = ($LASTEXITCODE -eq 0)

# --- Headless smokes --------------------------------------------------------
Write-Head "smokes"
$smokeScripts = @("command_center_runtime_proof.py")
$smokesOk = $true
foreach ($s in $smokeScripts) {
    $path = Join-Path $Root "scripts\$s"
    if (-not (Test-Path $path)) { Write-Host "skip (absent): $s"; continue }
    $log = Join-Path $TmpDir ("smoke_" + ($s -replace '\W', '_') + ".txt")
    & $Py $path *> $log
    $ok = ($LASTEXITCODE -eq 0)
    $tail = (Get-Content $log | Select-Object -Last 1)
    Write-Host ("{0}: {1} -- {2}" -f $s, ($(if ($ok) { "PASS" } else { "FAIL" })), $tail)
    if (-not $ok) { $smokesOk = $false }
}
$gates["smokes"] = $smokesOk

# --- Claim tripwire ----------------------------------------------------------
Write-Head "claim tripwire"
$tripLog = Join-Path $TmpDir "scan_claims.txt"
& $Py (Join-Path $Root "scripts\scan_claims.py") *> $tripLog
$gates["claims"] = ($LASTEXITCODE -eq 0)
$claimsSummary = (Get-Content $tripLog | Select-Object -First 1)
Write-Host "claims: $claimsSummary"

# --- Packaging verification -------------------------------------------------
Write-Head "packaging"
$exe = Join-Path $Root "dist\CacheVault.exe"
$packagingState = "SKIP"
if ($Build) {
    Write-Host "Rebuilding packaged exe (-Build)..."
    & pwsh (Join-Path $Root "packaging\build_exe.ps1")
    if ($LASTEXITCODE -ne 0) { $packagingState = "FAIL" }
}
if (Test-Path $exe) {
    $h = (Get-FileHash -Algorithm SHA256 $exe).Hash
    $sizeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "artifact: dist\CacheVault.exe  ${sizeMB} MB"
    Write-Host "sha256:   $h"
    if ($packagingState -ne "FAIL") { $packagingState = "PASS" }
} else {
    Write-Host "no packaged artifact (run with -Build to produce one)"
}

# --- Summary ----------------------------------------------------------------
$pytestOk = $gates["full"] -and $gates["founder-critical"] -and $gates["command-center"] `
    -and $gates["quick-paste"] -and $gates["receipts-export"]
$requiredOk = $preflightOk -and $pytestOk -and $gates["compileall"] -and $gates["selftest"] -and $gates["smokes"] -and $gates["claims"]
# Packaging only blocks when a build was requested and failed.
if ($packagingState -eq "FAIL") { $requiredOk = $false }

function Mark($b) { if ($b) { "PASS" } else { "FAIL" } }

$skipText = "$skipCount"
if ($skipCount -gt 0) { $skipText += " (" + ($skipReasons -join " | ") + ")" }
else { $skipText += " (none on this environment)" }

Write-Host "`n----------------------------------------"
Write-Host ("CACHE VAULT LOCAL CI: {0}" -f (Mark $requiredOk)) -ForegroundColor $(if ($requiredOk) { "Green" } else { "Red" })
Write-Host ("pytest: {0}  [full: {1}]" -f (Mark $pytestOk), $detail["full"])
Write-Host ("  founder-critical: {0} | command-center: {1} | quick-paste: {2} | receipts-export: {3}" -f `
    (Mark $gates["founder-critical"]), (Mark $gates["command-center"]), (Mark $gates["quick-paste"]), (Mark $gates["receipts-export"]))
Write-Host ("compileall: {0}" -f (Mark $gates["compileall"]))
Write-Host ("selftest: {0}" -f (Mark $gates["selftest"]))
Write-Host ("smokes: {0}" -f (Mark $gates["smokes"]))
Write-Host ("claims: {0}" -f (Mark $gates["claims"]))
Write-Host ("packaging: {0}" -f $packagingState)
Write-Host ("known skips: {0}" -f $skipText)
Write-Host "----------------------------------------"

exit $(if ($requiredOk) { 0 } else { 1 })
