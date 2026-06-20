# Publish custom Gumroad landing page for product eojmeb
# Prereq: gumroad auth login (or GUMROAD_ACCESS_TOKEN)
# Usage: pwsh scripts\publish_gumroad_landing.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PATH = "$env:USERPROFILE\go\bin;$env:PATH"

$page = Join-Path $root "landing.html"
if (-not (Test-Path $page)) { throw "Missing landing.html" }

Write-Host "Preview (sanitizer)..."
$preview = gumroad products page preview eojmeb $page --json --no-input --non-interactive 2>&1
$preview | Out-Host
if ($preview -match '"success"\s*:\s*false') { throw "Preview failed — fix landing.html and retry." }

Write-Host ""
Write-Host "Publishing..."
$publish = gumroad products page publish eojmeb $page --json --no-input --non-interactive 2>&1
$publish | Out-Host
if ($publish -match '"success"\s*:\s*false') { throw "Publish failed." }

Write-Host ""
Write-Host "Live URL:"
gumroad products page url eojmeb --json --jq '.product.landing_url' --no-input --non-interactive
