# Cache Vault Android Reconnect Device QA Run Sheet

Date: 2026-07-01

## Lane Status

- Android reconnect implementation: preserved
- Device installability: proven
- Reconnect reliability: pending real device QA
- Release/publish: `HOLD`

## Guardrails

- Do not update `/proof`.
- Do not publish APK.
- Do not merge into desktop `rc4/rc5`.
- Do not call reconnect reliable until the checklist passes.
- Do not call stable.

## Candidate Under Test

- Branch: `mobile/android-reconnect-lifecycle-qa`
- Remote tracking: pushed to `origin`
- Top commit: `5587924 fix: align mobile bridge repair and companion runtime`
- APK path: `C:\Users\KickA\Desktop\CacheVault\android\app\build\outputs\apk\debug\app-debug.apk`
- APK SHA256: `A1DBA223B4428158CA0A30F274E1CDB180CF5A328A4464A4796ED01739F76E33`
- Device serial: `R3CW40FY82W`
- Device model: `SM-S911W`
- Android version: `16`
- Android SDK: `36`
- Current verdict: `HOLD / DEVICE_QA_PENDING`

## Blocker / Fix Receipt

- Finding:
  - `Keep Connected` toggle could crash the Android app.
- Likely cause:
  - Foreground service was declared as `dataSync` without the required type-specific permission.
  - Service startup and notification permission path did not fail gracefully on-device.
- Fix commit:
  - `7f0728f fix: harden Android background connect toggle`
- Code changes:
  - Added Android manifest foreground service permission for `dataSync`.
  - Added notification permission handling before background-service start.
  - Added clean in-app error handling if service startup fails.
  - App startup check now respects notification availability before restarting background mode.
  - Desktop `Connect Phone` entry point added to surface the PC-side connect flow more clearly.
- Validation:
  - `pytest tests\test_dialogs.py tests\test_mobile_connection_lifecycle.py -q` PASS
  - `python -m compileall cache_vault` PASS
  - `.\gradlew.bat testDebugUnitTest` PASS
  - `.\gradlew.bat assembleDebug` PASS
  - `adb install -r app-debug.apk` SUCCESS
- Verdict:
  - `FIXED_CANDIDATE / RETEST_REQUIRED`
  - Overall device QA remains `HOLD`

## Runtime Mismatch Finding

- Title:
  - `Desktop runtime mismatch caused false no-typing repair failure`
- Observed:
  - Phone was talking to stale packaged desktop app:
    `C:\Users\KickA\Desktop\CacheVault\dist\CacheVault.exe`
  - That listener returned:
    `POST /mobile/v1/pair-device -> 405 method_not_allowed`
  - After stopping the stale packaged process and launching current branch desktop with:
    `python app.py`
    the same route returned `200`.
  - Tapping `Re-pair` on Android moved from repair sheet to connected home screen.
  - Desktop receipt log shows `pair_device ok` from phone IP `192.168.0.25`, followed by `status ok` and `list_clips ok`.
- Evidence:
  - Android screenshot:
    `C:\Users\KickA\Desktop\CacheVault\qa_artifacts\android_reconnect_2026-07-01\android\repair_retry_screen.png`
  - Android UI dump:
    `C:\Users\KickA\Desktop\CacheVault\qa_artifacts\android_reconnect_2026-07-01\android\cachevault_ui_repair_retry.xml`
- Verdict for this subtest:
  - `PASS_WITH_RUNTIME_CONSTRAINT`
- Meaning:
  - One-tap `Re-pair` works against current branch desktop runtime.
  - This does not prove the stale packaged EXE works.
  - This does not prove full reconnect reliability.
  - Relaunching old `dist\CacheVault.exe` without rebuilding will reproduce the `405` failure.
- Overall verdict remains:
  - `HOLD / DEVICE_QA_PENDING`

## Clean Runtime Custody Restored

- Runtime repair commit:
  - `5587924 fix: align mobile bridge repair and companion runtime`
