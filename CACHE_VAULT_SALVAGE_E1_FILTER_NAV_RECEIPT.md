# Cache Vault — Salvage E1 Receipt — Filter Nav Sidebar Menu Crash

**Date:** 2026-08-20
**Gate:** CACHE VAULT SALVAGE E1 — FILTER NAV SIDEBAR MENU CRASH
**Branch:** `fix/filter-nav-sidebar-menu-crash`
**Scope:** the smallest, highest-confidence single item from the post-canonical salvage audit — no other audit items touched.

## Provenance

| | |
|---|---|
| Canonical parent SHA | `bcfca9d081ed754e5fa7b54e6ff203c879116654` (`master`, Gate 5F-A + 5F-B, unchanged throughout this gate) |
| Historical source | `preservation/pre-gate5f-dirty-2026-08-20` → `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f` (referenced for provenance only; not merged, cherry-picked, or reapplied — the fix was independently re-authored as a single-line change matching the historical candidate) |
| Audit disposition | `VALID SALVAGE CANDIDATE`, item B5, score 94/100 — `CACHE_VAULT_POST_CANONICAL_DIRTY_TREE_SALVAGE_AUDIT.md` |
| Final commit | `f592e479e4af6deac536282a585e2b3c73f65e6c` on `fix/filter-nav-sidebar-menu-crash` |

## Exact historical finding

`FilterNav._show_sidebar_menu` (`cache_vault/ui/filters.py`) calls `tk.Menu(self, tearoff=0)`. `tkinter` is used elsewhere in the same file, but only via a *function-local* `import tkinter as tk` inside `SidebarRow.__init__` — a different class entirely. Python local imports are function-scoped, not class- or module-scoped, so `FilterNav`'s methods (a different class) have no `tk` binding anywhere in their reachable scope. No module-level `import tkinter as tk` existed anywhere in the file.

`_show_sidebar_menu` is not dead code: it is wired directly as the `command=` callback of a real, always-visible `CTkButton` (tooltip: "Sidebar Options") constructed in `FilterNav.__init__`. Zero existing test coverage exercised this method prior to this gate.

## Canonical reproduction

Reproduced live in the salvage audit against unmodified `master@bcfca9d`, via a minimal ad hoc harness constructing a real `FilterNav` and calling `_show_sidebar_menu()` directly:

```
NameError: name 'tk' is not defined
```

Independently re-confirmed in this gate through the project's own test infrastructure (not the ad hoc harness) — see below.

## Failing-before proof

`tests/test_filter_nav_sidebar_menu.py` was written first, against unmodified canonical `filters.py` (`bcfca9d`'s content, no fix applied), and run:

```
tests\test_filter_nav_sidebar_menu.py FF.                                [100%]
...
E       NameError: name 'tk' is not defined
cache_vault\ui\filters.py:709: NameError
...
FAILED tests/test_filter_nav_sidebar_menu.py::test_show_sidebar_menu_constructs_the_menu_without_crashing
FAILED tests/test_filter_nav_sidebar_menu.py::test_sidebar_options_button_invoke_reaches_the_real_path_without_crashing
2 failed, 1 passed in 4.23s
```

Both failures raise the exact reproduced `NameError` at the exact production line (`filters.py:709`). The third test (`test_canonical_defect_reproduces_as_a_nameerror_when_the_fix_is_absent`) is a defect-pinning test designed to pass in both the pre-fix and post-fix state — it passed here as expected, confirming the specific failure mode under test is precisely `NameError` on `tk`, not some other error a looser assertion could have masked.

## The fix

`cache_vault/ui/filters.py` — one line added, immediately after the existing `from typing import Callable` import:

```diff
 from typing import Callable

+import tkinter as tk
 import customtkinter as ctk
```

Matches the historical candidate's approach exactly (a module-level `import tkinter as tk`), independently re-verified correct for this codebase rather than blindly ported: it resolves for both the pre-existing, already-working `SidebarRow.__init__` usage (harmlessly redundant with that method's own local import) and the previously-broken `FilterNav._show_sidebar_menu` usage.

## Passing-after proof

Same three tests, same file, run again after the fix:

```
tests\test_filter_nav_sidebar_menu.py ...                                [100%]
3 passed in 4.14s
```

## Runtime/UI proof

