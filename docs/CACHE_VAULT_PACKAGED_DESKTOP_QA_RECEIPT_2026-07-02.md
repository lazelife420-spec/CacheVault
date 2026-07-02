# Cache Vault Packaged Desktop QA Receipt

Date: 2026-07-02

## Scope

- Branch: `release/v0.1.4-public-distribution`
- Commit under test: `83b6166`
- Artifact under test: `dist\CacheVault.exe`
- Final verdict: `PASS / INTERNAL_QA_ONLY`

## Hard rules still in force

- Do not publish.
- Do not update `/proof`.
- Do not call this stable.

## Fresh artifact custody

- Confirmed the repo was on `83b6166` before packaging.
- Found stale packaged runtime processes already running from `dist\CacheVault.exe`.
- Stopped all running `CacheVault.exe` processes before rebuild.
- Deleted the pre-existing `dist\CacheVault.exe` before rebuild.
- Previous EXE SHA256: `A8E91718E99E7796A8EA3CE946D6B2786F9FBAD7A4A46207EAF0DCFF4A8564B7`
- Previous EXE modified time: `2026-07-02T15:03:53.9050157-07:00`
- Rebuilt from source with `pwsh packaging\build_exe.ps1`.

## Fresh packaged artifact

- Path: `C:\Users\KickA\Desktop\CacheVault\dist\CacheVault.exe`
- SHA256: `43096DE565D6F14735D64F4F093641ECA00D5BAF22B86FDB7577B31AEA81F191`
- Size: `43177099` bytes
- Modified time: `2026-07-02T15:21:46.1784804-07:00`

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
  - `qa_artifacts\packaged_qa_2026-07-02_home.png`
  - `qa_artifacts\packaged_qa_2026-07-02_home_printwindow.png`
  - `qa_artifacts\packaged_qa_2026-07-02_mobile_access.png`
  - `qa_artifacts\packaged_qa_2026-07-02_sidebar_scrolled.png`
  - `qa_artifacts\packaged_qa_2026-07-02_sidebar_after_drag.png`
  - `qa_artifacts\packaged_qa_2026-07-02_sidebar_page_down.png`
  - `qa_artifacts\packaged_qa_2026-07-02_mobile_chip_dropdown.png`
  - `qa_artifacts\packaged_qa_2026-07-02_mobile_chip_click.png`
  - `qa_artifacts\packaged_qa_2026-07-02_remax.png`
- The packaged GUI visibly reported paired-device state in the top status chip (`Mobile: Paired (...)`) during the pass.
- Direct packaged navigation to the sidebar `Mobile Access` screen was only partially automatable in this environment because the packaged window relaunched at a smaller size and the sidebar scroll behavior was unreliable under the window-driving harness.

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
  - Desktop mobile inbox count increased from `36` to `37`.
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
- This verifies on current source, which was the exact source rebuilt into the packaged EXE:
  - `Mobile Access` screen exposes `Paired Devices`
  - `Pair Android Device` remains reachable
  - Per-device statuses render for:
    - `Online`
    - `Offline`
    - `Waiting for phone approval`
    - `Revoked`

## Local settings evidence after packaged-device QA

- `%LOCALAPPDATA%\CacheVault\settings.json` recorded packaged-EXE pairings and live `last_seen_at` updates for:
  - `hot-reload-smoke-phone`
  - `share-gate-phone`

## Conclusion

This pass proved that a freshly rebuilt packaged desktop from `83b6166` behaves like the source-tested runtime for the key Windows-user-facing mobile lane: the EXE was rebuilt from scratch, passed packaged selftest and founder smoke, accepted a real Android pairing, and still handled Send-to-PC end-to-end.

This receipt is a packaged QA receipt only. It is not a publish receipt, not a `/proof` update, and not a stable claim.
