# Offline Hotfix Receipt — v0.1.4.1 Local Stability

> Branch: `hotfix/v0.1.4.1-local-stability`
> Base version: `0.1.4` (pyproject.toml)
> Date: 2026-06-27
> Scope: Local correctness hardening from `CODEBASE_AUDIT.md`. No network, no publishing.

---

## Summary

This hotfix lane fixed four audit-confirmed correctness bugs (BUG-1, BUG-3,
BUG-4, BUG-5), added regression tests for each, and verified the full local CI
gate set with a fresh packaged exe.

Two audit items were intentionally **not** shipped:
- **BUG-2** (`storage.py` unused lock) — deferred to a dedicated concurrency
  lane with its own regression requirements.
- **BUG-6** (`win_mouse.py` 64-bit window-long) — **reverted after it caused a
  UI freeze** (see "Regression found and reverted" below). It is deferred to a
  proper redesign using `SetWindowSubclass`.

---

## Bugs Fixed

### BUG-1 — `source_domain()` corrupted `www.*` domains
- **File:** `cache_vault/core/clip_metadata.py`
- **Fix:** Replaced `host.lower().lstrip("www.")` with `host.lower().removeprefix("www.")`.
- **Why it mattered:** `lstrip` strips the character set `{w, .}`, so
  `www.wikipedia.org` became `ikipedia.org` and `www.weather.com` became
  `eather.com`. `removeprefix` strips only the literal `www.` prefix.

### BUG-3 — Safe `rename()` discarded all customization
- **File:** `cache_vault/core/safes.py`
- **Fix:** Rename now round-trips the existing Safe via `to_dict()`/`from_dict()`
  with only `name` overwritten, preserving icon, accent, description, favorite,
  receipt label, visual style, and other fields.

### BUG-4 — Duplicate context-menu dispatch key + dispatcher follow-through
- **Files:** `cache_vault/core/contextmenu.py`, `cache_vault/ui/shell.py`
- **Fix (part 1):** The "Mark Keep" menu item key was changed from the duplicate
  `toggle_favorite` to a distinct `mark_keep`.
- **Fix (part 2 — required follow-through):** `_open_clip_menu`'s dispatch table
  in `shell.py` did **not** contain `mark_keep`. Because `_add_menu_items` resolves
  commands with a direct `dispatch[item.key]` lookup, the renamed item would have
  raised `KeyError` and crashed the entire clip context menu. Added
  `"mark_keep": lambda: self._mark_keep(clip.id)`.
- **Note:** The preview-pane surface was already safe — it resolves actions via
  `self._actions.get(key)` against the general action table, which already mapped
  `mark_keep` → `_mark_keep`.

### BUG-5 — Macro shortcut listener `stop()` leaked its hook thread
- **File:** `cache_vault/core/macro_shortcut_listener.py`
- **Fix:** `_run()` now records the hook thread id via `GetCurrentThreadId()`.
  `stop()` unhooks, then posts `WM_QUIT` (`PostThreadMessageW`) to break the
  `GetMessageW` loop, and joins the worker thread. Previously the thread blocked
  in `GetMessageW` until process exit.
- **Test safety:** No real low-level keyboard hook is installed in tests. The
  unit test drives a fake `_user32` to assert the unhook + `WM_QUIT` post + thread
  join contract, so there is no message-loop hang risk.

### BUG-6 — `win_mouse.py` used 32-bit `SetWindowLong`/`GetWindowLong` (REVERTED — DEFERRED)
- **File:** `cache_vault/core/win_mouse.py`
- **Status:** Attempted, then **reverted**. The pointer-safe rewrite is correct
  in isolation, but it exposed a latent design problem that froze the app.
- **Deferred to:** a dedicated lane using the documented, reentrancy-safe
  `SetWindowSubclass` / `RemoveWindowSubclass` (comctl32) mechanism instead of
  raw `SetWindowLongPtr` subclassing of the live Tk root.

---

## Follow-up Stability Fix — Context-menu handle leak (BUG-9)

