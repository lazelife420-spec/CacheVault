# Cache Vault Mobile (Android)

**Cache Vault Mobile** — Cache Vault on the phone. A Proof Foundry companion app.

## CV-MOBILE-1 (2026-09-24) — local-first phone vault

This app is evolving from a paired companion into an **independent local-first
phone vault**. It now works before pairing, while the PC is offline, and after
process restart:

- **Phone-local vault**: text, links and single images saved on this device
  persist in app-private storage (`data/local/` → `SQLiteOpenHelper` schema v1
  + `local_assets/` file store). No PC or network required.
- **Local Safes** — named phone-side organizers (not encryption containers,
  not synced). Default Safe is protected.
- **Share target** — "Save on this phone" is the default destination; "Send to
  PC" remains a separate deliberate action when paired.
- **Add in-app** — paste text, type text, or pick one image.
- **Activity** — truthful local ledger of saves/copies/shares/failures on this
  phone (not signed receipts; no payloads).
- **Paired PC** tab — the existing companion surfaces (browse, images, proof,
  settings, pairing) live there, clearly remote ("On PC").

Debug/test builds install as `com.prooffoundry.cachevaultmobile.cvmobile1.debug`
so they cannot collide with the production app. The production applicationId,
version (0.2.1/8) and signing are unchanged.

## Companion (paired read-only client)

Paired read-only client for the desktop Cache Vault mobile bridge. No cloud sync.

## MVP honesty (read this first)

| Lane | Status |
|------|--------|
| Phone-local vault (text / link / code / single image) | Implemented — proven on emulator (real SQLite + UI flow); **physical-device smoke still required** |
| PC companion browsing (clips / search / images / receipts) | Implemented — real-device smoke still required |

Do **not** claim public mobile MVP is done until **real-device smoke** proves
the phone-local save/reuse loop **and** the paired companion flows on an actual
Android phone.

## Launch behavior

First launch opens the **local phone vault** — Add, search, Safes and Activity
work immediately. No pairing, PC, or network is required. Pairing is an
optional entry inside the **Paired PC** tab:

- **Set up pairing (guided)** — onboarding walk-through
- **Scan QR Code** — real CameraX + ML Kit scanner (implemented)
- **Find PC on this Wi-Fi** — mDNS `_cachevault._tcp`
- **Manual Setup** — always available

The app opens Wi-Fi Settings for you; it cannot join Wi-Fi silently.

## Merge / release gate

This working tree is **uncommitted** and unpublished. Do not merge, tag, or
release on emulator-only or JVM evidence alone — physical-device smoke is the
next gate for any release claim.

## Build & install

```powershell
cd android
.\gradlew.bat :app:assembleDebug
```

APK: `android/app/build/outputs/apk/debug/app-debug.apk`

Install (USB debugging):

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r app\build\outputs\apk\debug\app-debug.apk
```

Requires Android SDK, JDK 17+, and phone on same Wi‑Fi as PC.

## PC prep

1. Cache Vault → Settings → **Mobile Access** → **Enable**
2. **Pair Android Device** → generate credentials (device id + token)
3. PC LAN IP: `ipconfig` → Wi‑Fi IPv4 (not `localhost`)
4. Default port: **8742**
5. Allow Windows Firewall inbound on 8742 for private networks if prompted

## Pairing (optional — Paired PC tab)

1. Phone and PC on the **same Wi‑Fi** (not guest/isolated VLAN)
2. Android app → **Paired PC** tab → guided setup, QR scan, discovery, or enter PC **LAN IP**, port, device id, token
3. Tap **Pair with PC**

Pairing only unlocks remote browsing and Send to PC. Phone-local saving never needs it.

## Hard pass/fail smoke (real phone)

### Bridge OFF

- [ ] Android cannot connect
- [ ] Android shows clean failed/offline state
- [ ] PC does not expose clip data

### Bridge ON (paired)

- [ ] Connects using PC **LAN IP**, not localhost
- [ ] Status endpoint works
- [ ] All Clips loads **masked** previews
- [ ] Search works with **masked** previews
- [ ] Favorites loads
- [ ] Collections loads
- [ ] Recently Removed loads (read-only)

### Clip detail

- [ ] Valid paired device opens **full** clip content
- [ ] Copy puts full content on Android clipboard
- [ ] Share opens Android share sheet with full content

### Receipts (PC → View Mobile Access Receipts)

- [ ] List / search / detail writes receipts
- [ ] Copy / share writes receipts
- [ ] Rejected request writes receipt

### Security

- [ ] Wrong token → 401
- [ ] Revoked device → 401
- [ ] No delete / edit / permanent-remove UI against the **remote PC vault** (local reversible remove/restore is separate and allowed)
- [ ] No background clipboard monitoring
- [ ] No cloud claim in app

## Guardrails (Proof Foundry)

- **No cloud sync.** Local-first on both devices; the two vaults never auto-synchronize.
- **No background clipboard monitoring.** Camera permission is requested only for the QR pairing scanner.
- **Remote PC vault:** no destructive actions (delete, edit, restore, prune) — the bridge stays read-only-first.
- **Phone-local vault:** reversible removal → Recently Removed → restore is allowed; no permanent purge is exposed.
- **Plain-language errors** — see `UserMessages` in app source.
- **Logging:** never log clip content, tokens, or bearer headers.
- Full policy: [docs/MOBILE_THREAT_MODEL.md](../docs/MOBILE_THREAT_MODEL.md)

## LAN / firewall checklist

- [ ] Phone and PC on the **same Wi‑Fi** (not guest / isolated VLAN)
- [ ] Use PC **LAN IP** from `ipconfig` — **not** `localhost` or `127.0.0.1`
- [ ] Mobile Access **enabled** on PC
- [ ] Port **8742** allowed on Windows Firewall (private networks)
- [ ] Device **not revoked** on PC
- [ ] `pip install zeroconf` on PC if using **Find PC on this Wi‑Fi**

## Android offline / error states

| State | User sees |
|-------|-----------|
| Not paired | Local vault home (Vault tab) — pairing optional |
| PC offline | Local vault unaffected; Paired PC tab shows the connection state |
| Bridge disabled | Mobile Access is off… (Paired PC surfaces only) |
| Auth failed | Pairing failed… (Paired PC surfaces only) |
| Revoked | Device revoked… (Paired PC surfaces only) |
| Connected | Paired PC tab → remote vault browsing + sending |

The local vault does not depend on any bridge state. The desktop companion's
read-only remote browsing is unchanged — remote content is never inferred into
the local vault.

## Permissions policy

| Permission | When requested |
|------------|----------------|
| Internet | Only when pairing / bridge is used |
| Wi‑Fi multicast | LAN discovery (Paired PC tab) |
| Camera | QR pairing scanner only |
| Storage | Never — local vault uses app-private storage |

No permissions requested "just in case."
