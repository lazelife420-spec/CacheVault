# Cache Vault Android Reconnect APK RC Gate — 2026-07-02

## Decision

`APK_RC_CANDIDATE`

- Type: internal/debug QA APK candidate, not a public release.
- Public publish: NO
- `/proof` update: NO
- Merge into desktop `rc4`/`rc5`: NOT YET
- Tag: NO
- Stable/release claim: NO

## Artifact

- APK path: `android/app/build/outputs/apk/debug/app-debug.apk`
- APK type: debug/internal QA APK
- APK SHA256: `9CF3178FCDEEDA3C65C093380BE0CBB8517D0B813A0A108000CC56ABA472E934`

This hash matches the exact APK that was installed on the test phone and
live-tested throughout the 2026-07-02 QA pass (Steps 5, 7, 9, 10, plus the
original narrow-fix retest). Rebuilding from the current commit
(`gradlew assembleDebug`) reproduced the identical hash, confirming no
source drift between the tested build and the branch tip.

## Branch

- Branch: `mobile/android-reconnect-lifecycle-qa`
- HEAD: `85102ae`
- QA closeout commit: `85102ae`
- Tk native crash fix commit: `019fc14`

## Gates

| Gate | Result |
|---|---|
| `pytest tests/test_mobile_bridge.py tests/test_mobile_connection_lifecycle.py -q` | PASS |
| `python -m compileall cache_vault` | PASS |
| `python app.py --selftest` | PASS |
| `gradlew testDebugUnitTest` | BUILD SUCCESSFUL |
| `gradlew assembleDebug` | BUILD SUCCESSFUL |
| APK hash matches live-tested build | PASS |

## QA Summary

- Fresh pair: `PASS`
- Desktop restart reconnect (`Connect this time`): `PASS`
- `Not now` truthfulness: `PASS`
- Keep Connected foreground notification / no crash: `PASS`
- Foreground-service stop: `PASS` — live notification clears in `~0.4s`
- Revoked reconnect blocked: `PASS`
- Re-pair after revoke: `PASS`
- Re-pair reuses same `device_id`: `PASS`
- Send-to-PC Android share regression: `PASS`
- No Android crash: `PASS`
- No desktop crash: `PASS`
- Step 9 desktop labels: `PARTIAL` — the reachable desktop UI exposes
  aggregate mobile status (paired count / last connection), not full
  per-device online/offline/revoked labels. This is incomplete visibility,
  not a false or dishonest connected/online claim.

Full detail for every step lives in
`docs/CACHE_VAULT_ANDROID_RECONNECT_DEVICE_QA_2026-07-01.md`.

## Scope Disclosure

This lane's diff (`5587924~1..85102ae`) includes:

- Android reconnect lifecycle and pairing/re-pair fixes.
- Desktop mobile bridge support (`cache_vault/core/mobile/*`).
- A Tk tooltip native-crash fix (`cache_vault/ui/tooltip.py`) found live
  during Step 9 QA testing and fixed as an authorized exception, unrelated
  to the Android reconnect logic itself.
- QA docs/receipts.
- **Android companion UI polish also present in the lane**, bundled into
  the pre-session commit `5587924` (`ClipDetailScreen.kt`, `BrowseScreen.kt`,
  `ProofScreen.kt`, `VaultSections.kt`, `ClipCard.kt`, `VaultSectionCard.kt`).
  This is Android-app-only, predates this QA session, and is not
  reconnect-specific, but it is part of what this branch will carry if
  merged. Disclosed here rather than described as "reconnect only."
- No landing page residual changes: the accidental `7aad76e` commit is
  fully reverted by `4efc452`, confirmed via an empty diff on `landing.html`
  between the two states.
- No raw `qa_artifacts`/logcat tracked in git (`git ls-files` has zero
  matches; both exist only as untracked working-tree evidence).
- No `/proof` update.
- No stable/release claim.

## Known Follow-Up

- Desktop per-device mobile state labels need clearer, reachable UI
  (`PairedDevicesDialog` exists but is not wired into the live Settings
  Hub / Mobile Access screen). Tracked as a non-blocking desktop UX
  follow-up, not a release blocker.
- A public/release APK would require a separate release/signing/publish
  gate; this receipt covers the internal RC candidate decision only.

## Final

`APK_RC_CANDIDATE` with documented desktop-label UX follow-up.
