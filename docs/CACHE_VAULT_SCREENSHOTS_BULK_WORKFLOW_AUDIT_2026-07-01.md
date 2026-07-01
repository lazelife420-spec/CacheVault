# Cache Vault Screenshots Bulk Workflow Audit

Date: 2026-07-01
Scope: v0.1.5-rc2. Audit existing export/save/copy actions for screenshots
(images) and recommend a narrow, rc2-safe bulk workflow.

## 1. Existing actions inventory

| Action (label) | Impl | Output | Single menu | Bulk menu | Button |
|---|---|---|---|---|---|
| Save All As PNG / Save PNGs / Save Screenshots (same fn) | `batch_actions.py:234` `bulk_save_images` | Writes each PNG into a chosen folder (`askdirectory`) | No | Yes (`save_pngs`, `save_screenshots`) | Yes (bulk strip / home batch) |
| Export ZIP | `batch_actions.py:294` `bulk_export_zip` | One `.zip` of PNGs (`asksaveasfilename`) | No | Yes (`export_zip`) | Yes (bulk strip) |
| Copy File Paths | `batch_actions.py:367` `bulk_copy_paths` | Newline paths to clipboard | No | Yes (`copy_paths`) | Yes (bulk strip) |
| Copy PNGs | `batch_actions.py:200` `bulk_copy_images` | First image to clipboard only | No | No (mapped, not emitted) | Yes (bulk strip) |
| Export Bundle (mixed) | `batch_actions.py:412` `bulk_export_bundle` | Proof `.zip` via `export_proof_zip` | No | Yes (`export_bundle`) | Yes (bulk strip) |
| View Proof | `batch_actions.py:406` `bulk_view_proof` | **No-op** (toast only) | No | Yes (`view_proof`) | Yes (bulk strip) |
| Drag PNG / Drag File Out | `shell.py` `_drag_out_clip` -> `drag_export.py` | Temp PNG + native drag | Yes (`drag_out`) | No | No |
| Open Asset Folder | `shell.py` `_open_asset_folder` | Reveals asset in Explorer | Yes (`open_asset_folder`) | No | Yes (single strip) |
| Export Proof Zip (single) | `shell.py` `_export_clip_proof` | Per-clip proof `.zip` | Yes (`export_proof_zip`) | (bulk `export`) | Yes (single strip) |
| Copy Image (single) | `shell.py` `_copy_again` | Single PNG to clipboard | Yes (`copy_again`) | n/a | Yes (single strip) |

Menu specs: `core/contextmenu.py` (image_only / mixed blocks). Wiring +
dispatch: `ui/clip_context.py`. Bulk implementations: `ui/batch_actions.py`
(wrapped by `shell.py` `_bulk_*`).

## 2. Is there an obvious "Export Screenshots to Folder..." action?

**Not by that name.** The functional equivalent already exists:
`bulk_save_images` (`batch_actions.py:234`) uses
`filedialog.askdirectory(title="Save Screenshots As PNG")` and writes each PNG
into the chosen folder. But it is:
- labeled three different ways ("Save All As PNG" / "Save PNGs" /
  "Save Screenshots"), which hides intent;
- **multi-select only** (bulk menu / bulk strip); no single-clip folder export;
- absent from a persistent Screenshots-view toolbar (only appears after >=2
  items are selected).

So the capability is implemented; the workflow is not exposed clearly. Per the
task, this favors "expose clearly" over building new logic.

## 3. Safety and receipts (already handled)

- Empty selection/view: every bulk fn early-returns on `if not ids` and toasts
  "No screenshots selected..." when the filtered image set is empty. No crash.
- Missing/deleted files: `bulk_save_images` and `bulk_export_zip` check
  `storage.load_clip_asset_bytes` and count failures (partial vs completed);
  errors are caught. Note gap: `bulk_copy_paths` does **not** verify the file
  exists on disk before copying its path.
- Receipts: `bulk_save_images`, `bulk_export_zip`, `bulk_copy_paths`,
  `bulk_export_bundle` all write file/event receipts with
  `transfer_status` completed/partial. `bulk_view_proof` writes none (it is a
  no-op).
- Folder chosen via `filedialog.askdirectory`; assets loaded from
  `%LOCALAPPDATA%/CacheVault/assets` via `image_assets` /
  `storage.load_clip_asset_bytes`; filenames from
  `image_assets.make_smart_filename` with collision-safe `next_available_path`.

## 4. Recommendation (rc2-safe)

Do not build new export logic. Reuse `bulk_save_images` and expose it clearly:

1. Rename the surfaced action to a single, obvious label: **"Export Screenshots
   to Folder..."** (keep the underlying fn). Apply in `core/contextmenu.py`
   (image_only + mixed) and the bulk action strip.
2. Add a single-clip menu entry "Export Image to Folder..." that calls the same
   folder-copy path for one image (wrap `bulk_save_images` with a single id).
3. Optional low-risk: add a persistent button in the Screenshots
   (`FILTER_SCREENSHOTS`) view: "Export all / selected to folder...".
4. After a successful folder save, offer "Open folder" (reveal in Explorer)
   using existing `pathutil.reveal_in_explorer`.
5. Cleanup: remove the dead "View Proof" no-op from the image bulk menu/strip,
   and add existence validation to `bulk_copy_paths` for parity.

Behavioral guarantees to preserve (already true): copies image assets to a
chosen folder, never alters originals, handles empty view and missing files
safely, and produces a receipt.

## 5. Do NOT do in rc2

- Do not rewrite the export core or asset storage.
- Do not change what gets written (still copies of stored PNG assets).
- Do not add new formats/compression options; keep the action narrow.
