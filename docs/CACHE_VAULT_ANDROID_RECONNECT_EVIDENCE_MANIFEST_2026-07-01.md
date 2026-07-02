# Cache Vault — Android Reconnect Evidence Manifest (2026-07-01 / 2026-07-02)

This document is an **evidence index only**. It lists every artifact captured
during the Android reconnect QA + fix lane, its SHA256, what it proves (or
does not prove), the test step it belongs to, whether it was captured
against clean committed source or a dirty/stale build, and whether it is
usable evidence. It does **not** certify a release, does not update
`/proof`, and is not a substitute for the run sheet's verdict
(`docs/CACHE_VAULT_ANDROID_RECONNECT_DEVICE_QA_2026-07-01.md`).

Raw screenshots/UI dumps/logcat stay local under `qa_artifacts/` and
`android_reconnect_logcat_2026-07-01.txt` (untracked). Only this manifest is
committed.

## Code fix commits referenced

| Commit | Branch | Summary |
|---|---|---|
| `f9bcfbe` | `mobile/android-reconnect-lifecycle-qa` | Re-pair reuses remembered `device_id` (`ConnectionPlanner.deviceIdForPairing`, `BridgeRepository.pairDiscoveredPc`); updates `UserMessages.REPAIR_NEEDED` copy; adds desktop pytest + Android unit test coverage |
| `e99e355` | `mobile/android-reconnect-lifecycle-qa` | Fixes a second, missed occurrence of the old "pairing code was rejected" copy in `strings.xml` (`repair_needed_body`, used by `PcFoundBottomSheet`) |

## APK builds

| SHA256 | Built | String-resource fix included? | Used for |
|---|---|---|---|
| `5100981e3773f86970b950fe35979391accdbce8094b7c763d8c41728edb9be1` | after `f9bcfbe` | No (Kotlin constant only) | Section B below |
| `9cf3178fcdeeda3c65c093380be0cbb8517d0b813a0a108000cc56aba472e934` | after `e99e355` | Yes | Section A below (final, authoritative) |

## Section A — Final fix verification (2026-07-02, 00:07–00:13, clean source, FINAL APK)

Desktop: `python app.py` from committed source at branch tip, restarted
fresh between phases (3 separate process runs). Phone: `pm clear` to a known
empty pairing state, then rebuilt/reinstalled APK (`adb install -r`,
SHA256 `9cf3178f...`). This is the **authoritative** evidence for the narrow
fix; Sections B–D are prior/supporting/superseded context.

| File | SHA256 | Proves | Test step | Source | Usable |
|---|---|---|---|---|---|
| `retest_01_fresh_launch.png` | `5779dd5052bb38a672705b9ee074db541102fb144845aff8f6fa9d8d328b1cce` | Fresh phone (no stored pairing) shows `NO_TOKEN` "Pair This Phone" sheet | 1. Pair once (baseline) | Clean | Yes |
| `retest_02_after_pair.png` | `e3ebc4db8ebae995133c841d30632a4025afeef5c8b616356a9bbe5099dfead5` | First-ever pairing succeeds, vault populates (231/257/155/10/184) | 1. Pair once | Clean | Yes |
| `retest_03_relaunch_after_desktop_restart.png` | `e289770d8a744b520400da8b2c16d6e4357aa87a4b5819f63ca61ff65c0608ab` | After desktop restart + phone relaunch, sheet shows `APPROVAL_REQUIRED` ("This phone remembers the pairing…") | 2–3. Restart desktop, reopen phone | Clean | Yes |
| `retest_04_connect_this_time_success.png` | `20be7517303716fa937f1275cf9eb4094a1c2037720abe34d3a5a83c69df37da` | **"Connect this time" succeeds after a real desktop restart, no Re-pair needed** — the core fix target | 4–5. Tap Connect this time, confirm connected without Re-pair | Clean | Yes |
| `retest_05_after_revoke.png` | `12d59cde586bc914ff9d7e3c41805e6c993e0d713dc47f8bb889ec3552d0eb5a` | Sheet reappears after force-stop/relaunch, before the auth call that will fail | 6. (pre-)Revoke check | Clean | Yes |
| `retest_06_revoke_rejected.png` | `5763aa4cce1f0d9899784fd2a09e84b55c1118000d99c2d452f01c8f601c3a7d` | Revoked device correctly rejected; top status line shows accurate "Device revoked — pair again on your PC"; sheet still had the **old** copy at this exact moment (pre string-resource fix rebuild) | 8–9. Revoke, confirm reconnect fails with correct message | Clean | Yes (also the artifact that caught the missed second string) |
| `retest_07_revoke_message_fixed.png` | `50910beb564511dee82029124aaf88fa37a257e9a611d7ef46a982b854de2729` | After rebuilding with `e99e355` and reinstalling, sheet now shows the accurate **"This PC no longer trusts this phone. Re-pair to continue."** | 9. Confirm correct repair-required message | Clean | Yes |
| `retest_08_after_repair_success.png` | `8d9917f984d813b0f246ad84666d2d85b9d5e56294d7b10f6943a43e0175f9b9` | Tapping Re-pair after revoke reconnects and repopulates the vault | 10. Re-pair succeeds | Clean | Yes |

