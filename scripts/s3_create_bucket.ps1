# Cache Vault S3 Bucket Creation Script
# Requirements: AWS CLI v2 configured locally.

$BucketName = "proof-foundry-downloads"
$Region = "us-west-2"

Write-Host "--- Verifying AWS CLI ---"
aws --version
if ($LASTEXITCODE -ne 0) { Write-Error "AWS CLI not found. Please install AWS CLI v2."; exit 1 }

Write-Host "--- Verifying Identity ---"
aws sts get-caller-identity
if ($LASTEXITCODE -ne 0) { Write-Error "AWS identity not verified. Please run 'aws configure' or 'aws sso login'."; exit 1 }

Write-Host "--- Checking Bucket: $BucketName ---"
$bucketExists = aws s3api head-bucket --bucket $BucketName 2>&1
if ($bucketExists -match "404") {
    Write-Host "Creating bucket: $BucketName in $Region..."
    aws s3api create-bucket --bucket $BucketName --region $Region --create-bucket-configuration LocationConstraint=$Region
} else {
    Write-Host "Bucket already exists."
}

Write-Host "--- Configuring Bucket Security ---"
# Enable default encryption
aws s3api put-bucket-encryption --bucket $BucketName --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
}'

# Enable versioning
aws s3api put-bucket-versioning --bucket $BucketName --versioning-configuration Status=Enabled

# Enable Ownership Controls (BucketOwnerEnforced)
aws s3api put-bucket-ownership-controls --bucket $BucketName --ownership-controls="Rules=[{ObjectOwnership=BucketOwnerEnforced}]"

# Disable Block Public Access for public distribution
aws s3api put-public-access-block --bucket $BucketName --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

Write-Host "Bucket $BucketName is ready for policy application."
