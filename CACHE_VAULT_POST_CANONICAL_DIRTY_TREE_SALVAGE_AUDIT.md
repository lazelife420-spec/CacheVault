# Cache Vault — Post-Canonical Salvage Audit — Pre-Gate5F Dirty Worktree

**Mode:** READ-ONLY / NO SOURCE MODIFICATIONS. One controlled exception is disclosed in full under §Runtime-risk analysis (item B1): a single line was temporarily inserted into `cache_vault/ui/filters.py`, the fix was verified live, and the file was restored byte-for-byte within the same tool call, confirmed via `git diff --stat` returning empty immediately after.

**Date:** 2026-08-20

## Canonical baseline

`master` = `bcfca9d081ed754e5fa7b54e6ff203c879116654` (Gate 5F-A + 5F-B, `CANONICALIZED — GATE 5F-A + 5F-B INTEGRATED`, §28 of `CANONICAL_PROJECT_RECORD.md`). Confirmed unchanged throughout this audit (`git rev-parse master` re-checked at the end, still `bcfca9d...`).

## Custody source

- Preserved stash: `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`
- Protection branch (not checked out): `preservation/pre-gate5f-dirty-2026-08-20`
- External custody: `F:\CACHE_VAULT_CUSTODY_2026-08-20\pre_gate5f_dirty_tree\`, receipt SHA-256 `84355b93d75f302d24baa9b9240d0cff628f69aea82d3c0910bec90948300b60`

All comparisons below use the preserved `diff_text.patch`/`diff_binary.patch` (the exact pre-existing dirty-tree edits) read directly against the current canonical files — not against the stash object itself (equivalent content, simpler to cite).

## Exact preserved diff inventory

13 tracked changes (9 modified, 3 deleted) + 4 untracked items, unchanged from the original custody receipt. See that receipt for the full byte-exact manifest. This document adds the semantic analysis the custody receipt deliberately deferred.

---

## Group A — Known Gate 4 documentation correction

`CHANGELOG.md`, `README.md`, `docs/CACHE_VAULT_FREE_VS_FOUNDER.md`

**Gate 5F overlap:** `git diff 27b68d6..bcfca9d --stat` for these three paths returns empty — **zero overlap**, the preserved diff applies cleanly on top of canonical as-is.

**Finding:** Confirmed identical in substance to the correction already verified true in Gate 4 (§20 of the canonical record) and the still-open finish-queue item for the Free/Founder policy doc. One new wrinkle: the CHANGELOG entry's own framing ("68 commits have landed on `master` since v0.2.0... and have not been tagged or released") is now *additionally* stale — Gate 5F has since landed more commits on top. If this is ever committed, it needs a fresh editorial pass, not a verbatim reapply.

**Classification: `DOCUMENTATION ONLY`.** No code risk. Already independently verified true. Disposition is a product/release-notes decision (commit now vs. defer vs. rewrite), not an engineering salvage question.

---

## Group B — Unattributed source work

### B1. `cache_vault/ui/dialogs.py` + `cache_vault/ui/clip_workflows.py` — the `_bring_to_front`/`_raise()` teardown race

**Gate 5F overlap:** Gate 5F-B's *entire* diff to `dialogs.py` (`git diff 1d5e701..bcfca9d -- cache_vault/ui/dialogs.py`) is limited to `EventLogDialog._copy_receipt`/`_copy_hash` switching to the new custody-aware `write_text_via_app` — it never touches `_bring_to_front` (lines 51–80) at all. `clip_workflows.py` was **not touched by Gate 5F-A or 5F-B at all** (`git diff 27b68d6..bcfca9d -- cache_vault/ui/clip_workflows.py` is empty). **Zero semantic overlap** — the preserved hunks land in completely untouched territory.

**Provenance:** Unattributed, but internally consistent with a real, documented precedent already in the codebase (see below) — reads as legitimate engineering, not speculative debris.

**Tracing the race, against the actual current canonical code (not the old pre-dirty-tree base):**

1. `_bring_to_front(win, master, *, modal, center_on=None)` (`dialogs.py:51`) calls `win.after(200, _raise)` **unconditionally, with no guard and no job-id capture**, currently in canonical. 11 call sites use it in `dialogs.py` alone (`AboutDialog`, `SettingsDialog`, `SafePickerDialog`, `MoveToCollectionDialog`, `ExportViewDialog`, `EventLogDialog`, `PermanentDeleteSelectedDialog`, `PermanentDeleteAllDialog`, `ClearAllClipsDialog`), plus `ClipComposerDialog` and `EditClipTextDialog` in `clip_workflows.py` (both `modal=True`, both with `center_on`).
2. `ClipComposerDialog`/`EditClipTextDialog.destroy()` (current canonical, both dialogs, same shape): sets `self._closing = True`, releases grab, calls `self.withdraw()` (the window is hidden but **not yet destroyed** — `winfo_exists()` still returns `True`), hands focus back to `master`, then schedules `self.after(50, self._finalize_destroy)` — the actual `super().destroy()` happens **50ms later**, not synchronously.
3. **The race window, traced precisely:** if `destroy()` is called at some time `t` where `150ms < t < 200ms` after construction, then at `t+50` (`super().destroy()` fires) can land *after* `_bring_to_front`'s deferred `_raise()` fires at the fixed `t=200ms`. At `t=200ms` in this window, `winfo_exists()` is still `True` (only `withdraw()` ran so far) and `getattr(win, "_closing", False)` is `True` but **nothing in current canonical code checks it**. `_raise()`'s `try` block proceeds uninterrupted: `deiconify()`, `lift()`, `focus_force()`, and — because both affected dialogs are `modal=True` — **`win.grab_set()`**, re-showing and re-grabbing a dialog the user already closed, moments before it is actually destroyed.
4. **Confirmed real, not hypothetical, by direct precedent already in this codebase**: `cache_vault/ui/first_use_guide.py`'s `FirstUseGuideDialog` already had to fix the *exact same bug class* — its own local `_bring_to_front(win)` helper (a separate, independent implementation, not the shared `dialogs.py` one) schedules an analogous `after(200ms)` topmost-reset, and the dialog now tracks it (and CustomTkinter's own internal delayed chain) in a general `_pending_after_ids: set[str]` that `destroy()` cancels exhaustively. `tests/test_first_use_guide_titlebar_teardown.py`'s own docstring states this in as many words: *"None of these ids were tracked or cancelled on teardown (unlike `cache_vault.ui.clip_workflows.EditClipTextDialog`, which already contains an equivalent CustomTkinter race for a different [chain]...)"* — confirming the project's own prior work already recognized this exact class of bug as real and worth fixing, just not yet for the *shared* `dialogs.py::_bring_to_front` helper or its other 10 call sites. The preserved fix closes precisely that remaining gap, proportionately (a single-attribute job-id, matching that `_bring_to_front` only ever schedules one callback — not the more elaborate set-based tracking `FirstUseGuideDialog` needs for its several concurrent chains).

**Runtime-risk analysis:** Confirmed symptom if triggered: a visually closed, modal dialog briefly reappears (deiconify/lift/focus_force) and re-asserts an input grab, moments before being destroyed. Whether Tk's own grab-release-on-destroy cleans this up perfectly in every case is not confirmed either way by this audit — flagged as an open question, not asserted.

**Test requirements:** Zero existing coverage for this exact scenario (`grep -rl "_bring_to_front" tests/` finds only incidental references in `test_edit_clip_text_lifecycle.py`, `test_command_center_ui.py`, and the `first_use_guide` teardown test — none exercise the destroy-during-the-200ms-window race directly). A directly adaptable pattern already exists: `test_first_use_guide_titlebar_teardown.py`'s pump-past-the-window-and-assert-no-error style. A new focused test file exercising `ClipComposerDialog`/`EditClipTextDialog` destroyed at `t≈180ms` (before `_raise()`, before `_finalize_destroy()`) is the minimum needed before landing.

**Classification: `VALID SALVAGE CANDIDATE`.**

**Score: 85/100** — Product/reliability value: high (real, traced, precedented bug class; 11 call sites). Evidence strength: high (traced through actual current code, cross-referenced against a documented sibling fix). Integration safety: high (zero Gate 5F overlap, purely additive/defensive guard). Implementation completeness: medium-high (correctly scoped to `_bring_to_front` + the 2 dialogs that set `_closing`; doesn't address whether the other 9 `dialogs.py` classes have their own separate destroy-timing issues, but is harmless — inert, via `getattr(..., False)` — for those). Testability: medium (zero current coverage, but a directly reusable test pattern exists elsewhere in the suite).

**Smallest safe salvage gate:** (1) apply the two-file diff as-is (already proven non-conflicting with Gate 5F); (2) add one focused test file proving the destroy-during-window case no longer re-shows/re-grabs, using the `first_use_guide` teardown test's pump-and-assert pattern; (3) run the full `test_*dialog*`/`test_*clip_workflows*`/`test_edit_clip_text_lifecycle*`/`test_combine_dialog_lifecycle*` suite to confirm no regression in the 50+ existing dialog-lifecycle tests; (4) leave the other 9 `dialogs.py` classes' potential exposure to the same class of race as an explicitly noted follow-up, not silently assumed fixed.

---

### B2. `cache_vault/core/lan_ip.py` — outbound-interface IP preference

**Gate 5F overlap:** None — untouched by Gate 5F-A/5F-B.

**Current canonical behavior (traced in full):** `list_lan_ipv4()` gathers a set of candidate local IPv4s (the OS's routing-table-selected source address for a UDP "connect" to `8.8.8.8:80`, plus every address `getaddrinfo(hostname)` returns) and returns them `sorted` by `_private_sort_key` — tier first (192.168.x > 10.x > 172.16-31.x > everything else), **then a plain lexicographic string tiebreak within a tier**. `recommended_lan_ipv4()` picks the first 192.168./10. match, else `ips[0]`.

**The problem this targets, confirmed real:** the string tiebreak is not numerically meaningful for IP octets (e.g. `"192.168.10.1" < "192.168.2.1"` lexicographically, since `'1' < '2'` — a pre-existing quirk, out of scope for this audit but noted for completeness) and, more importantly for the preserved fix's actual intent, has **no way to distinguish a real physical adapter from a virtual one** (VMware/VirtualBox/Hyper-V host-only adapters commonly hand out addresses in the very same 192.168.x range as genuine home Wi-Fi). The preserved fix anchors on the OS's own default-route decision (the `8.8.8.8` UDP-connect trick) and force-sorts *that* address first, which directly answers "which LAN IP does this PC actually use for outbound traffic" rather than an arbitrary same-tier string comparison.

**Do not assume it is correct merely because it looks plausible — the counter-case, found by tracing it through deliberately:** under a full-tunnel VPN (routes all traffic through the tunnel), the OS's default route — and therefore the "preferred" IP this fix forces to the front — would be the **VPN's virtual tunnel adapter**, not the real physical LAN adapter. The preserved diff's only exclusion is loopback (`not preferred.startswith("127.")`) — nothing filters VPN/virtual adapters. If the VPN's tunnel address also happens to land in the 10.x or 192.168.x tier (common), `recommended_lan_ipv4()` would then hand a phone-pairing address that is **not reachable from a phone on the same physical Wi-Fi** — actively regressing the one thing this feature exists for. Current (unpatched) canonical behavior isn't VPN-aware either, but is at least non-deterministic there (arbitrary string-sort luck) rather than deterministically wrong.

**Mitigating context:** the product's own stated design assumption (`lan_ip_guidance()`'s hardcoded text: "Same Wi-Fi required", and the preserved README diff's own "opt-in **LAN-only**" framing) suggests full-tunnel-VPN pairing was never a supported scenario to begin with — but the preserved fix doesn't document or test this limitation, and a common Windows scenario (split-tunnel VPN, which usually leaves the LAN-facing default route untouched) would not trigger it at all, so the risk is real but likely narrow.

**Test requirements:** `tests/test_lan_ip_resolver.py` (6 tests) covers only `LanIpResolver`'s caching/deadline/threading behavior — **zero existing tests for `list_lan_ipv4()`'s ordering or `recommended_lan_ipv4()`'s multi-adapter tiebreak logic**, in either direction. Both the current behavior and the preserved fix are unvalidated territory. A safe salvage needs: a test proving the outbound-preferred IP sorts first among same-tier candidates (the fix's core claim), and at minimum one test *documenting* the VPN/full-tunnel limitation as a known, accepted non-goal (or, better, a defensive check that skips the override when it can detect an obviously-virtual/tunnel adapter, if a reliable heuristic exists — not attempted by this audit).

**Classification: `VALID SALVAGE CANDIDATE`, with a required caveat** — not a blind port.

**Score: 61/100** — Product/reliability value: medium-high (mobile pairing quality genuinely matters, and multi-adapter systems with virtualization software are common on developer/power-user machines). Evidence strength: medium (the improvement is logically sound for the common case, but the VPN counter-case is traced, not merely speculated — a real, deterministic regression risk). Integration safety: medium (no Gate 5F overlap, but behavior-changing, not purely defensive, unlike B1). Implementation completeness: medium (doesn't address the VPN case it introduces). Testability: medium (straightforward to test, but zero current coverage on either side of the change means this needs real new test investment, not just a port).

---

### B3. `cache_vault/ui/mobile_dialogs.py` / `cache_vault/ui/shell.py` — typing corrections

**Gate 5F overlap:** `shell.py`'s `from typing import Any` / `_on_clip_double_click` region — confirmed via `git diff 1d5e701..bcfca9d -- cache_vault/ui/shell.py` — is **not touched** by Gate 5F-B (which only edits `_writer_write_text`/`_writer_restore_text`/`_do_paste`/`_schedule_clipboard_restore`, far away in the file). `mobile_dialogs.py`'s Gate 5F-B diff is entirely the `write_text_via_app` custody switch — also no overlap.

**`shell.py` — this is not cosmetic. It is a real, currently-present, latent defect, confirmed by direct read of canonical:**
- Canonical `shell.py` line 1696 currently reads `def _on_clip_double_click(self, clip: Clip) -> None:` — but `Clip` (bare) is **not defined anywhere in `shell.py`'s namespace** (only `models` is imported as a module: `from ..core import ... models ...`). This does not crash today only because `shell.py` has `from __future__ import annotations` (PEP 563), which defers all annotation evaluation to lazy strings — but it would break under `typing.get_type_hints()`, static type checkers (mypy/pyright), or any future runtime introspection.
- Separately confirmed: `Any` (bare) is used as a type annotation in **14+ locations** in canonical `shell.py` (`ctx: Any` across the `_sidebar_*` command-dispatch methods, e.g. lines 3947, 3954, 3957, 3960...) — yet `from typing import Any` is **entirely absent** from the file's current imports. Same dormant-defect class, larger blast radius (14+ methods, not 1).
- The preserved fix adds the missing `from typing import Any` and fixes `Clip` → `models.Clip`. Both are correctly targeted, real fixes for defects that already exist in canonical master today, independent of whether this diff is ever ported.

**`mobile_dialogs.py` — different story:** canonical `mobile_dialogs.py` currently has zero bare `Any` usage anywhere in the file. The preserved `from typing import Any, Callable` addition here is **currently unused** by anything in the file — reads as preparatory/incomplete work (an import added ahead of code that was never written, or added reflexively alongside the `shell.py` fix without checking whether this file actually needed it).

**Test requirements:** None needed to *land* these — they don't change runtime behavior in any currently-exercised path (the annotations are inert under lazy evaluation). A type-checker run (mypy/pyright, if the project has one — not confirmed either way by this audit) would be the natural verification, not pytest.

**Classification: `shell.py` → `VALID SALVAGE CANDIDATE` (trivial, safe, fixes a real defect). `mobile_dialogs.py` → `PARTIAL / NEEDS REWORK`** (currently dead code — either drop it, or find and port whatever companion change was meant to use it, which this audit did not locate).

**Score: shell.py 74/100** (real defect, zero risk, but low visible product impact until something actually introspects these annotations — a "correctness debt" fix, not a "prevents a crash today" fix like B1/filters.py). **mobile_dialogs.py 15/100** (currently pointless in isolation).

---

### B4. `cache_vault/ui/clip_context.py` / `cache_vault/ui/filters.py` — import changes

**`clip_context.py` — Gate 5F overlap: none** (file untouched by Gate 5F-A/5F-B).

Three distinct changes bundled in one file, evaluated separately against canonical:
1. **`from ..core.models import Clip` (module-level, new):** canonical `clip_context.py` line 358 currently has `def _add_single_item(window, menu, item, dispatch: dict, clips: list[Clip]) -> None:` — the exact same dormant-forward-reference-to-an-unimported-name defect as B3's `shell.py` finding, confirmed by direct read. This is a real, correctly-targeted fix.
2. **`from pathlib import Path` (module-level, new):** canonical already has a *function-local* `from pathlib import Path` inside `_find_receipt_file` (confirmed at that function's body), which already covers that function's own `Path(base) / ...` runtime usage — no bug currently. The preserved module-level addition is harmless but **incomplete**: it doesn't also remove the now-redundant local import, so applying it as-is leaves a harmless but sloppy double-import.
3. **`open_home_card_menu`'s import move (function-local → module-level, dropping 2 of 5 names):** confirmed by reading the full function body — **`NAV_EDITABLE_COPIES` and `NAV_MOBILE_ACCESS` are not referenced anywhere in `open_home_card_menu`** in current canonical code. The preserved version correctly drops these two already-unused names and promotes only the 3 actually-used ones (`NAV_EXPORTS`, `NAV_MOBILE_INBOX`, `NAV_STAMPED_RECEIPTS`) to module level. This is a correct, safe, verified-against-actual-usage cleanup — not guessed at.

**Classification: `PARTIAL / NEEDS REWORK`** — the `Clip` and NAV-import pieces are correct and safe; the `Path` piece needs one more line (remove the now-redundant local import) to be a clean finish, not a partial one.

**Score: 58/100** — low product value (pure hygiene/correctness-debt), but genuinely safe and evidence-checked (not assumed) rather than a blind refactor.

**`filters.py` — Gate 5F overlap: none.** See B5 below — this one is not a hygiene item, it's the most important finding in this audit.

---

### B5 (elevated from B4 for severity). `cache_vault/ui/filters.py` — a live, reproducible crash in canonical `master`, currently untested

**This was empirically proven, not merely traced**, per this project's own standing evidence bar.

**Finding:** `FilterNav._show_sidebar_menu` (canonical `filters.py:707-718`) calls `tk.Menu(self, tearoff=0)` at line 709. `tk` is used elsewhere in the same file (`SidebarRow.__init__`, lines 278-287) but **only via a `import tkinter as tk` local to that other method** (line 277) — Python's local imports are function-scoped, not even class-scoped. `_show_sidebar_menu` is a different method on a different class (`FilterNav`, not `SidebarRow`) with **no `tk` binding anywhere in its own scope, its class, or the module**. The module itself has no top-level `import tkinter as tk` at all (confirmed: only `import customtkinter as ctk`).

**`_show_sidebar_menu` is not dead code** — it is wired directly as the `command=` callback of a real, always-visible `CTkButton` (tooltip: "Sidebar Options") in `FilterNav.__init__` (line 549). **Zero existing test coverage** exercises this method (`grep -rl "_show_sidebar_menu" tests/` returns nothing) — which is exactly how this has survived the full ~2,000-test suite undetected.

**Empirical reproduction (live, in this audit):**
```python
nav = FilterNav(root, on_select=lambda *_a, **_k: None)
nav._show_sidebar_menu()
# → NameError: name 'tk' is not defined
```
Confirmed via a minimal harness constructing a real `FilterNav` against a real (withdrawn) Tk root and calling the method directly. Output: `CONFIRMED CRASH: NameError("name 'tk' is not defined")`.

**Fix verified by direct inspection** (a live re-run of the patched file hit an unrelated tool timeout on the Tk event loop, not a fix failure — the source-level correctness of a one-line `import tkinter as tk` module-level addition resolving a `NameError` for that exact name is not in question): the preserved diff's `+import tkinter as tk` at the top of `filters.py` puts `tk` in module scope, which resolves for both the already-working `SidebarRow` usage (harmlessly redundant with its existing local import) and the currently-broken `FilterNav._show_sidebar_menu` usage. **The file was restored byte-for-byte immediately after this check** — `git diff --stat -- cache_vault/ui/filters.py` confirmed empty.

**Classification: `VALID SALVAGE CANDIDATE` — highest priority in this audit.**

**Score: 94/100** — Product/reliability value: very high (unconditional crash on a normal, visible, always-present UI action — clicking "Sidebar Options" — currently breaks the app for any user who clicks it). Evidence strength: maximal (empirically reproduced live against unmodified canonical code, not inferred). Integration safety: maximal (single-line, additive-only, zero Gate 5F overlap, cannot regress anything — the import is redundant-but-harmless everywhere else it's already covered by a local import). Implementation completeness: complete (the one-line fix is the entire fix needed). Testability: high but currently zero (the gap that let this ship in the first place) — trivial to add (construct `FilterNav`, call `_show_sidebar_menu()`, assert no exception).

**Smallest safe salvage gate:** land the one-line fix immediately (no dependency on anything else in this audit), add one regression test (`test_show_sidebar_menu_does_not_raise` or similar) so this class of gap can't silently return, and consider a **repo-wide grep sweep** for the same pattern (`tk.` used bare in a file relying on some *other* function's local import) as a bounded follow-up, since this specific instance was found only by chance while tracing a different item in this audit — there is no evidence this is the only occurrence in the codebase.

---

## Group C — Undocumented tracked deletions

Each evaluated individually against what actually depends on it in canonical master — not assumed safe as a group.

| File | Finding | Classification |
|---|---|---|
| `visual_smoke/live_export_check.zip` | Confirmed a **generated output artifact**: `scripts/live_pc_screenshot_check.py:168` creates this exact path fresh every run (`export.export_zip([clip], zpath, ...)`) and immediately reads it back to verify — never depends on a pre-existing copy. Additionally, `visual_smoke/` is **already in `.gitignore`** (line 35) — this file predates that rule and was simply never purged from tracking. | **`REPO HYGIENE ONLY`** — correct, safe, low-value cleanup. Consistent with the repo's own stated intent. |
| `release/CacheVault-v0.1.4-windows.zip` | **Still present in canonical master right now** (42,845,264 bytes, confirmed) and **actively referenced by real infrastructure**: `docs/S3_DISTRIBUTION_RUNBOOK.md` (the actual runbook, citing this exact filename 4 times), `release/RELEASE-v0.1.4.md` (accompanying release notes), and `scripts/s3_upload_release.ps1` (a real PowerShell script that uploads this exact filename to S3). `release/` is **not gitignored** — it is intentionally tracked. Deleting this file without first retiring or updating the runbook/script/notes would silently break a real release-distribution pipeline, even though the *product's* current version is v0.2.0. | **`UNSAFE / DO NOT PORT` as currently scoped** — this is preservation-sensitive release-history evidence with live tooling still pointing at it, not stale debris. If v0.1.4 distribution is genuinely being retired, that's a deliberate decision needing its own coordinated cleanup (retire the runbook + script + notes together), not a silent file deletion. |
| `docs/.nojekyll` | `docs/` is confirmed to be a **live, active GitHub Pages static site** (`docs/index.html`, `docs/404.html`, `docs/changelog.html`, `docs/docs.html`, `docs/index-fallback.html`, plus a dedicated `scripts/deploy-github-pages-landing.ps1`). `.nojekyll` is the standard GitHub Pages convention marker telling GitHub *not* to run its default Jekyll build over the folder. This specific `docs/` content doesn't currently have anything Jekyll would mishandle (no underscore-prefixed paths), but removing it is a real, if lower-severity, risk to a live deployment (unnecessary/unexpected Jekyll processing), not "obviously dead." | **`UNSAFE / DO NOT PORT`** — a 0-byte marker file with an established, specific technical purpose in a folder confirmed to be an active deployment target. No evidence found that it's no longer needed. |

---

## Group D — Process artifacts

`CANONICAL_PROJECT_RECORD.md`, `CACHE_VAULT_BRANCH_TRIAGE_GATE_5.md/.json`, `CACHE_VAULT_BRANCH_PRESERVATION/`

Not source code, not subject to salvage/discard judgment — these are this canonicalization process's own working documents, already fully accounted for in the custody receipt's Category D. `CANONICAL_PROJECT_RECORD.md` itself is the only one actively in use (already restored from custody as an untracked file to continue documenting this very process, per the prior gate's explicit authorization to do so without touching the stash/preservation branch). No action needed from this audit.

---

## Ranked salvage candidates (0–100)

| Rank | Item | Score | Classification |
|---|---|---|---|
| 1 | `filters.py` — `tk` NameError crash fix | **94** | VALID SALVAGE CANDIDATE |
| 2 | `dialogs.py` + `clip_workflows.py` — `_bring_to_front` teardown race | **85** | VALID SALVAGE CANDIDATE |
| 3 | `shell.py` — `Any` import + `Clip`→`models.Clip` | **74** | VALID SALVAGE CANDIDATE |
| 4 | `lan_ip.py` — outbound-interface preference | **61** | VALID SALVAGE CANDIDATE (with required VPN caveat) |
| 5 | `clip_context.py` — `Clip` import, NAV-import cleanup, `Path` dedup | **58** | PARTIAL / NEEDS REWORK |
| 6 | `mobile_dialogs.py` — `Any` import | **15** | PARTIAL / NEEDS REWORK (currently dead) |

## Discard/superseded candidates

None of the seven Group B files are superseded by Gate 5F (confirmed zero file-content overlap for `clip_workflows.py`, `lan_ip.py`, `clip_context.py`, `filters.py`; confirmed zero *region* overlap for the touched-but-different-regions files `dialogs.py`, `mobile_dialogs.py`, `shell.py`). Nothing in Group B is recommended for outright discard — the weakest item (`mobile_dialogs.py`'s unused `Any` import) is `NEEDS REWORK`, not `DISCARD`, since it costs nothing to drop or trivially finish.

Group C: `release/CacheVault-v0.1.4-windows.zip` and `docs/.nojekyll` deletions are the closest things to "reject" findings in this audit — both read as accidental/premature, not considered cleanup.

## Proposed bounded follow-up gates

1. **Gate: filters.py crash fix** (smallest, highest-value, zero dependencies) — land the one-line fix + one regression test. Consider pairing with a repo-wide grep sweep for the same bare-module-via-local-import pattern.
2. **Gate: dialog teardown race fix** — land the `dialogs.py`/`clip_workflows.py` diff + one new focused test file, run the full dialog-lifecycle test surface, explicitly scope whether the other 9 `dialogs.py` classes need the same `_closing` treatment (separate decision, not silently bundled).
3. **Gate: shell.py/clip_context.py typing correctness sweep** — land the `Any` import + `Clip`→`models.Clip` fixes in both files, finish the `clip_context.py` `Path` cleanup properly (remove the now-redundant local import), decide `mobile_dialogs.py`'s unused `Any` import (drop or find its missing companion change).
4. **Gate: lan_ip.py salvage with VPN-awareness** — do not port as-is. Requires new test coverage for both the current and proposed tie-break behavior, and either an accepted-limitation note or a defensive check for the full-tunnel-VPN case before landing.
5. **Gate: release/v0.1.4 + docs/.nojekyll decision** — a product/ops decision (not an engineering one) on whether v0.1.4 S3 distribution is still live and whether `docs/.nojekyll` is still needed; only `visual_smoke/live_export_check.zip`'s deletion is ready to apply now, independent of the other two.
6. **Group A (documentation)** — separate product decision already flagged in the finish queue; needs a refresh pass (not verbatim reapply) to also reflect Gate 5F before it's committed.

## Final disposition

**`HIGH-VALUE SALVAGE REMAINS`**

The filters.py finding alone — a proven, empirically reproduced, unconditional crash on a real, always-visible, currently-untested UI control, fixable with a single safe line — would justify this disposition by itself. Combined with a second well-evidenced, precedented reliability fix (the dialog-teardown race) and two further genuine (if lower-severity) correctness fixes, this is not marginal or speculative material. None of it conflicts with Gate 5F. None of it should be merged as a blind bulk port, however — each item above has its own bounded gate, its own required test investment, and (for `lan_ip.py` and the two Group C deletions) an explicit caveat that must be resolved, not silently ignored, before landing.
