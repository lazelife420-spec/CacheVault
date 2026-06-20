# Publish Cache Vault Founder landing to a dedicated GitHub Pages repo.
# Usage:
#   pwsh scripts\deploy-github-pages-landing.ps1 -Owner Z3r0DayZion-install -Repo cache-vault-landing -CheckoutUrl "https://cashdominion.gumroad.com/l/eojmeb"

param(
    [Parameter(Mandatory = $true)]
    [string]$Owner,

    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $false)]
    [string]$CheckoutUrl = "https://cashdominion.gumroad.com/l/eojmeb",

    [Parameter(Mandatory = $false)]
    [string]$ReleaseUrl = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $ReleaseUrl) {
    $ReleaseUrl = "https://github.com/$Owner/CacheVault/releases/tag/v0.1.3-founder-mvp.1"
}

$source = Join-Path $root "docs\index.html"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Missing $source"
}

$work = Join-Path $env:TEMP "cache-vault-landing-github-pages"
if (Test-Path $work) {
    Remove-Item $work -Recurse -Force
}

$remote = "https://github.com/$Owner/$Repo.git"
git clone $remote $work 2>$null
if (-not (Test-Path (Join-Path $work ".git"))) {
    New-Item -ItemType Directory -Path $work | Out-Null
    Push-Location $work
    git init
    git branch -M main
    git remote add origin $remote
    Pop-Location
}

Copy-Item $source (Join-Path $work "index.html") -Force
New-Item -ItemType File -Force -Path (Join-Path $work ".nojekyll") | Out-Null

$page = Get-Content (Join-Path $work "index.html") -Raw
$buy = "href=""$CheckoutUrl"" target=""_blank"" rel=""noopener noreferrer"""
$page = $page.Replace('class="button dark" href="#founder">Founder Edition', "class=""button dark"" $buy>Founder Edition")
$page = $page.Replace('class="button primary" href="#founder">Buy Founder</a>', "class=""button primary"" $buy>Buy Founder</a>")
$page = $page.Replace('class="button dark" href="#founder">Buy Founder', "class=""button dark"" $buy>Buy Founder")
$page = $page -replace 'https://github\.com/[^/]+/CacheVault/releases/tag/v[\w\.-]+', $ReleaseUrl
Set-Content -Path (Join-Path $work "index.html") -Value $page -Encoding UTF8

Push-Location $work
git add index.html .nojekyll
$status = git status --porcelain
if ($status) {
    git commit -m "update checkout URL to Gumroad"
    git pull origin main --rebase 2>$null
    git push -u origin main
} else {
    Write-Host "No changes to deploy."
}
Pop-Location

Write-Host ""
Write-Host "Live URL: https://$Owner.github.io/$Repo/"
Write-Host "Checkout: $CheckoutUrl"
