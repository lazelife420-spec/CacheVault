# Cache Vault — Salvage E3 Receipt — Annotation / Import Correctness

**Date:** 2026-08-20
**Gate:** CACHE VAULT SALVAGE E3 — ANNOTATION / IMPORT CORRECTNESS
**Branch:** `fix/annotation-import-correctness-e3`
**Scope:** the third salvage gate, its own isolated gate from canonical `master@2884463`. Deliberately scoped as a correctness investigation, not a predetermined patch — the audit's `clip_context.py` finding was explicitly not assumed to need a fix going in.

## Canonical parent SHA

`2884463d93fde57572d04bc28bbb1a4fedddd3be` (`master`, post Salvage E2, unchanged throughout this gate).

## Preserved-source provenance

`preservation/pre-gate5f-dirty-2026-08-20` → `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f` (referenced for provenance only; not merged, cherry-picked, or reapplied). Prior audit disposition: `shell.py` — `VALID SALVAGE CANDIDATE`, item B3, score 74/100; `clip_context.py` — `PARTIAL / NEEDS REWORK`, item B4, score 58/100; `mobile_dialogs.py` — `PARTIAL / NEEDS REWORK (currently dead)`, score 15/100 (this last assessment turned out to be **wrong** — see below).

## Each candidate file, considered independently

### `cache_vault/ui/shell.py` — classified `REAL CORRECTNESS DEFECT` (type-introspection class)

All three files have `from __future__ import annotations` (PEP 563) — every annotation is a lazy string, never evaluated during normal execution. This is why each file imports and runs fine despite the defects below. It is not a hypothetical concern for this codebase specifically: `cache_vault/modules/settings_schema.py` calls `typing.get_type_hints(settings_cls)` on the `Settings` class as part of its own schema validation, so real annotation resolution is a mechanism this project already depends on — just not, until now, on these specific symbols.

- `Any` used bare in **27 methods** (an exhaustive `get_type_hints()` sweep, not the original ~14-hit grep, found the true count — `_dispatch_sidebar_command`, every `_sidebar_*` command-dispatch method, `_report_clear_all_clips_result`, `_report_permanent_delete_result`, etc.), with `from typing import Any` absent from the file.
- `Clip` used bare in `_on_clip_double_click`'s parameter annotation, with no bare `Clip` name in the module (only `models` is imported, as a module).

### `cache_vault/ui/clip_context.py` — two separate questions, resolved differently

**The `Clip`/`Path` annotations — classified `REAL CORRECTNESS DEFECT`:**
- `_add_single_item(..., clips: list[Clip])` — `Clip` unbound, same class as shell.py.
- `_find_receipt_file(row) -> Path | None` — `Path` unbound *in the annotation only*; the function's own runtime body already has its own local `from pathlib import Path`, so the `Path(base) / ...` runtime call was never broken, only the return-type annotation itself.

**The NAV-import question — classified `IMPORT ORGANIZATION ONLY`, explicitly not ported:** the preserved candidate moved `open_home_card_menu`'s function-local `from .filters import NAV_EDITABLE_COPIES, NAV_EXPORTS, NAV_MOBILE_ACCESS, NAV_MOBILE_INBOX, NAV_STAMPED_RECEIPTS` to module scope, dropping the two names (`NAV_EDITABLE_COPIES`, `NAV_MOBILE_ACCESS`) the function body never actually references. Checked against every dimension the gate asked for:
- **Runtime behavior:** unchanged — Python's module cache means the same objects resolve either way.
- **Circular-import behavior:** investigated specifically, not assumed safe. `filters.py` itself has its own function-local `from .clip_context import popup_menu` (inside `_show_sidebar_menu`) — a genuine mutual reference between the two modules. Traced the real load order (`shell.py` imports `clip_context` at line 56, `filters` at line 65) and confirmed empirically: promoting `clip_context.py`'s import to module scope does not break anything, because `filters.py`'s own back-reference stays function-local regardless of load order, so there is no true load-time cycle — verified with a live patched-file import of `CacheVaultApp` and a full `app.py --selftest` run, both clean, file restored byte-for-byte immediately after (`git diff --stat` empty).
- **Typing resolution:** `get_type_hints(clip_context.open_home_card_menu)` succeeds today and would succeed identically either way — its own parameter/return annotations (`str`, `str | None`, `int`, `int`, `None`) reference none of the NAV names. Included as its own passing control test.
- **Startup ordering, performance, testability:** no meaningful difference either way.
- **Exception timing:** the only real distinction found — a module-level import would surface a hypothetical future `filters.py` import failure at app startup instead of the first time the menu is opened. A real, if minor, fail-fast argument, but not a fix for any currently-active defect.

**Conclusion: no functional or correctness defect exists in the current import placement. Not ported**, per the gate's explicit instruction ("If there is no functional or correctness defect: DO NOT PORT IT").

### `cache_vault/ui/mobile_dialogs.py` — classified `REAL CORRECTNESS DEFECT` (correcting the prior audit)

The original salvage audit (item B3) concluded this file's `Any` import was "currently unused" because a grep for `: Any\b|-> Any\b|\[Any\]` found nothing. **This was wrong**, caught by this gate's exhaustive `get_type_hints()` sweep, not a manual re-read: `PairAndroidDialog.__init__` has `create_pairing_offer: Callable[[], Any] | None = None` — `Any` sits *inside* a `Callable[...]` expression, a shape none of the three grep patterns matched. `typing.get_type_hints(PairAndroidDialog.__init__)` fails with `NameError: name 'Any' is not defined`, exactly the same defect class as `shell.py`. This gate corrects the record rather than silently carrying the earlier wrong conclusion forward.

## Failing-before evidence for each accepted fix

