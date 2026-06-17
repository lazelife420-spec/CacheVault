# Cache Vault v0.1.3-rc5 (release candidate)

**Status:** Release candidate — not a final release. **No git tag.** Do not replace the shipped **v0.1.2** desktop release.

## RC5 = RC4 + pairing hot-reload

```text
RC4 + no-restart pairing hot-reload
```

### Desktop (Windows exe in this zip)

Everything in **v0.1.3-rc4**, plus:

- **No-restart pairing** — after Pair Android Device in Settings, the bridge accepts the new token immediately (no CacheVault.exe restart)

RC4 desktop scope still included:

- **Luxury vault UI** — graphite palette, custody language, Command Center polish
- **Mobile Inbox** — receive items sent from a paired Android phone
- **Send-to-PC endpoint** — `POST /mobile/v1/inbox/send` with receipt stamping
- **First-use guide** — Welcome briefing; tooltips for receipts, Safes, Mobile Inbox, exports
- Vault Macros live execution (hotkeys, text shortcuts, picker) from rc3

**Safes are not encrypted.** Whole-Safe export UI is deferred.

**No cloud sync** — mobile companion uses a paired local Wi-Fi bridge only.

### Mobile companion (Android debug APK — separate artifact)

Install `CacheVault-Mobile-v0.1.3-rc5-debug.apk` from the same RC folder. It is **not** inside the Windows zip.

Requires **Mobile Access ON** on the PC:

- **Manual Setup** — enter PC address, bridge port, device ID, pairing code
- **Simple Mode** from Share Sheet — Send to PC, Copy Text, Share with Someone, Done
- **Send to PC** — lands in desktop Mobile Inbox with receipt proof
- Read-only vault browse on port **8742**

Pair from desktop Settings, enter credentials on phone — **no desktop restart required**.

This APK is a **debug/internal proof artifact**, not a signed production release.

## Honest limitations

- No cloud sync
- Safes are not encrypted
- Image/file send from Share Sheet — deferred
- Sensitive warn-before-send — deferred/planned

## What changed since v0.1.3-rc4

| Area | Change |
|------|--------|
| Desktop bridge | Hot-reload paired credentials before auth |
| Usability | Removes restart-after-pairing trap |
| Version | `0.1.3-rc5` (RC only — not final) |

## Artifacts (this RC)

- `CacheVault-v0.1.3-rc5-windows.zip`
- `CacheVault-Mobile-v0.1.3-rc5-debug.apk`
- `SHA256SUMS.txt`
- `docs/releases/v0.1.3-rc5.md`

## Explicit non-actions

- **No** git tag unless explicitly approved after proof
- **No** GitHub release publish
- **No** final release claim
- **No** modification of shipped v0.1.2, v0.1.3-rc3, or **v0.1.3-rc4** artifacts
- Root `README.md` and `RELEASE_NOTES.md` remain **v0.1.2** (shipped desktop truth)
