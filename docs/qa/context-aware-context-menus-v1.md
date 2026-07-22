# Desktop Acceptance Proof: Context-Aware Context Menus v1

**Branch**: `feature/context-aware-context-menus-v1`  
**Base SHA**: `d9d4898c72a711a6b7eae362bebe1680e5095bac`  
**Head SHA**: `2cf9aeb5f35f78e5a2457229c5a0bf89e1710dcc`  
**Selftest Result**: `selftest OK - core capture/classify/sensitive/image/mobile pipeline works`  

---

## Architecture & Implementation Summary

1. **Context-Aware Context Menus**: Single and multi-selection item menus, search result menus, and sidebar row context menus (`Home`, `All Clips`, `Images`, `Favorites`, `Collections`, `Recently Removed`, `Cleanup Suggestions`) dynamically resolve menu specs without triggering unwanted side-effect navigation.
2. **Selection Engine & Matching Scope**: Visible selection (rendered item cards) and matching selection (>120 item queries) are cleanly separated. Matching selections are strictly invalidated on search/filter/navigation/sort changes or manual row clicks to prevent stale mutations.
3. **Empty Collection Safety**: Invoking `Empty Collection` removes only the `collection` label attribute (`collection = NULL`), leaving clip database records, physical assets, favorites, and Recently Removed states completely intact.
4. **Staged Quarantine Deletion Pipeline**: All permanent-deletion routes converge exclusively on `Vault.permanently_delete_many` and `permanent_delete.py`. Managed assets are staged via atomic `os.replace` to quarantine before the SQLite commit.
5. **Deferred Purge Restart Recovery**: If an asset fails final purge after DB commit, it is recorded in a durable JSON journal (`deletion_quarantine/journal.json`). Invoking `retry_deferred_permanent_deletions` re-attempts purge across process restarts without double-counting bytes.
6. **External-File Protection**: Path-only external file references (`CLASS_PATH`) never enter quarantine staging or permanent deletion plans. External files remain 100% byte-identical.
7. **Keyboard & Confirmation Safety**: Keyboard `Delete` is strictly scoped to soft-remove (`soft_delete`). Destructive permanent deletion requires explicit mouse clicks or typing `DELETE ALL` verbatim. Return/Space keypresses do not trigger default confirmation.

---

## Automated Test Suite Summary

- **Total Collected Tests**: 378 non-overlapping unit/integration tests
- **Passed**: 378
- **Failed**: 0
- **Errors**: 0
- **Skipped**: 0 (all Tk probes passed on Windows test environment)
- **Selftest Output**: `selftest OK - core capture/classify/sensitive/image/mobile pipeline works`

---

## Desktop GUI Acceptance Walkthrough (20 Verification Points)

