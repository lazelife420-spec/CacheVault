# Cache Vault Free vs Founder

Product label: **Cache Vault Founder Edition**  
Studio: **Proof Foundry** — *Build it. Prove it. Ship it.*

One-liner: A local-first clipboard vault for useful text, code, screenshots, receipts, and reusable work.

## Feature matrix

| Feature | Free | Founder | Status | Notes |
|---|---:|---:|---|---|
| Capture clipboard text | Yes | Yes | Implemented | Core free feature |
| Search vault | Yes | Yes | Implemented | Core free feature |
| Favorites | Yes | Yes | Implemented | Core free feature |
| View saved clips | Yes | Yes | Implemented | Core free feature |
| Copy items back out | Yes | Yes | Implemented | Copy Clean basics free |
| Basic local vault | Yes | Yes | Implemented | No cloud claim |
| Stamped Receipts (view local history) | Yes | Yes | Implemented | Core proof feature |
| Vault Lock (UI privacy) | Yes | Yes | Implemented | Not encryption |
| Quick Paste picker | Yes | Yes | Implemented | Global hotkey |
| Single clip export TXT/MD/HTML/JSON | Yes | Yes | Implemented | Basic export stays free |
| Screenshot save as PNG | Yes | Yes | Implemented | Single asset export |
| Export folder (organized clips) | Limited | Yes | Implemented | Founder: `exports_advanced` |
| Export ZIP bundle | No | Yes | Implemented | Founder: `zip_export` |
| Proof-pack export | No | Yes | Implemented | Founder: `proof_pack_export` |
| HTML bundle export | No | Yes | Implemented | Founder: `html_bundle_export` |
| Editable copies (create/edit/save) | Limited | Yes | Implemented | Founder: `editable_copies_advanced` |
| Vault Macros | Limited | Yes | Implemented | Founder: `macros_advanced` |
| Custom Safes (organize beyond default) | Basic | Yes | Implemented | Founder: `safes_advanced` for custom safes |
| Advanced filters / duplicate review | Basic | Yes | Partial | Founder: `smart_filters_advanced` for duplicate/sensitive review screens |
| Mobile bridge | No | No | Not claimed | Do not ship in this SKU |
| Cloud sync | No | No | Not implemented | Do not claim |
| Encrypted safes | No | No | Not implemented | Do not claim |
| In-app payment | No | No | Not implemented | Manual license delivery only |

## Founder feature keys (internal)

| Key | Gates |
|---|---|
| `exports_advanced` | Bulk export view (folder with optional file copies) |
| `zip_export` | ZIP export from export view |
| `proof_pack_export` | Proof-pack zip exports (context menu, exports screen) |
| `html_bundle_export` | HTML bundle workflows and exports |
| `editable_copies_advanced` | Editable copy create/open/save workflows |
| `smart_filters_advanced` | Duplicates review, sensitive filter power tools |
| `macros_advanced` | Vault Macros screen and macro execution |
| `safes_advanced` | Create/customize Safes beyond default |

## Free limits (policy)

Free users retain full access to:

- Local clipboard vault capture and history
- Search, favorites, collections (basic)
- Copy back out with Copy Clean basics
- View Stamped Receipts (local proof ledger)
- Single-item export to TXT/MD/HTML/JSON
- Default Safe and basic organization
- Vault Lock for UI privacy

Founder unlocks power workflows:

- Bulk and proof-backed exports
- ZIP bundles with manifest + SHA256SUMS
- Editable-copy and HTML-bundle receipt workflows
- Vault Macros and custom Safes
- Advanced review filters

## Doctrine

```text
If it is not usable for free, it is garbage.
```

Founder is for advanced power workflows, not basic vault access. No fake marketing. Every release claim needs a receipt.
