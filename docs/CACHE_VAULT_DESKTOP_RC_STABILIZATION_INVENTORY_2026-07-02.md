# Cache Vault Desktop rc Stabilization Inventory

Date: 2026-07-02

## Scope

- Base branch: `release/v0.1.4-public-distribution`
- Base commit: `38a10b8`
- Compared branch: `mobile/android-reconnect-lifecycle-qa`
- Compared branch tip: `88c07f1`
- Comparison command:
  - `git diff --stat release/v0.1.4-public-distribution...mobile/android-reconnect-lifecycle-qa`
  - `git diff --name-status release/v0.1.4-public-distribution...mobile/android-reconnect-lifecycle-qa`
- Total files changed: `120`
- Final verdict: `INVENTORY_ONLY / NO_CODE_CHANGES`

## Summary

The old `mobile/android-reconnect-lifecycle-qa` branch is not a candidate for a single carry-forward PR.

It contains:

- legitimate desktop stabilization work worth splitting
- Android reconnect work already landed elsewhere
- public/release/landing contamination that must not be revived inside desktop stabilization PRs
- a large number of QA/audit docs and GUI verification scripts that should not be treated as product changes

The right next step is still to split the surviving desktop work into small PRs, not to merge or cherry-pick the whole branch.

## Classification Table

| Bucket | Meaning | File count | Notes |
|---|---|---:|---|
| `A` | crash/log visibility | `6` | Real desktop lane candidate |
| `B` | screenshot/image batch actions | `18` | Real desktop lane candidate |
| `C` | settings z-order/window ownership | `7` | Real desktop lane candidate |
| `D` | selection/metadata consistency | `7` | Real desktop lane candidate |
| `E` | hotkey recording | `0` unique | No uniquely recoverable old-branch hotkey lane remains; current release branch is now source of truth after `38a10b8` |
| `F` | main screen/sidebar polish | `27` | Mixed with many QA docs/scripts; must be trimmed hard |
| `G` | mobile bridge work already landed | `40` | Do not carry forward into desktop stabilization PRs |
| `H` | public/release/landing/proof contamination | `12` | Must not be carried forward |
| `I` | unrelated/unknown | `3` | Needs explicit judgment before any reuse |

## Files That Must Not Be Carried Forward

These files are out of scope for desktop stabilization split PRs and should not be revived from the old branch:

- Entire Android bucket `G`
- Entire public/release contamination bucket `H`
- `CNAME`
- `docs/LANDING.md`
- `docs/index-fallback.html`
- `packaging/RELEASE_NOTES-v0.1.4.md`
- `packaging/RELEASE_NOTES-v0.1.5-rc1.md`
- `packaging/RELEASE_NOTES-v0.1.5-rc2.md`
- `packaging/RELEASE_NOTES-v0.1.5-rc3.md`
- `pyproject.toml`
- `cache_vault/__init__.py`
- `tools/check_exe_version.py`

These are also not candidates for a desktop stabilization product PR by default, even though they appear in desktop-related buckets:

- old QA receipts
- old RC packaged GUI receipts
- one-off GUI verification scripts

They can inform future work, but they should not be pulled forward automatically.

## Files Already Superseded By Landed Work

These paths represent work already landed on the release branch through the Android reconnect lane, desktop label follow-up, packaged QA receipt lane, and hotkey lane:

- Android reconnect / pairing / lifecycle files under `android/`
- desktop mobile bridge files:
  - `cache_vault/core/mobile/api.py`
  - `cache_vault/core/mobile/bridge.py`
  - `cache_vault/core/mobile/models.py`
  - `cache_vault/ui/mobile_dialogs.py`
  - `tests/test_mobile_bridge.py`
  - `tests/test_mobile_connection_lifecycle.py`