- Clean-source APK:
  - Rebuilt from committed source on `mobile/android-reconnect-lifecycle-qa`
  - SHA256: `A1DBA223B4428158CA0A30F274E1CDB180CF5A328A4464A4796ED01739F76E33`
- Reinstall receipt:
  - `adb install -r android\app\build\outputs\apk\debug\app-debug.apk` -> `Success`
- Desktop runtime receipt:
  - Launched from committed source via `python app.py`
  - Mobile bridge port `8742` owned by `python.exe` running `app.py`
- Meaning:
  - APK source is now committed.
  - Desktop source runtime is now committed.
  - QA artifacts remain separate from runtime source.
  - Packaged `dist\CacheVault.exe` remains invalid for QA until rebuilt from current branch.
- Overall verdict remains:
  - `HOLD / DEVICE_QA_PENDING`

## Evidence Paths

- Android screenshots directory: `C:\Users\KickA\Desktop\CacheVault\qa_artifacts\android_reconnect_2026-07-01\android\`
- Desktop screenshots directory: `C:\Users\KickA\Desktop\CacheVault\qa_artifacts\android_reconnect_2026-07-01\desktop\`
- Logcat path on failure: `C:\Users\KickA\Desktop\CacheVault\android_reconnect_logcat_2026-07-01.txt`

## Mandatory Preflight

Run this before every phone QA pass to confirm runtime custody:

```powershell
cd C:\Users\KickA\Desktop\CacheVault

# Confirm no stale packaged CacheVault listener is running
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'CacheVault|python' -or $_.CommandLine -match 'CacheVault|app.py' } |
  Select-Object ProcessId, Name, ExecutablePath, CommandLine |
  Format-List

# Confirm what owns the mobile bridge port
netstat -ano | findstr ":8742"

