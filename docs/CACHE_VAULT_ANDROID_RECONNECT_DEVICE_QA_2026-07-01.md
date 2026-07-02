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

## Evidence Analysis (Cautious, Non-Certifying)

This section reviews the existing `qa_artifacts` captures and logcat against the
Run Sheet below. It does not promote any step to `PASS`. It only records what
the existing evidence does and does not show, so later live testing is not
duplicated or misinterpreted.

- Logcat coverage gap:
  - `android_reconnect_logcat_2026-07-01.txt` spans only `18:01:32` and earlier
    (file `LastWriteTime` `7/1/2026 6:01:31 PM`; first captured entries align
    with app activity starting around `17:54:46`).
  - It does **not** cover the `20:40`-`21:00` window where the runtime-mismatch
    finding, repair retry, and re-pair actually happened.
  - No `FATAL EXCEPTION`, `AndroidRuntime` crash, `ForegroundServiceStartNotAllowed`,
    or Cache Vault package exception was found in the captured window. The only
    exceptions present are unrelated `com.android.phone` `AppOps` `SecurityException`
    lines (system telephony noise, not Cache Vault).
  - This means the logcat neither confirms nor denies crash-free behavior for
    the actual repair/reconnect/Keep Connected testing later that evening.
- Screenshot inventory (`qa_artifacts\android_reconnect_2026-07-01\android\`):
  - `cachevault_ui.xml` / `cachevault_initial_retest.png` (`17:54:46`): shows a
    "Cache Vault found on this Wi-Fi / Pair This Phone" discovery sheet. Predates
    the runtime-mismatch fix; cannot be attributed to the clean-source runtime.
  - `cachevault_ui_now.png` (`18:01:31`) and `cachevault_scan_now.png` (`18:02:29`):
    show a different, earlier-onboarding-style "Connect to Cache Vault on this PC"
    screen. This is a non-sequential/contradictory state relative to the `17:54`
    capture and is not attributable to a known runtime.
  - `resume_check.png` (`20:40:55`): shows only the phone OS lock screen (clock,
    battery). Contains no Cache Vault app content; usable only as a timeline
    anchor, not as app-state evidence.
  - `live_check.png` (`20:56:15`) and `foreground_check.png` (`20:56:24`) are
    **byte-identical** (verified via SHA256, both `C99C9AD1...`): a single
    capture saved under two names, not two independent observations. Both show
    the phone home screen/launcher with unrelated third-party apps and **no
    visible Cache Vault notification or foreground-service indicator**. This
    evidence predates the confirmed clean-runtime fix and does not demonstrate
    Keep Connected foreground-service behavior either way.
  - `after_repair.png` (`20:56:36`) is timestamped **before** the rejected-pairing
    screens (`cachevault_ui_now.xml` / `cachevault_ui_aftertap.xml`, `20:58:xx`)
    and before the successful re-pair (`repair_retry_screen.png`, `21:00:16`).
    The filename does not match its position in the timeline; treat it as
    unordered/unconfirmed, not as a "post-repair" state.
  - `repair_retry_screen.png` / `cachevault_ui_repair_retry.xml` (`21:00:16`-`24`):
    the successful re-pair evidence, already credited above under
    `PASS_WITH_RUNTIME_CONSTRAINT`. This remains the only clean, attributable,
    already-scoped piece of evidence in the set.
- Desktop evidence:
  - `qa_artifacts\android_reconnect_2026-07-01\desktop\` is **empty**. No
    desktop-side screenshot exists for any Run Sheet step (paired-device list,
    online/offline/revoked labels, waiting-for-approval state, etc.).
- Conclusion:
  - None of the above evidence is sufficient to mark any numbered Run Sheet
    step `PASS`. Where evidence directly bears on a step's prerequisites, the
    step below is marked `BLOCKED / PREREQUISITE_NOT_MET` instead, with the
    supporting reasoning inline. All other steps remain `PENDING` for live
    device QA.

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
  - Pending manual execution against the clean-source runtime.
  - Existing captures (`cachevault_initial_retest.png` `17:54:46`,
    `cachevault_scan_now.png` `18:02:29`) show two different, non-sequential
    pre-pairing states and predate the runtime-mismatch fix, so they cannot be
    attributed to a known-clean runtime. Not usable to certify this step.
- Android screenshot filename/path:
  - Inconclusive prior capture only: `cachevault_initial_retest.png`,
    `cachevault_scan_now.png`. Fresh capture still pending.
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
  - `BLOCKED / PREREQUISITE_NOT_MET` for full step certification.
  - Phone-side evidence exists for one interactive re-pair action against the
    clean-source runtime (see `Runtime Mismatch Finding`, verdict
    `PASS_WITH_RUNTIME_CONSTRAINT`), but that only proves one manual re-pair
    tap worked, not that trusted metadata (PC name/IP/last seen) is
    persisted and displayed correctly.
  - Desktop-side confirmation has zero evidence: `qa_artifacts\...\desktop\`
    is empty, so the desktop trusted-phone record has never been observed.
- Android screenshot filename/path:
  - Partial/indirect only: `repair_retry_screen.png`,
    `cachevault_ui_repair_retry.xml` (re-pair action, not steady-state pairing
    metadata).
- Desktop screenshot filename/path:
  - None captured.
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - Confirm this uses the new reconnect lifecycle flow, not a stale prior pairing.
  - Live QA must capture the desktop trusted-device UI, which has never been evidenced.

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
  - `BLOCKED / PREREQUISITE_NOT_MET`. No evidence of a persistent remembered-PC
    pairing surviving a close/reopen cycle exists; only a single interactive
    `Re-pair` tap (after a rejected code) has been observed. This step tests a
    different flow (silent rediscovery + approval prompt on reopen) that has
    not been exercised.
- Android screenshot filename/path:
  - None captured for this exact flow.
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
  - `BLOCKED / PREREQUISITE_NOT_MET`. Requires the persistent-pairing state
    from Step 3, which has not been evidenced. Not tested.
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
  - `BLOCKED / PREREQUISITE_NOT_MET`. No evidence of the consent toggle being
    exercised or of a reconnect-without-retyping flow. Not tested.
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
  - `BLOCKED / PREREQUISITE_NOT_MET`. **Not** `PASS`, and not to be inferred
    as such: `live_check.png` (`20:56:15`) and `foreground_check.png`
    (`20:56:24`) are verified byte-identical (SHA256 match) and show only the
    phone home screen with unrelated third-party apps, with **no visible
    Cache Vault notification**. This is not evidence the foreground service
    works, nor proof it fails, since these captures predate confirmation of
    the clean-runtime fix (`21:00:16`) and may not even reflect an attempt to
    enable Keep Connected. `Keep Connected` has not been exercised against
    the clean-source runtime with usable evidence.
- Android screenshot filename/path:
  - Inconclusive/duplicate only: `live_check.png`, `foreground_check.png`
    (identical file, not two independent observations).
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
  - `BLOCKED / PREREQUISITE_NOT_MET`. No evidence of a force-stop/kill cycle
    being performed. Not tested.
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
  - `BLOCKED / PREREQUISITE_NOT_MET`. `Revoke All Devices` has not been
    exercised; no evidence exists either way. Not tested.
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
  - `BLOCKED / PREREQUISITE_NOT_MET`. The desktop evidence folder
    (`qa_artifacts\android_reconnect_2026-07-01\desktop\`) is empty; zero
    desktop-side screenshots exist for any state. Not tested.
- Android screenshot filename/path:
  - N/A unless paired state on phone helps explain.
- Desktop screenshot filename/path:
  - None captured.
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
  - `PENDING`, not `PASS`. The captured logcat (`android_reconnect_logcat_2026-07-01.txt`)
    shows no Cache Vault-specific crash/exception signature, but it only spans
    up to `18:01:32` and does not cover the `20:40`-`21:00` window where the
    actual repair-retry/Keep-Connected testing happened. This absence of
    evidence cannot certify crash-free behavior for the full lifecycle, and
    send-to-PC/mobile inbox regression has not been checked at all.
- Android screenshot filename/path:
  - Optional.
- Desktop screenshot filename/path:
  - Optional.
- Logcat filename/path if relevant:
  - `android_reconnect_logcat_2026-07-01.txt` (partial coverage only, see above).
- Notes / caveats:
  - Treat crashes as blocking failures even if reconnect otherwise works.
  - A fresh logcat capture spanning the full live test window is required for
    this step to be answerable.

## Post-Run Verdict

- Final verdict: `HOLD`
- Promote to `PASS` only if all critical reconnect, revoke, truthfulness, and regression flows pass on-device.
- Keep as `HOLD` if any blocker remains or any critical step is still untested.

## Commit Guidance After QA

- Commit only the QA doc updates and evidence-path references if appropriate.
- Do not publish anything from this lane.
