# Cache Vault Mobile — Android Direction

> **A Proof Foundry companion app** — proof-first, local-first access to your PC vault.
>
> **Android MVP** lives in `android/`. Desktop mobile bridge is on `master`.
> This document remains the canonical product + API direction.

## Product

| | |
|---|---|
| **Name** | Cache Vault Mobile |
| **Byline** | A Proof Foundry companion app |
| **Desktop product** | Cache Vault™ (source of truth) |
| **Studio** | The Proof Foundry™ |
| **Promise** | Saved on your PC. Ready on your phone. Keep the receipt. |

## Related docs

| Document | Scope |
|----------|-------|
| [MOBILE_API_CONTRACT.md](MOBILE_API_CONTRACT.md) | Endpoint contract, auth, mutation rules |
| [MOBILE_THREAT_MODEL.md](MOBILE_THREAT_MODEL.md) | Threats, mitigations, permissions, logging |
| [../android/README.md](../android/README.md) | Build, smoke gate, LAN/firewall help |

## Positioning

Copy/paste apps usually fail in one of four ways: unreliable sync, ugly UX,
cloud-sketchy backends, or indifference to user control. Cache Vault Mobile is
the opposite — a **local-first, proof-first companion** paired to the user's
own PC vault.

- **No fake sync.** No hidden cloud.
- **Local-first companion access** — the phone reads from the user's machine, not
  a vendor server.
- **Proof-first** — every mobile action leaves a receipt on the PC.

## Core idea

Let a **paired Android phone** access saved clips from the user's **PC Cache Vault**.

```
┌─────────────────────┐         LAN / local         ┌─────────────────────┐
│  Cache Vault™ (PC)  │ ◄──── paired, read-only ───►│  Cache Vault Mobile │
│  source of truth    │         API + receipts      │  (Android)          │
└─────────────────────┘                             └─────────────────────┘
```

## MVP direction

### Roles

| Layer | Role |
|-------|------|
| **PC (desktop)** | Source of truth. Captures, organizes, prunes, exports. Hosts read-only Mobile Access API when explicitly enabled. Writes mobile access receipts. |
| **Android** | Companion viewer / search / copy / share client. Never mutates the vault in MVP. |

### Mobile Access policy

- **Mobile Access is OFF by default** on desktop.
- User enables **Mobile Access** manually in Settings.
- Android pairs using a **QR code** shown on desktop.
- **Only paired devices** can connect.
- Unpaired or revoked devices are rejected.

### Android browse (read)

| Section | Access |
|---------|--------|
| All Clips | Browse + search |
| Favorites | Browse + search |
| Collections | Browse + search |
| Recently Removed | **Read-only** browse + search |

### Android actions (MVP)

| Action | Notes |
|--------|-------|
| Search clips | Same conceptual scope as desktop sidebar + search |
| Open clip detail | Preview + metadata |
| Copy to Android clipboard | Selected clip content |
| Share via Android share sheet | Selected clip content |

### PC mobile access receipts

For **each mobile action**, the desktop writes a **mobile access receipt**:

| Field | Description |
|-------|-------------|
| Timestamp | UTC ISO-8601 |
| Paired device id | Stable device identifier from pairing |
| Paired device name | User-visible label (e.g. "Pixel 8") |
| Action | e.g. `list_clips`, `get_clip`, `copy`, `share`, `search` |
| Clip id | When applicable |
| Result | e.g. `ok`, `not_found`, `denied` |

Receipts are local proof — same doctrine as **Stamped Receipts** on desktop.
No fake hashes, no fabricated verification status.

## Deferred (explicitly out of MVP)

| Feature | Reason deferred |
|---------|-----------------|
| Cloud sync | Violates local-first; not needed for LAN companion |
| Account system | No accounts on desktop today |
| iOS | Android first |
| Remote permanent delete | Destructive; desktop-only for MVP |
| Remote vault editing | PC is source of truth; read-only API first |
| Background phone clipboard monitoring | Scope creep; not a phone clipboard app |
| Android-to-PC auto capture | PC captures; phone consumes |
| Push notifications | Not required for read-only companion |
| End-to-end encrypted relay | No relay in MVP; local network pairing |
| Import from mobile | Export direction exists on PC; import is separate |

## Desktop bridge concept (future)