- reconnect and device-QA docs:
  - `docs/CACHE_VAULT_ANDROID_RECONNECT_DEVICE_QA_2026-07-01.md`
  - `docs/CACHE_VAULT_ANDROID_RECONNECT_EVIDENCE_MANIFEST_2026-07-01.md`
  - `docs/CACHE_VAULT_ANDROID_RECONNECT_QA_2026-07-01.md`
  - `docs/CACHE_VAULT_ANDROID_RECONNECT_RELEASE_GATE_2026-07-02.md`
  - `docs/CACHE_VAULT_MOBILE_CONNECTION_LIFECYCLE_PLAN_2026-07-01.md`
- hotkey lane note:
  - no uniquely recoverable old-branch hotkey-only delta should be used as source material now that hotkey recording stability landed at `38a10b8`

## Recommended Split PRs

### 2A — crash/log visibility

Primary code candidates:

- `app.py`
- `cache_vault/ui/crashlog.py`
- `cache_vault/ui/tooltip.py`
- `tests/test_crashlog.py`
- `tests/test_tooltip.py`

Notes:

- `cache_vault/ui/tooltip.py` belongs here because it is desktop stability/crash behavior, not polish.
- `docs/CACHE_VAULT_TK_NATIVE_CRASH_AUDIT_2026-07-01.md` is supporting evidence, not necessarily a carry-forward file.

### 2B — screenshot/image batch actions

Primary code candidates:

- `cache_vault/core/contextmenu.py`
- `cache_vault/ui/batch_actions.py`
- `cache_vault/ui/clip_context.py`
- `cache_vault/ui/clip_grid.py`
- `cache_vault/ui/clip_list.py`
- `tests/test_contextmenu.py`
- `tests/test_copy_to_safe.py`
- `tests/test_do_not_save.py`
- `tests/test_e4_contextmenu.py`
- `tests/test_menu_cleanup.py`

Carry forward cautiously:

- GUI verification scripts and old QA docs only if a future lane explicitly wants proof assets, not as default code-review scope.

### 2C — settings z-order/window ownership

Primary code candidates:

- `cache_vault/ui/dialogs.py`
- `cache_vault/ui/settings_hub.py`
- `cache_vault/ui/shell.py`
- `tests/test_destructive_confirmations.py`
- `tests/test_dialogs.py`
- `tests/test_settings_hub.py`
- `tests/test_settings_hub_integration.py`

Notes:

- `cache_vault/ui/shell.py` overlaps several buckets; only the settings-window ownership slice should be carried into this PR.

### 2D — selection/metadata consistency

Primary code candidates:

- `cache_vault/core/display_metadata.py`
- `cache_vault/core/models.py`
- `cache_vault/core/vault.py`
- `cache_vault/ui/preview.py`
- `cache_vault/ui/vault_lock.py`
- `cache_vault/ui/vault_screens.py`
- `tests/test_clip_selection.py`

Notes:

- This lane should focus on consistent source/time/type rendering across All Clips, Screenshots, Links, and mobile clips.

### 2E — main screen/sidebar polish

Primary code candidates:

- `cache_vault/modules/registry.py`
- `cache_vault/ui/shell.py`
- `cache_vault/ui/vault_screens.py`
- `tests/test_rc3_defect_fixes.py`
- `tests/test_rc4_consistency.py`
- `tests/test_ui_polish.py`
- `tests/test_workflow_integration.py`

Do not automatically include:

- RC packaged GUI receipts
- private soak checklists
- GUI proof scripts

Those are evidence artifacts, not product scope.

## Risk Notes

- `cache_vault/ui/shell.py` appears across several conceptual buckets. Any future PR touching it must isolate a very narrow slice or it will immediately become another oversized lane.
- The old branch mixed code, proof scripts, and receipts heavily. Future split PRs should carry code and tests first, then decide separately whether any old evidence docs are still useful.
- The Android reconnect branch contains public/release contamination (`H`) alongside legitimate desktop work. That contamination is exactly why this inventory lane exists.
- Bucket `I` should not be pulled into a stabilization PR without explicit justification:
  - `.gitignore`
  - `cache_vault/core/paste_delivery.py`
  - `docs/CACHE_VAULT_TK_NATIVE_CRASH_AUDIT_2026-07-01.md`