**Server-side corroboration** (`%LOCALAPPDATA%\CacheVault\settings.json`,
read directly, not just inferred from screenshots):

- Before revoke: `device_id=04ff3a088a494cd9a3009768a5709614`, `created_at=00:08:04`, `last_seen_at=00:09:14` (after "Connect this time").
- After revoke: same record, `revoked_at` set.
- After Re-pair: **same** `device_id=04ff3a088a494cd9a3009768a5709614`, `created_at` refreshed to `00:12:51`, `revoked_at` cleared, `last_seen_at=00:12:56`, and the paired-devices list still holds exactly the same 2 entries as before (no duplicate created). This is direct proof of "reuses existing deviceId" and "refreshes credential, does not duplicate."

## Section B — Prior diagnostic reconnect test (2026-07-01, 23:06, clean source, pre-string-fix APK)

Run before Section A, immediately after the `device_id`-reuse code fix
(`f9bcfbe`) but before the `strings.xml` fix (`e99e355`) was discovered.
Confirms the underlying reconnect mechanism was already sound even without
the copy fix; superseded by Section A for completeness but not contradicted.

| File | SHA256 | Proves | Test step | Source | Usable |
|---|---|---|---|---|---|
| `reconnect_retest_01_fresh_restart.png` | `97e38edb0f6031091050baee943a11ee70effb14c95209b164292e3c91efe91c` | Discovery sheet after a real desktop restart | Diagnostic (pre-retest) | Clean | Yes |
| `reconnect_retest_02_after_connect_tap.png` | `02fdec617ba515f9d8c63c0be68083104a15fb8693c7f3f27040122346859032` | "Connect this time" succeeded against restarted desktop, vault populated (230/257/154/10/184) | Diagnostic (pre-retest) | Clean | Yes |

## Section C — Original live QA session (2026-07-01, 22:20–22:52, clean source, pre-fix APK)

This is the session that **discovered** the "Connect this time" failure and
the misleading copy. Kept as the historical record per instruction (not
deleted). The specific "Connect this time" FAIL from this session is
**superseded** by Section A's clean PASS on the fixed build — it is not
retracted as "didn't happen," but it no longer reflects current behavior.

