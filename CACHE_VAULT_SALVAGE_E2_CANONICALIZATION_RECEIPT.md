# Cache Vault — Salvage E2 Canonicalization Receipt

**Date:** 2026-08-20
**Gate:** Cache Vault Salvage E2 canonicalization — Dialog Teardown Race

## Topology

| | |
|---|---|
| Pre-E2 canonical `master` SHA | `f592e479e4af6deac536282a585e2b3c73f65e6c` (post Salvage E1) |
| E2 candidate SHA | `2884463d93fde57572d04bc28bbb1a4fedddd3be` on `fix/dialog-teardown-race-e2` |
| Rollback tag | `pre-salvage-e2-dialog-teardown` → `f592e479e4af6deac536282a585e2b3c73f65e6c` (verified via `git show-ref --tags`) |

Confirmed before the move: `git merge-base master 2884463...` = `f592e479...` (= `master` itself), `git merge-base --is-ancestor master 2884463...` = `true`, `git status --short` showed no tracked working-tree changes. Pure fast-forward.

## Fast-forward

```
git merge --ff-only 2884463d93fde57572d04bc28bbb1a4fedddd3be
Updating f592e47..2884463
Fast-forward
 cache_vault/ui/clip_workflows.py                  |  12 ++
 cache_vault/ui/dialogs.py                         |  20 +-
 tests/test_clip_workflows_bring_to_front_race.py  | 136 +++++++++++++
 tests/test_dialog_bring_to_front_teardown_race.py | 221 ++++++++++++++++++++++
 4 files changed, 388 insertions(+), 1 deletion(-)
```

## Zero-diff tree identity proof

```
git rev-parse master                                                    → 2884463d93fde57572d04bc28bbb1a4fedddd3be
git rev-parse 2884463d93fde57572d04bc28bbb1a4fedddd3be                  → 2884463d93fde57572d04bc28bbb1a4fedddd3be
git diff master 2884463d93fde57572d04bc28bbb1a4fedddd3be --exit-code    → zero diff (exit 0)
git status --short                                                      → clean (only unrelated pre-existing untracked process files)
```

## Failing-before reproduction (carried forward from the E2 gate, not re-derived)

**Deterministic (fake scheduler):**
```
tests\test_dialog_bring_to_front_teardown_race.py .FF...   [100%]
2 failed, 4 passed in 0.38s
```
**Real-Tk, through the actual `EditClipTextDialog` close path:**
```
tests\test_clip_workflows_bring_to_front_race.py F.   [100%]
1 failed, 1 passed in 1.67s
```
Both reproduced the exact defect — a closing dialog getting deiconified/lifted/focused/grabbed by a deferred `_bring_to_front` callback — before any production code was touched.

## Exact vulnerable-dialog count

`_bring_to_front` is called from **13 sites across 12 dialog classes**. Every site was individually inspected for whether its class overrides `destroy()` with staged (async) teardown — the precondition for the race. **Exactly 2 of 12 are vulnerable**: `ClipComposerDialog` and `EditClipTextDialog` (both in `clip_workflows.py`, both `withdraw()` immediately then defer the real `super().destroy()` by 50ms). The other 10 — 9 in `dialogs.py` (none override `destroy()`) plus `MultiLinkPasteDialog` in `clip_workflows.py` (also unstaged) — destroy synchronously, so by the time any deferred callback could fire the widget is already genuinely gone; `deiconify()` raises and is caught by the pre-existing `try/except`, with no visible re-show. Full inventory table, per-site, in `CACHE_VAULT_SALVAGE_E2_DIALOG_TEARDOWN_RECEIPT.md`.

## Shared-helper vs. per-dialog fix responsibilities

