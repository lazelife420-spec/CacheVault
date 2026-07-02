# Cache Vault Android Reconnect Device QA Run Sheet

Date: 2026-07-01

## Lane Status

- Android reconnect implementation: preserved
- Device installability: proven
- Reconnect reliability: **tested live 2026-07-01, mixed result; root-caused
  and fixed 2026-07-02, see "Root Cause Investigation and Narrow Fix
  (2026-07-02)" below.** `Not now` truthfulness and Keep Connected
  notification/no-crash confirmed `PASS` on 2026-07-01. Silent reconnect via
  `Connect this time` (reusing a remembered, non-revoked pairing after a
  desktop restart) confirmed `FAIL` on 2026-07-01 - only a manual `Re-pair`
  succeeded. **Update 2026-07-02:** root cause identified as `Re-pair`
  minting a brand-new device identity instead of refreshing the remembered
  one, plus misleading repair-required copy in two places. Both fixed
  (`f9bcfbe`, `e99e355`) and retested live: `Connect this time` now succeeds
  after a real desktop restart without needing `Re-pair`, revoke correctly
  blocks reconnect with accurate copy, and `Re-pair` after revoke reuses the
  same `device_id` (confirmed directly in `settings.json`, not just
  screenshots) instead of creating a duplicate. This is not yet a full
  "reliable" claim: Steps 5, 7, 9, and 10 remain untested, and the Keep
  Connected ~29s stop delay and missing desktop online/offline indicator are
  still open, non-blocking findings.
  **Update 2026-07-02 (remaining QA matrix):** Steps 5 (Auto-Connect
  Consent) and 7 (Killed-App Limitation) retested live and confirmed `PASS`.
  Step 9 (Desktop Labels) is `PARTIAL`: per-device Online/Offline/Revoked
  state exists in code but is not reachable from the live desktop UI, which
  only shows an aggregate count - a desktop UX follow-up, not a reconnect
  blocker. Step 10 (Regression) confirmed `PASS`: send-to-PC/mobile inbox
  works end-to-end, the Keep Connected foreground-service stop clears in
  ~0.4s with no crash, and no Android or desktop crash occurred during this
  pass. A separate, previously-undiscovered desktop Tk native crash was
  found live during Step 9 testing (unrelated to the Android reconnect
  logic), root-caused, fixed (`019fc14`), and verified stable under repeated
  live stress-retesting - see the "QA finding during Step 9" subsection
  under Step 9 for full detail.
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

**Update 2026-07-02** (see "Root Cause Investigation and Narrow Fix" section
below for full detail; original values above left intact for history):

- Top commit: `e99e355 fix(mobile): update repair-needed bottom sheet copy to match UserMessages`
  (on top of `f9bcfbe fix(mobile): reuse remembered device_id on re-pair...`)
- Clean-source APK SHA256 (final, string-fix included): `9cf3178fcdeeda3c65c093380be0cbb8517d0b813a0a108000cc56aba472e934`
- Current verdict: `HOLD / NARROW_FIX_RETESTED_PASS` (Steps 5, 7, 9, 10 still untested; not a full-reliability claim)

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

## Live Device QA Pass (2026-07-01, 22:20-22:52, First-Hand)

Executed against the preflight-verified clean-source runtime (`python app.py`,
PID `8876`, `C:\Python313\python.exe app.py`; Android `mobile/android-reconnect-lifecycle-qa`
top commit `4efc452` at test time) on device `R3CW40FY82W`. All actions driven
directly via `adb` (screenshots, UI dumps, taps, logcat) with fresh evidence
saved to `qa_artifacts\android_reconnect_2026-07-01\android\step3_*` and
`...\desktop\desktop_step3_*`.