**Symptom (user-reported):** After using the app for a while, multi-clip copy
"doesn't actually copy anything" — the bulk action appears dead.

**Diagnosis:** `%LOCALAPPDATA%\CacheVault\crash.log` showed the real error:
```
TclError: No more menus can be allocated.
  cache_vault\ui\shell.py, in _open_bulk_clip_menu
  tkinter\__init__.py, in __init__   (tk.Menu)
```
Every right-click built a fresh `tk.Menu` (a parent plus ~6 submenus) that was
**never destroyed**. Over a session this exhausts the per-process Windows USER
object / menu-handle quota. Once exhausted, *no* new menu can be created — so
the bulk-copy context menu fails to build and the "Copy N clips" action never
runs. This is a pre-existing leak (the copy code itself is unchanged), unrelated
to the BUG-1/3/4/5 edits, surfaced by cumulative use.

**Fix:** Added `CacheVaultApp._destroy_menu()` and call it in the `finally` of
every popup site (`_open_clip_menu`, `_open_bulk_clip_menu`, `_open_locked_menu`,
`_popup_menu`, `_open_receipt_menu`, `_open_safe_menu`). Destroying the parent
menu also frees its submenus, reclaiming all handles per right-click. On Windows
`tk_popup` is modal, so the selected command has already run by the time the
`finally` executes — destruction is safe and does not cancel the action.

**Test:** `tests/test_contextmenu.py::test_context_menus_are_destroyed_after_use`
asserts the helper destroys the menu and that every `grab_release()` popup is
balanced by a `_destroy_menu(menu)` call (source-level, no Tk needed).

> Note: the same crash log also shows a benign `iconbitmap ... not defined`
> warning on dialog creation (CustomTkinter icon path inside the PyInstaller
> `_MEI` temp dir). It is cosmetic, does not affect copy, and is left for a
> separate cleanup.

---

## Regression Found and Reverted (BUG-6)

**Symptom:** After the initial hotfix commit, the app froze when copying
multiple clips.

**Root cause:** `win_mouse.WinMouseHandler` subclasses the **live Tk root
window's WndProc** (`shell.py` → `install_mouse_handler(self, ...)` →
`root.winfo_id()`) and runs a Python callback on the UI thread for *every*
window message. The pre-hotfix code passed a `ctypes` callback object to
`win32gui.SetWindowLong`, which requires an `int`, so the call **always raised
`TypeError` and was swallowed** — the subclass never actually installed and the
side-button navigation feature was inert.

The BUG-6 "fix" made the subclass install successfully for the first time. That
newly routed every UI message — including the **synchronous clipboard messages
that bulk copy triggers** (`clipboard_clear` / `clipboard_append`) — through a
Python WndProc holding the GIL, which deadlocked/froze the UI.

**Resolution:** `win_mouse.py` was restored to its pre-hotfix (commit
`dd03b57`) state, returning the app to its known-stable behavior (side-button
nav remains inert, exactly as before this lane). The accompanying
`tests/test_win_mouse.py` was removed. A correct fix requires `SetWindowSubclass`
and live GUI validation, which is out of scope for a stability hotfix.

---

## Files Changed

| File | Change |
|------|--------|
| `cache_vault/core/clip_metadata.py` | BUG-1 fix (`removeprefix`) |
| `cache_vault/core/safes.py` | BUG-3 fix (preserve customization on rename) |
| `cache_vault/core/contextmenu.py` | BUG-4 fix (distinct `mark_keep` key) |
| `cache_vault/ui/shell.py` | BUG-4 follow-through (`mark_keep` dispatch wiring) |
| `cache_vault/core/macro_shortcut_listener.py` | BUG-5 fix (`WM_QUIT` post + thread join) |

> `cache_vault/core/win_mouse.py` was modified for BUG-6 and then reverted to
> its pre-hotfix state; it carries no net change in this lane.

## Tests Added

