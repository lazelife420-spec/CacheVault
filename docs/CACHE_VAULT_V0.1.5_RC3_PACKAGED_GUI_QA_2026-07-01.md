# Cache Vault v0.1.5-rc3 — Packaged GUI QA

**Date:** 2026-07-01  
**Version:** 0.1.5-rc3 (Release Candidate)  
**Runner:** `scripts/verify_packaged_gui_run_rc3.py`  
**Target exe:** extracted from the R2 artifact at `%TEMP%\cv_rc3_smoke\extracted\CacheVault.exe`  
**Extracted exe SHA256:** `E9DBFD0112BD3D00C2C433A33EB9507F152F78695C85BF8E60805474266312B5`  

## Method

1. Downloaded and SHA-verified the public R2 ZIP (see R2 install smoke receipt).
2. Extracted `CacheVault.exe`.
3. Seeded a fresh temp profile DB with three clips (text, R2 link, PNG screenshot); confirmed clip count in DB = **3**.
4. Set `first_use_guide_dismissed = true` in the temp profile so the main Command Center is captured (not the onboarding overlay).
5. Launched the packaged exe against that profile, waited for render, captured a window screenshot, then terminated.

## Result

Runner report: `ok: true`, screenshot saved.

Screenshot: `visual_smoke/v0.1.5_rc3_packaged_gui_qa.png`

Observed in the packaged rc3 UI:

- Title bar: **Cache Vault™ — A Proof Foundry product**
- Toolbar: Capture: On · Mobile: Off · Receipts: Stamping · Default Safe: default · Lock Now · Export / Save As · Stamped Receipts
- Command Center header + "Local Vault Active" panel: `Local-first · Capture Active · Receipts Available`
- Stats line: **3 saved · 2 safes · 7 receipts · 0 exports · 0 HTML bundles**
- Custody Summary: All Clips **3**, Favorites 0, Screenshots **1**, Links **1**
- No crash; clean shutdown

## Checks

| Check | Result |
|---|---|
| Packaged exe launches and renders | **PASS** |
| Seeded clips visible (All Clips = 3) | **PASS** |
| Screenshot/image clip counted (Screenshots = 1) | **PASS** |
| Link clip counted (Links = 1) | **PASS** |
| No crash / clean terminate | **PASS** |

## Verdict

**PASS.** The publicly downloaded, SHA-verified rc3 build launches and renders the full Command Center with seeded data.
