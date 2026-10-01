# Cache Vault Mobile — Threat Model

Proof Foundry standard: **proof-first, user-control-first, local-first, no fake claims.**

## Product boundary

```text
Desktop Cache Vault = desktop vault (source of truth for PC content)
Android phone vault  = independent local-first vault on this device
Bridge               = optional LAN companion surface (read-only-first)
Receipts             = proof layer for bridge requests only
```

**CV-MOBILE-1 (2026-09-24):** The Android app is no longer companion-only. It
keeps a **phone-local vault** in app-private storage: items, Safes, favorites,
removals and a local activity ledger that never touch the bridge, pairing
credentials, or any network. Local Safes are organizers, not encryption
containers; the activity ledger is not signed; local item ids never denote
desktop clips. Pairing remains optional and unchanged; the desktop transport
and authentication model were not modified. Known bridge-trust concerns
(token/host trust, QR payload validation, transport authentication,
exactly-once/deduplication, lost-ack retry, remote image prefetch) remain
recorded and unresolved — this tranche neither expanded nor weakened them.

Cache Vault Mobile is **not** cloud sync, account login, or a remote file manager. It performs **no background clipboard reads**: the clipboard is read only when the user taps a save notification / action, or when an app activity gains window focus. Clipboard-change *monitoring* exists solely to post that notification; it never reads content while unfocused. Screenshots import automatically only while the user has capture enabled. All captured content stays in the phone-local vault — no bridge, no network, no cloud. Decision record: [review/CV-MOBILE-CAPTURE-TM-20260930/THREAT_MODEL_AMENDMENT.md](../review/CV-MOBILE-CAPTURE-TM-20260930/THREAT_MODEL_AMENDMENT.md).

## Assets to protect

| Asset | Owner |
|-------|-------|
| Full clip content (PC vault) | User PC vault |
| Phone-local items/assets (CV-MOBILE-1) | User's phone — app-private storage only |
| Local activity ledger | User's phone — no payloads/tokens/image bytes |
| Pairing tokens | User (shown once on pair) |
| Mobile Access Receipts | User PC (local audit) |
| Sensitive clip text | User — masked in list/search |

## Threats and mitigations

| Threat | Mitigation |
|--------|------------|
| Random LAN device reads clips | Mobile Access **OFF** by default; pairing + bearer token required |
| Stolen pairing token | Token shown once; stored as hash on PC; revoke device; encrypted storage on Android |
| Revoked phone still accesses | `revoked_at` checked on every request → `401` |
| Bridge exposed when disabled | No listener when disabled; `503` on requests |
| List/search leaks sensitive full content | Mask sensitive content in list/search; full text only on explicit detail |
| Receipts leak secrets | No plaintext tokens, full clip bodies, or image bytes in receipts |
| Android logs leak content/tokens | No clip content or bearer headers in logs |
| Fake “connected” UI | Android shows connected only after status + auth both succeed |
| Future endpoints mutate vault | API contract default `mutation: no`; review gate for any new route |
| Firewall / wrong IP confusion | Plain-language errors; docs: LAN IP not localhost |
| Bulk vault exfiltration | No bulk asset dump; future pagination limits (100 default, 500 max) |
| Capture saves a password to the phone vault | Sensitive detection + masking on reveal; sensitive auto-block toggle (desktop parity, default ON); vault lock pauses capture when locked |
| Capture runs without the user knowing | Toggles in Settings; persistent "Vault capture is on" notification with Stop action; capture defaults documented in the release notes |
| Screenshot import pulls existing photos | Watermark seeded on first enable; only rows newer than the watermark import |
| Captured content leaves the phone | Capture writes only to the phone-local vault; no network involvement; ledger records source labels, never payloads |
| Copies made while the process is dead | On-open focus drain catches them; the alert may be late but nothing is lost silently |

## Pairing lifecycle

```text
Unpaired
  → Pairing generated on PC
  → Phone connects with credentials
  → Paired / Active
  → Revoked (PC) or Disconnect (phone clears local secrets only)
  → Rejected until re-paired
```

Desktop paired-device record: `device_id`, `device_name`, `created_at`, `last_seen_at`, `revoked_at`, `token_hash` (optional `app_version`, `platform`, `protocol`, `device_model`, `build`).

**Never** store plaintext tokens in desktop settings.

## Android permissions

| Permission | When |
|------------|------|
| Internet | Bridge connection |
| Wi‑Fi multicast | LAN discovery |
| Camera | **Only** when QR scan is implemented |
| Storage/media | **Only** for explicit Save to Phone when required |
| Foreground service (dataSync) | Capture watch and bridge connection service |
| Post notifications | Capture and connection alerts (Android 13+) |
| Receive boot completed | Re-arm capture only if the user left it enabled |
| Read media images (+ visual user-selected, Android 14+) | Screenshot import only |
| Use biometric | Vault Lock unlock on this phone |

**Not allowed:** background clipboard reads, accessibility scraping, notification listener scraping.

## Screenshot / image rules

- List/search: metadata / path / thumbnail only
- Full asset: selected clip detail only, paired non-revoked device; `GET /mobile/v1/clips/{id}/asset` returns bytes (desktop stores PNG under `%LOCALAPPDATA%/CacheVault/assets/`)
- Save / share: explicit user tap
- No bulk image download or silent image library cache
- Receipts for asset view / share / save — no image contents in receipts

## Logging rules

**Do not log:** full clip content, tokens, bearer headers, image bytes, Wi‑Fi SSID.

**May log:** route, status code, action, clip id, device id, result, timestamp.

## Phone-side capture rules

- Capture destinations: phone-local vault only, Default Safe, source labels `clipboard` / `clipboard_image` / `screenshot`.
- Locked vault: clipboard capture is skipped with a truthful toast; screenshot import is deferred (watermark not advanced) — nothing lost, nothing imported.
- Automatic capture refuses sensitive-looking clips while the sensitive auto-block is on (desktop parity, default ON). Manual save paths are unaffected.
- No clip content in logs; failure reasons only; sensitive titles are redacted in the ledger.
- Own copies are echo-suppressed (30 s) and content is deduped by signature and active-item hash.
- Enabling screenshot capture never bulk-imports existing history.
- Manual paths (Add-sheet paste, share sheet) work regardless of capture toggles.

## Duplicate Review (desktop-first)

Mobile may **view** duplicate groups later. Mutation (keep one, move extras to Recently Removed) stays on desktop with Stamped Receipt. No silent permanent delete.

## Release gate

No public release tag until desktop pytest, Android build, and **real phone smoke** pass. See [android/README.md](../android/README.md).
