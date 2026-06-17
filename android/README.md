# Cache Vault Mobile (Android MVP)

**Cache Vault Mobile** — A Proof Foundry companion app.

Paired read-only client for the desktop Cache Vault mobile bridge. No cloud sync.

## MVP honesty (read this first)

| Lane | Status |
|------|--------|
| Text / link / code | Near MVP — real-device smoke can prove this loop |
| Screenshots / images | **Implemented on `feature/cache-vault-screenshot-assets`** — View loads `/asset` on tap; Share/Save are explicit; **not proven** until smoke |

Do **not** claim public mobile MVP is done until **real-device smoke** proves screenshot open/share/save with receipts (plus text/link/code).

**MVP done** only when text, links, code, **and screenshots** work end-to-end with receipts on a real phone.

Branch: `feature/cache-vault-screenshot-assets` (from `feature/cache-vault-mobile-easy-connect-assets`) — **keep unmerged** until smoke PASS per [MOBILE_ANDROID_DIRECTION.md](../docs/MOBILE_ANDROID_DIRECTION.md).

## Onboarding (Easy Connect)

First launch shows:

- **Connect to My PC** (primary)
- Scan QR Code (placeholder — Manual Setup fallback)
- Find PC on this Wi-Fi (mDNS `_cachevault-mobile._tcp`)
- Manual Setup (always available)

The app opens Wi-Fi Settings for you; it cannot join Wi-Fi silently.

## Merge gate (required before merge)

Branch `android/cache-vault-mobile-mvp` merges **only** after real-device smoke **PASS** on an actual Android phone. No release tag.

Do **not** merge on emulator-only or JVM tests alone.

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

## Pairing

1. Phone and PC on the **same Wi‑Fi** (not guest/isolated VLAN)
2. Android app → enter PC **LAN IP**, port, device id, token
3. Tap **Pair with PC**

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
- [ ] No delete / edit / permanent-remove UI
- [ ] No background clipboard monitoring
- [ ] No cloud claim in app

## After smoke PASS

1. Merge `android/cache-vault-mobile-mvp` (or current feature branch)
2. Then start `feature/cache-vault-mobile-qr-pairing` (not before)

## Guardrails (Proof Foundry)

- **No cloud sync.** Local-first companion only.
- **No background clipboard monitoring.** No camera permission until QR scan ships.
- **No destructive mobile actions** (delete, edit, restore, prune).
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
| Not paired | Welcome / Connect to My PC |
| PC offline | Cannot reach your PC… |
| Bridge disabled | Mobile Access is off… |
| Auth failed | Pairing failed… |
| Revoked | Device revoked… |
| Connected | Home + Paired · Active in Settings |

MVP does not cache vault content offline.

## Permissions policy

| Permission | When requested |
|------------|----------------|
| Internet | Always (bridge) |
| Wi‑Fi multicast | LAN discovery |
| Camera | **Only** when QR scanner is implemented |
| Storage | **Only** for explicit Save to Phone when required |

No permissions requested "just in case."
