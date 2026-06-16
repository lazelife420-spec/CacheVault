# Cache Vault Mobile (Android MVP)

**Cache Vault Mobile** — A Proof Foundry companion app.

Paired read-only client for the desktop Cache Vault mobile bridge. No cloud sync.

## Build

```powershell
cd android
.\gradlew.bat test assembleDebug
```

Requires Android SDK (`ANDROID_HOME` or default `%LOCALAPPDATA%\Android\Sdk`) and JDK 17+.

## Pairing

1. On PC: Settings → Mobile Access → Enable → Pair Android Device
2. Note PC LAN IP, port (default 8742), device id, and token
3. On Android: enter credentials on the Pair screen

## Manual smoke checklist

- [ ] Bridge OFF → app cannot connect (503)
- [ ] Unpaired token → rejected (401)
- [ ] Revoked device → rejected
- [ ] Paired → browse All / Favorites / Collections / Recently Removed
- [ ] Search returns clips
- [ ] Clip detail shows full content (including sensitive after explicit open)
- [ ] Copy places text on Android clipboard; PC writes copy receipt
- [ ] Share opens Android share sheet; PC writes share receipt
- [ ] No delete/edit UI
- [ ] Disconnect clears pairing secrets