- **`cache_vault/ui/dialogs.py` (shared `_bring_to_front`/`_raise()`):** the actual correctness guarantee. `_raise()` now returns early if `not win.winfo_exists() or getattr(win, "_closing", False)` — holds even if job-cancellation loses a narrow race, since Python's single-threaded event loop means `_closing = True` is set before any queued `_raise()` invocation can run. Inert (always `False`) for the 10 unaffected classes, confirmed via a real `AboutDialog` control test, not merely assumed.
- **`cache_vault/ui/clip_workflows.py` (`ClipComposerDialog.destroy()`, `EditClipTextDialog.destroy()`):** a courtesy on top of the guarantee, not a substitute for it — cancels the job captured by `_bring_to_front` (`win._bring_to_front_job`) at the start of teardown, preventing a harmless-but-wasted pending callback from sitting in Tk's after-queue. Matches the existing guarded-`try/except` idiom already used for every other "may already be gone" step in these two methods.
- `FirstUseGuideDialog`'s existing, more general `<Destroy>`-event/`_pending_after_ids` machinery (fixing a related-but-different bug: CustomTkinter's own internal callbacks raising uncaught errors under Tcl-cascade destruction) was inspected and deliberately not copied — `_bring_to_front`'s `_raise()` already self-protects with `try/except`, and `winfo_exists()` alone already covers the cascade case, so the smaller two-part fix is the correct minimum for this specific invariant.

## Focused after-fix proof (re-confirmed here on canonical `master` post-fast-forward)

```
tests\test_dialog_bring_to_front_teardown_race.py .........              [ 75%]
tests\test_clip_workflows_bring_to_front_race.py ...                     [100%]
12 passed in 1.86s
```
All 10 invariants (A–J: live-dialog raise still works, no re-show/re-lift/re-grab during staged teardown, job cancellation, idempotent repeated close, safe cancellation of an already-fired job, no leaked pending callback, affected dialog closes normally, unrelated dialogs unaffected) individually covered in the E2 gate's own receipt.

## Prior 128-pass regression surface (not re-run here — tree is byte-identical)

From the E2 gate's own validation, against the exact tree content now canonical: `test_combine_dialog_lifecycle.py`, `test_ctk_textbox_scrollbar_teardown.py`, `test_dialog_placement.py`, `test_dialogs.py`, `test_first_use_guide.py`, `test_first_use_guide_titlebar_teardown.py`, `test_macro_dialogs.py`, `test_packaged_dialogs_harden.py`, `test_shell_pump_teardown.py`, `test_shell_titlebar_icon_teardown.py`, `test_toast_destroy_teardown.py`, `test_edit_clip_text_lifecycle.py`, plus the two new E2 files — **128 passed, 0 failed** (176.82s). Not re-run here per this gate's own instruction — the zero-diff check above already proves tree identity is unchanged from that validated content.

## Post-fast-forward sanity gates (run fresh against the now-canonical checkout)

| Gate | Result |
|---|---|
| `tests/test_dialog_bring_to_front_teardown_race.py` + `tests/test_clip_workflows_bring_to_front_race.py` (focused, on canonical `master`) | **12 passed**, 1.86s |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on `cache_vault/ui/dialogs.py`, `cache_vault/ui/clip_workflows.py` | **PASS** |

## Working-tree state

```
git status --short
?? CACHE_VAULT_POST_CANONICAL_DIRTY_TREE_SALVAGE_AUDIT.md
?? CACHE_VAULT_SALVAGE_E1_CANONICALIZATION_RECEIPT.md
?? CACHE_VAULT_SALVAGE_E1_FILTER_NAV_RECEIPT.md
?? CACHE_VAULT_SALVAGE_E2_DIALOG_TEARDOWN_RECEIPT.md
?? CANONICAL_PROJECT_RECORD.md
```
Clean of tracked changes. The untracked files are this canonicalization process's own working documents, unrelated to E2's source diff.

## Final classification

**`CANONICALIZED — DIALOG TEARDOWN RACE FIXED`**

## Stop condition honored

E3 not started. `lan_ip.py`, `shell.py`, `mobile_dialogs.py` not touched. `preservation/pre-gate5f-dirty-2026-08-20` (stash and branch) not reapplied — reconfirmed via direct `git rev-parse` immediately after the fast-forward, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. The `fix/dialog-teardown-race-e2` branch was not pruned (still points at `2884463...`, now also `master`'s tip). `master` not pushed to any remote.
