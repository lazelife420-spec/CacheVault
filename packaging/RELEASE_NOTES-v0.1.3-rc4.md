# Cache Vault v0.1.3-rc4 (release candidate)

**Status:** Release candidate — not a final release. **No git tag.** Do not replace the shipped **v0.1.2** desktop release.

## Two-part RC4

```text
Desktop RC4 = luxury vault UI + Mobile Inbox receiver
Android RC4 = Simple Mode Share Sheet + Manual Setup + Send to PC
```

### Desktop (Windows exe in this zip)

Everything in **v0.1.3-rc3**, plus:

- **Luxury vault UI** — graphite palette, custody language, Command Center polish
- **Mobile Inbox** — receive items sent from a paired Android phone
- **Send-to-PC endpoint** — `POST /mobile/v1/inbox/send` with receipt stamping
- **Default Safe** assignment for mobile-sent items
- Vault Macros live execution (hotkeys, text shortcuts, picker) from rc3

**Safes are not encrypted.** Whole-Safe export UI is deferred.

**No cloud sync** — mobile companion uses a paired local Wi-Fi bridge only.

### Mobile companion (Android debug APK — separate artifact)

Install `CacheVault-Mobile-v0.1.3-rc4-debug.apk` from the same RC folder. It is **not** inside the Windows zip.

Requires **Mobile Access ON** on the PC:

- **Manual Setup** — enter PC address, bridge port, device ID, pairing code
- **Simple Mode** from Share Sheet — Send to PC, Copy Text, Share with Someone, Done
- **Send to PC** — lands in desktop Mobile Inbox with receipt proof
- Read-only vault browse on port **8742**

This APK is a **debug/internal proof artifact**, not a signed production release.

## Honest limitations

- No cloud sync
- Safes are not encrypted
- Image/file send from Share Sheet — deferred
- Sensitive warn-before-send — deferred/planned

## What changed since v0.1.3-rc3

| Area | Change |
|------|--------|
| Desktop | Luxury UI + Mobile Inbox receiver |
| Mobile bridge | Inbox send API + receipts |
| Android | Share Sheet Simple Mode + Manual Setup pairing fix |
| Version | `0.1.3-rc4` (RC only — not final) |

## Artifacts (this RC)

- `CacheVault-v0.1.3-rc4-windows.zip`
- `CacheVault-Mobile-v0.1.3-rc4-debug.apk`
- `SHA256SUMS.txt`
- `docs/releases/v0.1.3-rc4.md`

## Explicit non-actions

- **No** git tag unless explicitly approved after proof
- **No** GitHub release publish
- **No** final release claim
- **No** modification of shipped v0.1.2 or v0.1.3-rc3 artifacts
- Root `README.md` and `RELEASE_NOTES.md` remain **v0.1.2** (shipped desktop truth)
