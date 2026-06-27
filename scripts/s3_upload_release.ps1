# Cache Vault S3 Release Upload Script
# Requirements: AWS CLI v2 configured locally.

$BucketName = "proof-foundry-downloads"
$Region = "us-west-2"
$ReleasePrefix = "cache-vault/v0.1.4"
$ArtifactDir = "release"

Write-Host "--- Verifying AWS CLI ---"
aws --version
if ($LASTEXITCODE -ne 0) { Write-Error "AWS CLI not found."; exit 1 }

Write-Host "--- Verifying Identity ---"
aws sts get-caller-identity
if ($LASTEXITCODE -ne 0) { Write-Error "AWS identity not verified."; exit 1 }

Write-Host "--- Preparing Artifacts ---"
if (!(Test-Path $ArtifactDir)) { Write-Error "Artifact directory '$ArtifactDir' not found."; exit 1 }

# Ensure SHA256SUMS.txt exists in the artifact dir
$zipFile = Get-ChildItem -Path "$ArtifactDir\CacheVault-v0.1.4-windows.zip"
if (!$zipFile) { Write-Error "ZIP artifact not found in $ArtifactDir."; exit 1 }

$hash = (Get-FileHash $zipFile.FullName -Algorithm SHA256).Hash
$hashLine = "$hash  $($zipFile.Name)"
$hashLine | Out-File -FilePath "$ArtifactDir\SHA256SUMS.txt" -Encoding ascii -Force

Write-Host "--- Uploading Artifacts to S3 ---"
aws s3 cp "$ArtifactDir\CacheVault-v0.1.4-windows.zip" "s3://$BucketName/$ReleasePrefix/CacheVault-v0.1.4-windows.zip"
aws s3 cp "$ArtifactDir\SHA256SUMS.txt" "s3://$BucketName/$ReleasePrefix/SHA256SUMS.txt"
aws s3 cp "$ArtifactDir\RELEASE-v0.1.4.md" "s3://$BucketName/$ReleasePrefix/RELEASE-v0.1.4.md"

Write-Host "--- Final Public URLs ---"
$BaseUrl = "https://$BucketName.s3.$Region.amazonaws.com"
Write-Host "ZIP:      $BaseUrl/$ReleasePrefix/CacheVault-v0.1.4-windows.zip"
Write-Host "HASH:     $BaseUrl/$ReleasePrefix/SHA256SUMS.txt"
Write-Host "NOTES:    $BaseUrl/$ReleasePrefix/RELEASE-v0.1.4.md"
Write-Host "SHA256:   $hash"
