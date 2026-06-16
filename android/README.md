# Cache Vault Mobile (Android MVP)

**Cache Vault Mobile** — A Proof Foundry companion app.

Paired read-only client for the desktop Cache Vault mobile bridge. No cloud sync.

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

1. Merge `android/cache-vault-mobile-mvp`
2. Then start `feature/cache-vault-mobile-qr-pairing` (not before)