| File | SHA256 | Proves | Test step | Source | Usable |
|---|---|---|---|---|---|
| `step3_01_launch.png` | `32e41a08ca5b52bbde4d9e8cbd0ab3312d3a3adf09c17dfb7eafaa0b3f6f53b9` | Approval prompt on reopen (Test 1 PASS) | Close/reopen | Clean (pre-fix) | Yes |
| `step3_03_after_not_now.png` | `385101ba1372df6a082d4230884e7301833fe99684ed7e64bae86053ecc2ac6d` | "Not now" leaves desktop/phone truthfully disconnected (Test 2 PASS) | Not now path | Clean (pre-fix) | Yes |
| `step3_07_after_connect_fixed.png` | `f034f0053cf27a039e6426b6ceecf08d943b9765a4e595639a1563bb2388354b` | Original "Connect this time" rejection ("the pairing code was rejected") — the defect this fix addresses | Connect this time (original FAIL) | Clean (pre-fix) | Yes — historical, superseded by Section A |
| `step3_12_after_repair_tap.png` | `26689067f06bdb08b098817de31dc147210a79a81339e59b87c9cf0761fa88e1` | Re-pair recovered the connection that night | Re-pair (original) | Clean (pre-fix) | Yes |
| `step3_15_keep_connected_toggled.png` | `db9a833d9e4e112bac49000f3d32c9dfb2fcd3500db39e23cfa7edd9dd164eb4` | Keep Connected toggle UI | Keep Connected | Clean (pre-fix) | Yes |
| `step3_16_after_allow.png` | `a2236d102a775383ef161f3daae5e70d8e6a177bb783e59f0671fb665a55f391` | Notification permission granted | Keep Connected | Clean (pre-fix) | Yes |
| `step3_17_notification_shade.png` | `b00a38763005c8613b64a03a53d32f8bcb1d7e9a5c0ed6b04222bce4d2d7f4ce` | Persistent foreground notification confirmed (Test 3 PASS) | Keep Connected | Clean (pre-fix) | Yes |
| `step3_18_toggle_off.png` / `step3_19_toggle_off_retry.png` | `78391fb6ac602eda2b61527767f151b6a4c18bbf2e402d63e2de902e7a2ee341` / `c420ef369d1250a89d249e0bac8b092916c217be5f67c2953af3ec577cd62e6d` | Toggle-off delayed ~29s (OS `Stop FGS timeout`), no crash | Keep Connected off | Clean (pre-fix) | Yes |
| `step3_00_current_state.png`, `step3_01b_recheck.png`, `step3_02_prompt_recheck.png`, `step3_04..06`, `step3_08..11`, `step3_13_settings_screen.png`, `step3_14_settings_screen2.png` | (not individually itemized) | Intermediate/retry captures during coordinate-correction and manual-setup mis-taps that night | Various (see run sheet) | Clean (pre-fix) | Supporting only |
| `desktop_step3_00_baseline.png` | `564314c585c2559107ba34413a9bdaf44261d70608fbf140376ff07f4b6366ea` | Desktop baseline, "Mobile: Paired (1)", no distinct online/offline indicator | Desktop UX finding | Clean (pre-fix) | Yes |
| `desktop_step3_01_after_not_now.png` | `28fc4c96a052dae6fd86409aff2ef3196997e0e6d2e4ff0e485a499bf6f1fa3d` | Desktop unchanged after "Not now" | Not now path | Clean (pre-fix) | Yes |
| `desktop_step3_02_full.png`, `desktop_step3_03_after_click_mobile.png`, `desktop_step3_04_try2.png`, `desktop_step3_05_try3.png` | all `bb1cb64257e0a538b214b67fec9eb270b50a8571d78aaeeda3889ba55a513809` (byte-identical, confirmed via SHA256) | Desktop window unchanged across the coordinate-correction retries that night — **not 4 independent observations** | Coordinate-correction retries | Clean (pre-fix) | Duplicate — only counts once |
| `desktop_step3_06_final_connected.png` | `c443a215d6c962f08c4ecfb9c9f310067e33fef0fb968ad1532701fd372acb50` | Desktop after the original Re-pair success | Re-pair (original) | Clean (pre-fix) | Yes |

## Section D — Pre-session / inconclusive evidence (not usable as proof)

