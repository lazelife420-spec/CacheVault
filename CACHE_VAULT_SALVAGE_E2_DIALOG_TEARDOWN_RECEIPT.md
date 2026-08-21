# Cache Vault — Salvage E2 Receipt — Dialog Teardown Race

**Date:** 2026-08-20
**Gate:** CACHE VAULT SALVAGE E2 — DIALOG TEARDOWN RACE
**Branch:** `fix/dialog-teardown-race-e2`
**Scope:** the second-ranked audit item, its own isolated gate from canonical `master@f592e47` (post-E1).

## Provenance

| | |
|---|---|
| Canonical parent | `f592e479e4af6deac536282a585e2b3c73f65e6c` (`master`, post Salvage E1, unchanged throughout this gate) |
| Historical custody SHA | `preservation/pre-gate5f-dirty-2026-08-20` → `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f` (referenced for provenance only; not merged, cherry-picked, or reapplied — the fix was independently designed and re-derived from first principles, arriving at the same two-part mechanism as the historical candidate after verifying each piece was actually necessary) |
| Prior audit disposition | `VALID SALVAGE CANDIDATE`, item B1, score 85/100 — `CACHE_VAULT_POST_CANONICAL_DIRTY_TREE_SALVAGE_AUDIT.md` |
| Final candidate SHA | `2884463d93fde57572d04bc28bbb1a4fedddd3be` on `fix/dialog-teardown-race-e2` |

## Affected dialog/helper paths — complete call-site inventory

`_bring_to_front` (`cache_vault/ui/dialogs.py`) is called from **13 sites across 12 dialog classes**. Every site was individually traced for whether its class overrides `destroy()` with a staged (async) teardown — the precondition for the race to be reachable at all.

| # | Call site | Class | `destroy()` override? | Vulnerable? |
|---|---|---|---|---|
| 1 | `dialogs.py:122`* | `AboutDialog` | No (synchronous default) | No |
| 2 | `dialogs.py:507`* | `SettingsDialog` | No | No |
| 3 | `dialogs.py:661`* | inline `help_win` helper (inside `SettingsDialog`) | No — closed via `command=help_win.destroy` | No |
| 4 | `dialogs.py:916`* | `SafePickerDialog` | No — also separately schedules its own `after(20, self._focus_popup)` with an equivalent deiconify/lift/focus_force/grab_set sequence; both are synchronous-safe for the same reason | No |
| 5 | `dialogs.py:1017`* | `MoveToCollectionDialog` | No | No |
| 6 | `dialogs.py:1072`* | `ExportViewDialog` | No | No |
| 7 | `dialogs.py:1172`* | `EventLogDialog` | No | No |
| 8 | `dialogs.py:1382`* | `PermanentDeleteSelectedDialog` | No | No |
| 9 | `dialogs.py:1425`* | `PermanentDeleteAllDialog` | No | No |
| 10 | `dialogs.py:1564`* | `ClearAllClipsDialog` | No | No |
| 11 | `clip_workflows.py:143` | `ClipComposerDialog` | **Yes** — `withdraw()` immediately, `super().destroy()` deferred 50ms | **Yes** |
| 12 | `clip_workflows.py:365` | `EditClipTextDialog` | **Yes** — identical staged pattern | **Yes** |
| 13 | `clip_workflows.py:502` | `MultiLinkPasteDialog` | No | No |

*Line numbers as of the pre-fix commit (`f592e47`); the fix adds lines above `_bring_to_front`, shifting everything below it in `dialogs.py` by ~20.

**Why synchronous-destroy classes are provably safe without a fix:** for any of the 10 unstaged classes, if `destroy()` runs before the deferred `_raise()` fires, `super().destroy()` (the real, only teardown step) has already fully removed the underlying Tcl widget by the time `_raise()` executes. `win.deiconify()` on a genuinely-destroyed widget raises, and `_raise()`'s own pre-existing `try/except Exception: pass` catches it — no visible re-show, no error. The race is possible *only* for a dialog whose teardown is deliberately staged across two points in time, creating a window where the widget is hidden (`withdraw()`) but not yet gone.

