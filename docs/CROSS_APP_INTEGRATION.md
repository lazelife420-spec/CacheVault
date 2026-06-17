# Cache Vault proof-pack format (cross-app integration)

This document describes the **proof-pack export zip** produced by Cache Vault desktop.
The format is defined in `cache_vault/core/exports.py` — core-only, no UI dependency.

Third-party tools can verify exports without the desktop app using:

- `verify_export_pack(path)` — SHA256SUMS + manifest validation
- `verify_zip_hashes(path)` — hash verification only
- `validate_manifest(dict)` — manifest schema checks

## Zip structure

```
CacheVault-export-YYYY-MM-DD-HHMMSS.zip
├── README.txt
├── EXPORT_RECEIPT.txt
├── manifest.json
├── SHA256SUMS.txt
├── receipts/
│   ├── event-*.json          # stamped event log excerpts
│   └── *.json                # file receipts (metadata only)
├── items/
│   ├── {clip_id}.txt
│   ├── {clip_id}.png         # image clips
│   └── original/             # optional original file copies
├── editable_copies/
│   └── {clip_id}/...
└── html_bundles/
    └── {clip_id}/...
```

## SHA256SUMS.txt

Format (GNU-style):

```
<sha256_hex>  <relative/path/in/zip>
```

Rules:

- Hashes are computed **after staging**, before zipping.
- Every staged file is listed **except** `SHA256SUMS.txt` itself.
- The final zip is **not** hashed inside its own SHA256SUMS file.
- `manifest.json` is included and hashed.

## manifest.json (top level)

| Field | Description |
|-------|-------------|
| `document_type` | Always `cache_vault_proof_export` |
| `export_id` | Unique export identifier |
| `export_timestamp` | ISO-8601 UTC |
| `app_version` | Cache Vault version string |
| `machine_label` | `HOST/user` (local only) |
| `export_type` | `single_item` or `multi_clip` |
| `safes` | Distinct Safe summaries for exported clips |
| `safe_id` / `safe_name` | Present for single-item exports |
| `items` | Per-clip manifest entries (see below) |
| `file_list` | All hashed relative paths |
| `hashes` | Map of path → SHA-256 (mirrors SHA256SUMS) |
| `receipts_included` | Boolean |
| `sha256sums_included` | Boolean |
| `manifest_included` | Boolean |
| `limitations` | Honest deferred capabilities |

## manifest.json item entry

Each object in `items[]` includes, where available:

| Field | Description |
|-------|-------------|
| `clip_id` / `item_id` | Vault clip identifier |
| `type` / `item_type` | Classification (code, path, plain, …) |
| `source_app` | Foreground app when captured |
| `source_window` | Window title when captured |
| `source_app_version` | `null` (not tracked today) |
| `safe_id`, `safe_name` | Local Safe destination |
| `capture_mode` | `auto`, `manual_save_hotkey`, `armed_next_copy`, `mobile_share`, … |
| `auto_saved` | Boolean |
| `content_hash` | Clip content SHA-256 |
| `files` | Exported relative paths in zip |
| `file_hashes` | Per-file SHA-256 for staged paths |
| `receipt_references` | Paths under `receipts/` |
| `export_used` | `clip_content`, `editable_copy`, `html_bundle_copy`, … |
| `used_editable_copy` | Boolean |
| `editable_copy` | Revision, paths, original clip id |
| `html_bundle` | Asset counts, bundle dir, remote skip confirmation |
| `original_path_metadata` | Path reference (not mutated) |
| `warnings`, `unsupported` | Best-effort edge cases |

### HTML bundle metadata

```json
"html_bundle": {
  "original_clip_id": "...",
  "bundle_dir": "html_bundles/{clip_id}",
  "exported_html_path": "html_bundles/{clip_id}/page.copy.001.html",
  "copied_asset_count": 2,
  "missing_asset_count": 0,
  "remote_assets_skipped": 1,
  "original_assets_not_fetched": true,
  "original_assets_not_mutated": true
}
```

Remote URLs are counted and skipped — never fetched.

### Editable copy metadata

```json
"editable_copy": {
  "original_clip_id": "...",
  "revision": 1,
  "copy_path_in_zip": "editable_copies/{clip_id}/note.copy.001.txt",
  "export_used": "editable_copy",
  "used_editable_copy": true
}
```

Originals on disk are never modified; exports use managed copies.

## Export receipt (`export_zip_created`)

File receipt under `%LOCALAPPDATA%/CacheVault/Receipts/` plus event log entry.

Includes: `export_id`, `clip_ids`, `output_zip_path`, `manifest_included`,
`sha256sums_included`, `receipts_included`, `file_count`, `receipt_count`,
`safe_id`/`safe_name`/`capture_mode` (single item), `safes[]`, `app_version`.

**Never includes full clipboard content.**

## Safes

Safes are **local vault sections** — not encrypted containers.

Whole-Safe export (`Export selected Safe`) is **deferred**; manifest schema already
includes `safe_id`, `safe_name`, `safes[]`, and per-item capture metadata.

## Boundaries

- **Local only** — no cloud dependency for proof packs.
- **Read-only mobile bridge** — mobile does not create proof packs.
- **Core API**: `create_export_pack`, `verify_export_pack`, `validate_manifest`, `hash_file`, `write_export_receipt`.

## Verification example

```python
from pathlib import Path
from cache_vault.core.exports import verify_export_pack

ok, errors = verify_export_pack(Path("CacheVault-export-....zip"))
assert ok, errors
```
