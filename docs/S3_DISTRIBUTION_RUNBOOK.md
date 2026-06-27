# Cache Vault v0.1.4 S3 Distribution Runbook

This runbook provides instructions for setting up a GitHub-independent S3 distribution for Cache Vault v0.1.4. It assumes you have administrative access to an AWS account and will be executing these steps from your local Windows desktop.

## 1. Install and Configure AWS CLI v2

Before proceeding, ensure you have the AWS Command Line Interface (CLI) version 2 installed and configured with appropriate credentials. AWS recommends using IAM Identity Center (SSO) for authentication, or least-privilege IAM user credentials, rather than root access keys.

### Installation (Windows)

Open PowerShell (or Command Prompt) and run the following commands:

```powershell
winget install -e --id Amazon.AWSCLI
aws --version
```

Verify that `aws --version` shows `aws-cli/2.x.x`.

### Configuration

Configure your AWS CLI with credentials that have permissions to create S3 buckets, manage bucket policies, and upload objects. If using IAM Identity Center (SSO), follow the AWS documentation for `aws configure sso`.

```powershell
# For IAM user credentials (less recommended for long-lived keys)
aws configure

# For IAM Identity Center (SSO) - recommended
aws configure sso
```

Verify your configured identity:

```powershell
aws sts get-caller-identity
```

## 2. Prepare Local Release Artifacts

Ensure the following files are present in the `release/` directory within your local `CacheVault` repository clone. These files were prepared by the agent in a previous step.

```text
CacheVault/
├── release/
│   ├── CacheVault-v0.1.4-windows.zip
│   ├── CacheVault-v0.1.4-windows.sha256
│   └── RELEASE-v0.1.4.md
└── scripts/
    ├── s3_create_bucket.ps1
    ├── s3_upload_release.ps1
    └── s3_bucket_policy_public_download.json
```

## 3. Create and Configure S3 Bucket

This step creates the S3 bucket, enables encryption and versioning, and configures ownership controls. It also sets the bucket to allow public access (which is necessary for public downloads).

Open PowerShell, navigate to your `CacheVault` repository root, and run:

```powershell
.\scripts\s3_create_bucket.ps1
```

This script will:
*   Verify AWS CLI installation and identity.
*   Create the `proof-foundry-downloads` bucket in `us-west-2` if it doesn't exist.
*   Enable default encryption (AES256).
*   Enable bucket versioning.
*   Set bucket ownership controls to `BucketOwnerEnforced`.
*   Disable AWS S3 Block Public Access settings for the bucket.

## 4. Apply Public Read Bucket Policy

After creating the bucket, you need to apply a bucket policy to allow public read access to its objects. This is crucial for unauthenticated downloads.

Open PowerShell, navigate to your `CacheVault` repository root, and run:

```powershell
aws s3api put-bucket-policy --bucket proof-foundry-downloads --policy file://.\scripts\s3_bucket_policy_public_download.json
```

## 5. Upload Release Artifacts

This step uploads the `CacheVault-v0.1.4-windows.zip`, `CacheVault-v0.1.4-windows.sha256`, and `RELEASE-v0.1.4.md` files to the S3 bucket under the `cache-vault/v0.1.4/` prefix.

Open PowerShell, navigate to your `CacheVault` repository root, and run:

```powershell
.\scripts\s3_upload_release.ps1
```

The script will output the final public URLs for the ZIP, SHA256, and Release Notes files.

## 6. Create a Lightweight Landing Page Stub (Optional but Recommended)

To provide a simple, branded landing page for your downloads, you can create an `index.html` file and upload it to the root of your S3 bucket. This `index.html` can be a minimal stub for now.

Create `index.html` locally in your `CacheVault` repository root (e.g., `C:\Users\KickA\Desktop\CacheVault\index.html`):

```html
<!doctype html>
<meta charset="utf-8">
<title>Cache Vault v0.1.4</title>
<style>
    body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; background: #0d1117; color: #c9d1d9; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 24px; margin-bottom: 20px; }
    .button { display: inline-block; background: #238636; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; }
    .hash { font-family: monospace; background: #0d1117; padding: 10px; border-radius: 4px; font-size: 0.9em; word-break: break-all; }
    a { color: #58a6ff; }
</style>
<h1>Cache Vault v0.1.4</h1>
<p>Local-first Windows clipboard vault. No cloud account. No subscription.</p>
<ul>
  <li><a href="cache-vault/v0.1.4/CacheVault-v0.1.4-windows.zip">Download ZIP (Windows x64)</a></li>
  <li><a href="cache-vault/v0.1.4/CacheVault-v0.1.4-windows.sha256">SHA-256 file</a></li>
  <li><a href="cache-vault/v0.1.4/RELEASE-v0.1.4.md">Release notes & proof</a></li>
</ul>
<p>Release candidate – feedback welcome. No installer telemetry. All tests & packaged smoke PASS.</p>
```

Then upload it to the bucket root:

```powershell
aws s3 cp index.html s3://proof-foundry-downloads/
```

To access this landing page, you will need to enable Static Website Hosting for your S3 bucket in the AWS Console. The endpoint will typically be `http://proof-foundry-downloads.s3-website-us-west-2.amazonaws.com/`.

## 7. Verification

After all uploads are complete, verify unauthenticated access to all URLs and confirm the SHA256 hash of the downloaded ZIP against the `CacheVault-v0.1.4-windows.sha256` file.

## 8. Next Steps

Once you have verified the S3 distribution, you can use these URLs for public announcements. Do not publish or post until you are ready.