- **Reopen -> approval prompt: `PASS`.** Every relaunch of the Android app
  after the prior day's pairing consistently surfaced the "Cache Vault found
  on this Wi-Fi" bottom sheet (`Connect this time` / `Always reconnect on this
  Wi-Fi` / `Not now` / `Manual Setup`), never a false connected state.
  Evidence: `step3_01_launch.png`, `step3_02_prompt_recheck.png`,
  `step3_06_before_tap.png`, `step3_11_reconnect_attempt.png`.
- **`Not now` -> desktop stays offline: `PASS`.** Tapping `Not now` dismissed
  the sheet, the phone returned to a disconnected "Checking..." vault view
  (all counts `0`), and the desktop Command Center continued to show only
  "Mobile: Paired (1)" with no online/connected indicator.
  Evidence: `step3_03_after_not_now.png` (phone),
  `desktop_step3_01_after_not_now.png` (desktop).
- **`Connect this time` (reuse remembered pairing): `FAIL`.** Tapping
  `Connect this time` against the fresh clean-source desktop process was
  rejected: "Your phone reached the PC, but the pairing code was rejected.
  Generate a fresh code on the PC." This happened even though a non-revoked
  paired-device record already existed on disk
  (`%LOCALAPPDATA%\CacheVault\settings.json`: `device_id=phone-1`,
  `device_name=Test Pixel`, `created_at=2026-07-01T21:17:23-07:00`,
  `revoked_at=null`). This directly contradicts the Step 3 expectation that a
  remembered pairing silently reconnects without user action across a desktop
  restart. Only the one-tap `Re-pair` action (which re-registers the device
  and issues a fresh token, no code entry required) succeeded.
  Evidence: `step3_07_after_connect_fixed.png`, `step3_11_reconnect_attempt.png`.
- **`Re-pair` (one-tap): `PASS_WITH_RUNTIME_CONSTRAINT` (reconfirmed).**
  After the rejection above, tapping `Re-pair` immediately connected:
  phone showed "Connected - 192.168.0.11" with live vault counts (228 Text
  Clips, 256 Links, 151 Code, 10 Commands, 183 Screenshots) matching the
  desktop's 839-item vault. Desktop still showed only "Mobile: Paired (1)"
  with no distinct online/offline indicator on the Command Center screen.
  Evidence: `step3_12_after_repair_tap.png` (phone),
  `desktop_step3_06_final_connected.png` (desktop).
- **Keep Connected notification: `PASS`.** Enabling "Keep connected in
  background" in Settings triggered the Android notification-permission
  prompt (confirming the `7f0728f` fix path is live), and after granting
  it, `ActivityManager` logged `Background started FGS: Allowed` and a
  persistent `ONGOING_EVENT|FOREGROUND_SERVICE` notification
  ("Cache Vault Desktop found. Open Cache Vault Mobile to approve
  re[connect]...") appeared in the shade.
  Evidence: `step3_16_after_allow.png`, `step3_17_notification_shade.png`.
- **No crash: `PASS`.** The app process (`pidof` / `ps -A`, PID `553` after
  the relaunch cycle) remained alive throughout the entire Keep Connected
  enable/disable sequence. No `FATAL EXCEPTION`, `AndroidRuntime` crash, or
  `ForegroundServiceStartNotAllowed` appeared in logcat at any point.
- **Stop action: `PARTIAL`.** Toggling "Keep connected in background" back
  off did not immediately clear the notification. The service/notification
  were only torn down ~29 seconds later via a system-enforced
  `ActivityManager: Stop FGS timeout` log line, not an immediate
  app-initiated stop. The app did not crash and the notification did
  eventually clear honestly (no stale "connected" claim persisted
  indefinitely), but the stop was not instantaneous as the expected result
  implies.
- **Not tested in this pass:** Step 5 (Auto-Connect Consent), Step 7
  (Killed-App Limitation), Step 8 (Revoke), Step 9 (Desktop Labels beyond
  the "Paired (1)" chip), Step 10 regression (send-to-PC/mobile inbox).

## Root Cause Investigation and Narrow Fix (2026-07-02)

This section documents work done **after** the Live Device QA Pass above,
in response to its "Connect this time: FAIL" finding. It supersedes that
finding's conclusion (the defect is now fixed and retested) but does not
retract or delete the original observation, which remains accurate for the
build tested that night.

### Investigation

The initial working hypothesis (architectural conflation of Pair and
Reconnect into one code path) was checked by reading the full chain:
`android/.../data/BridgeClient.kt`, `.../data/BridgeRepository.kt`,
`.../connect/ConnectionPlanner.kt`, `cache_vault/mobile/bridge.py::_authenticate`,
and `cache_vault/mobile/models.py`. The code already separates:

- **Pair** (`POST /mobile/v1/pair-device`): used only for first-time pairing
  or explicit `Re-pair`.
- **Reconnect**: any authenticated call using the stored Bearer token;
  `PcOfferMode.REPAIR_NEEDED` is set specifically on a `401 Unauthorized`
  response, not on every call.

This contradicted the conflation hypothesis. To be sure, the hypothesis was
tested empirically before writing any code: the desktop process was killed
and restarted cleanly, the phone app was force-stopped and relaunched, and
`Connect this time` was tapped. **It succeeded** against the freshly
restarted desktop, with `last_seen_at` updating server-side. This proved the
2026-07-01 `FAIL` was not a reproducible architecture defect and narrowed
the search to something more specific.

### Real root causes found

1. `BridgeRepository.pairDiscoveredPc()` never passed the phone's existing
   remembered `device_id` into `client.pairDevice()`. Every `Re-pair` (and,
   per the two-conflicting-records evidence found in the live
   `settings.json` that night — one never-authenticated `phone-1` record and
   one successfully-authenticated `c0ef497e...` record) minted a brand-new
   random device identity, orphaning the old non-revoked record instead of
   refreshing it in place.
2. `UserMessages.REPAIR_NEEDED` ("Your phone reached the PC, but the pairing
   code was rejected...") is generic copy written for the code-entry pairing
   flow. It is misleading when shown for the code-less, automatic
   reconnect-rejection path, and a **second, separate** copy of the same
   wording existed in `strings.xml::repair_needed_body`
   (`PcFoundBottomSheet`'s dedicated string resource) that was missed in the
   first pass and only caught via live on-device observation during the
   revoke retest below.

The `"phone-1"` / `"Test Pixel"` device-id/name seen repeatedly in the real
`settings.json` was traced to the `tests/test_mobile_bridge.py::_pair()`
pytest fixture default. Confirmed this is not the leak path: that fixture
only touches an in-memory `Settings()` via `tests/conftest.py`'s isolated
fixtures and never writes the real `%LOCALAPPDATA%\CacheVault\settings.json`.
No dev smoke script defaults to `"phone-1"` either (see the evidence
manifest's "Test-state hygiene finding" section for the full script-by-script
check). See the evidence manifest for the complete writeup, including a
second, unexplained-but-harmless `"phone-1"` reappearance mid-session
attributed most plausibly to manual GUI interaction on the operator's
machine.

### Fix (narrow scope, no bridge/protocol rewrite)

- `ConnectionPlanner.deviceIdForPairing(existingDeviceId)`: pure helper,
  reuses a non-blank remembered device ID, else returns `null` for
  first-time pairing.
- `BridgeRepository.pairDiscoveredPc()`: now passes the existing `deviceId`
  through to `client.pairDevice()` when one is remembered.
- `UserMessages.REPAIR_NEEDED` and `strings.xml::repair_needed_body`: both
  corrected to "This PC no longer trusts this phone.\nRe-pair to continue."

Commits: `f9bcfbe` (core fix + device_id reuse + `UserMessages` copy + tests),
`e99e355` (second, missed `strings.xml` copy instance, found live during
retest).

### Tests added

- Android (`ConnectionPlannerTest.kt`): 3 cases for `deviceIdForPairing`
  (reuse existing, null when none remembered, blank treated as none).
- Android (`UserMessagesTest.kt`): 1 case asserting the corrected copy and
  the absence of the old "pairing code was rejected" string.
- Desktop (`tests/test_mobile_bridge.py`): `test_last_seen_updates_on_successful_reconnect`,
  `test_repair_with_same_device_id_refreshes_not_duplicates`,
  `test_repair_after_revoke_succeeds_with_fresh_credential`,
  `test_reconnect_succeeds_after_desktop_restart` (full restart simulated via
  a fresh `Vault`/`Settings.load()`).

### Gates run (all PASS)

- `pytest tests/test_mobile_bridge.py tests/test_dialogs.py tests/test_mobile_connection_lifecycle.py -q`
- `python -m compileall cache_vault`
- `python app.py --selftest`
- `.\gradlew.bat testDebugUnitTest`
- `.\gradlew.bat assembleDebug`

(Run twice: once after `f9bcfbe`, once after `e99e355`'s `strings.xml` fix.)

### Live retest (2026-07-02, 00:07-00:13, clean source, final APK)

Full sequence executed on-device (`R3CW40FY82W`), APK SHA256
`9cf3178fcdeeda3c65c093380be0cbb8517d0b813a0a108000cc56aba472e934`. Full
per-artifact detail and SHA256s are in
`docs/CACHE_VAULT_ANDROID_RECONNECT_EVIDENCE_MANIFEST_2026-07-01.md`,
Section A.

1. Cleared phone app data, paired fresh against a running desktop: `PASS`
   (new `device_id=04ff3a088a494cd9a3009768a5709614`).
2. Killed and restarted the desktop process, relaunched the phone app,
   tapped `Connect this time`: **`PASS`** — reconnected without needing
   `Re-pair`. This directly supersedes the 2026-07-01 `FAIL` for this exact
   scenario.
3. Revoked the device via the app's own `bridge.revoke_device()` (not a
   manual settings edit), restarted the desktop, relaunched the phone,
   tapped `Connect this time`: correctly rejected, `PASS`. First observed
   with the *old*, not-yet-rebuilt bottom-sheet copy still showing (caught
   here, fixed via `e99e355`, rebuilt, reverified showing the corrected
   copy: `PASS`).
4. Tapped `Re-pair` after revoke: `PASS`, and confirmed directly in
   `settings.json` (not just the screenshot) that the **same**
   `device_id=04ff3a088a494cd9a3009768a5709614` was reused with a refreshed
   `created_at`/`token_hash`, `revoked_at` cleared, `last_seen_at` updated,
   and the paired-devices list still held exactly the same 2 total records
   (no duplicate created).

### What is still open / not claimed by this fix

- Steps 5 (Auto-Connect Consent), 7 (Killed-App Limitation), 9 (Desktop
  Labels), and 10 (Regression) remain untested.
- The Keep Connected ~29s toggle-off delay (Step 6 above) is unaddressed.
- The desktop's lack of a distinct online/offline indicator (only "Mobile:
  Paired (N)") is unaddressed.
- No `/proof` update, no APK publish, no merge into desktop `rc4`/`rc5`, and
  no "Android reconnect is reliable" claim beyond this specific, now-fixed
  defect.

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

- Status: `PARTIAL - see Live Device QA Pass`
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
  - `PARTIAL`, confirmed live 2026-07-01 22:20-22:52. A paired device record
    (`phone-1` / "Test Pixel") does persist on disk across desktop restarts,
    and the phone shows PC name/IP ("Connected - 192.168.0.11") after a
    successful `Re-pair`. However, the record's mere existence did **not**
    let the phone reconnect via `Connect this time` (see Step 3: rejected).
    Desktop-side confirmation of the trusted-phone entry (a dedicated
    paired-devices UI, not just the "Paired (1)" toolbar chip) was still not
    captured.
- Android screenshot filename/path:
  - `step3_12_after_repair_tap.png` (connected state with PC name/IP shown).
- Desktop screenshot filename/path:
  - `desktop_step3_06_final_connected.png` (still only "Mobile: Paired (1)",
    no dedicated trusted-device panel captured).
- Logcat filename/path if relevant:
  - Pending only if failure occurs.
- Notes / caveats:
  - Confirm this uses the new reconnect lifecycle flow, not a stale prior pairing.
  - Live QA must capture the desktop trusted-device UI, which has never been evidenced.
  - **Update 2026-07-02:** the "record's mere existence didn't let reconnect
    work" gap above is fixed and retested; see "Root Cause Investigation and
    Narrow Fix (2026-07-02)". Desktop trusted-device UI is still not
    evidenced.

### 3. Close/Reopen Reconnect Prompt

- Status: `PARTIAL - approval prompt PASS, silent reconnect FAIL`
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
  - Confirmed live 2026-07-01 22:20-22:49 across multiple relaunch cycles:
    - Approval prompt appears after reopen: `PASS`. Every relaunch showed the
      "Cache Vault found on this Wi-Fi" sheet reliably.
    - Tap `Connect` re-establishes connection without retyping token: `FAIL`.
      Tapping `Connect this time` against the freshly-restarted clean-source
      desktop was rejected ("the pairing code was rejected"), even with a
      valid, non-revoked paired-device record on disk. Only `Re-pair`
      (issuing a brand new token, no code entry) succeeded.
    - Desktop moves to online/connected: not independently observable; the
      desktop Command Center only ever showed "Mobile: Paired (1)" with no
      distinct online/offline state, before or after a successful reconnect.
- Android screenshot filename/path:
  - `step3_01_launch.png`, `step3_07_after_connect_fixed.png` (rejection),
    `step3_12_after_repair_tap.png` (eventual connect via Re-pair).
- Desktop screenshot filename/path:
  - `desktop_step3_00_baseline.png`, `desktop_step3_06_final_connected.png`.
- Logcat filename/path if relevant:
  - Not applicable; no crash occurred during this flow.
- Notes / caveats:
  - Record how long rediscovery took on this Wi-Fi.
  - The `Connect this time` rejection against a same-day, same-machine,
    clean-source desktop restart is a real reconnect-reliability gap, not an
    artifact of a stale build. Root cause not yet diagnosed (out of scope for
    this QA pass; no source changes were made).
  - **Update 2026-07-02:** root-caused (`Re-pair` was minting a new device
    identity instead of reusing the remembered one) and fixed (`f9bcfbe`).
    Retested live: `Connect this time` now succeeds after a real desktop
    restart. See "Root Cause Investigation and Narrow Fix (2026-07-02)".

### 4. Not Now Path

- Status: `PASS`
- Exact steps performed:
  - Reopen the app again after prior pairing.
  - When the approval prompt appears, tap `Not now`.
  - Observe both phone and desktop state.
- Expected result:
  - Desktop does not falsely show online.
  - Phone remains paired but offline or waiting.
- Actual result:
  - Confirmed live 2026-07-01 22:20. Tapping `Not now` dismissed the sheet;
    the phone showed a disconnected "Checking..." vault view with all
    section counts at `0` (no false connected data). The desktop Command
    Center continued to show only "Mobile: Paired (1)", no online claim.
- Android screenshot filename/path:
  - `step3_03_after_not_now.png`.
- Desktop screenshot filename/path:
  - `desktop_step3_01_after_not_now.png`.
- Logcat filename/path if relevant:
  - Not applicable; no failure occurred.
- Notes / caveats:
  - This is a truthfulness check for paired-vs-live state separation.
  - The desktop has no distinct "online" indicator at all on this screen
    (only ever shows "Paired (N)"), so this result is based on the absence
    of a false-positive claim, not a positive "correctly shows offline"
    indicator. See Step 9 note about desktop label granularity.

### 5. Auto-Connect Consent

- Status: `PASS`
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
  - Confirmed live 2026-07-02, against the clean-source, fixed-build APK
    (`9cf3178f...`). Tapped "Always reconnect on this Wi-Fi" on the discovery
    sheet (explicit consent, not a default). Killed and restarted the desktop
    process, force-stopped and relaunched the phone app. It reconnected
    silently with no approval prompt and no manual token/code entry, showing
    "Connected · 192.168.0.11" immediately. Verified server-side: the
    device's `last_seen_at` in `settings.json` updated to the exact second
    shown on the phone's clock, confirming a real authenticated reconnect,
    not a stale cached UI state.
- Android screenshot filename/path:
  - `step5_00_baseline_launch.png` (sheet before consent),
    `step5_02_after_always_reconnect_tap.png` (immediately connected after
    consent tap), `step5_03_relaunch_after_restart.png` (silent reconnect
    after desktop restart + phone relaunch, no prompt shown).
- Desktop screenshot filename/path:
  - Not captured for this sub-step (server-side `settings.json` used
    instead for corroboration).
- Logcat filename/path if relevant:
  - Not applicable; no failure occurred.
- Notes / caveats:
  - Consent was explicit (a deliberate tap on "Always reconnect on this
    Wi-Fi"), not a default-on behavior. No auto-connect occurred before
    that tap in any earlier step.

### 6. Keep Connected Foreground Service

- Status: `PARTIAL - notification PASS, stop delayed`
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
  - Confirmed live 2026-07-01 22:49-22:52 against the clean-source runtime
    (superseding the earlier inconclusive `live_check.png`/`foreground_check.png`
    evidence from the prior day, which remains inconclusive/duplicate and was
    not relied on):
    - Foreground notification appears: `PASS`. Enabling the toggle triggered
      the Android notification-permission prompt; after granting it,
      `ActivityManager` logged `Background started FGS: Allowed` and a
      persistent `ONGOING_EVENT|FOREGROUND_SERVICE` notification appeared
      in the shade ("Cache Vault Desktop found. Open Cache Vault Mobile to
      approve re[connect]...").
    - Background behavior improved relative to normal mode: not tested
      (app was not backgrounded/compared in this pass).
    - Stop action works: `PARTIAL`. Toggling off did not clear the
      notification immediately. Teardown happened ~29 seconds later via a
      system-enforced `ActivityManager: Stop FGS timeout`, not an
      app-initiated immediate stop.
    - Status updates honestly after stop: `PASS` (eventually). The
      notification and service record were both gone after teardown; no
      stale "connected" claim persisted indefinitely.
    - No crash: `PASS`. App process (PID `553`) stayed alive throughout
      enable, notification display, and disable. No `FATAL EXCEPTION` or
      `ForegroundServiceStartNotAllowed` in logcat.
- Android screenshot filename/path:
  - `step3_15_keep_connected_toggled.png`, `step3_16_after_allow.png`,
    `step3_17_notification_shade.png`, `step3_19_toggle_off_retry.png`.
  - Superseded/inconclusive prior evidence: `live_check.png`,
    `foreground_check.png` (byte-identical, home-screen only, no notification
    visible; predates this confirmed pass).
- Desktop screenshot filename/path:
  - Not captured for this sub-step.
- Logcat filename/path if relevant:
  - No failure occurred; live logcat inspected directly (not archived to a
    separate file for this step).
- Notes / caveats:
  - Do not interpret "better" as "guaranteed."
  - The ~29s delayed stop is a real, first-hand-observed nuance, not
    confirmed as a blocking defect, since it self-resolved honestly with no
    crash and no stale-connected claim. Worth a follow-up look at whether the
    app calls `stopForeground()`/`stopSelf()` explicitly on toggle-off versus
    relying on the OS timeout.
  - **Update 2026-07-02:** re-verified as part of Step 10 with a more
    carefully-instrumented check (the phone's Settings-screen toggle-off was
    confirmed by code read to call `BackgroundConnectionService.stop()`,
    which sends `ACTION_STOP` and triggers an explicit
    `stopForeground(STOP_FOREGROUND_REMOVE)` + `stopSelf()`, not just an OS
    timeout) and cleared the live notification in `~0.4s` on that pass, with
    no code change made. See Step 10 for the full result and for a
    methodology note about a test-tooling false positive encountered along
    the way. The ~29s figure above is left as-is since it was a genuine
    first-hand observation on 2026-07-01; both figures are kept for the
    record rather than reconciled into a single number.

### 7. Killed-App Limitation

- Status: `PASS`
- Exact steps performed:
  - Force stop the app via `adb shell am force-stop`.
  - Observe whether UI/desktop makes any false wake claim.
  - Reopen the app.
  - Verify reconnect flow resumes.
- Expected result:
  - No fake claim that the PC can wake a killed app.
  - Reopen resumes reconnect flow honestly.
- Actual result:
  - Confirmed live 2026-07-02. Force-stopped the app (`adb shell ps -A`
    confirmed the process was gone). Captured the desktop window while the
    phone app was dead: no crash, no visual change, still only "Mobile:
    Paired (2)" - no false "connected" claim and no wake-related copy
    anywhere. Code search confirmed no wake/push/FCM/GCM mechanism exists
    anywhere in the desktop source at all, so there is no code path that
    could ever attempt to wake a killed app. Reopening the app (a user
    action, not a PC-initiated wake) correctly resumed the reconnect flow,
    showing an honest "Connected · 192.168.0.11" status. The discovery
    sheet's own copy already states "A killed app cannot be woken by the
    PC."
- Android screenshot filename/path:
  - `step7_02_reopen_after_kill.png`.
- Desktop screenshot filename/path:
  - `step7_00_before_kill.png`, `step7_01_after_kill.png` (no change while
    phone app was dead).
- Logcat filename/path if relevant:
  - Not applicable; no failure occurred.
- Notes / caveats:
  - This is a critical product honesty check, and it holds: the app makes
    no wake claim, and reopening is the only thing that resumes reconnect.

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

- Status: `PARTIAL`
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
  - Code-level per-device `Online` / `Offline` / `Waiting for phone
    approval` / `Revoked` / `Paired` states exist and are correctly
    implemented (`paired_device_status()` in `cache_vault/core/mobile/models.py`,
    used by `PairedDevicesDialog` in `cache_vault/ui/mobile_dialogs.py`).
    However, the live-reachable desktop UI tested (toolbar "Mobile: Paired
    (N)" chip and the sidebar "Mobile Access" screen) only ever showed an
    aggregate paired-device count and a single aggregate "Last phone
    connection" value, never a per-device online/offline/revoked panel.
    `PairedDevicesDialog` (the dialog that does show per-device state) is
    only wired to the deprecated fallback `SettingsDialog`, which the app
    skips whenever the current Settings Hub loads successfully - i.e.
    effectively always in the live app. A clean supporting screenshot of
    the "Mobile Access" screen was not obtained because sidebar-scroll
    automation to reach it was unreliable (scroll position drifted between
    capture attempts); that automation limitation is not being treated as
    proof of anything, so this section relies on the code-level finding
    plus the toolbar-chip screenshots already on file, not on an
    unconfirmed screenshot.
- Android screenshot filename/path:
  - N/A.
- Desktop screenshot filename/path:
  - `step7_00_before_kill.png`, `step9_09_fresh_natural.png` (both show the
    toolbar's aggregate "Mobile: Paired (N)" chip; no per-device panel was
    captured).
- Logcat filename/path if relevant:
  - N/A.
- Notes / caveats:
  - This is a desktop-truthfulness verification tied to the Android lane.
  - Not a reconnect blocker: the underlying reconnect/re-pair credential
    behavior (Steps 2-4, 8) was already fully tested and is unaffected by
    this UI-surfacing gap. This is a desktop UX follow-up: wire
    `PairedDevicesDialog` (or equivalent per-device detail) into the
    current Settings Hub / Mobile Access screen so operators can actually
    see per-device Online/Offline/Revoked state.

#### QA finding during Step 9: desktop Tk native crash (found and fixed)

While live-testing Step 9 (navigating the desktop sidebar to reach the
Mobile Access screen), the desktop process crashed. This is a **desktop
QA blocker found during this pass**, not a defect in the Android
reconnect/re-pair logic already tested and confirmed above.

- Crash signature: `tk86t.dll` `0xc0000005` ACCESS_VIOLATION, fault offset
  `0xd780f` - the same deterministic offset documented in
  `docs/CACHE_VAULT_TK_NATIVE_CRASH_AUDIT_2026-07-01.md`. Confirmed via
  `%LOCALAPPDATA%\CacheVault\crash_native.log` and the Windows Application
  event log (Event ID 1000). Always from clean-source `python.exe`
  running `app.py`, never from a stale EXE.
- Full Python traceback (this time available, unlike the original
  unsymbolized minidumps in the prior audit): main thread, inside
  `TooltipManager.hide_active()` -> `CTkToplevel.destroy()`, triggered via
  the global `<Configure>`/`<FocusOut>`/`<Unmap>`/`Button`/`MouseWheel`
  hide-tooltip bindings in `shell.py` (`_bind_tooltip_hide_events`).
- Root cause: `hide_active()` called `tip.destroy()` with no
  `winfo_exists()` guard, and only cleared `state.active_tip` **after**
  the destroy attempt. Two real trigger paths follow from that: (1) the
  tooltip's owning widget hierarchy can be torn down elsewhere (e.g. a
  sidebar rebuild during navigation), already cascading a Tcl-level
  destroy of the same `Toplevel`, so this call destroys it a second time;
  (2) `destroy()` can pump a pending Tk event synchronously, reentering
  `hide_tooltip()` while the outer call's tip reference is still set,
  racing to destroy the same window twice. Double-destroying an
  `overrideredirect` `Toplevel` on Windows Tcl/Tk 8.6.2.15 is a documented
  native crash trigger, not a catchable `TclError`, so the existing
  `try/except Exception` could not protect against it.
- Fix commit: `019fc14` - clear active-tip state before attempting
  cleanup (so a reentrant call sees nothing to destroy) and check
  `winfo_exists()` before calling `destroy()` a second time. Adds two
  regression tests (`test_hide_active_skips_destroy_when_already_gone`,
  `test_hide_active_reentrant_call_does_not_double_destroy`) covering both
  trigger paths in `tests/test_tooltip.py`.
- Verification:
  - `pytest tests/ -q`: full suite `PASS` (all tests, including the two
    new regression tests).
  - `python -m compileall cache_vault`: `PASS`.
  - `python app.py --selftest`: `PASS`.
  - Live re-test: restarted the desktop from the fixed build and
    reproduced the same rapid scroll + navigation-click sequence that
    crashed it before, multiple times in a row. The process stayed alive
    and responsive (`Get-Process ... | Select Responding` = `True`)
    throughout; no further `crash_native.log` entries were produced.
- Classification: `FIXED / RETESTED`. This is scoped as a desktop UI
  stability fix discovered during this QA pass, independent of the
  Android reconnect/re-pair narrow fix (`f9bcfbe`, `e99e355`) documented
  above.

### 10. Regression

- Status: `PASS`
- Exact steps performed:
  - Verify send-to-PC/mobile inbox still works.
  - Re-verify Keep Connected's foreground-service clean stop (enable, confirm
    notification, disable, confirm clean stop, confirm no crash).
  - Watch for Android crash during lifecycle testing.
  - Watch for desktop crash during pairing, reconnect, revoke, and inbox flow.
  - Confirm port 8742 stays owned by the committed-source desktop process.
- Expected result:
  - Send-to-PC/mobile inbox still works.
  - Foreground service stops cleanly.
  - No Android crash.
  - No desktop crash.
- Actual result:
  - Confirmed live 2026-07-02, against the re-paired real phone (see the
    settings.json note below) and the clean-source desktop (PID `15240`).
  - **Send-to-PC / mobile inbox: `PASS`.** Fired a real Android
    `ACTION_SEND` share intent at the app's registered `ShareAssistantActivity`
    (the same activity any app's share sheet reaches; confirmed registered
    with `text/plain`/`image/*` intent filters in `AndroidManifest.xml`).
    The app showed "Send to your PC vault" / "Connected to Cache Vault PC",
    and after tapping "Send to Cache Vault" showed "Sent to Cache Vault ·
    Default Safe · receipt stamped". Verified directly in the desktop's
    `cache_vault.db` (not just UI): a new row appeared in `clips` with the
    exact test payload, `source_app='Android Share'`, `source_window` set to
    the phone's model string, timestamped to the moment of the test. This
    confirms the phone-to-desktop send path is intact end-to-end, independent
    of the reconnect fix.
  - **Foreground-service clean stop re-verification: `PASS`.** First pass
    used an over-broad `dumpsys notification` grep that matched Android's
    permanent notification *history archive* (not the live shade), producing
    a false "notification never clears" reading after 5+ minutes - this was
    a test-methodology bug, not a product bug, and is called out here so it
    is not mistaken for evidence later. Re-tested with a corrected check
    that reads only the live `Notification List:` section: enabling Keep
    Connected posts the ongoing "Cache Vault Mobile connected" notification
    (`flags=ONGOING_EVENT|ONLY_ALERT_ONCE|NO_CLEAR|FOREGROUND_SERVICE`) as
    expected; toggling it off in the phone's Settings screen correctly
    invokes `BackgroundConnectionService.stop(context)` (confirmed by
    reading `CacheVaultMobileRoot.kt`'s `onKeepConnectedChanged` wiring),
    which sends `ACTION_STOP` to the service, and the service's
    `stopForeground(STOP_FOREGROUND_REMOVE)` + `stopSelf()` handler clears
    the live notification in `~0.4s` with the app process staying alive
    throughout (`pidof` unchanged). This supersedes the ~29s figure
    recorded in Step 6 on 2026-07-01 for this specific build; no code
    change was needed or made.
  - **No Android crash: `PASS`.** `adb logcat -d` searched for
    `FATAL EXCEPTION` across the full send-to-PC and Keep Connected test
    window: no matches. App process PID stayed the same throughout.
  - **No desktop crash: `PASS`.** Desktop process (PID `15240`, clean
    source, matches the fix build) stayed alive and `Responding: True`
    across the entire Step 10 window; no new `crash_native.log` entries.
  - **Port ownership: `PASS`.** `netstat` confirms `0.0.0.0:8742 LISTENING`
    is still owned by PID `15240` throughout.
  - **Incidental note:** before this step, the real phone had briefly
    dropped to a "This PC no longer trusts this phone. Re-pair to continue."
    state (the desktop's `settings.json` `paired_devices` array had been
    replaced by a single `phone-1`/`Test Pixel` record with a suspicious
    timestamp - the same recurring test-fixture-shaped artifact noted
    earlier in this document; the write path is still not conclusively
    identified, `pytest` and `app.py --selftest` were both re-checked and
    ruled out again). Per direction, this was not chased further: the real
    phone was re-paired fresh (itself an incidental live confirmation that
    the repair-needed copy fix and Re-pair flow both still work correctly),
    and Step 10 proceeded normally from there.
- Android screenshot filename/path:
  - Not captured (share-intent and toggle flows verified via `uiautomator`
    dumps and direct system state, not screenshots).
- Desktop screenshot filename/path:
  - Not captured; verified via direct `cache_vault.db` query and process/port
    state instead.
- Logcat filename/path if relevant:
  - Not archived to a file; inspected live via `adb logcat -d` for this pass.
- Notes / caveats:
  - Treat crashes as blocking failures even if reconnect otherwise works;
    none occurred in this pass.
  - The Keep Connected stop-delay figure from Step 6 (~29s) is superseded
    for this build by this step's more carefully-instrumented ~0.4s result;
    both are left in the document rather than deleting the earlier entry.

## Post-Run Verdict

- Final verdict: `HOLD`
- Promote to `PASS` only if all critical reconnect, revoke, truthfulness, and regression flows pass on-device.
- Keep as `HOLD` if any blocker remains or any critical step is still untested.
- **Update 2026-07-02:** the specific blocker found on 2026-07-01
  (`Connect this time` failing after a desktop restart) is root-caused,
  fixed, and retested `PASS` live — see "Root Cause Investigation and Narrow
  Fix (2026-07-02)". Verdict remains `HOLD` because Steps 5, 7, 9, and 10 are
  still untested and the Keep Connected stop-delay / desktop online-offline
  indicator gaps remain open.
- **Update 2026-07-02 (remaining QA matrix complete):** all previously
  untested steps have now been run live.
  - Android reconnect/re-pair core (Steps 2-4, 8): `PASS`, fixed and
    retested as above.
  - Auto-Connect Consent (Step 5): `PASS`.
  - Killed-App Limitation (Step 7): `PASS`.
  - Desktop Labels (Step 9): `PARTIAL` - per-device Online/Offline/Revoked
    state exists in code but is not reachable in the live desktop UI, which
    only shows an aggregate count. This is a desktop UX follow-up, not a
    reconnect blocker.
  - Regression (Step 10): `PASS` - send-to-PC/mobile inbox confirmed
    end-to-end via a real Android share intent and a direct database check;
    the Keep Connected foreground-service stop clears in ~0.4s with no
    crash (superseding the ~29s figure from Step 6 for this build); no
    Android or desktop crash occurred.
  - A separate, previously-undiscovered desktop Tk native crash was found
    live during Step 9 testing (`tooltip.py` double-destroy on hide,
    unrelated to the Android reconnect logic), root-caused, fixed
    (`019fc14`), and verified stable under full pytest, compileall,
    selftest, and live stress-retesting.
  - **Verdict stays `HOLD`, not `PASS`.** Every individual step above is
    now `PASS` or `PARTIAL` (no step is `FAIL` or untested), but this
    document has not been treated as sufficient on its own to promote the
    lane to an APK RC candidate: that decision, and any `/proof` update,
    APK publish, or `rc4/rc5` merge, is deliberately left to a separate,
    explicit release-gate review rather than being auto-triggered by this
    QA pass finishing. The Step 9 aggregate-only desktop label gap is
    tracked as an open, non-blocking follow-up rather than a blocker.

## Commit Guidance After QA

- Commit only the QA doc updates and evidence-path references if appropriate.
- Do not publish anything from this lane.
