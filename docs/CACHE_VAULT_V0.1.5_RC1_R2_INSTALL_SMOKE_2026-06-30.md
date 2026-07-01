# Cache Vault v0.1.5-rc1 — R2 Artifact Install Smoke Receipt

**Date:** 2026-06-30
**Status:** Verification Complete — Release Candidate Installed and Verified

---

## Artifact Sources & Checksums

| Field | Value |
|---|---|
| **R2 ZIP URL** | `https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc1/CacheVault-v0.1.5-rc1-windows.zip` |
| **R2 SHA URL** | `https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc1/CacheVault-v0.1.5-rc1-windows.zip.sha256.txt` |
| **Expected SHA256** | `31a82ba5c84f31f0faa002f8b02f61c3af0b0ff316cf9458588834c98800e88e` |
| **Computed SHA256** | `31a82ba5c84f31f0faa002f8b02f61c3af0b0ff316cf9458588834c98800e88e` |
| **Integrity Verdict** | **PASS** |

---

## Installation & Smoke Environment

- **Download Method:** curl.exe (avoided fragile PowerShell decryption errors)
- **Local Download Path:** `C:\Users\KickA\AppData\Local\Temp\cache_vault_smoke_v015_rc1\CacheVault-v0.1.5-rc1-windows.zip`
- **Extracted Path:** `C:\Users\KickA\AppData\Local\Temp\cache_vault_smoke_v015_rc1\extracted`
- **Source Dependency Check:** Verified independent execution (run in a clean temp directory outside the source tree)

---

## Verification Commands & Output

```powershell
# Extract ZIP
Expand-Archive -Path $zipDest -DestinationPath $extractDest -Force

# Execute Packaged Selftest
.\CacheVault.exe --selftest
```

### Output:
```text
selftest OK — core capture/classify/sensitive/image/mobile pipeline works
```
- **Exit Code:** `0`
- **Verdict:** **PASS**

---

## Packaged Features Verification

1. **Version Reporting:** Checked PEP resource and runtime metadata reports `0.1.5-rc1` (Release Candidate) in frozen builds.
2. **Founder & Crypography Check:** Verified cryptography Ed25519 license checks successfully load in frozen/packaged execution.
3. **Headless Execution:** Selftest confirmed core capture/classify/sensitive/image/mobile pipelines execute cleanly without requiring a display server on headless CI.

---

## Known Caveats
- **Tkinter/Headless Skip:** Headless execution skips Tk window instantiation tests. This is expected behavior. The manual GUI walkthrough receipts verify interactive window features (selected paste, copy-to-safe, ignore next copy).

---

## Final Verdict

### **GREEN / INSTALL-READY**

The Cache Vault v0.1.5-rc1 R2 package artifact installs, extracts, and runs perfectly in a clean environment independent of the repository codebase.
