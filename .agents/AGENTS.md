# Project-Scoped Rules for Cache Vault

## Release Artifacts and Cloudflare R2 Distribution

1. **Do not create full project backup ZIPs on the Desktop** unless the user explicitly asks for an emergency local snapshot. The Desktop should only be used as a workspace, not as a routine release artifact repository.
2. **For release artifacts, use the Cloudflare-first flow:**
   - Build artifacts locally into the project release folder only (e.g., `C:\Users\KickA\Desktop\CacheVault\dist\release\v0.1.5-rc1\`).
   - Generate SHA256 checksum files beside the artifact.
   - Upload release artifacts to the Cloudflare R2 bucket: `proof-foundry-downloads`.
   - Use product/version paths:
     `cache-vault/<version>/CacheVault-<version>-windows.zip`
     `cache-vault/<version>/CacheVault-<version>-windows.zip.sha256.txt`
3. **Do not put full source-code project ZIPs on the Desktop as routine output.**
4. **Cloudflare Pages should only host:**
   - site pages
   - `/proof/`
   - product landing pages
   - receipts
   - links to R2 artifacts
5. **Cloudflare R2 should host:**
   - release ZIPs
   - APKs
   - EXEs if needed
   - SHA256 files
   - public downloadable artifacts
6. **Do not update Proof Foundry `/proof`** until the R2 artifact URL and SHA256 URL are live and verified.
7. **Do not generate or paste API tokens.** If R2 upload requires authentication and the agent cannot use it safely, stop and provide manual upload instructions for the Cloudflare dashboard.
