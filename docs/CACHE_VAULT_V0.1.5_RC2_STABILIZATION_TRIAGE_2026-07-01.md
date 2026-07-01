# Cache Vault v0.1.5-rc2 Stabilization Triage

Date: 2026-07-01
Status: Planning + crash-visibility hardening. rc1 is frozen and unchanged.

Constraints honored: rc1 not mutated/rebuilt/re-uploaded; Proof Foundry /proof
and public landing pages untouched; nothing published; scope kept tight.

## 1. Crash triage result

Source of truth: `%LOCALAPPDATA%/CacheVault/crash.log` (663 KB, 72 blocks). The
recurring logged signatures, most recent 2026-06-29, were:

| Signature | Count | Status in current source |
|---|---|---|
| `RecursionError` selection loop (set_selected <-> clear_selection <-> shell) | 6 | Fixed. `_guard_selection` reentrancy guard in `home_dashboard.py` + shell skips `set_selected` on FILTER_HOME. |
| `AttributeError: 'ClipList' object has no attribute 'see'` | 100 | Fixed. `_safe_see()` try/except in `clip_list.py` / `clip_grid.py`. |
| `TclError: No more menus can be allocated` | 17 | Fixed. `popup_menu()` destroys menus in a finally block (`clip_context.py`). |
| batch toolbar `... isn't packed` | ~8 | Fixed. Refactored to `_batch_toolbar_host`. |
| `brand.TEXT_COLOR` missing | 8 | Fixed. No current reference. |
| packaged icon `bitmap not defined` (startup) | ~10 | Startup-only, non-fatal. |

Key finding: **all six recurring signatures are already fixed in the current
source, and those fixes shipped in the frozen rc1 build** (verified in commit
`cabf8c1`). The crash.log has **no entries during the 2026-06-30 -> 07-01 soak
window**, even though the app ran (receipts dated 07-01). So the intermittent
soak crash was **not captured** by crash logging.

Root cause of the visibility gap: `crashlog.install_global_hook()` installed only
`sys.excepthook` (main thread). Worker threads (mobile bridge `serve_forever`,
mDNS discovery, command-hotkey listener, foreground-window tracker) raise into a
default handler that, in a windowed packaged build with no console, is invisible
and leaves no crash.log entry. A cross-thread fault or a deep RecursionError
storm can also abort before clean logging.

### Fix applied this lane (safe, rc2-appropriate, blocker-first)

1. `cache_vault/ui/crashlog.py`: also install `threading.excepthook` so
   background-thread exceptions are written to crash.log with the thread name.
2. `cache_vault/ui/shell.py` `report_callback_exception`: add a `_reporting_crash`
   re-entrancy guard so a crash storm (e.g. RecursionError re-entering a Tk
   callback) records once instead of recursing through the dialog path and
   flooding crash.log (which is what bloated it to 663 KB).

Verification: `python app.py --selftest` passes; full `pytest` suite passes
(100%); `threading.excepthook` confirmed installed.

### Still required (manual, cannot be done headlessly here)

Run the packaged EXE with stdout/stderr captured and exercise: Settings Hub,
Mobile Access, Pair Device dialog, Screenshots/Images, right-click menus, image
preview, window close/reopen, bridge enable/disable. With the new thread hook in
place, any recurrence during rc2 soak will now land in crash.log with a thread
name and a single (non-flooded) traceback for diagnosis.

## 2. Security note (private soak screenshots)

Private soak screenshots showed pairing token/passkey information. Reminder:
- Revoke devices or generate a fresh token after testing
  ("Revoke Old Phone + Fresh Pair" / Revoke All in the pairing dialogs;
  desktop `revoke_all_active`).
- Do not use token-visible screenshots publicly.
- The pairing dialog already hides the token by default; keep it hidden and add
  screenshot-safe hiding of the token/QR region (tracked in the QR flow plan).

## 3. Recommended rc2 fix list

Must fix (blocker):
- [x] Crash visibility: worker-thread exceptions + re-entrant crash guard
  (applied this lane). Re-soak to confirm no un-logged crash remains.

Should fix (tight, rc2-safe):
- [ ] Remove dead context-menu items (e.g. "View Proof" no-op) so only
  implemented actions show.
- [ ] Expose "Export Screenshots to Folder..." clearly (reuse `bulk_save_images`;
  add single-clip entry + post-save "Open folder").
- [ ] Hide pairing token by default everywhere + screenshot-safe hiding.
- [ ] Confirm fresh install has Mobile Bridge OFF by default (soak checklist
  item; verify, do not assume).
- [ ] Visual-only UI polish toward the Settings Hub baseline: unify
  section-header style, card radius/fill, dashboard spacing; plain-language +
  Advanced-collapse on Mobile Access.

Should NOT do yet:
- Full app redesign or dashboard rewrite.
- QR pairing end to end (phone cannot scan yet; see QR flow plan).
- New cloud/sync system.
- Any public promotion or Proof Foundry /proof update.

## 4. Companion documents

- `docs/MOBILE_PAIRING_QR_FLOW_PLAN_2026-07-01.md`
- `docs/CACHE_VAULT_UI_CONSISTENCY_AUDIT_2026-07-01.md`
- `docs/CACHE_VAULT_SCREENSHOTS_BULK_WORKFLOW_AUDIT_2026-07-01.md`