- Bucket `E` currently has no unique carry-forward delta. Hotkey work should proceed from current release branch state, not from this old branch.

## Full File Classification

### A. crash/log visibility

- `A .agents/AGENTS.md`
- `M app.py`
- `M cache_vault/ui/crashlog.py`
- `M cache_vault/ui/tooltip.py`
- `A tests/test_crashlog.py`
- `M tests/test_tooltip.py`

### B. screenshot/image batch actions

- `M cache_vault/core/contextmenu.py`
- `M cache_vault/ui/batch_actions.py`
- `M cache_vault/ui/clip_context.py`
- `M cache_vault/ui/clip_grid.py`
- `M cache_vault/ui/clip_list.py`
- `A docs/COPY_TO_SAFE_WORKFLOW_QA_2026-06-30.md`
- `A docs/DO_NOT_SAVE_NEXT_COPY_QA_2026-06-30.md`
- `A docs/MENU_SETTINGS_CLEANUP_QA_2026-06-30.md`
- `A docs/SELECTED_ITEM_PASTE_WORKFLOW_QA_2026-06-30.md`
- `A scripts/verify_copy_to_safe_gui.py`
- `A scripts/verify_do_not_save_gui.py`
- `A scripts/verify_menu_cleanup_gui.py`
- `A scripts/verify_paste_workflow_gui.py`
- `M tests/test_contextmenu.py`
- `A tests/test_copy_to_safe.py`
- `A tests/test_do_not_save.py`
- `M tests/test_e4_contextmenu.py`
- `A tests/test_menu_cleanup.py`

### C. settings z-order/window ownership

- `M cache_vault/ui/dialogs.py`
- `M cache_vault/ui/settings_hub.py`
- `M cache_vault/ui/shell.py`
- `M tests/test_destructive_confirmations.py`
- `M tests/test_dialogs.py`
- `M tests/test_settings_hub.py`
- `M tests/test_settings_hub_integration.py`

### D. selection/metadata consistency

- `A cache_vault/core/display_metadata.py`
- `M cache_vault/core/models.py`
- `M cache_vault/core/vault.py`
- `M cache_vault/ui/preview.py`
- `M cache_vault/ui/vault_lock.py`
- `M cache_vault/ui/vault_screens.py`
- `M tests/test_clip_selection.py`

### E. hotkey recording

- No unique files in the old branch diff should be treated as the source of truth for hotkey work.
- Any incidental old-branch overlap in `cache_vault/ui/shell.py` is superseded by the already-landed hotkey lane on the release branch.

### F. main screen/sidebar polish

- `M cache_vault/modules/registry.py`
- `A docs/CACHE_VAULT_MENU_AUDIT_2026-06-30.md`
- `A docs/CACHE_VAULT_RC3_REAL_USE_UI_AUDIT_2026-07-01.md`
- `A docs/CACHE_VAULT_SCREENSHOTS_BULK_WORKFLOW_AUDIT_2026-07-01.md`
- `A docs/CACHE_VAULT_UI_CONSISTENCY_AUDIT_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC1_PACKAGED_GUI_QA_2026-06-30.md`
- `A docs/CACHE_VAULT_V0.1.5_RC1_PRIVATE_SOAK_CHECKLIST_2026-06-30.md`
- `A docs/CACHE_VAULT_V0.1.5_RC1_R2_INSTALL_SMOKE_2026-06-30.md`
- `A docs/CACHE_VAULT_V0.1.5_RC1_RELEASE_CANDIDATE_RECEIPT_2026-06-30.md`
- `A docs/CACHE_VAULT_V0.1.5_RC2_PACKAGED_GUI_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC2_R2_INSTALL_SMOKE_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC2_STABILIZATION_TRIAGE_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC3_MANUAL_DEFECT_FIX_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC3_PACKAGED_GUI_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC3_R2_INSTALL_SMOKE_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC4_LOCAL_EXE_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_V0.1.5_RC4_UI_CONSISTENCY_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_WORKFLOW_INTEGRATION_RC_AUDIT_2026-06-30.md`
- `A docs/DATESTAMP_IMAGE_VIEWER_POLISH_QA_2026-06-30.md`
- `A scripts/verify_packaged_gui_run.py`
- `A scripts/verify_packaged_gui_run_rc2.py`
- `A scripts/verify_packaged_gui_run_rc3.py`
- `A scripts/verify_ui_polish_gui.py`
- `A tests/test_rc3_defect_fixes.py`
- `A tests/test_rc4_consistency.py`
- `A tests/test_ui_polish.py`
- `A tests/test_workflow_integration.py`