**`FirstUseGuideDialog` precedent, inspected and deliberately not copied:** `cache_vault/ui/first_use_guide.py` already fixed a related-but-different bug class — CustomTkinter's own internal deferred callbacks (titlebar-color workaround, titlebar-icon workaround) raising uncaught `"invalid command name"` errors when they fire against an already-destroyed widget, including under **Tcl-level cascaded destruction** (a parent window destroyed while this dialog's callbacks are still pending — a scenario where a Python-level `destroy()` override never runs at all, documented there as "issue #78"). Its fix binds `<Destroy>` (fires for any teardown path, cascade included) and tracks every scheduled job in a general `_pending_after_ids` set. That mechanism is not needed here: `_bring_to_front`'s `_raise()` already self-protects with a broad `try/except`, so it cannot raise an uncaught error under cascade the way `FirstUseGuideDialog`'s raw internal callbacks could — and the `winfo_exists()` half of this fix's guard independently covers the cascade case (the widget is genuinely gone by the time `_raise()` runs, `_closing` or not). The smaller fix below is the correct minimum for this specific invariant, not a shortcut around the precedent.

## Failing-before reproduction

Both regression files were written and run against unmodified `dialogs.py`/`clip_workflows.py` **before any production code was touched**.

**Deterministic (fake scheduler), `tests/test_dialog_bring_to_front_teardown_race.py`:**
```
tests\test_dialog_bring_to_front_teardown_race.py .FF...   [100%]
E   AssertionError: ... called: ['deiconify', 'lift', 'focus_force', 'grab_set']
2 failed, 4 passed in 0.38s
```
`test_raise_must_not_reshow_a_window_mid_staged_teardown` and `test_raise_must_not_reshow_an_already_destroyed_window` both failed, reproducing the exact defect via direct control flow (a fake `win` records real re-show calls, with `_closing`/`winfo_exists()` set by the test, not by wall-clock timing).

**Real-Tk, `tests/test_clip_workflows_bring_to_front_race.py`, through the actual `EditClipTextDialog` close path:**
```
tests\test_clip_workflows_bring_to_front_race.py F.   [100%]
E   AssertionError: ... but saw: ['deiconify', 'deiconify', 'lift', 'focus_force', 'grab_set']
1 failed, 1 passed in 1.67s
```
`destroy()` scheduled at 180ms after construction (inside the 150–200ms vulnerable window), pumped past both `_raise()`'s 200ms mark and `_finalize_destroy`'s 230ms mark, against the real, unmodified widget and the real Tk event loop.

## Root cause

`_bring_to_front`'s `win.after(200, _raise)` is unconditional. `_raise()` has no awareness of whether the window it targets has begun tearing down. For the two staged-destroy dialogs, a `destroy()` call landing in the ~50ms gap between `withdraw()` and the real `super().destroy()` leaves the widget in a state (`winfo_exists() == True`, logically closing) that `_raise()` cannot distinguish from "still fully open" — so it proceeds to reshow and (for modal dialogs) re-grab it.

## Exact fix

**`cache_vault/ui/dialogs.py`** — `_raise()` now returns immediately if the window no longer exists or has begun closing:
```diff
     def _raise() -> None:
         try:
+            if not win.winfo_exists() or getattr(win, "_closing", False):
+                return
             if center_on is not None:
```
`getattr(win, "_closing", False)` is inert (always `False`) for the 10 classes that never set `_closing` — confirmed by the `AboutDialog` control test below, not merely assumed. `_bring_to_front` also now records the scheduled job:
```diff
-    win.after(200, _raise)
+    win._bring_to_front_job = win.after(200, _raise)
```