| File | SHA256 | Status |
|---|---|---|
| `live_check.png` | `c99c9ad13ef1f32a457aadf1893d78a83a13dab0b692c959b891843e221e132a` | Byte-identical to `foreground_check.png`; predates confirmed clean-source Keep Connected pass; **not usable** |
| `foreground_check.png` | `c99c9ad13ef1f32a457aadf1893d78a83a13dab0b692c959b891843e221e132a` | Same as above; **not usable** |
| `cachevault_initial_retest.png`, `cachevault_ui_now.png`, `cachevault_scan_now.png`, `resume_check.png`, `repair_retry_screen.png`, `after_repair.png` | (individually hashed above, timestamps 17:54–21:00) | Pre-dates the confirmed clean-source runtime fix window; non-sequential; **not usable as current-behavior proof**, kept only for audit trail |
| `android_reconnect_logcat_2026-07-01.txt` | `a5ab090825d3ac5190439d066919a18bdd4087aec808081876f5b1c899207188` | Only covers 17:54–18:01; misses the entire 20:40–23:31 window where all real testing happened; **not usable** for the events described in this manifest |

## Test-state hygiene finding (confirmed)

The orphaned `device_id="phone-1"` / `device_name="Test Pixel"` record
repeatedly seen in `settings.json` was traced to the **pytest fixture
default** in `tests/test_mobile_bridge.py::_pair()` — confirmed by exact
string match. However, that fixture only ever touches an in-memory
`Settings()` object via the isolated `vault`/`mobile_bridge` fixtures in
`tests/conftest.py`; it never runs against the real
`%LOCALAPPDATA%\CacheVault\settings.json`, so automated pytest runs are
**not** the leak path.

None of the reviewed dev smoke scripts (`scripts/android_asset_smoke.py`,
`scripts/android_manual_pairing_smoke.py`, `scripts/restore_phone_pairing.py`,
`scripts/rc_gate.py`, `scripts/pairing_hot_reload_smoke.py`,
`scripts/android_share_inbox_smoke.py`, `scripts/companion_ui_polish_screenshots.py`)
default to `device_id="phone-1"` either (they use `"pixel-live"`,
`"manual-pair-gate"`, `"rc5-gate-phone"`, `"share-gate-phone"`, etc.). Several
of them (`android_asset_smoke.py::fresh_pair()`) do intentionally call
`Settings.load()`/`.save()` against the **real** production settings path —
by design, since their purpose is smoke-testing against a real running
`CacheVault.exe`/phone. That is a legitimate, if noisy, use of the real
settings file for local dev tooling, not a bug; no code change was made to
these scripts as part of this narrow fix.

A second, fresh `"phone-1"` record (new `created_at`) appeared in the real
`settings.json` mid-session, replacing the entire `paired_devices` array.
Every production code path was checked (`cache_vault/ui/mobile_dialogs.py`'s
"Generate Fresh Pairing Code" dialog uses `models.new_id()` — a real UUID,
never `"phone-1"`) and ruled out. No scheduled automation was found
(`CronList` returned none). The most plausible explanation is manual
interaction with the live desktop GUI window that was open on the operator's
machine during testing. It is harmless (an inert, ignorable extra record)
and does not affect the correctness of the fix or any result in this
manifest — every check above was re-verified directly against
`settings.json`, not inferred from screenshots alone.

## What this manifest does not claim

- Does not certify the Android reconnect lane as fully "reliable" for
  release — only that the specific defect found in Section C is fixed and
  re-verified live in Section A.
- Does not update `/proof`, does not publish the APK, does not merge into
  desktop `rc4`/`rc5`.
- Keep Connected's ~29s toggle-off delay (Section C) remains an open,
  non-blocking observation, not addressed by this fix.
- The desktop's lack of a distinct online/offline indicator (only "Mobile:
  Paired (N)") remains an open UX finding, not addressed by this fix.
