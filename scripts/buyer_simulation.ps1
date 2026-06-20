# Buyer simulation — run before first public sale
# Usage: pwsh scripts\buyer_simulation.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$exe = Join-Path $root "dist\CacheVault.exe"
$zip = Join-Path $root "dist\release\v0.1.3-founder-mvp\CacheVault-v0.1.3-founder-mvp-windows.zip"
$testLicense = "C:\secure\cachevault-keys\founder-test-license.json"
$releaseUrl = "https://github.com/Z3r0DayZion-install/CacheVault/releases/tag/v0.1.3-founder-mvp"
$landingUrl = "https://z3r0dayzion-install.github.io/cache-vault-landing/"

$results = @()

function Step($label, $pass, $detail = "") {
    $script:results += [pscustomobject]@{ Step = $label; Pass = $pass; Detail = $detail }
}

# 1. Artifacts exist
Step "Release ZIP built locally" (Test-Path $zip) $zip
Step "Packaged EXE exists" (Test-Path $exe) $exe
Step "Production test license exists" (Test-Path $testLicense) $testLicense

# 2. GitHub release has asset
try {
    $rel = gh release view v0.1.3-founder-mvp --repo Z3r0DayZion-install/CacheVault --json assets,url 2>$null | ConvertFrom-Json
    $hasZip = ($rel.assets | Where-Object { $_.name -like "*.zip" }).Count -gt 0
    Step "GitHub Release has ZIP asset" $hasZip $rel.url
} catch {
    Step "GitHub Release has ZIP asset" $false "Release v0.1.3-founder-mvp not found — run gh release create"
}

# 3. Landing reachable
try {
    $resp = Invoke-WebRequest -Uri $landingUrl -UseBasicParsing -TimeoutSec 20
    Step "Landing page HTTP 200" ($resp.StatusCode -eq 200) $landingUrl
    Step "Landing links to release" ($resp.Content -match "v0.1.3-founder-mvp") ""
} catch {
    Step "Landing page HTTP 200" $false $_.Exception.Message
}

# 4. Free mode packaged selftest
$freeDir = Join-Path $env:TEMP "cv-buyer-sim-free"
$env:LOCALAPPDATA = $freeDir
Remove-Item -Recurse -Force $freeDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $freeDir | Out-Null
if (Test-Path $exe) {
    $out = & $exe --selftest 2>&1 | Out-String
    Step "Free mode selftest (packaged EXE)" ($out -match "selftest OK") $out.Trim()
} else {
    Step "Free mode selftest (packaged EXE)" $false "Missing exe"
}

# 5. Invalid license rejected
$badDir = Join-Path $env:TEMP "cv-buyer-sim-bad"
$env:LOCALAPPDATA = $badDir
Remove-Item -Recurse -Force $badDir -ErrorAction SilentlyContinue
$licDir = Join-Path $badDir "CacheVault"
New-Item -ItemType Directory -Force -Path $licDir | Out-Null
'{"product":"cache-vault","edition":"founder","licensee":"bad","issued_at":"2026-01-01T00:00:00Z","expires_at":null,"features":["proof_pack_export"],"signature":"AAAA"}' |
    Set-Content (Join-Path $licDir "license.json") -Encoding utf8
if (Test-Path $exe) {
    $badOut = & $exe --selftest 2>&1 | Out-String
    Step "Invalid license rejected" (($badOut -match "license smoke failed") -or ($LASTEXITCODE -ne 0)) ""
}

# 6. Founder license accepted + persists
$founderDir = Join-Path $env:TEMP "cv-buyer-sim-founder"
$env:LOCALAPPDATA = $founderDir
Remove-Item -Recurse -Force $founderDir -ErrorAction SilentlyContinue
$founderLicDir = Join-Path $founderDir "CacheVault"
New-Item -ItemType Directory -Force -Path $founderLicDir | Out-Null
if (Test-Path $testLicense) {
    Copy-Item $testLicense (Join-Path $founderLicDir "license.json") -Force
}
if (Test-Path $exe) {
    $fOut = & $exe --selftest 2>&1 | Out-String
    Step "Founder license accepted (selftest)" ($fOut -match "selftest OK") ""
    $licPath = Join-Path $founderLicDir "license.json"
    Step "License file persists on disk" (Test-Path $licPath) $licPath
    # Restart simulation: run selftest again
    $fOut2 = & $exe --selftest 2>&1 | Out-String
    Step "Founder active after restart (selftest)" ($fOut2 -match "selftest OK") ""
}

# 7. Proof receipt — no clipboard leak
$receiptOut = Join-Path $env:TEMP "cv-buyer-sim-receipt"
Remove-Item -Recurse -Force $receiptOut -ErrorAction SilentlyContinue
$env:LOCALAPPDATA = $founderDir
python -c "from pathlib import Path; from cache_vault.core import app_receipt; print(app_receipt.export_app_receipt(Path(r'$receiptOut')))" 2>&1 | Out-Null
$receiptFolder = Get-ChildItem $receiptOut -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($receiptFolder) {
    $receiptText = Get-Content (Join-Path $receiptFolder.FullName "APP_RECEIPT.md") -Raw
    $noSecrets = ($receiptText -notmatch "sk-") -and ($receiptText -match "Founder|Free")
    Step "Proof receipt exports" $true $receiptFolder.FullName
    Step "Receipt has no clipboard leak" $noSecrets ""
} else {
    Step "Proof receipt exports" $false ""
}

# 8. Checkout placeholder (informational — expected until you wire payment)
try {
    $landing = (Invoke-WebRequest -Uri $landingUrl -UseBasicParsing).Content
    $isPlaceholder = $landing -match 'href="#founder"'
    if ($isPlaceholder) {
        Write-Host ""
        Write-Host "WARN  Checkout still placeholder (#founder) — wire before first sale."
        Write-Host "      See docs/FOUNDER_FIRST_SALE.md step 2."
    } else {
        Step "Checkout URL wired on landing" $true ""
    }
} catch {
    Write-Host "WARN  Could not verify checkout URL on landing."
}

Write-Host ""
Write-Host "=== Buyer simulation ==="
$failed = 0
foreach ($r in $results) {
    $mark = if ($r.Pass) { "PASS" } else { "FAIL" }
    if (-not $r.Pass) { $failed++ }
    $detail = if ($r.Detail) { " — $($r.Detail)" } else { "" }
    Write-Host "$mark  $($r.Step)$detail"
}
Write-Host ""
if ($failed -eq 0) {
    Write-Host "All automated checks passed. Complete manual UI checklist in docs/FOUNDER_FIRST_SALE.md"
} else {
    Write-Host "$failed check(s) failed. Fix before first sale."
    exit 1
}
