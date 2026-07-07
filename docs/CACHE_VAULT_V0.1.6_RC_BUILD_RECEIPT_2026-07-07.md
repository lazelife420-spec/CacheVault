# Cache Vault v0.1.6 RC Build Receipt

Date: 2026-07-07

## Verdict

```text
VERDICT: PASS / INTERNAL_RC_ONLY
Publish: HOLD
/proof: unchanged
Stable: not claimed
No tag
```

## Artifact Facts

- **Commit:** `697a73e`
- **EXE Path:** `dist\CacheVault.exe`
- **EXE Size:** `43202546` bytes
- **EXE SHA256:** `89961C43F1D94093DF9EC6E4D0FE4CD5707565459794463E1D4CCBCAC73889D4`
- **Version Metadata:** `0.1.6` (source and pyproject agree, internal file/product version is `0.1.6.0`)

## Gate Verification Results

| Gate | Result | Notes |
|---|---|---|
| Packaged Selftest (`dist\CacheVault.exe --selftest`) | **PASS** | core capture/classify/sensitive/image/mobile pipeline works |
| Founder Package Smoke (`scripts\founder_package_smoke.ps1`) | **PASS** | 4/4 checks passed (negative path, valid license, receipt generation) |
| unit tests (`pytest`) | **PASS** | 836 passed, 2 warnings |
| compilation (`compileall cache_vault`) | **PASS** | all files compiled successfully |
| app.py Selftest (`python app.py --selftest`) | **PASS** | core pipeline verified successfully |

## Custody Affirmations

- **Tag Status:** **Confirmed**. No release candidate tag points at the current HEAD commit or has been created.
- **Sovereign Proofs Status:** **Confirmed**. The `/proof` directory remains completely unchanged.
- **v0.1.5 Tag Custody:** **Confirmed**. The `v0.1.5` tag remains unmoved at commit `39257be`.
- **f56c6ec Exclusion:** **Confirmed**. The commit `f56c6ec` remains excluded from this branch lineage.
