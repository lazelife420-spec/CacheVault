# Offline Hotfix Receipt — v0.1.4.1 Local Stability

> Branch: `hotfix/v0.1.4.1-local-stability`
> Base version: `0.1.4` (pyproject.toml)
> Date: 2026-06-27
> Scope: Local correctness hardening from `CODEBASE_AUDIT.md`. No network, no publishing.

---

## Summary

This hotfix lane fixed five audit-confirmed correctness bugs (BUG-1, BUG-3,
BUG-4, BUG-5, BUG-6), added regression tests for each, and verified the full
local CI gate set with a fresh packaged exe. The `storage.py` locking issue
(BUG-2) was intentionally **not** touched — it is a separate concurrency lane
with its own regression requirements.

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

### BUG-6 — `win_mouse.py` used 32-bit `SetWindowLong`/`GetWindowLong`
- **File:** `cache_vault/core/win_mouse.py`
- **Fix:** Reworked the WndProc subclassing to use pointer-safe
  `SetWindowLongPtrW`/`GetWindowLongPtrW` via `ctypes`, with `LONG_PTR`
  (`c_ssize_t`) arg/return types, `CallWindowProcW`/`DefWindowProcW` prototypes,
  and a 32-bit fallback to the `*W` variants. The WndProc callback is passed as a
  full pointer-sized value, eliminating pointer truncation on 64-bit Python.

---

## Files Changed

| File | Change |
|------|--------|
| `cache_vault/core/clip_metadata.py` | BUG-1 fix (`removeprefix`) |
| `cache_vault/core/safes.py` | BUG-3 fix (preserve customization on rename) |
| `cache_vault/core/contextmenu.py` | BUG-4 fix (distinct `mark_keep` key) |
| `cache_vault/ui/shell.py` | BUG-4 follow-through (`mark_keep` dispatch wiring) |
| `cache_vault/core/macro_shortcut_listener.py` | BUG-5 fix (`WM_QUIT` post + thread join) |
| `cache_vault/core/win_mouse.py` | BUG-6 fix (pointer-safe window-long APIs) |

## Tests Added

| File | Coverage |
|------|----------|
| `tests/test_clip_labels_grouping.py` | BUG-1: `www.` prefix stripping, `w`-leading domains, none/empty inputs |
| `tests/test_customization_architecture.py` | BUG-3: rename preserves customization + persistence round-trip |
| `tests/test_contextmenu.py` | BUG-4: distinct `mark_keep` key, unique menu keys, dispatch wiring, behavioral `mark_keep` sets `is_kept` (not favorite) |
| `tests/test_macro_shortcut_listener.py` (new) | BUG-5: `stop()` posts `WM_QUIT`, idempotent no-op without hook, thread join — fake `_user32`, no real hook |
| `tests/test_win_mouse.py` (new) | BUG-6: `LONG_PTR` is pointer-sized, source uses `*Ptr*` APIs, no legacy `win32gui.SetWindowLong`/`GetWindowLong` calls |

---

## Verification Results

### Targeted tests
```
pytest -p no:xonsh \
  tests/test_clip_labels_grouping.py \
  tests/test_customization_architecture.py \
  tests/test_contextmenu.py \
  tests/test_macro_shortcut_listener.py \
  tests/test_win_mouse.py
```
Result: **PASS** (41 tests).

> Note: the audit's suggested command named `tests/test_clip_metadata.py` and
> `tests/test_safes.py`, which do not exist in this repo. The actual BUG-1 and
> BUG-3 tests live in `tests/test_clip_labels_grouping.py` and
> `tests/test_customization_architecture.py` respectively.

### Full pytest
```
python -m pytest -p no:xonsh
```
Result: **559 passed**, 2 warnings (Pillow `getdata` deprecation, pre-existing).

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
- pytest: PASS (full: 559 passed)
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
- SHA256: `4A76AC11F2FF47C70A366870C8389688CB04023FAB6B778E0E23092C086B691D`

---

## Compliance Confirmations

- **No GitHub commands were run** (no `git push`, no `gh`, no remote operations).
- **No tag, release, or public posting** was created or published.
- **`storage.py` locking (BUG-2) was intentionally not touched** — it is a
  separate concurrency pass requiring its own regression tests.
- No Settings/UI polish work was started.
- This lane stops here per instruction.
