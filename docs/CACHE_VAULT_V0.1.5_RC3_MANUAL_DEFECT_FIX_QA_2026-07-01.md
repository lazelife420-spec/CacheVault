# Cache Vault v0.1.5-rc3 — Manual Defect Fix QA

**Date:** 2026-07-01  
**Version:** 0.1.5-rc3 (Release Candidate)  
**Visual proof:** [v0.1.5_rc3_defect_fix_qa.png](file:///c:/Users/KickA/Desktop/CacheVault/visual_smoke/v0.1.5_rc3_defect_fix_qa.png)  

## Method

Verified both programmatically via the automated test suite in [test_rc3_defect_fixes.py](file:///c:/Users/KickA/Desktop/CacheVault/tests/test_rc3_defect_fixes.py) and verified structural/visual layouts via the visual smoke test suite.

## Checks

| Check | Result | Detail |
|---|---|---|
| Settings Hub opens in front every time | **PASS** | `SettingsHub` is transient/owned by the main app and topmost-pulsed for 100ms. |
| Reopening Settings Hub lifts existing window | **PASS** | Re-invocation of `_open_settings` detects the existing instance, lifts/focuses it and pulses topmost. |
| Multi-select screenshots works | **PASS** | Context menu actions and toolbar actions correctly display and function. |
| Export Screenshots to Folder writes files | **PASS** | Writes matching PNG files to the chosen folder path successfully. |
| Export ZIP creates valid ZIP with selected image files | **PASS** | Creates a valid deflate ZIP archive containing selected PNGs. |
| Copy Paths copies selected image file paths | **PASS** | File paths are copied correctly to the system clipboard. |
| Empty/missing assets do not crash | **PASS** | Empty selections notify the user via a toast; missing asset files are gracefully skipped with a count warning. |
| Command Center selected highlight matches All Clips | **PASS** | Selected cards/rows in Command Center use the same border/accent colors and styling as All Clips rows. |
| No crash during photo/screenshot flow | **PASS** | Programmatic flows run safely without exceptions. |
| `crash_native.log` remains clean during QA | **PASS** | No native tkinter or python thread crashes were logged. |

## Verdict

**PASS.** All three RC3 defects (Settings Hub z-order, Screenshot multi-select export actions, and Command Center highlighting consistency) are successfully resolved, verified, and regression tested.