| File | Coverage |
|------|----------|
| `tests/test_clip_labels_grouping.py` | BUG-1: `www.` prefix stripping, `w`-leading domains, none/empty inputs |
| `tests/test_customization_architecture.py` | BUG-3: rename preserves customization + persistence round-trip |
| `tests/test_contextmenu.py` | BUG-4: distinct `mark_keep` key, unique menu keys, dispatch wiring, behavioral `mark_keep` sets `is_kept` (not favorite) |
| `tests/test_macro_shortcut_listener.py` (new) | BUG-5: `stop()` posts `WM_QUIT`, idempotent no-op without hook, thread join — fake `_user32`, no real hook |

> `tests/test_win_mouse.py` was added for BUG-6 and then removed along with the
> BUG-6 revert.

---

## Verification Results

### Targeted tests
```
pytest -p no:xonsh \
  tests/test_clip_labels_grouping.py \
  tests/test_customization_architecture.py \
  tests/test_contextmenu.py \
  tests/test_macro_shortcut_listener.py
```
Result: **PASS**.

> Note: the audit's suggested command named `tests/test_clip_metadata.py` and
> `tests/test_safes.py`, which do not exist in this repo. The actual BUG-1 and
> BUG-3 tests live in `tests/test_clip_labels_grouping.py` and
> `tests/test_customization_architecture.py` respectively.

### Full pytest
```
python -m pytest -p no:xonsh
```
Result: **558 passed**, 2 warnings (Pillow `getdata` deprecation, pre-existing).
(559 with BUG-6 tests → 557 after the BUG-6 revert → 558 after adding the
BUG-9 menu-leak regression test.)

### compileall
```
python -m compileall cache_vault tests app.py
```
Result: **PASS** (no syntax errors).

### selftest
```
python app.py --selftest
```
Result: **PASS** — `selftest OK — core capture/classify/sensitive/image/mobile pipeline works`.

### Local CI (after closing running app + fresh packaging)
```
pwsh scripts/ci_local_full.ps1
```
Result: **CACHE VAULT LOCAL CI: PASS**
- pytest: PASS (full: 558 passed)
- founder-critical: PASS | command-center: PASS | quick-paste: PASS | receipts-export: PASS
- compileall: PASS
- selftest: PASS
- smokes: PASS (runtime proof 20/20)
- claims: PASS
- secrets: PASS
- packaging: **PASS** (no stale-exe warning)

> The CI script must be run with **PowerShell 7 (`pwsh`)**, not Windows
> PowerShell 5.1. Under 5.1 the script's non-ASCII characters are ANSI-decoded
> and cause a spurious parser error before any work runs.

### Packaging note (process lock resolved)
The first CI run failed packaging with `PermissionError: [WinError 5] Access is
denied: dist\CacheVault.exe` because two running `CacheVault.exe` instances
(PIDs 9892, 16052) held the exe locked. A graceful close was attempted first;
when the tray processes did not exit, only those two confirmed PIDs were
terminated. After confirming no `CacheVault.exe` processes remained, CI was
re-run and packaging rebuilt the exe cleanly.

### Fresh exe
- `dist/CacheVault.exe` — 41.1 MB
- SHA256: `E2AEAD2D862D8BEFB259D70EDC140D1E84174FA70F45069D66B7F376A6CE181A`
  (rebuilt after the BUG-9 context-menu leak fix)
- Prior builds in this lane:
  - `EF17BB58017151A56EC2A2DD93D1C121C65BF683D4A4561A808A488D9E32A03B` — after BUG-6 revert
  - `4A76AC11F2FF47C70A366870C8389688CB04023FAB6B778E0E23092C086B691D` — froze copy (BUG-6 active); superseded

---

## Compliance Confirmations

- **No GitHub commands were run** (no `git push`, no `gh`, no remote operations).
- **No tag, release, or public posting** was created or published.
- **`storage.py` locking (BUG-2) was intentionally not touched** — it is a
  separate concurrency pass requiring its own regression tests.
- **BUG-6 (`win_mouse.py`) was reverted** after it froze multi-clip copy; it is
  deferred to a `SetWindowSubclass` redesign lane with live GUI validation.
- No Settings/UI polish work was started.
- This lane stops here per instruction.
