# Capture Rules

Cache Vault does **not** blindly save every copy. Capture Rules give you control over what gets saved, what gets ignored, and which **Safe** (local vault section) receives each item.

> **Safes are not encrypted.** They are named logical destinations inside your local vault database — not secure containers unless real encryption is implemented separately.

## Auto Capture

**Setting:** `Save normal clipboard copies automatically` (Settings → Capture Rules)

| State | Behavior |
|-------|----------|
| **ON** (default) | Normal Ctrl+C clipboard changes are classified and saved according to default rules (excluded apps, size limits, sensitive blocking). |
| **OFF** | Ctrl+C still copies to the system clipboard, but Cache Vault does **not** save the item unless you use a hotkey or armed capture. |

**Pause capture** (Settings → Capture) still stops all automatic ingestion when enabled.

## Manual Save Hotkey

**Setting:** `Save current clipboard to Safe` — default **Ctrl+Shift+C**

1. Copy text or an image normally.
2. Press the manual-save hotkey.
3. Cache Vault saves the **current** clipboard contents to the chosen Safe.

If **Show Safe picker when saving manually** is OFF, items go to the **Default Safe**. If ON, a Safe picker appears at the cursor.

## Save Next Copy (Armed Capture)

**Setting:** `Save next copy to selected Safe` — default **Ctrl+Alt+C**

1. Press the hotkey → Safe picker opens.
2. Choose a Safe (Default, Temporary, user Safes, or create new).
3. Copy once in any app (Ctrl+C).
4. That **one** copy is saved to the selected Safe; armed mode turns off.
5. Esc or ~60s timeout cancels armed mode (via controller expiry).

## Ignore Next Copy

**Setting:** `Ignore next copy` — default **Ctrl+Shift+X**

1. Press the hotkey → toast: `Next copy will not be saved.`
2. The next clipboard change is ignored by Cache Vault (system clipboard still works).
3. Ignore mode turns off after one clipboard change or timeout.

## Safes

Built-in Safes:

| ID | Name |
|----|------|
| `default` | Default Safe |
| `temporary` | Temporary Safe |
| `ignore` | Ignore / Do Not Save (virtual — not a storage destination) |

User Safes are created from the Safe picker or Settings → Capture Rules → **Manage Safes…**

**Safe picker** is available from:

- Manual-save hotkey (when picker enabled)
- Save-next-copy hotkey
- Clip context menu → **Move to Safe…**
- Inspector shows Safe + capture mode metadata

Sidebar **SAFES** section filters clips by Safe when items exist.

## Sensitive handling (best-effort)

When **Do not auto-capture sensitive-looking clips** is enabled (default ON):

- Passwords, tokens, private keys, API key shapes, etc. are **not auto-saved**.
- A non-blocking toast appears: `Sensitive-looking clipboard item was not auto-saved.`
- You can still **manually save** via the manual-save hotkey (explicit intent).

Detection is conservative but **not perfect** — treat it as a helper, not a security guarantee.

## Other capture settings

| Setting | Purpose |
|---------|---------|
| Default Safe | Default destination for auto-capture and manual save (when picker off) |
| Excluded apps | One app name per line — clipboard from matching foreground apps is skipped |
| Max auto-capture size | Bytes limit for automatic saves (0 = unlimited) |

## Item metadata

Each saved clip records:

- `safe_id` / `safe_name`
- `capture_mode`: `auto`, `manual_save_hotkey`, `armed_next_copy`, `moved_to_safe`, `imported`, `mobile`, `external_app`
- timestamp, source app/window (when detectable), item type, content hash

## Receipts

File receipts under `%LOCALAPPDATA%/CacheVault/Receipts/` (and stamped event log) for:

| Action | Receipt / event |
|--------|-----------------|
| Auto save | `clipboard_auto_saved` |
| Manual hotkey save | `clipboard_manual_saved` |
| Next copy armed | `clipboard_next_copy_armed` |
| Armed copy saved | `clipboard_next_copy_saved` |
| Ignored copy | `clipboard_next_copy_ignored` |
| Sensitive blocked | `clipboard_sensitive_not_auto_saved` |
| Moved to Safe | `item_moved_to_safe` |
| Safe created | `safe_created` |

Receipts store metadata only — **never full sensitive clipboard content**.

## Exports & manifest

Proof-pack zip structure and verification: `docs/CROSS_APP_INTEGRATION.md`.

Each `manifest.json` item entry includes:

- `safe_id`, `safe_name`, `capture_mode`, `auto_saved`
- `source_app`, `content_hash`, `file_hashes`, `receipt_references`
- `editable_copy` / `html_bundle` blocks when applicable

Top-level manifest includes `safes[]`, `receipts_included`, `sha256sums_included`, and `limitations.export_by_safe`.

Export-by-whole-Safe from the UI is **deferred**; schema is ready for Safe-scoped proof packs.

## Mobile boundary

- Mobile bridge remains **read-only** — it does not bypass capture rules or enable auto-capture.
- Clip API responses include `safe_id`, `safe_name`, and `capture_mode` for display.
- Mobile cannot push captures into the vault.

## No cloud dependency

All capture rules, Safes, and receipts are stored locally on this PC.
