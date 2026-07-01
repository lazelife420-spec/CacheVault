# Cache Vault Workflow Integration RC Audit — 2026-06-30

## Summary

This audit verifies that the recently stacked workflow changes behave correctly **together** before any further feature work. Each feature passed individually; this receipt proves they work as an integrated system.

---

## Branch & Commit Range

| Field | Value |
|---|---|
| **Branch** | `ux/mobile-image-polish-local` |
| **Top commit** | `1a8dcdd feat: clean up menus and settings organization` |
| **Commit range audited** | `e6fe972..1a8dcdd` (7 commits) |
| **Slices covered** | Public proof reconciliation, Selected paste, Copy-to-Safe, Do Not Save Next Copy, Date/image polish, Menu/settings cleanup |

---

## Flows Tested — Pass/Fail Table

| # | Flow | Tests | Verdict |
|---|---|---|---|
| 1 | **Selected paste + focus safety** | `hwnd_belongs_to_widget` guard, `_guard_unlocked` check, `no_target_window` graceful fail, `_keyboard_focus_is_text_input` guard | **PASS** |
| 2 | **Copy-to-Safe interaction** | Duplicate created with new ID, original preserved, `CAPTURE_COPIED_TO_SAFE` mode set, invalid safe returns None, invalid clip returns None, original not soft-deleted | **PASS** |
| 3 | **Do Not Save Next Copy interaction** | Arms and consumes correctly, one-shot only (second consume returns False), does not block copy-to-safe, does not interfere with paste delivery, expires after timeout, arming ignore cancels arm-next-copy | **PASS** |
| 4 | **Date/image preview regression** | `_short_time` produces readable format, preview uses `vault_card` style, preview renders dimensions and filename | **PASS** |
| 5 | **Menu honesty** | All shipped action keys present (`copy_again`, `paste_selected`, `copy_to_safe`, `copy_to_last_safe`), cascade submenus wired, dispatch dict covers all leaf keys, copy_clean constants valid | **PASS** |
| 6 | **Release proof regression** | No stale v0.1.4.1 in current public docs, no stale test counts (545/561), all v0.1.4.1 references are in historical audit files only | **PASS** |

---

## Integration Test File

**File:** `tests/test_workflow_integration.py`
**Tests:** 25 passed, 0 failed

Key cross-feature interaction tests:
- `test_ignore_does_not_block_copy_to_safe` — Arms bypass, then verifies copy-to-safe still works
- `test_ignore_does_not_block_selected_paste_code_path` — Verifies paste delivery does not consult ignore flag
- `test_arm_ignore_cancels_arm_next_copy` — Verifies mutual exclusion between armed modes
- `test_copy_to_safe_does_not_delete_original` — Non-destructive duplication confirmed
- `test_dispatch_dict_covers_all_leaf_keys` — Every context menu key maps to a handler

---

## Required Gates

| Gate | Command | Result |
|---|---|---|
| **pytest** | `pytest -p no:xonsh` | **785 passed** |
| **compileall** | `python -m compileall cache_vault` | **PASS** |
| **selftest** | `python app.py --selftest` | **PASS** (`selftest OK`) |

---

## Screenshots

| Screenshot | Description |
|---|---|
| `visual_smoke/workflow_integration_rc_audit.png` | Settings Hub showing advanced category labels and overall UI state |
| `visual_smoke/menu_settings_cleanup.png` | Context menu cascade structure verification |

---

## Stale Reference Scan

```
Pattern scanned: v0.1.4.1, 545 tests, 561 tests, 07d604, 7A56B8, No network calls
Files checked: docs/*.md, README.md, docs/index.html
```

| File | Match | Context | Verdict |
|---|---|---|---|
| `docs/OFFLINE_HOTFIX_v0.1.4.1_STABILITY.md` | v0.1.4.1 | Historical hotfix receipt | **OK — historical** |
| `docs/CACHE_VAULT_PUBLIC_SURFACE_AUDIT_2026-06-30.md` | v0.1.4.1 | Audit notes referencing historical doc | **OK — audit context** |
| `docs/index.html` | "No network calls" | Landing page proof caption | **OK — refers to local-first design** |

No stale current-release claims found.

---

## Known Caveats

1. **Paste delivery is headless-safe but not headless-testable.** The `deliver_ctrl_v` function requires a real Windows HWND. Integration tests verify the code path structure, not actual keystroke delivery. The prior manual GUI QA receipt (`docs/SELECTED_ITEM_PASTE_QA_2026-06-30.md`) covers live delivery.

2. **Branch name drift.** The branch `ux/mobile-image-polish-local` now contains significantly more than mobile/image polish. This is fine during development but should be noted for release packaging.

3. **Menu cascade rendering is new.** The cascaded submenus were just introduced in `1a8dcdd`. While tested programmatically, a manual right-click visual check is recommended before final RC packaging.

---

## Final Verdict

### **RC-READY**

All 6 audit flows pass. The feature stack works together without regressions. No stale release claims detected. All three required gates are green.

The product is ready for either:
- **Option A:** Release candidate packaging (version bump, fresh build, fresh SHA256, Proof Foundry update)
- **Option B:** One final polish pass (menu/settings cleanup), then RC packaging

No fake proof added. No features expanded during this audit.