# If stale dist\CacheVault.exe owns it, stop it before source-branch QA.
```

For source-branch QA:

```powershell
cd C:\Users\KickA\Desktop\CacheVault
python app.py
```

Packaged desktop QA is invalid until a fresh EXE is built from the current branch. Do not reuse old `dist\CacheVault.exe`.

## Pre-Run Commands

```powershell
adb logcat -c
```

If any issue occurs:

```powershell
adb logcat -d > C:\Users\KickA\Desktop\CacheVault\android_reconnect_logcat_2026-07-01.txt
```

## Run Sheet

### 1. Fresh Launch

- Status: `PENDING`
- Exact steps performed:
  - Launch the freshly installed app on the phone.
  - Observe first visible state before any pairing.
- Expected result:
  - App opens cleanly.
  - No false connected state.
  - No trusted PC state if none exists.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - N/A unless desktop shows unexpected state.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - This step is visual and must be verified on-device.

### 2. Pairing

- Status: `PENDING`
- Exact steps performed:
  - Pair phone to desktop.
  - Confirm pairing completes on both devices.
  - Check the phone connection/settings screen for remembered PC metadata.
  - Check desktop paired-device UI for the trusted phone entry.
- Expected result:
  - Trusted PC metadata is saved on phone.
  - Desktop trusted phone record is saved.
  - Phone shows PC name, IP, and last seen.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Pending.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - Confirm this uses the new reconnect lifecycle flow, not a stale prior pairing.

### 3. Close/Reopen Reconnect Prompt

- Status: `PENDING`
- Exact steps performed:
  - Close the app normally.
  - Reopen the app.
  - Wait for rediscovery of the remembered PC.
  - Verify the `Connect to this PC?` prompt appears.
  - Tap `Connect`.
  - Observe desktop state change.
- Expected result:
  - Approval prompt appears after reopen.
  - Tap `Connect` re-establishes connection without retyping token.
  - Desktop moves to online/connected.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Pending.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - Record how long rediscovery took on this Wi-Fi.

### 4. Not Now Path

- Status: `PENDING`
- Exact steps performed:
  - Reopen the app again after prior pairing.
  - When the approval prompt appears, tap `Not now`.
  - Observe both phone and desktop state.
- Expected result:
  - Desktop does not falsely show online.
  - Phone remains paired but offline or waiting.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Pending.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - This is a truthfulness check for paired-vs-live state separation.

### 5. Auto-Connect Consent

- Status: `PENDING`
- Exact steps performed:
  - Explicitly enable auto-connect consent on the phone.
  - Close and reopen the app.
  - Observe whether reconnect occurs without retyping token.
  - Confirm status text remains understandable.
- Expected result:
  - Auto-connect is only enabled after explicit consent.
  - Reconnect occurs without manual token entry.
  - Status remains clear and honest.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Optional if helpful.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - If the app reconnects before consent, mark as `FAIL`.

### 6. Keep Connected Foreground Service

- Status: `PENDING`
- Exact steps performed:
  - Enable `Keep Connected`.
  - Confirm Android foreground notification appears.
  - Background the app.
  - Observe whether connection survives better than normal backgrounding.
  - Stop the service from notification or app.
  - Observe resulting status.
- Expected result:
  - Foreground notification appears.
  - Background behavior is improved relative to normal mode.
  - Stop action works.
  - Status updates honestly after stop.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Optional if state transition is visible.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - Do not interpret “better” as “guaranteed.”

### 7. Killed-App Limitation

- Status: `PENDING`
- Exact steps performed:
  - Force stop or swipe away the app if applicable on this device.
  - Observe whether UI/desktop makes any false wake claim.
  - Reopen the app.
  - Verify reconnect flow resumes.
- Expected result:
  - No fake claim that the PC can wake a killed app.
  - Reopen resumes reconnect flow honestly.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Optional if useful.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - This is a critical product honesty check.

### 8. Revoke

- Status: `PENDING`
- Exact steps performed:
  - On desktop, use `Revoke All Devices`.
  - Attempt reconnect from phone using old token.
  - Observe phone state.
  - Re-pair using a fresh token.
  - Confirm fresh re-pair succeeds.
- Expected result:
  - Old token is rejected.
  - Phone shows revoked / needs re-pair state.
  - Fresh re-pair works.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Pending.
- Desktop screenshot filename/path:
  - Pending.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - If revoked token still works, mark as critical `FAIL`.

### 9. Desktop Labels

- Status: `PENDING`
- Exact steps performed:
  - Exercise the phone flow needed to show each desktop state.
  - Capture desktop UI in:
    - waiting for approval
    - online
    - offline
    - revoked
    - last seen
- Expected result:
  - Desktop clearly distinguishes all target states.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - N/A unless paired state on phone helps explain.
- Desktop screenshot filename/path:
  - Pending.
- Logcat filename/path if relevant:
  - Usually N/A.
- Notes / caveats:
  - This is a desktop-truthfulness verification tied to the Android lane.

### 10. Regression

- Status: `PENDING`
- Exact steps performed:
  - Verify send-to-PC/mobile inbox still works.
  - Watch for Android crash during lifecycle testing.
  - Watch for desktop crash during pairing, reconnect, revoke, and inbox flow.
- Expected result:
  - Send-to-PC/mobile inbox still works.
  - No Android crash.
  - No desktop crash.
- Actual result:
  - Pending manual execution.
- Android screenshot filename/path:
  - Optional.
- Desktop screenshot filename/path:
  - Optional.
- Logcat filename/path if relevant:
  - Required if any failure or crash occurs.
- Notes / caveats:
  - Treat crashes as blocking failures even if reconnect otherwise works.

## Post-Run Verdict

- Final verdict: `HOLD`
- Promote to `PASS` only if all critical reconnect, revoke, truthfulness, and regression flows pass on-device.
- Keep as `HOLD` if any blocker remains or any critical step is still untested.

## Commit Guidance After QA

- Commit only the QA doc updates and evidence-path references if appropriate.
- Do not publish anything from this lane.
