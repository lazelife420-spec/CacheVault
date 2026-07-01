# Cache Vault Mobile Pairing: QR Flow Plan

Date: 2026-07-01
Scope: v0.1.5-rc2 stabilization/design lane (planning only)

## 1. Confirmed current state (do not assume beyond this)

Desktop (`cache_vault/core/mobile/`):
- `bridge.py` `pair_device(device_id, device_name)` generates a token with
  `secrets.token_urlsafe(32)`, stores only `token_hash` (SHA-256), and returns
  the plaintext token exactly once.
- Tokens never expire and are trusted immediately; there is no "PC approves the
  phone" handshake today. The token itself is the credential.
- Auth is header based: `X-Device-Id` + `Authorization: Bearer <token>`.
- `discovery.py` advertises `_cachevault._tcp` over mDNS (product + pc_name +
  port). No token is ever placed in mDNS.
- Revoke exists: `revoke_device`, `revoke_all_active`. Bridge is read-only.
- Default port 8742, cleartext HTTP on the LAN.

Desktop pairing dialog (`cache_vault/ui/mobile_dialogs.py` `PairAndroidDialog`):
- "Generate Fresh Pairing Code" shows host/port/device_id/token as text.
- Token is hidden by default (Show Token toggle); label already says
  "QR pairing is coming next."

Android app (`android/`, package `com.prooffoundry.cachevaultmobile`):
- Real, buildable Kotlin + Jetpack Compose app (minSdk 26, versionName
  0.1.3-rc5). Not a stub.
- Pairing today = manual entry of host/port/device_id/token
  (`ManualSetupScreen.kt`), stored encrypted (`PairingStore.kt`,
  EncryptedSharedPreferences). Sends `X-Device-Id` + `Bearer` headers
  (`BridgeClient.kt`).
- mDNS discovery via `NsdManager` on `_cachevault._tcp` pre-fills host/port only
  (`PcDiscovery.kt`); it does not complete pairing.
- `QrScanScreen.kt` is a **placeholder** ("QR pairing is coming next. Use Manual
  Setup for this MVP."). No camera library (no CameraX / ML Kit / ZXing), no
  `CAMERA` permission in the manifest.

### Confirmed constraint (blocks implementation)

**The phone cannot scan a QR code today.** Per the directive "do not implement QR
pairing until the current phone app capabilities are confirmed": the Android app
has no scanner, no barcode dependency, and no camera permission. QR pairing
therefore cannot ship desktop-only; it requires paired Android work. This plan is
design-only and must not be coded into rc2 pairing until the Android scanner
exists.

## 2. Target product flow

```
PC: click "Pair Phone"        -> opens modal with a QR code
Phone: tap "Scan PC Code"     -> camera scans QR
Phone: connects using payload -> calls pairing endpoint on PC
PC: "Allow this phone?"       -> user confirms
PC: issues durable device token, phone stores it
Done.
```

Manual host/token entry stays as an Advanced / Manual Setup fallback.

## 3. QR payload schema

The QR encodes a short-lived pairing offer, not the durable credential:

```json
{
  "app": "cache-vault",
  "version": 1,
  "host": "192.168.0.11",
  "port": 8742,
  "device_id": "desktop-device-id",
  "pair_token": "one-time-token",
  "expires_at": "2026-07-01T12:34:56Z"
}
```

Notes:
- `pair_token` is a one-time, short-lived enrollment token (not the durable
  device bearer token). It is exchanged once for the durable token.
- `host`/`port` reuse the existing recommended LAN IP logic
  (`recommended_lan_ipv4`) and `DEFAULT_MOBILE_PORT`.
- `device_id` here identifies the desktop offer; the phone still gets its own
  paired `device_id` on approval.

## 4. Protocol change required (honest gap)

Today the durable token is minted and shown immediately (`pair_device`), and any
holder of it is trusted. The target flow adds a two-step enrollment that does not
exist yet:

1. Desktop mints a one-time `pair_token` with an expiry, renders it in the QR,
   and starts listening for one enrollment attempt.
2. Phone POSTs to a new enrollment endpoint (e.g. `POST /mobile/v1/pair`) with
   `pair_token` + its device name/platform.
3. Desktop shows "Allow this phone?" (name, platform, LAN IP). On approve, it
   calls the existing `pair_device` path to mint the durable token and returns it
   to the phone once. On deny or expiry, the `pair_token` is burned.

This requires: a new bridge endpoint, one-time/expiring token storage, a desktop
approval dialog, and a matching Android enrollment call. None of this is in rc2
scope to implement; it is the design target for a later lane.

## 5. Security rules

- `pair_token` is one-time and short-lived (recommend 5 minutes / single use).
- The QR expires (`expires_at`); expired offers are rejected.
- Desktop still asks the user to approve the phone before trusting it.
- The durable bearer token is never placed in the QR or mDNS; only the
  short-lived `pair_token` is.
- Manual token remains hidden by default (already true in the dialog).
- Screenshot-safe mode: hide token and QR automatically so public screenshots
  cannot leak a live credential (see UI note below).
- "Revoke All Devices" / "Revoke Old Phone + Fresh Pair" stays available
  (already implemented via `revoke_all_active`).

## 6. Desktop UI direction

- One primary button: "Pair Phone" opens a clean modal.
- Modal shows: numbered steps, the QR image, "This code expires in 5 minutes",
  and a collapsed "Manual setup" section (host, port, pairing code hidden by
  default) as fallback.
- Add a "Screenshot-safe" toggle (or auto-detect) that blurs/hides the QR and
  token region so soak screenshots are safe to share.
- Reuse existing tokens: primary_button / secondary_button, `vault_card`, page
  title size 24, section header size 11 bold uppercase (match Settings Hub).

## 7. Phased implementation (later lanes, not rc2)

1. Desktop QR rendering of the current manual payload (no protocol change) as a
   convenience, plus screenshot-safe hiding. Low risk, desktop-only.
2. Android: add CameraX + a barcode library, `CAMERA` permission + runtime
   request, real scanner UI, and a payload parser into `PairingStore`.
3. One-time/expiring `pair_token` + `POST /mobile/v1/pair` enrollment endpoint +
   "Allow this phone?" approval dialog.
4. Deprecate manual entry to Advanced-only once QR is proven.

## 8. Do NOT do in rc2

- Do not ship QR pairing end to end (phone cannot scan yet).
- Do not invent Android scanning behavior.
- Do not change the auth header contract or break manual setup.
- Do not weaken revoke or expose the durable token in any transport.