### G. mobile bridge work already landed

- `M android/app/build.gradle.kts`
- `M android/app/src/main/AndroidManifest.xml`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/CacheVaultMobileApp.kt`
- `A android/app/src/main/java/com/prooffoundry/cachevaultmobile/connect/BackgroundConnectionService.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/connect/ConnectionPlanner.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/BridgeClient.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/BridgeRepository.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/Models.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/PairingStore.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/UserMessages.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/VaultNavigation.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/AppViewModel.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/CacheVaultMobileRoot.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/ClipListFormatter.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/MainShell.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/VaultSections.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/components/ClipCard.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/components/VaultSectionCard.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/screens/BrowseScreen.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/screens/ClipDetailScreen.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/screens/PcFoundBottomSheet.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/screens/ProofScreen.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/screens/SettingsScreen.kt`
- `M android/app/src/main/java/com/prooffoundry/cachevaultmobile/ui/screens/VaultHomeScreen.kt`
- `M android/app/src/main/res/values/strings.xml`
- `M android/app/src/test/java/com/prooffoundry/cachevaultmobile/connect/ConnectionPlannerTest.kt`
- `M android/app/src/test/java/com/prooffoundry/cachevaultmobile/data/BridgeClientTest.kt`
- `M android/app/src/test/java/com/prooffoundry/cachevaultmobile/data/PairingConfigLabelTest.kt`
- `M android/app/src/test/java/com/prooffoundry/cachevaultmobile/data/UserMessagesTest.kt`
- `M cache_vault/core/mobile/api.py`
- `M cache_vault/core/mobile/bridge.py`
- `M cache_vault/core/mobile/models.py`
- `M cache_vault/ui/mobile_dialogs.py`
- `A docs/CACHE_VAULT_ANDROID_RECONNECT_DEVICE_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_ANDROID_RECONNECT_EVIDENCE_MANIFEST_2026-07-01.md`
- `A docs/CACHE_VAULT_ANDROID_RECONNECT_QA_2026-07-01.md`
- `A docs/CACHE_VAULT_ANDROID_RECONNECT_RELEASE_GATE_2026-07-02.md`
- `A docs/CACHE_VAULT_MOBILE_CONNECTION_LIFECYCLE_PLAN_2026-07-01.md`
- `M tests/test_mobile_bridge.py`
- `A tests/test_mobile_connection_lifecycle.py`

### H. public/release/landing/proof contamination

- `D CNAME`
- `M cache_vault/__init__.py`
- `A docs/CACHE_VAULT_PUBLIC_SURFACE_AUDIT_2026-06-30.md`
- `M docs/LANDING.md`
- `A docs/MOBILE_PAIRING_QR_FLOW_PLAN_2026-07-01.md`
- `M docs/index-fallback.html`
- `M packaging/RELEASE_NOTES-v0.1.4.md`
- `A packaging/RELEASE_NOTES-v0.1.5-rc1.md`
- `A packaging/RELEASE_NOTES-v0.1.5-rc2.md`
- `A packaging/RELEASE_NOTES-v0.1.5-rc3.md`
- `M pyproject.toml`
- `M tools/check_exe_version.py`

### I. unrelated/unknown

- `M .gitignore`
- `M cache_vault/core/paste_delivery.py`
- `A docs/CACHE_VAULT_TK_NATIVE_CRASH_AUDIT_2026-07-01.md`
