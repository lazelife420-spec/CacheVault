# Cache Vault Mobile — Threat Model

Proof Foundry standard: **proof-first, user-control-first, local-first, no fake claims.**

## Product boundary

```text
Desktop Cache Vault = source of truth
Android = paired companion (viewer / search / copy / share)
Bridge = local, gated, read-only-first
Receipts = proof layer
```

Cache Vault Mobile is **not** cloud sync, account login, background clipboard scraping, or a remote file manager.

## Assets to protect

| Asset | Owner |
|-------|-------|
| Full clip content | User PC vault |
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

## Pairing lifecycle

```text
Unpaired
  → Pairing generated on PC
  → Phone connects with credentials
  → Paired / Active
  → Revoked (PC) or Disconnect (phone clears local secrets only)
  → Rejected until re-paired
```

Desktop paired-device record: `device_id`, `device_name`, `created_at`, `last_seen_at`, `revoked_at`, `token_hash` (optional `app_version`, `platform`).

**Never** store plaintext tokens in desktop settings.

## Android permissions

| Permission | When |
|------------|------|
| Internet | Bridge connection |
| Wi‑Fi multicast | LAN discovery |
| Camera | **Only** when QR scan is implemented |
| Storage/media | **Only** for explicit Save to Phone when required |

**Not allowed:** clipboard monitoring, accessibility scraping, notification listener scraping.

## Screenshot / image rules

- List/search: metadata / path / thumbnail only
- Full asset: selected clip detail only, paired non-revoked device; `GET /mobile/v1/clips/{id}/asset` returns bytes (desktop stores PNG under `%LOCALAPPDATA%/CacheVault/assets/`)
- Save / share: explicit user tap
- No bulk image download or silent image library cache
- Receipts for asset view / share / save — no image contents in receipts

## Logging rules

**Do not log:** full clip content, tokens, bearer headers, image bytes, Wi‑Fi SSID.

**May log:** route, status code, action, clip id, device id, result, timestamp.

## Duplicate Review (desktop-first)

Mobile may **view** duplicate groups later. Mutation (keep one, move extras to Recently Removed) stays on desktop with Stamped Receipt. No silent permanent delete.

## Release gate

No public release tag until desktop pytest, Android build, and **real phone smoke** pass. See [android/README.md](../android/README.md).
