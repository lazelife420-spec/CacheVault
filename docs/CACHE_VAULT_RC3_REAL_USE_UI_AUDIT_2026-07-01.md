# Cache Vault v0.1.5-rc3 — Real-Use UI Audit

**Date:** 2026-07-01  
**Version:** 0.1.5-rc3  
**Auditor:** Coding Assistant  

During private soak of Cache Vault v0.1.5-rc3, several usability gaps and UI/UX consistency defects were identified. Below is the technical audit and impact analysis for each defect.

---

## 1. All Clips Selection Inconsistency

### Problem
- In `ClipList` (used by All Clips, Links, Search, etc.) and `ClipGrid` (used by Screenshots/Images), selection behaves differently for mixed types.
- The selection tracking state in `shell.py` (`self._selected_clip_ids` and `self._selected_clip_id`) does not always remain in lockstep.
- The selection counts do not show clear type breakdowns when selection is mixed (e.g. showing only "3 selected" instead of "3 selected: 1 screenshot, 1 text, 1 link").

### Code Surface
- [clip_list.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/clip_list.py): `_notify_selection_change`, `_repaint_selection`, `_select`, `_toggle_select`.
- [clip_grid.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/clip_grid.py): `_notify_selection_change`, `_repaint_selection`.
- [shell.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/shell.py): `_on_clip_select`, `_on_clip_selection_change`.
- [selection.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/core/selection.py): `SelectionSummary` and `analyze_selection` helper.

### Risk Level
- **Medium**. Multiple event loops are involved, and incorrect tracking can lead to mismatching context menus or command strip rendering.

### Proposed Fix (RC4-Safe: YES)
- Standardize Ctrl-click and Shift-click behaviors in both lists.
- Update `SelectionSummary` in `selection.py` to produce a verbose type breakdown label (e.g. `3 selected: 1 screenshot, 1 text, 1 link`).
- Ensure both plain selection clicks and multi-selection changes notify the master controller in `shell.py` to correctly calculate and show selection summaries.

---

## 2. Bulk Actions Adaptability to Selection Types

### Problem
- Bulk actions (both in the bottom action strip and in the context menus) are displayed statically, regardless of whether the selected items are eligible.
- "Export ZIP" is only displayed for `image_only` selections, leaving mixed selections with only "Export Bundle" (which creates a complex proof bundle with manifests and databases) rather than a simple ZIP of files/screenshots.
- No dynamic labels showing exactly how many items will be affected (e.g. "Export 2 Screenshots to Folder..." instead of generic "Export Screenshots").

### Code Surface
- [shell.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/shell.py): `_update_bulk_action_strip`.
- [contextmenu.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/core/contextmenu.py): `clip_menu_items` for multiple clips.
- [batch_actions.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/batch_actions.py): `bulk_save_images`, `bulk_export_zip`, `bulk_copy_paths`, `bulk_copy_format`.

### Risk Level
- **Medium**. Dynamically changing menu items requires strict validation of counts to avoid IndexError or KeyError when dispatching commands.

### Proposed Fix (RC4-Safe: YES)
- Redefine multi-clip menu items dynamically based on counts:
  - If any images/screenshots are selected in a mixed list, show: `"Export [N] Screenshots to Folder..."`
  - If any files/images with local paths exist, show: `"Copy [N] File Paths"`
  - If any text/links are selected, show: `"Copy [N] Text/Links"`
- Adapt `bulk_export_zip` in `batch_actions.py` so that if text or link items are present, it falls back to a clean zip with images as PNGs and text/links as text files (or calls `export_proof_zip`).
- Ensure no-op actions are hidden or disabled.

---

## 3. Screenshot/Image Card Image-First Treatment

### Problem
- In `ClipList` (All Clips), image/screenshot clips look virtually identical to text cards, showing only text titles instead of an image-centric representation (dimensions, file size, source application, local capture timestamp, preview thumbnail, and direct quick-action buttons).

### Code Surface
- [clip_list.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/clip_list.py): `_build_row` (specifically the branch handling image clips).

### Risk Level
- **Medium**. Modifying card height and adding inline image loading can impact vertical scroll performance and memory usage.

### Proposed Fix (RC4-Safe: YES)
- Redesign image rows in `ClipList`:
  - Fetch and show thumbnail preview using PIL (resized to `40x30` or `50x38` fit).
  - Query image dimensions (e.g., "1920x1080") and file size (e.g., "154 KB") from database or file storage.
  - Display clear origin tags (e.g. "PC · Screenshot" or "Android Share · From Phone").
  - Render inline action buttons for swift operations: `Copy Image`, `Save As`, and `Open Folder`.

---

## 4. Unified Metadata and Timestamp Display

### Problem
- Metadata is inconsistent: mobile-origin clips show helpful app/origin details, while desktop-origin clips show less detail.
- Timestamps display UTC strings directly without local timezone conversion, creating confusion for user-facing timelines.

### Code Surface
- [clip_list.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/clip_list.py): `_build_row` metadata logic.
- [clip_grid.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/clip_grid.py): Grid row metadata layout.
- A new formatting class or helper utility in `cache_vault/ui/` or `cache_vault/core/`.

### Risk Level
- **Low**. Purely a display layer modification. The underlying SQLite DB timestamps remain UTC.

### Proposed Fix (RC4-Safe: YES)
- Write a unified metadata formatter that handles:
  - Timezone conversion from UTC to local Windows timezone.
  - Display labels like `Today · 6:09 PM`, `Yesterday · 3:20 PM`, or `Jun 30 · 8:33 PM`.
  - Tooltips or secondary text exposing full timestamps.
  - Clear origin context: source app/device/device name.

---

## 5. Main Window Resizing and Layout Scaling

### Problem
- The main window has no minimum size set and doesn't scale its grid layout gracefully, causing overlapping frames or clipping controls when resized to common desktop window sizes.

### Code Surface
- [shell.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/shell.py): `__init__`, grid column/row weights.

### Risk Level
- **Low**. Layout constraints only.

### Proposed Fix (RC4-Safe: YES)
- Set `self.minsize(1024, 720)` on `CacheVaultApp`.
- Re-configure column weightings on the main frames (`self._left_nav`, `self._center`, `self._preview`) to allow fluid scaling without clipping or overlap.

---

## 6. Command Center Highlight Consistency

### Problem
- Command Center hotkey action cards still use slightly different accenting/borders compared to the main All Clips list row selections.

### Code Surface
- [vault_screens.py](file:///c:/Users/KickA/Desktop/CacheVault/cache_vault/ui/vault_screens.py): `_build_hotkey_actions`.

### Risk Level
- **Low**. Pure styling alignment.

### Proposed Fix (RC4-Safe: YES)
- Synchronize background color to `brand.ROW_SELECTED_BG`, border width to `1`, and border color to `brand.PROOF_TEAL` when selected.