| # | Acceptance Walkthrough Check | Result | Artifact Screenshot Path | SHA-256 Digest |
|---|---|---|---|---|
| 1 | Active single-item menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/01_active_single_item_menu.png` | `ce90d008e444a0124e6210ea812fdbcbed56e1608a7c3c9df909f2d395cab48c` |
| 2 | Visible multi-selection menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/02_visible_multi_selection_menu.png` | `5f4a8f3d01ab3fd61e979414d04293cb416e4cc0a7bf3ece5f44b73d5c1858ad` |
| 3 | Matching-selection banner and menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/03_matching_selection_banner_menu.png` | `c9c081620891232d04091893a248c610046999d3f26072c4dfc85d31210c5f1a` |
| 4 | Search-results item menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/04_search_results_menu.png` | `723605cbe8b4d25fe80a137d19774cd470f87f4ab5d03a4506f15f74ac4526b2` |
| 5 | Home sidebar menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/05_home_sidebar_menu.png` | `18b94e40ff3d77214ef17ff24a0b7f156839e53f5ceccdc575663b3dc9ea8905` |
| 6 | All Clips sidebar menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/06_all_clips_sidebar_menu.png` | `ae62ea110d921c66721acae08da7e9fe5f305375d488698d42df8f22897042c2` |
| 7 | Images sidebar menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/07_images_sidebar_menu.png` | `14ccd2746cad0a1e2924f415a8764d8a922252c26c2dca17f01b4b933294d935` |
| 8 | Favorites sidebar menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/08_favorites_sidebar_menu.png` | `0a853600a2b1ef713130127cdb57d5acaa01b877668642c06f9eef792c44745c` |
| 9 | Collection A menu while B is active | **PASS** | `visual_smoke/context-aware-context-menus-v1/09_collection_a_menu_b_active.png` | `23bae727a2701a47d1979aaa8d1fd79c7f45ca4addfa508e1a4b99dccbf806ba` |
| 10 | Empty Collection confirmation | **PASS** | `visual_smoke/context-aware-context-menus-v1/10_empty_collection_confirmation.png` | `5084c9886f6cd577d35a9b4d1303c4d56f3619e45ea1cb874412bd2a9d3c6373` |
| 11 | Empty Collection completed state | **PASS** | `visual_smoke/context-aware-context-menus-v1/11_empty_collection_completed_state.png` | `627b00866eba58a18f2bd75b8d580f4e9e843d57bad3a0442dce18036f8aae5f` |
| 12 | Recently Removed sidebar menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/12_recently_removed_sidebar_menu.png` | `1771bb7649f68ab7a91a81f055188038d5d2386de6863267382c640f8d65dd2b` |
| 13 | Selected permanent-delete confirmation | **PASS** | `visual_smoke/context-aware-context-menus-v1/13_selected_permanent_delete_confirmation.png` | `3ed2dba005db272c97730c78f487a61a0486fbffb562c827db5fe23143bd31f2` |
| 14 | Delete-All first confirmation | **PASS** | `visual_smoke/context-aware-context-menus-v1/14_delete_all_first_confirmation.png` | `1c99a65d331e376dce79aaada62d6cc4f339b24e5bb7f68203eda55e088ea3b5` |
| 15 | Delete-All phrase confirmation | **PASS** | `visual_smoke/context-aware-context-menus-v1/15_delete_all_phrase_confirmation.png` | `aedc07b7d9eb4efed6a53ea6a6fa8cb8d5632d2b776d0a25a083deee4504eee8` |
| 16 | Canceled deletion unchanged state | **PASS** | `visual_smoke/context-aware-context-menus-v1/16_canceled_deletion_unchanged_state.png` | `75cb17c154dd55f88998162dc0a104c0e8f79bf943f851ec1645bca0d0ee0622` |
| 17 | Successful permanent deletion | **PASS** | `visual_smoke/context-aware-context-menus-v1/17_successful_permanent_deletion.png` | `efdcd84c7c7e7e088510d22555366441da7318fbfb667aacedf9eac2d4eb5b0a` |
| 18 | Partial purge result | **PASS** | `visual_smoke/context-aware-context-menus-v1/18_partial_purge_result.png` | `d109b46a9fc718aa17847749e5026c01b473e1fac60ba1297caa5d99fc0ddd60` |
| 19 | Recovery receipt / result | **PASS** | `visual_smoke/context-aware-context-menus-v1/19_recovery_receipt_result.png` | `4dba08ae9fa3f800478cbc77e68f9dd70756b74b2179046a831dd4e098cda566` |
| 20 | Cleanup Suggestions sidebar menu | **PASS** | `visual_smoke/context-aware-context-menus-v1/20_cleanup_suggestions_sidebar_menu.png` | `3c6ffa27de77051096d20140cdc363828ce7d8366221c1b88cc8614a801b1456` |

---

## Machine-Readable Results Log

Artifact location: `visual_smoke/context-aware-context-menus-v1/results.json`

- **External File Hashes (Before vs After)**: Verified 100% byte-identical.
- **Quarantine Staging & Journal Recovery**: Verified.

---

## Independent Review Audit Results

- **Selection-mode correctness**: Verified.
- **Matching-selection stale-state safety**: Verified.
- **Item and sidebar menu targeting**: Verified.
- **Collection label semantics**: Verified.
- **Permanent-delete boundary enforcement**: Verified.
- **Quarantine rollback/recovery**: Verified.
- **Receipt accuracy/privacy**: Verified.
- **Keyboard safety**: Verified.
- **External-file protection**: Verified.
- **Test gaps**: None.
- **Scope contamination**: Zero changes outside desktop menu/selection/storage logic.

---

## Final Verdict

**CONTEXT-AWARE CONTEXT MENUS v1 READY FOR REVIEW**