`tests/test_annotation_introspection_correctness.py`, written and run against unmodified `shell.py`/`clip_context.py`/`mobile_dialogs.py` before any production code was touched:

```
tests\test_annotation_introspection_correctness.py FFFFFFFFFF.FFF   [100%]
13 failed, 1 passed in 1.05s
```

Every failure is a `NameError` raised from inside `typing.get_type_hints()` (via `typing._eval_type` → `ForwardRef._evaluate`), for exactly three names: `Clip` (shell.py, clip_context.py), `Any` (shell.py, mobile_dialogs.py), `Path` (clip_context.py). The one pass, `test_open_home_card_menu_has_no_annotation_defect_either_way`, is the NAV-import control — confirming that specific function had no defect *before* the fix either, exactly as the investigation concluded.

## Exact fix

Each change is the minimal addition against what the file already imports — no new import where a qualified reference to an existing one suffices:

**`cache_vault/ui/shell.py`:**
```diff
 import traceback
 from pathlib import Path
+from typing import Any
...
-    def _on_clip_double_click(self, clip: Clip) -> None:
+    def _on_clip_double_click(self, clip: models.Clip) -> None:
```
(`models` was already imported at module level; no new import needed for the `Clip` fix.)

**`cache_vault/ui/clip_context.py`:**
```diff
 import customtkinter as ctk
 from datetime import datetime
+from pathlib import Path
...
-def _add_single_item(window, menu, item, dispatch: dict, clips: list[Clip]) -> None:
+def _add_single_item(window, menu, item, dispatch: dict, clips: list[models.Clip]) -> None:
```
(`models` was already imported; only `Path` needed a new import, since nothing in the file already had a bare `pathlib` reference to qualify against.)

**`cache_vault/ui/mobile_dialogs.py`:**
```diff
-from typing import Callable
+from typing import Any, Callable
```

## Passing-after proof

```
tests\test_annotation_introspection_correctness.py ..............   [100%]
14 passed in 0.32s
```

## Regression results

| Suite | Result |
|---|---|
| `tests/test_annotation_introspection_correctness.py` (new) | **14 passed** (post-fix); 13/14 failed pre-fix |
| Broader relevant surface — `test_clip_context_menu.py`, `test_filter_nav_sidebar_menu.py` (E1), `test_mobile_pairing.py`, `test_shell_pump_teardown.py`, `test_shell_selection_keys.py`, `test_shell_titlebar_icon_teardown.py`, `test_sidebar_context.py`, `test_sidebar_menu_context.py`, `test_dialog_bring_to_front_teardown_race.py` + `test_clip_workflows_bring_to_front_race.py` (E2), plus the new file | **251 passed, 0 failed** (695.47s) — E1 and E2's own focused regressions included and confirmed still green on top of this change |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on all three touched files | **PASS** |

The full ~25-minute suite was not run — no broader failure or unexpected dependency appeared to justify it; the affected files' own shared-import consumers (`test_clip_context_menu.py`, `test_sidebar_context.py`, `test_sidebar_menu_context.py`) were included in the broader run specifically because this change touches shared imports.

## Final diff

```
git diff --check                    → clean
git diff --stat
 cache_vault/ui/clip_context.py   | 3 ++-
 cache_vault/ui/mobile_dialogs.py | 2 +-
 cache_vault/ui/shell.py          | 3 ++-
 3 files changed, 5 insertions(+), 3 deletions(-)
git diff --name-status
M	cache_vault/ui/clip_context.py
M	cache_vault/ui/mobile_dialogs.py
M	cache_vault/ui/shell.py
```
Plus 1 new test file (`tests/test_annotation_introspection_correctness.py`), staged and committed alongside. `filters.py`, `dialogs.py`, `clip_workflows.py`, `lan_ip.py` untouched. No speculative cleanup included — the NAV-import reorganization was investigated and deliberately excluded, not silently dropped.

## Candidate SHA

```
2e90b46b09dba6032e54ce9fdebb6299020723c8   fix(ui): resolve annotation and import correctness
```
4 files changed, 161 insertions(+), 3 deletions(-), on `fix/annotation-import-correctness-e3`, parent `2884463d93fde57572d04bc28bbb1a4fedddd3be` (canonical `master`, confirmed unchanged throughout).

## Known limitations

- The exhaustive `get_type_hints()` sweep covered every function/method in the three files reachable via `inspect.getmembers`. It does not cover nested/local functions defined inside other functions (not addressable via `inspect.getmembers` on the module or class), so a defect hidden inside such a closure would not have been caught by this gate's method. None of the three fixed symbols are nested this way, and nothing in the sweep's output hinted at one, but this is a real methodological boundary, not a claim of 100% file-wide coverage.
- The NAV-import question in `clip_context.py` was investigated thoroughly (including live empirical verification of the circular-import question) but deliberately left unchanged. If the "fail fast at startup rather than at first menu-open" argument is ever judged worth acting on, that would be its own, separately-authorized cleanup gate — not bundled here as an unproven correctness fix.
- `dist/CacheVault.exe` was not rebuilt for this gate (not required by the authorization).

## Classification

**`PROVEN FIXED — ANNOTATION / IMPORT CORRECTNESS`**

(Applies to all three files' accepted fixes. The `clip_context.py` NAV-import candidate specifically resolved to no-defect-found and was excluded — see above.)

## Stop condition honored

Not merged to `master`. E4 not started. LAN-IP policy not touched (`lan_ip.py` untouched — confirmed via `git diff --name-status`). `preservation/pre-gate5f-dirty-2026-08-20` (stash and branch) not reapplied — reconfirmed via direct `git rev-parse` before writing this receipt, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. `master` confirmed unchanged, still `2884463d93fde57572d04bc28bbb1a4fedddd3be`.
