# Cache Vault v0.1.5-rc3 — Release Notes

**Status:** Release Candidate / diagnostic soak build (not final; not published to /proof)
**Base:** v0.1.5-rc2 (frozen; not mutated)
**Branch:** `ux/mobile-image-polish-local`
**Date:** 2026-07-01

---

## Why rc3

An rc2 soak crash occurred during normal use (while screenshotting the app) but
left **no** entry in crash.log. rc2's handler only captured uncaught *Python*
exceptions; an interpreter-fatal / native fault (Tcl/Tk C-level, image layer,
segfault) leaves no Python traceback, and in a windowed build there is no
console either. rc3 closes that gap so the next occurrence is recorded.

This is diagnostic instrumentation. **The intermittent crash is not yet
root-caused or fixed** — rc3 exists to capture it.

## What's New in rc3

### Built-in crash handler
- Armed first in the launch path, before any UI import can fault.
- Four channels:
  - `sys.excepthook` — uncaught main-thread Python errors → `crash.log`
  - `threading.excepthook` — worker-thread Python errors → `crash.log`
  - Tk `report_callback_exception` (re-entrancy guarded) → `crash.log`
  - **`faulthandler` (new)** — native/fatal faults (Tcl/Tk, segfault, abort),
    per-thread C traceback written to a raw fd → `crash_native.log`

## Crash logs

- `%LOCALAPPDATA%\CacheVault\crash.log` — Python-level crashes
- `%LOCALAPPDATA%\CacheVault\crash_native.log` — native/fatal crashes (new)

## Test Proof

| Gate | Result |
|---|---|
| `pytest -p no:cacheprovider` | **790 passed, 0 skipped** |
| `python -m compileall cache_vault` | **PASS** |
| `python app.py --selftest` | **PASS** |

## Holds

- Not uploaded to R2; not tagged; `/proof` untouched; landing pages untouched.
- rc1 and rc2 remain frozen.
- Local diagnostic build for private soak only.