**`cache_vault/ui/clip_workflows.py`** — both `ClipComposerDialog.destroy()` and `EditClipTextDialog.destroy()` cancel that job at the start of teardown, matching the existing guarded-`try/except` idiom already used for every other "may already be gone" step in these methods:
```diff
         self._closing = True
+        try:
+            job = getattr(self, "_bring_to_front_job", None)
+            if job is not None:
+                self.after_cancel(job)
+        except Exception:  # noqa: BLE001 - job may have already fired
+            pass
         try:
             self.grab_release()
```

**Why both pieces, not just one:** the `winfo_exists()`/`_closing` guard in `_raise()` is the actual correctness guarantee — it holds even if cancellation loses a narrow race against an already-dispatched Tcl event (Python is single-threaded against the Tk event loop, so `_closing = True` is set synchronously at the very start of `destroy()`, before any queued `_raise()` invocation gets a chance to run its body — the guard cannot be bypassed by timing). The cancellation is a courtesy on top of that: it prevents a harmless-but-wasted pending callback (and the dangling reference to `win` it holds) from sitting in Tk's after-queue until its scheduled time, satisfying "no leaked pending callbacks" in a way a test can actually verify (confirmed via `test_cancelling_the_job_before_it_fires_leaves_no_pending_callback`), rather than relying on an unobservable guard-then-noop.

## Passing-after invariants (A–J)

All run against the fixed `dialogs.py`/`clip_workflows.py`, `tests/test_dialog_bring_to_front_teardown_race.py` (9 tests, deterministic) + `tests/test_clip_workflows_bring_to_front_race.py` (3 tests, real-Tk):

| Invariant | Test | Result |
|---|---|---|
| A. scheduled bring-to-front still works on a live dialog | `test_raise_still_works_normally_on_a_live_dialog`, `test_normal_bring_to_front_still_raises_a_live_dialog` (real-Tk) | **PASS** |
| B. closing dialog prevents deferred re-show | `test_raise_must_not_reshow_a_window_mid_staged_teardown` | **PASS** |
| C. closing dialog prevents deferred lift/focus | (same test — asserts the full call list is empty, not just `deiconify`) | **PASS** |
| D. closing dialog prevents deferred grab_set | (same test) | **PASS** |
| E. pending callback is cancelled or rendered inert | `test_cancelling_the_job_before_it_fires_leaves_no_pending_callback` | **PASS** |
| F. repeated close is safe/idempotent | `test_repeated_destroy_calls_are_idempotent` (existing, `test_edit_clip_text_lifecycle.py`) — re-run against this fix | **PASS** |
| G. cancelling an already-fired/nonexistent job is safe | `test_cancelling_an_already_fired_or_nonexistent_job_is_safe` | **PASS** |
| H. no pending callback leak remains after teardown | `test_cancelling_the_job_before_it_fires_leaves_no_pending_callback`, `test_bring_to_front_records_a_cancellable_job_id` | **PASS** |
| I. affected clip-workflow dialog closes normally | `test_destroy_during_the_staged_teardown_window_leaves_the_dialog_gone` (real-Tk, asserts `winfo_exists()` is False after) | **PASS** |
| J. unrelated dialogs using `_bring_to_front` still behave normally | `test_unrelated_synchronous_destroy_dialog_still_behaves_normally` (real-Tk, `AboutDialog`) + `test_raise_still_works_normally_for_non_modal_dialogs`, `test_repeated_legitimate_bring_to_front_calls_each_still_work` | **PASS** |

## Runtime smoke evidence

