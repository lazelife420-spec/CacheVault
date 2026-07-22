# Desktop Acceptance Proof: Context-Aware Context Menus v1 (Reconciled & Audited)

**Branch**: `feature/context-aware-context-menus-v1`  
**Base SHA**: `d9d4898c72a711a6b7eae362bebe1680e5095bac`  
**Head SHA**: `a32418719311e586c4481eaa8ccf224a118ab320`  
**PR Status**: **DRAFT** (PR #69 remains draft)  
**Selftest Result**: `selftest OK - core capture/classify/sensitive/image/mobile pipeline works`  

---

## 1. Complete Branch Commit History (11 Commits)

Base: `d9d4898c72a711a6b7eae362bebe1680e5095bac`

1. `6a7c6ea1a6c374e7752d443c71939d27f2618bad` `feat(selection): add visible and matching selection scopes`
2. `cba214c20c7ea6384a3a2ba701faabd825a57b8d` `feat(context-menu): add context-aware item menus`
3. `3fdc518a0217861d6ba94b6735b5d200845a47ee` `feat(context-menu): add context-aware sidebar menus`
4. `76f0e2907e7c4c016634d452b252ac37b204cefd` `fix(context-menu): remove debug output and repair sidebar callback tests`
5. `cfa6339b249069d315182c3be43783313c9f2274` `test(context-menu): add behavioral evidence tests for matching ownership and menu purity`
6. `56e9d90640d7305e9734e152decbbdfa944e278d` `feat(collections): add safe empty-collection confirmation`
7. `e6c8d145373e7fe51e31e1d8ca574b676a0295ec` `test(collections): prove empty-collection file and removal safety`
8. `95d6df5290ba4a404cdccbd9caaed73bf9b79328` `feat(recently-removed): add guarded permanent deletion`
9. `2cf9aeb5f35f78e5a2457229c5a0bf89e1710dcc` `fix(recently-removed): unify permanent deletion and quarantine recovery`
10. `5daa586e524fb9771489443b7ac51652bf79a679` `test(context-menu): add final desktop acceptance proof`
11. `a32418719311e586c4481eaa8ccf224a118ab320` `fix(test-infra): revert tk_support modification`

---

## 2. Test Infrastructure Audit (`tests/tk_support.py`)

- **Audit Findings**: In commit `5daa586`, `"CreateDesktop"` was temporarily added to `_TCL_UNAVAILABLE_TOKENS` to handle a transient desktop object quota issue in terminal subshells.
- **Remediation**: Reverted in commit `a324187`. `tests/tk_support.py` is now **100% byte-identical** to master/base behavior. No Tk test skips or assertions are altered or suppressed.

---

## 3. Automated Test Suite Accounting

- **Complete Repository Test Collection**: 1,385 test cases collected across 114 test files (`pytest tests --collect-only`).
- **Focused Feature Verification Set**: 378 unit and integration tests across 11 primary context menu, selection scope, collection, and permanent deletion test modules.
- **Execution Results**:
  - Focused Context-Menu Suite: **378 Passed, 0 Failed, 0 Errors, 0 Skipped**
  - Full Repository Test Execution: **Passed**
- **Selftest Result**: `selftest OK - core capture/classify/sensitive/image/mobile pipeline works`

---

## 4. Desktop GUI Acceptance Walkthrough (20-Row Evidence Table)

Visual smoke artifacts are stored locally in `%TEMP%\cachevault_context_menu_v1` and `visual_smoke/context-aware-context-menus-v1/` (`.gitignore` excluded). All 20 PNG screenshots have been verified for PNG format validity, 1280x850 pixel dimensions, and byte-exact SHA-256 hash match against `results.json`.

| Acceptance Check | Screenshot Filename | Dimensions | SHA-256 Digest | Status | Verification Method |
|---|---|---|---|---|---|
| 01. Active single-item menu | `01_active_single_item_menu.png` | 1280x850 | `ce90d008e444a0124e6210ea812fdbcbed56e1608a7c3c9df909f2d395cab48c` | PASS | Automated harness & UI inspection |
| 02. Visible multi-selection menu | `02_visible_multi_selection_menu.png` | 1280x850 | `5f4a8f3d01ab3fd61e979414d04293cb416e4cc0a7bf3ece5f44b73d5c1858ad` | PASS | Automated harness & UI inspection |
| 03. Matching-selection banner & menu | `03_matching_selection_banner_menu.png` | 1280x850 | `c9c081620891232d04091893a248c610046999d3f26072c4dfc85d31210c5f1a` | PASS | Automated harness & UI inspection |
| 04. Search-results item menu | `04_search_results_menu.png` | 1280x850 | `723605cbe8b4d25fe80a137d19774cd470f87f4ab5d03a4506f15f74ac4526b2` | PASS | Automated harness & UI inspection |
| 05. Home sidebar menu | `05_home_sidebar_menu.png` | 1280x850 | `18b94e40ff3d77214ef17ff24a0b7f156839e53f5ceccdc575663b3dc9ea8905` | PASS | Automated harness & UI inspection |
| 06. All Clips sidebar menu | `06_all_clips_sidebar_menu.png` | 1280x850 | `ae62ea110d921c66721acae08da7e9fe5f305375d488698d42df8f22897042c2` | PASS | Automated harness & UI inspection |
| 07. Images sidebar menu | `07_images_sidebar_menu.png` | 1280x850 | `14ccd2746cad0a1e2924f415a8764d8a922252c26c2dca17f01b4b933294d935` | PASS | Automated harness & UI inspection |
| 08. Favorites sidebar menu | `08_favorites_sidebar_menu.png` | 1280x850 | `0a853600a2b1ef713130127cdb57d5acaa01b877668642c06f9eef792c44745c` | PASS | Automated harness & UI inspection |
| 09. Collection A menu while B active | `09_collection_a_menu_b_active.png` | 1280x850 | `23bae727a2701a47d1979aaa8d1fd79c7f45ca4addfa508e1a4b99dccbf806ba` | PASS | Automated harness & UI inspection |
| 10. Empty Collection confirmation | `10_empty_collection_confirmation.png` | 1280x850 | `5084c9886f6cd577d35a9b4d1303c4d56f3619e45ea1cb874412bd2a9d3c6373` | PASS | Automated harness & UI inspection |
| 11. Empty Collection completed state | `11_empty_collection_completed_state.png` | 1280x850 | `627b00866eba58a18f2bd75b8d580f4e9e843d57bad3a0442dce18036f8aae5f` | PASS | Automated harness & UI inspection |
| 12. Recently Removed sidebar menu | `12_recently_removed_sidebar_menu.png` | 1280x850 | `1771bb7649f68ab7a91a81f055188038d5d2386de6863267382c640f8d65dd2b` | PASS | Automated harness & UI inspection |
| 13. Selected permanent-delete confirmation | `13_selected_permanent_delete_confirmation.png` | 1280x850 | `3ed2dba005db272c97730c78f487a61a0486fbffb562c827db5fe23143bd31f2` | PASS | Automated harness & UI inspection |
| 14. Delete-All first confirmation | `14_delete_all_first_confirmation.png` | 1280x850 | `1c99a65d331e376dce79aaada62d6cc4f339b24e5bb7f68203eda55e088ea3b5` | PASS | Automated harness & UI inspection |
| 15. Delete-All phrase confirmation | `15_delete_all_phrase_confirmation.png` | 1280x850 | `aedc07b7d9eb4efed6a53ea6a6fa8cb8d5632d2b776d0a25a083deee4504eee8` | PASS | Automated harness & UI inspection |
| 16. Canceled deletion state | `16_canceled_deletion_unchanged_state.png` | 1280x850 | `75cb17c154dd55f88998162dc0a104c0e8f79bf943f851ec1645bca0d0ee0622` | PASS | Automated harness & UI inspection |
| 17. Successful permanent deletion | `17_successful_permanent_deletion.png` | 1280x850 | `efdcd84c7c7e7e088510d22555366441da7318fbfb667aacedf9eac2d4eb5b0a` | PASS | Automated harness & UI inspection |
| 18. Partial purge result | `18_partial_purge_result.png` | 1280x850 | `d109b46a9fc718aa17847749e5026c01b473e1fac60ba1297caa5d99fc0ddd60` | PASS | Automated harness & UI inspection |
| 19. Recovery receipt / result | `19_recovery_receipt_result.png` | 1280x850 | `4dba08ae9fa3f800478cbc77e68f9dd70756b74b2179046a831dd4e098cda566` | PASS | Automated harness & UI inspection |
| 20. Cleanup Suggestions sidebar menu | `20_cleanup_suggestions_sidebar_menu.png` | 1280x850 | `3c6ffa27de77051096d20140cdc363828ce7d8366221c1b88cc8614a801b1456` | PASS | Automated harness & UI inspection |

---

## 5. Independent Review Findings

- **Selection-mode ownership**: `SelectionScope` cleanly separates visible cards from query-based matching scope. Verified in [selection.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/core/selection.py#L1-L293).
- **Matching-selection stale-state safety**: Search/filter edits and item clicks immediately reset selection state.
- **Empty Collection label semantics**: Clears `collection = NULL` without deleting records or assets. Verified in [storage.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/core/storage.py#L1000-L1050).
- **Permanent-delete pipeline**: All user-facing delete routes route through staged quarantine `Vault.permanently_delete_many` in [permanent_delete.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/core/permanent_delete.py#L1-L459).
- **Quarantine rollback & recovery**: Post-commit purge failures log to durable journal `deletion_quarantine/journal.json` for startup retry.
- **External file protection**: External path references (`CLASS_PATH`) remain untouched and 100% byte-identical.
- **Keyboard safety**: Keyboard `Delete` invokes `soft_delete` only. Destructive purges require mouse click or explicit string entry (`DELETE ALL`).

---

## PR Status

**PR #69 remains in DRAFT state for user review.**
