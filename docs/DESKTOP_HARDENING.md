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
| 4 | Local HTML bundle support | Planned |
| 5 | Receipts, manifest, export zip | Partial — export exists; receipt model expansion planned |
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

## Core rules (all phases)

- Originals are immutable — never edit source files in place.
- Every important action gets a receipt (Phases 3–5).
- No fake cloud/sync claims.
- Mobile bridge must not regress.
