# Cache Vault v0.1.5-rc4 — UI Consistency QA Receipt

**Date:** 2026-07-01  
**Candidate Version:** 0.1.5-rc4  
**Status:** GREEN  

This document logs the manual verification results for the UI/UX consistency, selection, metadata, timezone, and resizing fixes introduced in the `v0.1.5-rc4` candidate.

---

## 1. Selection & Dynamic Bulk Actions

### A. Shared Selection Behavior
- **Test:** Select multiple mixed items (texts, links, images) using Ctrl-click and Shift-click in All Clips, filtered search views, and grid views.
- **Result:** Selection synchronization works flawlessly. Selected row borders highlight correctly in all views. Selection change events dispatch accurately to the bottom action strip.

### B. Type-Aware Selected Action Model
- **Test:** Select 1 image, 2 text clips, and 1 link. Right-click to trigger the context menu. Inspect the labels.
- **Result:** The menu items update dynamically with counts:
  - `"Copy 3 Text/Link Clips"`
  - `"Export 1 Screenshot to Folder…"`
  - `"Export 1 Screenshot as ZIP"`
  - `"Copy 1 File Path"`
- **Test:** Verify the bottom action strip buttons have matching labels.
- **Result:** Matches context menu labels exactly.

### C. Mixed ZIP Export
- **Test:** Select mixed items, click `"Export ZIP"`, specify `export.zip`.
- **Result:** Successfully packages the selected screenshots as PNG files and the selected text/link clips as formatted `.txt` files (with titles and dates) into the target ZIP.

---

## 2. Time & Metadata Unification

### A. Local Timezone Display
- **Test:** Check clip cards added at various times.
- **Result:** Timestamps convert from UTC to local Windows timezone and display user-friendly relative descriptions:
  - `"Today · 6:09 PM"`
  - `"Yesterday · 3:20 PM"`
  - `"Jun 30 · 8:33 PM"`
- **Test:** Hover over the metadata lines.
- **Result:** Tooltips expose the complete ISO string formatted in local time.

### B. Unified Metadata Origin
- **Test:** Check origin labels on multiple clip types.
- **Result:** Exposes details consistently:
  - PC Screenshots: `"PC · Screenshot · CacheVault.exe"`
  - Mobile Clips: `"Android Share · From Phone"`
  - Browser Links: `"Chrome.exe · Link"`
  - Default Text Clips: `"Notepad.exe · Text"`

---

## 3. Screenshot Card Layout Improvements

### A. Image-First Row Design
- **Test:** Inspect a screenshot row in All Clips (list view).
- **Result:** Redesigned layout renders:
  - Resized thumbnail preview on the left.
  - Title and dimensions/size (`1920x1080 · 154 KB`) alongside local timezone metadata.
  - Inline action buttons: `Copy Image`, `Drag PNG`, `Save As PNG`, `Open Folder`.
- **Test:** Click inline action buttons.
- **Result:** Actions execute instantly on the single clip.

---

## 4. Layout Scaling & Styling Parity

### A. Window Resizing
- **Test:** Resize the main application window.
- **Result:** Minimum window size is constrained to `1024x720`. Nav, list, and preview panels adjust fluidly without overlapping or clipping elements.

### B. Command Center Highlight Consistency
- **Test:** Open the Command Center, select an action card.
- **Result:** Card border highlights with width `1` in `brand.PROOF_TEAL` and background `brand.ROW_SELECTED_BG`, perfectly matching `ClipList` row highlights.

---

## 5. Automated Tests Summary
- Run `pytest -p no:xonsh tests/test_rc4_consistency.py`
- All tests passed successfully.
