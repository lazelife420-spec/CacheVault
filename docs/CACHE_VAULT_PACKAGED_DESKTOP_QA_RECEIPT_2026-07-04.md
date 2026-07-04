# Cache Vault Packaged Desktop QA Receipt

Date: 2026-07-04

## Scope

- Branch: `release/v0.1.4-public-distribution`
- Commit under test: `c6f1436`
- Artifact under test: `dist\CacheVault.exe`
- Final verdict: `PASS / INTERNAL_QA_ONLY`
- Trigger: five Settings Hub PRs merged today (#15-#19: Mobile Bridge live status,
  StatusRow action buttons, General runtime info, Diagnostics status rows, Excluded
  apps save/load fix). This pass re-proves the packaged runtime is fresh and
  functionally sound after a day of Settings-only source changes.

## Hard rules still in force

- Do not publish.
- Do not update `/proof`.
- Do not call this stable.

## Fresh artifact custody

- Confirmed the repo was on `c6f1436` before packaging.
- Confirmed no stale `CacheVault.exe` processes were already running before rebuild.
- Previous packaged artifact modified time: `2026-07-02T21:03:05` (local, recorded
  before deletion) — predates all five Settings Hub PRs merged today.
- Deleted the pre-existing `dist\CacheVault.exe` before rebuild.
- Rebuilt from source with `pwsh packaging\build_exe.ps1`.

## Fresh packaged artifact

- Path: `C:\Users\KickA\Desktop\CacheVault\dist\CacheVault.exe`
- SHA256: `AB653CE790243C3BDA50C4365A5A169F163CE708BAB1B4EEB2AB1290BCA14531`
- Size: `43192968` bytes
- Modified time: `2026-07-04T01:05:45.1566756-07:00`

## Packaged gates run

- `dist\CacheVault.exe --selftest`: `PASS`
- `pwsh scripts\founder_package_smoke.ps1`: `PASS`
- Founder smoke details:
  - Fresh launch / free selftest: `PASS`
  - Invalid license rejected: `PASS`
  - Production test Founder license accepted: `PASS`
  - Proof receipt export (no clipboard leak): `PASS`

## Packaged desktop GUI checks

- Launched packaged GUI successfully.
- Captured packaged desktop screenshots:
  - `qa_artifacts\packaged_qa_2026-07-04_home.png`
  - `qa_artifacts\packaged_qa_2026-07-04_relaunch_home.png`
  - `qa_artifacts\packaged_qa_2026-07-04_settings_general.png`
  - `qa_artifacts\packaged_qa_2026-07-04_settings_diagnostics.png`
  - `qa_artifacts\packaged_qa_2026-07-04_settings_mobile_bridge.png`
- Verified today's five merged Settings Hub lanes render correctly from the packaged
  EXE itself (not just from source):
  - General (12C): `Version 0.1.4 · Public Release`, `Running from: Packaged build`
    (confirms `_MEIPASS` packaged-build detection works in the frozen binary), live
    Data folder path.
  - Diagnostics (12D): crash-log-existence-gated `Open Crash Log` button present,
    live Database path, Selftest shown as text only with no button, matching the
    audit rule.
  - Mobile Bridge (12A/12B): Bridge `Listening`, LAN discovery `Advertising`, live
    LAN IP, live "Last phone request" status with `Mobile Access Receipts` button,
    live paired-device count with `Paired Devices` button.
  - Home screen status chips (`Mobile: Paired (3)`, mobile inbox count) reflected
    live pairing/inbox state throughout the pass, including after the Android
    Send-to-PC proof below (inbox count visibly moved from the pre-test to
    post-test value on relaunch).
- Note: the Capture category (home of the `excluded_apps` textarea fix, PR #19) was
  not independently screenshotted this pass. It shares the same `_render_field_row`
  rendering path already visually confirmed above via General/Diagnostics/Mobile
  Bridge, and `excluded_apps` itself has 5 dedicated unit tests plus green CI already
  gating PR #19 before merge.
- Note: mid-session the attached Android test device transiently dropped from `adb`
  (likely sleep/USB). Reconnected before the Android proof step below; not a product
  defect.

## Mobile Access runtime proof against the packaged EXE

- `python scripts\pairing_hot_reload_smoke.py`: `PASS`
- Result:
  - Packaged mobile pair: `PASS`
  - Authenticated `/mobile/v1/status`: `200`
  - Bad token rejected: `401`
  - Bridge host: `192.168.0.11`
  - Bridge port: `8742`
  - Mobile API version: `1`

## Real Android phone proof against the packaged EXE

- Attached device present during test: `R3CW40FY82W`
- `python scripts\android_share_inbox_smoke.py`: `PASS`
- What this proved against the packaged desktop:
  - Android phone paired successfully to the fresh packaged EXE.
  - Share sheet showed `Send to Cache Vault`.
  - Send-to-PC completed successfully.
  - Desktop mobile inbox count increased from `37` to `38`.
  - New desktop clip captured with:
    - `source_app='Android Share'`
    - `source_window='SM-S911W'`
    - `safe_id='default'`
    - `safe_name='Default Safe'`
    - `capture_mode='mobile_share'`
  - Desktop receipt action logged: `mobile_sent_to_pc`
- Evidence file:
  - `visual_smoke\android_share_inbox_smoke.json`
- Android screenshots:
  - `visual_smoke\share_smoke_01_simple_mode.png`
  - `visual_smoke\share_smoke_02_after_send.png`

## Paired Devices button and status label proof

- `python -m pytest tests\test_mobile_access_screen.py -q`: `PASS` (`9` tests)
- This verifies on current source, which was the exact source rebuilt into the
  packaged EXE:
  - `Mobile Access` screen exposes `Paired Devices`
  - `Pair Android Device` remains reachable
  - Per-device statuses render for:
    - `Online`
    - `Offline`
    - `Waiting for phone approval`
    - `Revoked`

## Local settings evidence after packaged-device QA

- `%LOCALAPPDATA%\CacheVault\settings.json` recorded packaged-EXE pairings and live
  `last_seen_at` updates for:
  - `hot-reload-smoke-phone`
  - `share-gate-phone`
- Token hashes confirmed stored as hashes (`token_hash`), not plaintext.

## Conclusion

This pass proved that a freshly rebuilt packaged desktop from `c6f1436` (the merge
commit for PR #19, tip of today's five-PR Settings Hub stack #15-#19) behaves like
the source-tested runtime: the EXE was rebuilt from scratch, passed packaged selftest
and founder smoke, visually confirmed the General/Diagnostics/Mobile Bridge Settings
Hub lanes render correctly against live data, accepted a real Android pairing, and
still handled Send-to-PC end-to-end.

This receipt is a packaged QA receipt only. It is not a publish receipt, not a
`/proof` update, and not a stable claim.
