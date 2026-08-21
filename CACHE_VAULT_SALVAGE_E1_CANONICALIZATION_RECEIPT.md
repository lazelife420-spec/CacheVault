# Cache Vault — Salvage E1 Canonicalization Receipt

**Date:** 2026-08-20
**Gate:** Cache Vault Salvage E1 canonicalization — Filter Nav Sidebar Menu Crash

## Topology

| | |
|---|---|
| Pre-E1 canonical `master` SHA | `bcfca9d081ed754e5fa7b54e6ff203c879116654` |
| E1 commit SHA | `f592e479e4af6deac536282a585e2b3c73f65e6c` on `fix/filter-nav-sidebar-menu-crash` |
| Rollback tag | `pre-salvage-e1-filter-nav` → `bcfca9d081ed754e5fa7b54e6ff203c879116654` (verified via `git show-ref --tags`) |

Confirmed before the move: `git merge-base master f592e47...` = `bcfca9d...` (= `master` itself), `git merge-base --is-ancestor master f592e47...` = `true`, `git status --short` showed no tracked working-tree changes. Pure fast-forward, no merge commit needed.

## Fast-forward

```
git merge --ff-only f592e479e4af6deac536282a585e2b3c73f65e6c
Updating bcfca9d..f592e47
Fast-forward
 cache_vault/ui/filters.py             |   1 +
 tests/test_filter_nav_sidebar_menu.py | 102 ++++++++++++++++++++++++++++++++++
 2 files changed, 103 insertions(+)
 create mode 100644 tests/test_filter_nav_sidebar_menu.py
```

## Zero-diff tree identity proof

```
git rev-parse master                                                    → f592e479e4af6deac536282a585e2b3c73f65e6c
git rev-parse f592e479e4af6deac536282a585e2b3c73f65e6c                  → f592e479e4af6deac536282a585e2b3c73f65e6c
git diff master f592e479e4af6deac536282a585e2b3c73f65e6c --exit-code    → zero diff (exit 0)
git status --short                                                      → clean (only unrelated pre-existing untracked process files)
```

## Before-fix reproduction (carried forward from the E1 gate, not re-derived)

`tests/test_filter_nav_sidebar_menu.py` run against unmodified `filters.py` at `bcfca9d` (before the fix existed):

```
tests\test_filter_nav_sidebar_menu.py FF.                                [100%]
...
E       NameError: name 'tk' is not defined
cache_vault\ui\filters.py:709: NameError
2 failed, 1 passed in 4.23s
```

Both failures — the direct `_show_sidebar_menu()` call and the real `_overflow_btn.invoke()` click path — reproduced the identical `NameError` at the identical production line.

## After-fix focused proof

Same three tests, against `filters.py` with the one-line `import tkinter as tk` fix, both at the original E1 commit and re-confirmed here on canonical `master` post-fast-forward:

```
tests\test_filter_nav_sidebar_menu.py ...                                [100%]
3 passed in 3.98s
```

## Broader 254-pass result from candidate validation (not re-run here — tree is byte-identical)

From the E1 gate's own validation, against the exact tree content now canonical: `test_clip_context_menu.py`, `test_contextmenu.py`, `test_e4_contextmenu.py`, `test_filter_nav_sidebar_menu.py`, `test_menu_context.py`, `test_menu_lifecycle.py`, `test_navigation.py`, `test_sidebar_context.py`, `test_sidebar_menu_context.py` — **254 passed, 1 skipped, 0 failed** (517.43s). The 1 skip is the same pre-existing, environment-conditional skip pattern documented throughout this canonicalization process, unrelated to this change. Not re-run here per this gate's own instruction — the zero-diff check above already proves tree identity is unchanged from that validated content, so a rerun would prove nothing new.

## Post-fast-forward sanity results (run fresh against the now-canonical checkout)

| Gate | Result |
|---|---|
| `tests/test_filter_nav_sidebar_menu.py` (focused, on canonical `master`) | **3 passed**, 3.98s |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on `cache_vault/ui/filters.py` | **PASS** |
| Cheap UI/menu smoke | Already covered by the focused suite's `test_sidebar_options_button_invoke_reaches_the_real_path_without_crashing`, which asserts the real overflow button is wired to `_show_sidebar_menu` and drives it via CustomTkinter's own `invoke()` API — the genuine click path, not a synthetic call. No separate script needed. |

## Working-tree state

```
git status --short
?? CACHE_VAULT_POST_CANONICAL_DIRTY_TREE_SALVAGE_AUDIT.md
?? CACHE_VAULT_SALVAGE_E1_FILTER_NAV_RECEIPT.md
?? CANONICAL_PROJECT_RECORD.md
```

Clean of tracked changes. The three untracked files are this canonicalization process's own working documents (unrelated to E1's source diff), consistent with their state throughout this entire process.

## Final classification

**`CANONICALIZED — FILTER NAV SIDEBAR MENU CRASH FIXED`**

## Stop condition honored

E2 not started. `dialogs.py`, `clip_workflows.py`, `lan_ip.py` not touched. `preservation/pre-gate5f-dirty-2026-08-20` (stash and branch) not read from or reapplied — reconfirmed via direct `git rev-parse` immediately after the fast-forward, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. The `fix/filter-nav-sidebar-menu-crash` branch was not pruned (still points at `f592e47...`, now also `master`'s tip). `master` not pushed to any remote.
