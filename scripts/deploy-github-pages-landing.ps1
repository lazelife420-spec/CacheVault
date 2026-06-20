# Publish Cache Vault Founder landing to a dedicated GitHub Pages repo.
# Usage:
#   pwsh scripts\deploy-github-pages-landing.ps1 -Owner Z3r0DayZion-install -Repo cache-vault-landing -CheckoutUrl "https://your-checkout-url"
#
# For in-repo Pages (docs/index.html), enable:
#   GitHub → Settings → Pages → Deploy from branch → master → /docs

param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $false)]
    [string]$CheckoutUrl = "#founder",

    [Parameter(Mandatory = $false)]
    [string]$ReleaseUrl = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $ReleaseUrl) {
    $ReleaseUrl = "https://github.com/$Owner/CacheVault/releases/tag/v0.1.3-founder-mvp"
}

$source = Join-Path $root "docs\index.html"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Missing $source — run landing integration first."
}

$work = Join-Path $env:TEMP "cache-vault-landing-github-pages"
if (Test-Path $work) {
    Remove-Item $work -Recurse -Force
}

New-Item -ItemType Directory -Path $work | Out-Null
Copy-Item $source (Join-Path $work "index.html")
New-Item -ItemType File -Force -Path (Join-Path $work ".nojekyll") | Out-Null

$page = Get-Content (Join-Path $work "index.html") -Raw
$page = $page.Replace("#founder", $CheckoutUrl)
if ($CheckoutUrl -ne "#founder") {
    $page = $page.Replace('href="#founder"', "href=""$CheckoutUrl""")
}
Set-Content -Path (Join-Path $work "index.html") -Value $page -Encoding UTF8

Push-Location $work
git init
git add .
git commit -m "launch Cache Vault Founder landing page"
git branch -M main
git remote add origin "https://github.com/$Owner/$Repo.git"
git push -u origin main
Pop-Location

Write-Host ""
Write-Host "Pushed landing page to https://github.com/$Owner/$Repo"
Write-Host "Enable GitHub Pages: Settings -> Pages -> Deploy from branch -> main -> /(root)"
Write-Host "Live URL: https://$Owner.github.io/$Repo/"
