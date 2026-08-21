# Cache Vault — Salvage E3 Canonicalization Receipt

**Date:** 2026-08-20
**Gate:** Cache Vault Salvage E3 canonicalization — Annotation / Import Correctness

## Topology

| | |
|---|---|
| Pre-E3 canonical `master` SHA | `2884463d93fde57572d04bc28bbb1a4fedddd3be` (post Salvage E2) |
| E3 candidate SHA | `2e90b46b09dba6032e54ce9fdebb6299020723c8` on `fix/annotation-import-correctness-e3` |
| Rollback tag | `pre-salvage-e3-annotation-import` → `2884463d93fde57572d04bc28bbb1a4fedddd3be` (verified via `git show-ref --tags`) |

Confirmed before the move: `git checkout master` → `2884463d93fde57572d04bc28bbb1a4fedddd3be` (matches the expected E2 canonical baseline exactly), `git merge-base master 2e90b46...` = `2884463d93fde57572d04bc28bbb1a4fedddd3be` (= `master` itself), `git merge-base --is-ancestor master 2e90b46...` = `true`, `git status --short` showed no tracked working-tree changes. Pure fast-forward.

## Fast-forward

```
git merge --ff-only 2e90b46b09dba6032e54ce9fdebb6299020723c8
Updating 2884463..2e90b46
Fast-forward
 cache_vault/ui/clip_context.py                     |   3 +-
 cache_vault/ui/mobile_dialogs.py                   |   2 +-
 cache_vault/ui/shell.py                            |   3 +-
 tests/test_annotation_introspection_correctness.py | 156 +++++++++++++++++++++
 4 files changed, 161 insertions(+), 3 deletions(-)
```

## Zero-diff tree identity proof

```
git rev-parse master                                                    → 2e90b46b09dba6032e54ce9fdebb6299020723c8
git rev-parse 2e90b46b09dba6032e54ce9fdebb6299020723c8                  → 2e90b46b09dba6032e54ce9fdebb6299020723c8
git diff master 2e90b46b09dba6032e54ce9fdebb6299020723c8 --exit-code    → zero diff (exit 0)
git status --short                                                      → clean (only unrelated pre-existing untracked process files)
```

## Acceptance gates run (scoped exactly as authorized — focused only, no broader rerun)

| Gate | Result |
|---|---|
| Focused E3 acceptance (`tests/test_annotation_introspection_correctness.py`) | **14 passed**, 0.45s |
| E1 focused regression (`tests/test_filter_nav_sidebar_menu.py`) | **3 passed**, 3.59s |
| E2 focused regression (`tests/test_dialog_bring_to_front_teardown_race.py`, `tests/test_clip_workflows_bring_to_front_race.py`) | **12 passed**, 1.85s |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on `cache_vault/ui/shell.py`, `cache_vault/ui/clip_context.py`, `cache_vault/ui/mobile_dialogs.py` | **PASS** |

The broader 251-pass surface from the E3 gate's own validation was not re-run — tree identity is proven byte-identical by the zero-diff check above, so a rerun would prove nothing the E3 gate's own receipt didn't already establish. All three cumulative fixes (E1's sidebar-crash fix, E2's dialog-teardown-race fix, E3's annotation/import fixes) are now confirmed still mutually compatible on the same canonical tree via their combined focused suites above.

## Working-tree state

```
git status --short
?? CACHE_VAULT_POST_CANONICAL_DIRTY_TREE_SALVAGE_AUDIT.md
?? CACHE_VAULT_SALVAGE_E1_CANONICALIZATION_RECEIPT.md
?? CACHE_VAULT_SALVAGE_E1_FILTER_NAV_RECEIPT.md
?? CACHE_VAULT_SALVAGE_E2_CANONICALIZATION_RECEIPT.md
?? CACHE_VAULT_SALVAGE_E2_DIALOG_TEARDOWN_RECEIPT.md
?? CACHE_VAULT_SALVAGE_E3_ANNOTATION_IMPORT_RECEIPT.md
?? CANONICAL_PROJECT_RECORD.md
```
Clean of tracked changes. The untracked files are this canonicalization process's own working documents, unrelated to E3's source diff.

## Final classification

**`CANONICALIZED — ANNOTATION / IMPORT CORRECTNESS FIXED`**

## Stop condition honored

E4 not started. LAN-IP not touched (`lan_ip.py` untouched by this fast-forward — the E3 diff was limited to `shell.py`, `clip_context.py`, `mobile_dialogs.py`, plus the new test file). `preservation/pre-gate5f-dirty-2026-08-20` (stash and branch) not reapplied — reconfirmed via direct `git rev-parse` immediately after the fast-forward, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. The `fix/annotation-import-correctness-e3` branch was not pruned (still points at `2e90b46...`, now also `master`'s tip). `master` not pushed to any remote.

## Final master SHA

```
2e90b46b09dba6032e54ce9fdebb6299020723c8
```
