# Cache Vault Public Surface Audit — 2026-06-30

## Verified Release Truth
- **Product:** Cache Vault
- **Version:** v0.1.4 release.1
- **Test count:** 740/740
- **Download artifact:** CacheVault-v0.1.4-windows.zip
- **ZIP SHA256:** `710c8988455b30a3fa8589862e3e7c8a36c7faf73b015cfda5024f700a2c81bf`
- **Receipt status:** published / available
- **Proof Foundry /proof receipt:** Already populated and GREEN

---

## Buyer/Download Path Audit

| Surface | Expected current truth | Actual found | Action taken | Remaining risk |
|---|---|---|---|---|
| `docs/index.html` (Landing) | Version `v0.1.4 release.1`, `740` tests, ZIP SHA256 `710c8988455b30a3fa8589862e3e7c8a36c7faf73b015cfda5024f700a2c81bf`. Links point to release.1. | Matches expected truth | None (verified correct) | None |
| `landing.html` (Sales Page) | Version `v0.1.4 release.1`, `740` tests, ZIP SHA256 `710c8988455b30a3fa8589862e3e7c8a36c7faf73b015cfda5024f700a2c81bf`. | Matches expected truth | None (verified correct) | None |
| `docs/index-fallback.html` | ZIP SHA256 matches verified truth. | Old ZIP SHA256: `07d6049153c5f4fd980990099a27062ffce5304fe8d5c73a41fbbb0d6874fa4a` | Updated to `710c8988455b30a3fa8589862e3e7c8a36c7faf73b015cfda5024f700a2c81bf` | None |
| `docs/LANDING.md` | References current ZIP SHA256 and release.1 download tag. | Old ZIP SHA256 `07d60491...` and tag `v0.1.4`. | Updated ZIP SHA256 and download tag references | None |
| `packaging/RELEASE_NOTES-v0.1.4.md` | Verification table matches test count 740 and current ZIP/EXE SHA256. | Old test count `545`, old EXE SHA256 `CEEA23AD...`, old ZIP SHA256 `07d60491...` | Updated verification table to correct release metadata | None |

### Historical Documents (Retained unaltered)
The following documents contain older test counts/versions matching their specific historical context:
- `docs/audits/CODEBASE_AUDIT.md`: Historical codebase audit from June 27, 2026 (545 tests).
- `docs/OFFLINE_HOTFIX_v0.1.4.1_STABILITY.md`: Historical stability hotfix receipt (v0.1.4.1, 561 tests).
- `docs/POST_PR34_PACKAGE_PROOF.md`: Historical package verification receipt (545 tests).

---

## Files Changed
- `docs/index-fallback.html` (updated SHA256 text)
- `docs/LANDING.md` (updated tag and SHA256 text)
- `packaging/RELEASE_NOTES-v0.1.4.md` (updated test count, EXE SHA256, and ZIP SHA256 in verification table)

---

## Commands Run & Test Results
1. **Pytest Run:**
   ```powershell
   pytest -p no:xonsh
   ```
   *Result:* **740 passed** in 61.71s

2. **Compilation check:**
   ```powershell
   python -m compileall cache_vault
   ```
   *Result:* SUCCESS (0 errors)

3. **App Selftest:**
   ```powershell
   python app.py --selftest
   ```
   *Result:* SUCCESS (`selftest OK`)

---

## Remaining Holds & Proof Foundry Status
- **Remaining Holds:** None. Public surface aligns completely with release artifacts.
- **Proof Foundry status:** Green / no follow-up needed.

No fake proof added.
