# Cache Vault v0.1.5-rc2 — Release Notes

**Status:** Release Candidate (not final public release)
**Base:** v0.1.5-rc1 (frozen; not mutated)
**Branch:** `ux/mobile-image-polish-local`
**Date:** 2026-07-01

---

## Why rc2

Private soak of rc1 surfaced an intermittent crash and UX gaps. Crash triage
found that the previously logged crash signatures were already fixed in rc1, but
the soak crash was not captured because worker-thread exceptions were not logged.
rc2 makes future crashes visible and ships narrow, safe polish. This does not
prove the intermittent crash is fixed; it makes a recurrence loggable for
diagnosis during rc2 soak.

## What's New in rc2

### Stability / crash visibility
- Worker-thread exceptions (mobile bridge, mDNS discovery, hotkey listener,
  foreground tracker) are now written to crash.log via `threading.excepthook`.
- `report_callback_exception` has a re-entrancy guard so a crash storm records
  once instead of flooding crash.log.

### Screenshots
- Clear "Export Screenshots to Folder…" action (bulk and single image),
  reusing the existing save logic. Empty views and missing asset files are
  handled safely; a receipt is written.

### Context-menu honesty
- Removed the dead "View Proof" no-op from the image menu and action strip.

### Mobile pairing safety
- Pairing dialog shows screenshot-safe and revoke guidance; the token stays
  hidden by default. "Revoke All Devices" remains available.

## Test Proof

| Gate | Result |
|---|---|
| `pytest -p no:cacheprovider` | **789 passed, 0 skipped** |
| `python -m compileall cache_vault` | **PASS** |
| `python app.py --selftest` | **PASS** |

New tests: fresh-profile bridge-OFF proof, worker-thread crash logging,
`report_callback_exception` re-entrancy guard, single-image folder-export action
presence, removal of the dead "View Proof" item.

## Holds

- Not yet published to Proof Foundry `/proof`.
- No public hash until the package artifact is built and verified.
- rc1 remains frozen: not mutated, rebuilt, or re-uploaded.
- QR pairing is planned only (phone cannot scan yet); not implemented.
- No git tag / no publish until the RC gate passes and the user approves.

## Planning / Audit Docs

- `docs/CACHE_VAULT_V0.1.5_RC2_STABILIZATION_TRIAGE_2026-07-01.md`
- `docs/MOBILE_PAIRING_QR_FLOW_PLAN_2026-07-01.md`
- `docs/CACHE_VAULT_UI_CONSISTENCY_AUDIT_2026-07-01.md`
- `docs/CACHE_VAULT_SCREENSHOTS_BULK_WORKFLOW_AUDIT_2026-07-01.md`
