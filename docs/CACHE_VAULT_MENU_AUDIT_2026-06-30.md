# Cache Vault Menu and Settings Audit — 2026-06-30

Audit of all user-facing menu systems, toolbar dropdowns, settings pages, and context menus. This document identifies clutter, duplication, and planned improvements to group and organize menus intentionally.

---

## 1. Single Clip Right-Click Context Menu (Single Selection)

| Category / Submenu | Action Label | Implemented? | Destination Handler | Action / Notes |
|---|---|---|---|---|
| **Primary** | Copy Selected Item | Yes | `window._copy_again` | **Keep flat** (quick access) |
| **Primary** | Paste Selected Item | Yes | `window._paste_clip` | **Keep flat** (quick access) |
| **Primary** | Open Link | Yes | `window._open_clip_link` | **Keep flat** (link classification only) |
| **Primary** | Drag PNG | Yes | `window._drag_out_clip` | **Keep flat** (image type only) |
| **Primary** | Open Asset Folder | Yes | `window._open_asset_folder` | **Keep flat** (image type only) |
| **Copy Clean** | *Format options (Plain Text, Title + Link, Markdown, etc.)* | Yes | `window._copy_clean` | **Group in "Copy Clean ▸" Submenu** |
| **Organize** | Copy to Last Safe (Name) | Yes | `window._copy_last_safe` | **Group in "Organize ▸" Submenu** |
| **Organize** | Copy to Safe... | Yes | `window._copy_to_safe` | **Group in "Organize ▸" Submenu** |
| **Organize** | Move to Safe... | Yes | `window._move_to_safe` | **Group in "Organize ▸" Submenu** |
| **Organize** | Add to Favorites / Remove from Favorites | Yes | `window._toggle_favorite` | **Group in "Organize ▸" Submenu** |
| **Organize** | Mark Keep | Yes | `window._mark_keep` | **Group in "Organize ▸" Submenu** |
| **Organize** | Send to Snippet Macros | Yes | `window._send_to_macro_safe` | **Group in "Organize ▸" Submenu** |
| **Proof** | View Receipts | Yes | `window._open_events` | **Group in "Proof ▸" Submenu** |
| **Proof** | Export Proof Zip | Yes | `window._export_clip_proof` | **Group in "Proof ▸" Submenu** |
| **Proof** | View Mobile Receipt | Yes | `window._open_events` | **Group in "Proof ▸" Submenu** (mobile capture only) |
| **Advanced** | Create Editable Copy | Yes | `window._create_editable_copy` | **Group in "Advanced ▸" Submenu** |
| **Advanced** | Copy Metadata | Yes | `window._copy_metadata` | **Group in "Advanced ▸" Submenu** |
| **Advanced** | Copy Item ID | Yes | `window._copy_text` | **Group in "Advanced ▸" Submenu** |
| **Advanced** | Copy Source Summary | Yes | `window._copy_clean` | **Group in "Advanced ▸" Submenu** (mobile capture only) |
| **Advanced** | Open Editable Copy / Open Folder | Yes | `window._open_clip_path` | **Group in "Advanced ▸" Submenu** (local paths only) |
| **Advanced** | Reveal in Explorer | Yes | `window._reveal_clip_path` | **Group in "Advanced ▸" Submenu** (local paths only) |
| **Danger** | Remove from History | Yes | `window._remove_from_history` | **Group in "Danger ▸" Submenu** |

---

## 2. Bulk Selection Right-Click Context Menu (Multiple Clips)

| Action Label | Implemented? | Destination Handler | Action / Notes |
|---|---|---|---|
| **Copy as Plain List** | Yes | `window._bulk_copy_format` | Keep flat |
| **Copy as Markdown** | Yes | `window._bulk_copy_format` | Keep flat |
| **Copy as Numbered List** | Yes | `window._bulk_copy_format` | Keep flat |
| **Save to Safe…** | Yes | `window._bulk_move_to_safe` | Keep flat |
| **Create Receipt** | Yes | `window._bulk_create_receipt` | Keep flat |
| **Export** | Yes | `window._bulk_export_proof` | Keep flat |
| **Delete Selected** | Yes | `window._bulk_remove` | Keep flat |
| **Save All As PNG** | Yes | `window._bulk_save_images` | Keep flat (images only) |
| **Export ZIP** | Yes | `window._bulk_export_zip` | Keep flat (images only) |
| **Copy File Paths** | Yes | `window._bulk_copy_paths` | Keep flat (images only) |
| **View Proof** | Yes | `window._bulk_view_proof` | Keep flat (images only) |
| **Export Bundle** | Yes | `window._bulk_export_bundle` | Keep flat (mixed only) |
| **Copy Text + Links** | Yes | `window._bulk_copy_text_links` | Keep flat (mixed only) |
| **Save Screenshots** | Yes | `window._bulk_save_images` | Keep flat (mixed only) |

---

## 3. Top Console Control Strip Menu

| Dropdown Menu | Option Label | Implemented? | Handler | Action / Notes |
|---|---|---|---|---|
| **Capture** | Pause Capture | Yes | `self._set_paused` | Keep |
| **Capture** | Save Current Clipboard | Yes | `self._manual_save_clipboard` | Keep |
| **Capture** | Save Next Copy | Yes | `self._arm_next_copy` | Keep |
| **Capture** | Do Not Save Next Copy | Yes | `self._ignore_next_copy` | Keep |
| **Capture** | Capture Rules | Yes | `self._open_settings` | Keep |
| **Mobile** | Mobile Access | Yes | `_navigate_screen` | Keep |
| **Mobile** | Pair Device | Yes | `_open_pair_android` | Keep |
| **Mobile** | Mobile Inbox | Yes | `_navigate_screen` | Keep |
| **Mobile** | Mobile Receipts | Yes | `_open_mobile_receipts` | Keep |
| **Receipts** | Stamped Ledger | Yes | `_navigate_screen` | Keep |
| **Receipts** | Export Proof Zip | Yes | `_export_view` | Keep |
| **Receipts** | Open Receipts Folder | Yes | `_open_receipts_folder` | Keep |
| **Quick Actions** | Quick Paste | Yes | `_schedule_quick_paste` | Keep |
| **Quick Actions** | Snippet Macros | Yes | `_navigate_screen` | Keep |
| **Quick Actions** | Export Selected | Yes | `_open_export_selected` | Keep |
| **Quick Actions** | Show First-Use Guide | Yes | `_open_guide` | Keep |
| **Quick Actions** | Lock Vault | Yes | `lock_now` | Keep |

---

## 4. Settings Panel Options Audit

| Settings Section | Action Label | Implemented? | Handler | Action / Notes |
|---|---|---|---|---|
| **Auto-Capture Rules** | Enable Auto-Capture / Max capture size | Yes | Settings UI | Keep |
| **Advanced Custody** | Stamped Ledger mode, block sensitive data | Yes | Settings UI | Keep |
| **Global Shortcuts** | Quick Paste, Macro menus | Yes | Settings UI | Keep |
| **Dangerous / Advanced Actions** | Clear Entire Clipboard History | Yes | Settings UI | **Ensure separate confirmation dialog is used** |

---

## Planned Action Plan
1. **Cascade Context Submenus:** Modify `open_clip_menu` in [clip_context.py](file:///C:/Users/KickA/Desktop/CacheVault/cache_vault/ui/clip_context.py) to render nested submenus (cascades) instead of flat list items for groups: "Copy Clean", "Organize", "Proof", "Advanced", and "Danger".
2. **Settings Organization & Separation:** Audit the settings page to make sure dangerous options (like clearing history) are visually separated or have distinct warning prompts.
