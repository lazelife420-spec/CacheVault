# Cache Vault Mobile API Contract

Base path: `/mobile/v1`  
Transport: HTTP on LAN (cleartext; local network only)  
Auth: `X-Device-Id` + `Authorization: Bearer <pairing-token>`

See also: [MOBILE_THREAT_MODEL.md](MOBILE_THREAT_MODEL.md), [MOBILE_ANDROID_DIRECTION.md](MOBILE_ANDROID_DIRECTION.md)

## Version

| Field | Value |
|-------|-------|
| Contract version | 1 |
| `mobile_api_version` (status) | `"1"` |

Android clients must reject unsupported `mobile_api_version` values.

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

```json
{
  "product": "Cache Vault",
  "byline": "A Proof Foundry companion app",
  "mobile_api_version": "1",
  "mobile_access_enabled": true,
  "cache_vault_version": "0.1.x",
  "device_id": "<paired-device-id>",
  "read_only": true
}
```

Errors: `503 mobile_access_disabled`, `401 unauthorized`

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
| MVP allowed | **yes** (returns `404 asset_not_available` until desktop stores binaries) |
| Receipt action | `get_asset` |
| Scope | **one clip id only** — no bulk |

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
