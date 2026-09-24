# Cache Vault Mobile API Contract

Base path: `/mobile/v1`  
Transport: HTTP on LAN (cleartext; local network only)  
Auth: `X-Device-Id` + `Authorization: Bearer <pairing-token>`

See also: [MOBILE_THREAT_MODEL.md](MOBILE_THREAT_MODEL.md), [MOBILE_ANDROID_DIRECTION.md](MOBILE_ANDROID_DIRECTION.md)

> **CV-MOBILE-1 (2026-09-24):** This contract is **unchanged**. The new
> phone-local vault (`data/local/` — SQLite schema v1 + app-private
> `local_assets/`) does not use the bridge at all: local items, Safes,
> favorites and activity never travel over `/mobile/v1`, and no new endpoints
> exist. Pairing and every endpoint below still govern only the companion
> surfaces under the Paired PC tab.

## Version

| Field | Value |
|-------|-------|
| Contract version | 1 |
| `mobile_api_version` (status) | `"1"` |

Android clients must reject unsupported `mobile_api_version` values.

## Version compatibility handshake

Every client identifies itself with `app_version`, `build`, and `protocol`
(an integer) at pairing time, and may resend `X-App-Version` /
`X-App-Build` / `X-Protocol-Version` headers on later requests so an
already-paired phone's compatibility state updates on reconnect (e.g. after
the app is updated) without a full re-pair.

`protocol` is the hard compatibility gate — a device outside
`[server_protocol_min, server_protocol_max]` is rejected outright, on
**every** request, independent of token validity. A valid token does not
bypass this check, and this check does not bypass token authentication:
an invalid token still fails `401` even for an incompatible client. Missing
or unparsable `protocol` is treated conservatively as unsupported.

`app_version` is a softer signal layered on top once `protocol` is
acceptable: below `minimum_mobile_version` is also a hard rejection;
unparsable is accepted but flagged unknown.

Incompatible requests return **`426 Upgrade Required`** with a structured
body — never a generic `401`/`403`/`500`:

```json
{
  "error": "mobile_update_required",
  "compatible": false,
  "client_protocol": 0,
  "server_protocol_min": 1,
  "server_protocol_max": 1,
  "minimum_mobile_version": "0.1.0",
  "update_required": true,
  "message": "Update the CacheVault mobile companion to continue."
}
```

Compatible responses (pairing and `/status`) carry the same range fields so
the client can self-report its standing:

```json
{
  "compatible": true,
  "server_protocol_min": 1,
  "server_protocol_max": 1,
  "minimum_mobile_version": "0.1.0",
  "update_required": false
}
```

## Auth headers

| Header | Required | Notes |
|--------|----------|-------|
| `X-Device-Id` | Yes (except when bridge disabled) | Paired device id from desktop |
| `Authorization` | Yes | `Bearer <one-time pairing token>` |

Desktop stores **token hash only**. Receipts never log plaintext tokens.

## Global rules

| Rule | Value |
|------|-------|
| Default mutation | **no** |
| Mobile Access default | **OFF** |
| Listener when disabled | **none** |
| List/search content | **masked** (sensitive + bulk) |
| Detail content | **full** for paired, non-revoked, explicit open |
| Pagination (future) | `limit` default 100, max 500 |

## Endpoints

### `GET /mobile/v1/status`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `status` |

Response (200):

Example (illustrative — desktop version reflects whatever build is running):

```json
{
  "product": "Cache Vault",
  "byline": "A Proof Foundry companion app",
  "mobile_api_version": "1",
  "mobile_access_enabled": true,
  "cache_vault_version": "0.2.0",
  "device_id": "<paired-device-id>",
  "read_only": true
}
```

Errors: `503 mobile_access_disabled`, `401 unauthorized`, `426 mobile_update_required` (see [Version compatibility handshake](#version-compatibility-handshake))

---

### `POST /mobile/v1/pair-device`

| | |
|---|---|
| Auth required | No (this is how a device first obtains a token) |
| Mutation | Registers a paired device record |
| MVP allowed | **yes** |
| Receipt action | `pair_device` |

Request body (illustrative — `app_version`/`build` reflect whatever companion
build is actually pairing; any client at or above `minimum_mobile_version`
is accepted, not only the latest):

```json
{
  "client": "cachevault-android",
  "device_id": "optional-existing-id",
  "device_name": "Galaxy S23",
  "app_version": "0.2.0",
  "build": 7,
  "protocol": 1,
  "platform": "android",
  "device": {"name": "Galaxy S23", "model": "SM-S911W"}
}
```

Response (200) on success carries `device_id`, `device_name`, `token` (shown
once) plus the compatibility fields above. An incompatible handshake returns
`426` (see above) and **does not** issue a token or store a device record.

---

### `GET /mobile/v1/clips`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `list_clips` |
| Content in list | preview + masked `content` |

Future query params: `limit`, `offset`/`cursor`, `sort`, `filter`

---

### `GET /mobile/v1/clips/{id}`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `get_clip` |
| Content | **full** text for valid paired device |

---

### `GET /mobile/v1/clips/{id}/asset`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `get_asset` |
| Scope | **one clip id only** — no bulk |
| Response | `200` with `Content-Type: image/png` (or stored mime) and raw bytes; `404 asset_not_available` for non-image or missing file |
| **Honest status** | Implemented on `feature/cache-vault-screenshot-assets`; treat as **functional only after** desktop pytest + Android build + **real-device smoke** pass |

---

### `GET /mobile/v1/search?q=`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `search` |
| Content | masked previews only |

---

### `GET /mobile/v1/collections`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `list_collections` |

---

### `GET /mobile/v1/favorites`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `list_favorites` |

---

### `GET /mobile/v1/recently-removed`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `list_recently_removed` |
| Notes | Read-only browse; no restore/delete from mobile |

---

### `POST /mobile/v1/clips/{id}/copy`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `copy` |
| Notes | Receipt-only; Android performs clipboard copy locally |

---

### `POST /mobile/v1/clips/{id}/share`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `share` |
| Notes | Receipt-only; Android opens share sheet locally |

---

### `POST /mobile/v1/clips/{id}/save`

| | |
|---|---|
| Auth required | Yes |
| Mutation | **no** |
| MVP allowed | **yes** |
| Receipt action | `save` |
| Notes | Receipt-only; explicit user “Save to Phone” on Android |

## Forbidden (must not exist in MVP)

| Pattern | Status |
|---------|--------|
| `DELETE *` | **not allowed** |
| `PUT *` / `PATCH *` | **not allowed** |
| delete / edit / restore / permanent-remove routes | **not allowed** |
| capture-from-mobile | **not allowed** |
| cloud / account / sync endpoints | **not allowed** |
| bulk vault export / file-copy from PC | **not allowed** |

Non-GET methods on read routes return `405 method_not_allowed`.

## Receipt fields

Every accepted or rejected mobile request writes a **Mobile Access Receipt**:

`timestamp`, `device_id`, `device_name`, `action`, `route`, `clip_id`, `result`, `reason`

Receipts must **not** include: plaintext tokens, full clip content, image bytes, Wi‑Fi SSID.

## LAN discovery (optional)

Service type: `_cachevault-mobile._tcp`  
Advertised when Mobile Access is enabled. Does not replace pairing.