`tests/test_clip_workflows_bring_to_front_race.py` **is** the requested "open affected dialog → trigger close quickly → allow the event loop to run past the original delayed callback time → prove it remains closed and produces no error" smoke — run against a real `tk_root`, a real `EditClipTextDialog`, and the real Tk event loop via `_pump()`, not a mock. It is not the primary proof (the deterministic fake-scheduler tests are authoritative, per the gate's own instruction), but it independently confirms the deterministic model matches real widget behavior. Additionally confirmed by direct instrumentation during test development: the one `deiconify()` call CustomTkinter's own construction-time window-draw cycle makes fires at ~0.1ms after construction — verified unrelated to the race, not filtered away by assumption.

## All test results

| Suite | Result |
|---|---|
| `tests/test_dialog_bring_to_front_teardown_race.py` (new, deterministic) | **9 passed** (post-fix); 2/6 failed with the reproduced defect pre-fix |
| `tests/test_clip_workflows_bring_to_front_race.py` (new, real-Tk) | **3 passed** (post-fix); 1/2 failed pre-fix |
| Full relevant dialog/lifecycle/modal surface — `test_combine_dialog_lifecycle.py`, `test_ctk_textbox_scrollbar_teardown.py`, `test_dialog_placement.py`, `test_dialogs.py`, `test_first_use_guide.py`, `test_first_use_guide_titlebar_teardown.py`, `test_macro_dialogs.py`, `test_packaged_dialogs_harden.py`, `test_shell_pump_teardown.py`, `test_shell_titlebar_icon_teardown.py`, `test_toast_destroy_teardown.py`, `test_edit_clip_text_lifecycle.py`, plus the two new files | **128 passed, 0 failed** (176.82s) |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on `dialogs.py`, `clip_workflows.py` | **PASS** |

The full ~25-minute suite was not run — no broader failure or unexpected dependency appeared to justify it.

## Exact diffstat

```
git diff --check                    → clean
git diff --stat
 cache_vault/ui/clip_workflows.py | 12 ++++++++++++
 cache_vault/ui/dialogs.py        | 20 +++++++++++++++++++-
 2 files changed, 31 insertions(+), 1 deletion(-)
git diff --name-status
M	cache_vault/ui/clip_workflows.py
M	cache_vault/ui/dialogs.py
```
Plus 2 new test files (`tests/test_dialog_bring_to_front_teardown_race.py`, `tests/test_clip_workflows_bring_to_front_race.py`), staged and committed alongside. `lan_ip.py`, `shell.py`, `mobile_dialogs.py`, `clip_context.py`, `filters.py` untouched — confirmed via `git diff --name-status` showing only the two authorized files. The preservation stash/branch were not read from programmatically.

## Final candidate SHA

```
2884463d93fde57572d04bc28bbb1a4fedddd3be   fix(ui): prevent dialog reactivation during teardown
```
4 files changed, 388 insertions(+), 1 deletion(-), on `fix/dialog-teardown-race-e2`, parent `f592e479e4af6deac536282a585e2b3c73f65e6c` (canonical `master`, confirmed unchanged throughout).

## Known limitations

- `SafePickerDialog` schedules a second, separate deferred re-show mechanism (`self.after(20, self._focus_popup)`, its own local deiconify/lift/focus_force/grab_set sequence) alongside `_bring_to_front`. It is unaffected by this fix (not routed through `_bring_to_front` at all) and was confirmed safe for the same reason as the other synchronous-destroy classes — but it was not given its own explicit regression test in this gate, since it is not currently vulnerable and adding one was judged out of this gate's deliberately narrow scope.
- This gate does not add `_closing`-awareness to any of the 10 currently-unaffected dialog classes. If a future change ever gives one of them a staged/deferred `destroy()`, the shared `_raise()` guard already protects it for free (confirmed inert-but-present via the `AboutDialog` control test) — but nothing currently prompts or requires that change.
- `dist/CacheVault.exe` was not rebuilt for this gate (not required by the authorization).

## Classification

**`PROVEN FIXED — DIALOG TEARDOWN RACE`**

## Stop condition honored

Not merged to `master`. E3 not started. LAN-IP salvage not touched. `preservation/pre-gate5f-dirty-2026-08-20` (stash and branch) not reapplied — reconfirmed via direct `git rev-parse` before writing this receipt, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. `master` confirmed unchanged, still `f592e479e4af6deac536282a585e2b3c73f65e6c`.
