# Build a one-file Cache Vault executable.
#   pwsh packaging\build_exe.ps1
# Output: dist\CacheVault.exe
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

pyinstaller packaging\cache_vault.spec --noconfirm --clean

Write-Host ""
Write-Host "Built: $root\dist\CacheVault.exe"
