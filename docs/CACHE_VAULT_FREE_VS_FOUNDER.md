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
| Snippet Macros | Limited | Yes | Implemented | Founder: `macros_advanced` |
| Custom Safes (organize beyond default) | Basic | Yes | Implemented | Founder: `safes_advanced` for custom safes |
| Advanced filters / duplicate review | Basic | Yes | Partial | Founder: `smart_filters_advanced` for duplicate/sensitive review screens |
| Mobile bridge / Android companion | Yes | Yes | Implemented | **Ungated. Free for the 0.2.1 external-test release** — external-test policy, not a permanent commitment. See note below |
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
| `macros_advanced` | Snippet Macros screen and macro execution |
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
- Snippet Macros and custom Safes
- Advanced review filters

## Correction — 2026-08-14: mobile bridge status

This document previously recorded:

> `| Mobile bridge | No | No | Not claimed | Do not ship in this SKU |`

That is no longer accurate and was stale relative to the mobile work.

**Verified facts as of the 0.2.1 external-test freeze:**

- A release-signed Android companion **is shipping** in the external test
  (`CacheVaultMobile-0.2.1-external.apk`, versionCode 8).
- The mobile bridge and the mobile share/capture path are **ungated**. No
  `is_feature_enabled`, `_require_founder`, or `is_founder_unlocked` check exists
  anywhere in `cache_vault/core/mobile/` or in the capture path in
  `cache_vault/core/vault.py`.
- Confirmed empirically: with the licence removed (`MISSING_LICENSE`, all eight
  Founder keys `False`), `app.py --selftest` reports
  *"core capture/classify/sensitive/image/mobile pipeline works"*, and the LAN
  bridge listens and enforces auth (401 to an unauthenticated request).

### Policy decision — made 2026-08-14

> **For the 0.2.1 external-test release, the Android companion and LAN mobile
> bridge are part of Free. This is an external-test policy, not a permanent
> commitment for all future commercial versions.**

Rationale:

- It matches the binary that is already frozen. No rebuild, no re-signing.
- All wave-1 testers can exercise the strongest cross-device workflow before
  they have earned a Founder licence.
- It produces real evidence about whether mobile is valuable enough to inform
  later pricing, which is the point of the external test.
- It avoids ratifying an accidental implementation detail as permanent policy.

The frozen Free build already communicates this to users: the first-run welcome
includes *"4. Send from phone — Use Cache Vault Mobile to share from Android and
send items to your PC inbox."*

**Copy rule.** Tester-facing and website copy must scope the claim to this
release — for example *"the free external-test build includes the local Android
companion"*. Do **not** write copy that promises mobile is free permanently, and
do not describe it as a paid feature.

Future commercial policy is deliberately deferred to tester evidence.

Unchanged and still correct: **Cloud sync** and **Encrypted safes** are not
implemented and must not be claimed. Vault Lock is UI privacy, not encryption.

## Doctrine

```text
If it is not usable for free, it is garbage.
```

Founder is for advanced power workflows, not basic vault access. No fake marketing. Every release claim needs a receipt.
