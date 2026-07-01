# Cache Vault Android Reconnect Device QA

Date: 2026-07-01

## Candidate

- Claim allowed: `Android reconnect lifecycle implemented; device QA pending.`
- Claim not allowed: `Android reconnect is fixed.`
- Claim not allowed: `Phone can be woken when app is killed.`
- Claim not allowed: `Background connection is guaranteed.`

## Build under test

- APK path: `C:\Users\KickA\Desktop\CacheVault\android\app\build\outputs\apk\debug\app-debug.apk`
- APK SHA256: `62FC51F9B5CD213F4D9572BFA0FB7CF975269164580A15FDF77BA97AE35B48D4`
- Android app version: `0.1.3-rc6`
- Desktop version: `0.1.5-rc4`
- Desktop commit: `b82348fca44f25b984f640cdc18bada0a6238a8c`
- Git branch: `verify/v0.1.5-rc4-ui-consistency`

## Device under test

- Device model: `SM-S911W`
- Android version: `16`
- Android SDK: `36`

## Test network

- Not yet recorded in this session.
- Manual QA should note the actual Wi-Fi/LAN used for pairing and reconnect checks.

## Proven in this session

| Check | Result | Notes |
| --- | --- | --- |
| APK assembled | PASS | `assembleDebug` completed successfully. |
| APK SHA256 recorded | PASS | Matches the candidate hash above. |
| Device detected by `adb` | PASS | `adb devices` showed one attached device. |
| APK installed on real Android device | PASS | `adb install -r` returned `Success`. |
| Launch command sent to device | PASS | `adb shell monkey -p com.prooffoundry.cachevaultmobile ...` completed. |

## Manual lifecycle QA

| Checklist item | Result | Notes |
| --- | --- | --- |
| 1. Fresh install / first launch honest disconnected state | PENDING | Needs human visual verification on device. |
| 2. Pairing stores trusted PC / desktop records phone / UI shows metadata | PENDING | Needs live desktop + phone interaction. |
| 3. Reconnect after app close/reopen with approval prompt | PENDING | Needs human interaction and desktop observation. |
| 4. `Not now` path stays paired but offline | PENDING | Needs human interaction and desktop observation. |
| 5. Optional silent auto-connect only after explicit consent | PENDING | Needs repeated close/reopen testing. |
| 6. `Keep connected in background` foreground notification and honest stop flow | PENDING | Needs backgrounding and notification interaction. |
| 7. Killed-app limitation remains honest | PENDING | Needs force stop / swipe-away behavior verification. |
| 8. Revoke rejects old token and requires fresh re-pair | PENDING | Needs desktop revoke flow plus phone retry. |
| 9. Desktop labels show waiting / online / offline / revoked / last seen | PENDING | Needs desktop screenshots during each state. |
| 10. Regression: send-to-PC / mobile inbox still works and no crash | PENDING | Needs live end-to-end check. |

## Screenshots captured

- None yet in this session.
- Required before PASS:
  - Android remembered PC screen
  - Android approval prompt
  - Android connected state
  - Android foreground notification
  - Android revoked / re-pair-needed state
  - Desktop waiting state
  - Desktop online state
  - Desktop offline state
  - Desktop revoked state

## Log capture

- No `adb logcat` error excerpt captured yet.
- If any failure occurs during manual QA, capture a focused log excerpt around the failing step.

## Known caveats

- Real reconnect reliability is not proven by unit tests or install success.
- A fully killed Android app still cannot be claimed wakeable by the PC without an explicit wake mechanism.
- Background service behavior is implemented, but not yet proven under real OS lifecycle pressure on this device.

## Verdict

- Final verdict: `HOLD`
- Reason: installability is proven, but interactive Android lifecycle QA is still pending.
