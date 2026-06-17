# Cache Vault desktop hardening lane

**Branch:** `feature/cache-vault-desktop-hardening`  
**Goal:** `capture → organize → edit safe copy → paste/export → receipt everything`

## Release truth (unchanged)

| Version | Status |
|---------|--------|
| v0.1.2 | Shipped desktop-only — do not mutate |
| v0.1.3-rc1 | Mobile bridge RC — not tagged, not released |

## Phase status

| Phase | Topic | Status |
|-------|--------|--------|
| **1** | Windows scroll behavior | **Done** — `win_scroll.py`, `scroll_patch.py`, settings |
| **2** | Paste-from-selection UX | **Done** — focus capture, deliver Ctrl+V, receipts, image paste, restore setting |
| **3** | Immutable originals + editable copies | **Done** — `editable_copies.py`, vault API, preview/context menu, receipts |
| **4** | Local HTML bundle support | **Done** — HTML asset scan/copy, bundle revisions, zip export, receipts |
| **4.5** | UI information architecture | **Done** — Command/Vault/Proof/Access nav, vault screens, inspector |
| **5** | Proof export zip + manifest + SHA256SUMS | **Done** — finalized; see `CROSS_APP_INTEGRATION.md` |
| **5.5** | Capture rules + Safes + hotkey capture | **Done** — `safes.py`, `capture_rules.py`, settings, receipts |
| 6 | Smart folders, tags, notes, search | Planned |
| 7 | Sensitive item handling | Partial — auto-expiry exists |
| 8 | Delete/archive/revision model | Partial — Recently Removed exists |
| 9 | Mobile boundaries | Enforced — read-only bridge; regression gate in `scripts/rc_gate.py` |

## Phase 1 — scroll

- Reads `SPI_GETWHEELSCROLLLINES` / `SPI_GETWHEELSCROLLCHARS` on Windows.
- Patches `CTkScrollableFrame` and `CTkTextbox` wheel handlers at startup.
- Settings → Display → **Use Windows scroll settings** (default on).
- Optional multiplier default `1.0`.

## Phase 2 — paste picker

- Captures foreground window before quick-paste picker opens.
- Delivers Ctrl+V to the prior target (not Cache Vault itself).
- Settings for immediate paste and optional clipboard restore (text only).
- Events: `item_pasted` with delivery receipt metadata.

## Phase 3 — editable copies

- Local files referenced by path clips are never opened for in-place edit.
- `EditableCopyStore` keeps working copies under `%LOCALAPPDATA%/CacheVault/EditableCopies/`.
- Revision files: `{stem}.copy.{revision:03d}{suffix}`; originals are never modified.
- Preview + context menu: Open Editable Copy, Create, Save Revision, Show Original, Reveal Copy Folder.
- File receipts under `%LOCALAPPDATA%/CacheVault/Receipts/YYYY-MM-DD/`.
- Events: `editable_copy_created`, `editable_copy_saved`.

## Phase 4 — HTML bundles

- `.html` / `.htm` path clips use the same editable-copy store with `kind=html_bundle`.
- Local assets detected from `href=`, `src=`, and CSS `url(...)`; copied with relative paths preserved.
- Remote URLs counted and skipped — never fetched.
- Missing local assets reported in bundle meta, preview labels, and receipts.
- Preview actions: Create HTML Copy, Preview Copy, Edit Source, Reveal Copied Bundle, Show Original, Export HTML Bundle (zip).
- Receipts: `editable_html_copy_created`, `editable_html_copy_saved`.
- Smoke: `scripts/html_bundle_smoke.py`.

## Phase 4.5 — UI information architecture

- Sidebar groups: **Command**, **Vault**, **Review**, **Proof**, **Access**, **Time**, **Collections**.
- Center screens: Stamped Receipts, Exports, Editable Copies, HTML Bundles, Mobile Access.
- Command Center home with editable-copy and HTML-bundle counts.
- Inspector panel shows proof status, receipts, editable-copy metadata.
- Exports screen shows honest Phase 5 capability labels (manifest, SHA256SUMS, receipts, Safe metadata).
- Smoke: `scripts/ui_ia_smoke.py`.

## Phase 5 — proof exports (finalized)

- `cache_vault/core/exports.py` — core proof-pack service (no UI imports).
- Zip includes: `manifest.json`, `SHA256SUMS.txt`, `README.txt`, `EXPORT_RECEIPT.txt`, `receipts/`, `items/`, `editable_copies/`, `html_bundles/`.
- Public core API: `create_export_pack`, `verify_export_pack`, `validate_manifest`, `hash_file`, `write_export_receipt`.
- Manifest item entries: Safe metadata, capture mode, source app, file hashes, receipt references, editable-copy + HTML-bundle blocks.
- SHA256SUMS hashes all staged files except itself; manifest hashes synced after final write.
- Export receipt: `export_zip_created` with manifest/SHA256/receipt flags + Safe summary.
- Never mutates originals; HTML remote assets never fetched.
- Whole-Safe export deferred — manifest schema ready (`limitations.export_by_safe`).
- Docs: `docs/CROSS_APP_INTEGRATION.md`.
- Smoke: `scripts/export_manifest_smoke.py` → `visual_smoke/export_manifest_smoke.json` (not committed).

## Phase 5.5 — capture rules & Safes

- User-controlled auto-capture ON/OFF (normal Ctrl+C may skip vault save).
- Safes: local vault sections (`default`, `temporary`, user-created) — **not encrypted**.
- Hotkeys: manual save (`Ctrl+Shift+C`), arm next copy (`Ctrl+Alt+C`), ignore next copy (`Ctrl+Shift+X`).
- Safe picker: settings, hotkeys, context menu **Move to Safe…**, inspector metadata.
- Clip fields: `safe_id`, `safe_name`, `capture_mode`.
- Receipts: `clipboard_auto_saved`, `clipboard_manual_saved`, armed/ignored/moved/safe_created.
- Sensitive best-effort auto-block with manual override via hotkey.
- Proof manifest item entries include Safe + capture metadata.
- Docs: `docs/CAPTURE_RULES.md`.

## Core rules (all phases)

- Originals are immutable — never edit source files in place.
- Every important action gets a receipt (Phases 3–5).
- No fake cloud/sync claims.
- Mobile bridge must not regress.
