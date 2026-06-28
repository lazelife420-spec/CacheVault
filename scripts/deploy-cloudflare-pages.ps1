# Deploy Cache Vault landing page to Cloudflare Pages.
# Usage:
#   pwsh scripts\deploy-cloudflare-pages.ps1
#   pwsh scripts\deploy-cloudflare-pages.ps1 -Token "cfut_..." -AccountId "abc123..."
#
# Prerequisites: wrangler (npm install -g wrangler), Cloudflare API token
# with "Cloudflare Pages:Edit" permission.

param(
    [Parameter(Mandatory = $false)]
    [string]$Token = "",

    [Parameter(Mandatory = $false)]
    [string]$AccountId = "02211a4486b2c6bd88f5b594ede1950d",

    [Parameter(Mandatory = $false)]
    [string]$ProjectName = "cache-vault-landing",

    [Parameter(Mandatory = $false)]
    [string]$Branch = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Token) {
    $env:CLOUDFLARE_API_TOKEN = $Token
}
$env:CLOUDFLARE_ACCOUNT_ID = $AccountId

$workDir = Join-Path $env:TEMP "cachevault-pages-deploy"
Remove-Item $workDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

Copy-Item (Join-Path $root "landing.html") (Join-Path $workDir "index.html") -Force

$socialImg = Join-Path $root "docs\cache-vault-social-share.png"
if (Test-Path -LiteralPath $socialImg) {
    Copy-Item $socialImg (Join-Path $workDir "cache-vault-social-share.png") -Force
}

# Cache headers: HTML is short-lived, assets are long-lived.
@"
/index.html
  Cache-Control: public, max-age=300

/cache-vault-social-share.png
  Cache-Control: public, max-age=604800, immutable
"@ | Set-Content -Path (Join-Path $workDir "_headers") -Encoding UTF8

Write-Host "Deploying to Cloudflare Pages: $ProjectName"
$branchArg = if ($Branch) { "--branch=$Branch" } else { "" }
$cmd = "wrangler pages deploy `"$workDir`" --project-name `"$ProjectName`" --commit-dirty=true $branchArg"
Invoke-Expression $cmd

Remove-Item $workDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Live: https://$ProjectName.pages.dev/"
