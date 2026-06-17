# Cache Vault v0.1.3-rc2 (release candidate)

**Status:** Release candidate — not a final release. **No git tag.** Do not replace the shipped **v0.1.2** desktop release.

## Scope

### Desktop (Windows exe in this zip)

Everything in **v0.1.2**, plus the desktop hardening lane through Phase 5:

- Command Center home and grouped sidebar (Command / Vault / Review / Proof / Access / Time)
- Stamped Receipts, Exports, Editable Copies, HTML Bundles, Mobile Access screens
- **Capture Rules** — auto-capture toggle, default Safe, manual/arm/ignore hotkeys, sensitive auto-block
- **Safes** — default, temporary, ignore, user-created; clip metadata and sidebar filters
- **Proof export zip** — `manifest.json`, `SHA256SUMS.txt`, `README.txt`, receipts, editable copies, HTML bundles
- Windows scroll behavior, paste-from-selection delivery, immutable originals + editable copies
- Local HTML bundle support (local assets only; remote URLs never fetched)

**Safes are not encrypted.** Whole-Safe export UI is deferred; manifest schema is ready.

### Mobile companion (Android app — separate artifact)

Requires **Mobile Access ON** on the PC running this build:

- Read-only LAN bridge on port **8742**
- Pairing, vault browse, image thumbnails, proof/settings screens
- Clip payloads include Safe metadata when present

Install the matching Android APK from the same branch build; it is **not** inside this Windows zip.

## What changed since v0.1.3-rc1

| Area | Change |
|------|--------|
| Capture rules | User-controlled copy capture, hotkeys, armed/ignore modes |
| Safes | Registry, picker, Move to Safe, manifest + mobile metadata |
| Proof exports | Finalized manifest, SHA256SUMS sync, export receipts, README in zip |
| UI IA | Command Center, honest Exports labels, inspector Safe metadata |
| Tests | Shared Tk session fixture; dialog geometry contract gate |
| Version | `0.1.3-rc2` (RC only — not final) |

## Artifacts (this RC)

- `CacheVault-v0.1.3-rc2-windows.zip`
- `SHA256SUMS.txt`
- `docs/releases/v0.1.3-rc2.md`

## Explicit non-actions

- **No** git tag unless explicitly approved after proof
- **No** GitHub release publish
- **No** modification of shipped v0.1.2 artifacts
- Root `README.md` and `RELEASE_NOTES.md` remain **v0.1.2** (shipped desktop truth)