Performed, per the gate's "if practical" instruction. `test_sidebar_options_button_invoke_reaches_the_real_path_without_crashing` does not call `_show_sidebar_menu()` directly — it asserts `nav._overflow_btn.cget("command") == nav._show_sidebar_menu` (proving the button is genuinely wired to the method under test, not merely nearby code) and then calls `nav._overflow_btn.invoke()`, CustomTkinter's real button-invocation API, exercising the exact same call path a physical click on "Sidebar Options" would take. `popup_menu` (the OS-level `tk_popup()` call, which the crash occurs strictly before reaching) was patched, matching this suite's own established convention for menu-construction tests (see `test_sidebar_context.py`) — construction itself, where the defect lived, ran unmodified and for real.

## Exact files changed

```
git diff --stat  (pre-commit)
 cache_vault/ui/filters.py | 1 +
 1 file changed, 1 insertion(+)

git diff --name-status  (pre-commit)
M	cache_vault/ui/filters.py

git status --short  (pre-commit, full working tree)
 M cache_vault/ui/filters.py
?? CACHE_VAULT_POST_CANONICAL_DIRTY_TREE_SALVAGE_AUDIT.md   (untracked, out of scope, not committed)
?? CANONICAL_PROJECT_RECORD.md                               (untracked, out of scope, not committed)
?? tests/test_filter_nav_sidebar_menu.py                     (new, staged and committed)
```

`git diff --check` returned empty (no whitespace or conflict-marker issues). No unrelated source changes. `dialogs.py`, `clip_workflows.py`, `lan_ip.py`, `shell.py`, and `mobile_dialogs.py` were not touched, per the gate's explicit exclusion list. The preservation stash/branch were not read from programmatically at any point — the fix was authored fresh, matching the historical candidate's approach only in that both independently arrived at the same one-line, module-level `import tkinter as tk` addition.

## Test results

| Suite | Result |
|---|---|
| `tests/test_filter_nav_sidebar_menu.py` (new, focused) | **3 passed** (post-fix); 2/3 failed with the exact reproduced `NameError` pre-fix |
| Broader filters/navigation/sidebar/menu surface — `test_clip_context_menu.py`, `test_contextmenu.py`, `test_e4_contextmenu.py`, `test_filter_nav_sidebar_menu.py`, `test_menu_context.py`, `test_menu_lifecycle.py`, `test_navigation.py`, `test_sidebar_context.py`, `test_sidebar_menu_context.py` | **254 passed, 1 skipped, 0 failed** (517.43s) — the 1 skip is the same pre-existing, environment-conditional skip pattern documented throughout this canonicalization process, unrelated to this change |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on `cache_vault/ui/filters.py` and `tests/test_filter_nav_sidebar_menu.py` | **PASS** |

The full ~25-minute suite was not run, per the gate's instruction — no broader failure or unexpected dependency appeared to justify it.

## Commit

```
f592e479e4af6deac536282a585e2b3c73f65e6c  fix(ui): prevent Sidebar Options menu crash
```
2 files changed, 103 insertions(+), on `fix/filter-nav-sidebar-menu-crash`, parent `bcfca9d081ed754e5fa7b54e6ff203c879116654` (canonical `master`, confirmed unchanged throughout).

## Known limitations

- This gate does not address whether other files in the codebase have the same class of defect (a name only valid via one function's local import, relied on bare by a different function/class). The salvage audit flagged this as a worthwhile bounded follow-up (a repo-wide grep sweep); not attempted here, out of this gate's deliberately narrow scope.
- The runtime/UI proof exercises the button's real `invoke()` path but does not drive a literal OS-level mouse click through the packaged executable; that level of proof was judged unnecessary given the precision of the reproduced `NameError` and the directness of the one-line fix, consistent with "if practical" rather than mandatory.
- `dist/CacheVault.exe` was not rebuilt for this gate (not required by the authorization; the dev-interpreter `--selftest` lane was run instead).

## Classification

**`PROVEN FIXED — FILTER NAV SIDEBAR MENU CRASH`**

## Stop condition honored

Not merged to `master`. E2 not started. `preservation/pre-gate5f-dirty-2026-08-20` (branch and stash) untouched — confirmed via `git rev-parse` immediately before writing this receipt, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. `master` confirmed unchanged, still `bcfca9d081ed754e5fa7b54e6ff203c879116654`.
