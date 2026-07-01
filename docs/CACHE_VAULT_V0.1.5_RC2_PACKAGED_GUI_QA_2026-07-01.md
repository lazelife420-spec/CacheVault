# Cache Vault v0.1.5-rc2 — Packaged GUI QA

**Date:** 2026-07-01
**Version:** 0.1.5-rc2 (Release Candidate)
**Runner:** `scripts/verify_packaged_gui_run_rc2.py`
**Target exe:** extracted from the R2 artifact at `%TEMP%\cv_rc2_smoke\extracted\CacheVault.exe`
**Extracted exe SHA256:** `df74b78862fae5e7a697ff0b191900d01b349d3404342a2721579c22e47b4a8a`

## Method

1. Downloaded and SHA-verified the public R2 ZIP (see R2 install smoke receipt).
2. Extracted `CacheVault.exe`.
3. Seeded a fresh temp profile DB with three clips (text, R2 link, PNG screenshot); confirmed clip count in DB = **3**.
4. Set `first_use_guide_dismissed = true` in the temp profile so the main Command Center is captured (not the onboarding overlay).
5. Launched the packaged exe against that profile, waited for render, captured a window screenshot, then terminated.

## Result

Runner report: `ok: true`, screenshot saved.

Screenshot: `visual_smoke/v0.1.5_rc2_packaged_gui_qa.png`

Observed in the packaged rc2 UI:

- Title bar: **Cache Vault™ — A Proof Foundry product**
- Toolbar: Capture: On · **Mobile: Off** · Receipts: Stamping · Default Safe: default · Lock Now · Export / Save As · Stamped Receipts
- Command Center header + "Local Vault Active" panel: `Local-first · Capture Active · Receipts Available · **Mobile Access off**`
- Stats line: **3 saved · 2 safes · 7 receipts · 0 exports · 0 editable copies · 0 HTML bundles · 0 mobile inbox**
- Custody Summary: All Clips **3**, Favorites 0, Screenshots **1**, Links **1**
- No crash; clean shutdown

## Checks

| Check | Result |
|---|---|
| Packaged exe launches and renders | **PASS** |
| Seeded clips visible (All Clips = 3) | **PASS** |
| Screenshot/image clip counted (Screenshots = 1) | **PASS** |
| Link clip counted (Links = 1) | **PASS** |
| Mobile Access OFF by default (packaged build) | **PASS** |
| No crash / clean terminate | **PASS** |

## Verdict

**PASS.** The publicly downloaded, SHA-verified rc2 build launches and renders the full Command Center with seeded data and Mobile Access off.

## Caveats

- Onboarding guide was intentionally dismissed for this capture to expose the main window; first-run onboarding itself was separately observed rendering correctly.
- Crash instrumentation is visibility only, not a proven fix.
- Not published to `/proof`; not tagged stable.