Settings → **Mobile Access**

| Control | Purpose |
|---------|---------|
| Toggle: **Enable Mobile Access** | Master switch; API unavailable when OFF |
| Button: **Pair Android Device** | Opens QR pairing dialog |
| **Paired Devices** list | Name, paired date, last seen |
| **Revoke Device** | Immediately blocks that device |
| **View Mobile Access Receipts** | Audit log of mobile actions |

**Read-only API first** — no mutation endpoints in MVP.

## API sketch (read-only, MVP)

Base path: `/mobile/v1`  
Transport: local network (exact binding TBD — e.g. HTTPS on LAN with pairing token).

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/mobile/v1/status` | Server up, mobile access enabled, vault version |
| `GET` | `/mobile/v1/clips` | Paginated clip list (filters via query params) |
| `GET` | `/mobile/v1/clips/{id}` | Single clip detail |
| `GET` | `/mobile/v1/search?q=` | Search across browseable sections |
| `GET` | `/mobile/v1/collections` | Collection names + counts |
| `GET` | `/mobile/v1/favorites` | Favorite clips |
| `GET` | `/mobile/v1/recently-removed` | Recently Removed clips (read-only) |

### Endpoints that must **not** exist in MVP

- No `DELETE`
- No permanent-remove route
- No edit / mutate route
- No capture-from-mobile route

When Mobile Access is disabled, **no API is available** (listener off or requests
rejected).

## Pairing flow (conceptual)

1. User enables **Mobile Access** on desktop.
2. User taps **Pair Android Device** → desktop shows QR (pairing payload:
   host, port, one-time or rotating token, vault instance id).
3. Android app scans QR → stores pairing credentials locally.
4. Desktop adds device to **Paired Devices** list.
5. Android calls `GET /mobile/v1/status` to confirm.
6. User can **Revoke** any device from desktop; revoked devices fail auth
   immediately.

## Android UI sketch (future)

```
┌──────────────────────────────────────┐
│  Cache Vault Mobile                  │
│  A Proof Foundry companion app       │
├──────────────────────────────────────┤
│  [ Pair with PC ]  (first run)       │
│  [ Search........................ ]  │
├──────────────────────────────────────┤
│  All │ Favorites │ Collections │ Removed │
├──────────────────────────────────────┤
│  clip rows…                          │
├──────────────────────────────────────┤
│  Clip detail                         │
│  [ Copy ]  [ Share ]                 │
├──────────────────────────────────────┤
│  Settings                            │
│  Connected PC · Re-pair · Disconnect │
└──────────────────────────────────────┘
```

Branding on Android should match Proof Foundry palette and voice (see desktop
`cache_vault/brand.py`). Tagline: **Access your saved clips. Keep the receipt.**

## Future proof gates (must pass before ship)

| Gate | Requirement |
|------|-------------|
| Default OFF | Mobile Access disabled on fresh install |
| No API when disabled | Listener off or hard reject |
| Pairing required | Unpaired requests rejected |
| Read-only | Endpoints cannot mutate vault state |
| Receipts | Every mobile action logged on PC |
| No delete route | Permanent delete impossible via API |
| Sensitive clips | Policy TBD — likely masked or excluded from mobile API |
| File paths | Path clips export reference only; no remote file execution |

## Relationship to desktop docs

| Document | Scope |
|----------|-------|
| [FEATURE_DIRECTION.md](FEATURE_DIRECTION.md) | Desktop Cache Vault — implemented direction |
| **MOBILE_ANDROID_DIRECTION.md** (this file) | Android companion — future direction only |

Desktop behavior (storage, pruning, favorites, collections, exports, file safety)
is **unchanged** by this document.

## Implementation status

| Component | Status |
|-----------|--------|
| Android app | **MVP** (`android/` — Easy Connect, browse, copy, share) |
| Screenshot/image assets | **Gap** — desktop stores text only; `/asset` + UI placeholder ready |
| Desktop mobile server | **Bridge implemented** (read-only, OFF by default) |
| QR pairing UI | **Placeholder** (manual credentials; QR later) |
| Mobile access receipts | **Implemented** (`mobile_access_receipts.json`) |
| Release tag | **None** |

When implementation begins, start with desktop bridge + read-only API behind
Mobile Access OFF-by-default, then Android pair + browse + copy/share.
