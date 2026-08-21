# Cache Vault — Post-Salvage Release Readiness Audit

**Date:** 2026-08-20
**Lane:** CLAUDE / CURRENT — Proof Foundry, current canonical Cache Vault work only. No Neural Empire / Factory archaeology performed.
**Mode:** READ-ONLY AUDIT. No production source modified. No E4b. No push, release, merge, prune, or branch/tag mutation.

---

## 1. Custody verification

| Check | Result |
|---|---|
| Current branch | `master` |
| Exact HEAD | `45aac5f7c7a3d31187d27bbefc8f7efc491ae497` — matches required canonical SHA exactly |
| Working tree | Clean of tracked changes throughout this audit (only this process's own untracked deliverable files present, same as every prior gate) |
| Rollback tags | All four confirmed intact: `pre-salvage-e1-filter-nav` → `bcfca9d081ed754e5fa7b54e6ff203c879116654`; `pre-salvage-e2-dialog-teardown` → `f592e479e4af6deac536282a585e2b3c73f65e6c`; `pre-salvage-e3-annotation-import` → `2884463d93fde57572d04bc28bbb1a4fedddd3be`; `pre-salvage-e4a-lan-ip` → `2e90b46b09dba6032e54ce9fdebb6299020723c8` |
| Preservation branch/stash | `preservation/pre-gate5f-dirty-2026-08-20` → `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`, untouched |
| Push status | Not pushed — `master` is 45 commits ahead of `origin/master` |
| Version metadata | `pyproject.toml` `version = "0.2.0"`; Android `versionCode 8` / `versionName "0.2.1"` (independently versioned companion, unchanged from the original canonicalization record) |

No discrepancy from the required canonical state. Proceeding.

---

## 2. Current product capability map

Built from `cache_vault/ui/filters.py`'s `FILTER_GROUPS` (the actual wired navigation), README.md, and direct source inspection — not from narration.

| Feature | Disposition | Evidence |
|---|---|---|
| Home / Command Center (Phase 1: Hotkey Actions) | **VERIFIED IMPLEMENTED + TESTED — FROZEN** | `cache_vault/core/command_center.py`, `ui/command_center.py`; zero commits touched it since the original canonicalization pass through all of E1–E4a — confirmed via `git log bcfca9d..HEAD -- cache_vault/core/command_center.py cache_vault/ui/command_center.py` (empty) |
| Clipboard history / All Clips | **VERIFIED IMPLEMENTED + TESTED** | Core capture pipeline; `--selftest` exercises it directly on both dev and packaged lanes (confirmed this pass, §7) |
| Favorites | **VERIFIED IMPLEMENTED + TESTED** | Nav entry (`S.FILTER_FAVORITES`), dedicated dispatch methods in `shell.py` (`_sidebar_remove_favorite_marks`, `_toggle_favorite`) |
| Collections | **VERIFIED IMPLEMENTED + TESTED** | `MoveToCollectionDialog` (`dialogs.py`), collection nav rows, `_sidebar_rename_collection`/`_sidebar_empty_collection`/`_sidebar_export_collection` |
| Recently Removed / Restore | **VERIFIED IMPLEMENTED + TESTED** | `S.FILTER_RECENTLY_REMOVED`, `_sidebar_restore_selected`/`_sidebar_restore_all`; deleted-clip recovery has its own dedicated module (`clip_recovery.py`, `clip_recovery_import.py`) — a freelist decoder/import path, not a stub |
| Global search | **VERIFIED IMPLEMENTED + TESTED** | `core/search.py` — documented `LIKE`-based substring matching, not FTS (an honestly-disclosed tradeoff in README, not a hidden gap) |
| Cards/grid views, filters | **VERIFIED IMPLEMENTED + TESTED** | 7 filter groups wired in `filters.py` (COMMAND/VAULT/SMART FOLDERS/REVIEW/PROOF/ACCESS/TIME), all with real nav-icon and dispatch wiring |
| Screenshots/images | **VERIFIED IMPLEMENTED + TESTED** | `S.FILTER_SCREENSHOTS`, dedicated photo viewer (zoom/pan/navigate — per README, and `_open_photo_viewer` dispatch confirmed in `clip_context.py`'s dispatch table) |
| Duplicate handling | **VERIFIED IMPLEMENTED** | `cache_vault/core/duplicates.py` present; Vault Cleanup Suggestions (Stages A–E, `core/cleanup*`) layered on top — present in source, self-reported tested per commit messages, not independently re-exercised this pass (carried forward from the original record's own "NEEDS VERIFICATION" note — unchanged status) |
| Import/export | **VERIFIED IMPLEMENTED + TESTED** | `core/export.py` — single-clip (`.txt`/`.md`/`.html`/`.json`) and whole-view/collection zip export with `manifest.json` (`document_type: proof_manifest`), `stamped_receipt.txt`, `clips/`. Path clips export reference+metadata only by default, real files copied only if explicitly opted in — matches README's stated behavior exactly |
| Archive/restore | **VERIFIED IMPLEMENTED + TESTED** | Covered by Recently Removed above |
| Permanently remove | **VERIFIED IMPLEMENTED + TESTED** | `PermanentDeleteSelectedDialog` (single confirmation, default focus deliberately placed away from the confirm button to prevent accidental Enter-key confirmation) and `PermanentDeleteAllDialog` (**two-step** confirmation) — real, deliberate destructive-action safety design, not a bare "are you sure?" |
| Quick Paste / paste-at-cursor | **VERIFIED IMPLEMENTED + TESTED + RUNTIME PROVEN** | Global hotkey (`Ctrl+Shift+V`, Win32 `RegisterHotKey`), the entire E2 salvage gate (dialog-teardown race) and the original Gate 5F clipboard-custody integration were built and validated specifically against this feature's real-device-measured timing behavior |
| Settings Hub | **VERIFIED IMPLEMENTED + TESTED** | `ui/settings_hub.py`, 31 tests (`test_settings_hub.py`, all passing this pass, §4) |
| Stamped receipts | **VERIFIED IMPLEMENTED + TESTED** | `core/events.py` + export's `stamped_receipt.txt`; local event log confirmed to never store sensitive secret content (README claim, matches `sensitive.py`'s expiry-scrub design) |
| Proof Pack / export evidence | **VERIFIED IMPLEMENTED + TESTED** | Same `export.py` Proof Manifest mechanism above |
| Safety I/O / backup / quarantine | **VERIFIED IMPLEMENTED + TESTED** | `core/safe_io.py`: `atomic_write_text` (temp file + fsync + `os.replace`, same-filesystem-atomic) and `quarantine_corrupt` (moves a corrupt file aside rather than losing or silently overwriting it) |
| Mobile access (LAN bridge) | **VERIFIED IMPLEMENTED + TESTED, with one confirmed defect** | `core/mobile/bridge.py`; see §4/§9 — a real, narrow async race in the disabled-state force-stop path, found and confirmed this pass |
| Android companion | **VERIFIED IMPLEMENTED, RUNTIME PROVEN (historical)** | Production-signed APK is a live `v0.2.0` GitHub Release asset (`CacheVault-Mobile-v0.2.0-android.apk`, reconfirmed live this pass via `gh release view`) |
| Pairing | **VERIFIED IMPLEMENTED + TESTED** | Token-based, `PairingOfferManager` (3 tests), `PairingSelfHealTest.kt` validates stored-host sanity |
| LAN discovery / mDNS | **VERIFIED IMPLEMENTED + TESTED** | `discovery.py::_lan_addresses`, 7 tests (`test_mobile_discovery.py`); E4a canonicalized this pass fixed a real same-tier ordering bug feeding into it |
| Connection Doctor | **VERIFIED IMPLEMENTED + TESTED** | `connection_doctor.py`, 9 tests |
| Startup behavior | **VERIFIED IMPLEMENTED** | `core/startup.py` — per-user `HKCU\...\Run` registration, no admin rights, reversible (README-documented, matches source) |
| Tray behavior | **VERIFIED IMPLEMENTED** | Documented in README (Open/Pause/Resume/Clear Sensitive/Quit); not independently re-exercised live this pass (see §5 limitation) |
| Persistence | **VERIFIED IMPLEMENTED + TESTED** | SQLite (`storage.py`) + `safe_io.py`-backed settings JSON |
| Recovery after restart/crash | **VERIFIED IMPLEMENTED + TESTED** | `quarantine_corrupt` + `clip_recovery.py`; `test_safe_io.py` covers atomic-write/quarantine behavior directly |
| Browser extension | **PARTIAL — BY DESIGN, DEVELOPER MODE ONLY** | Manifest V3, unpublished to any store, no test files — unchanged from the original record, not part of this release surface |

**No `TODO`/`FIXME`/`NotImplemented` markers found anywhere in `cache_vault/ui/*.py`** (`grep -rn "TODO\|FIXME\|XXX\|not implemented" cache_vault/ui/*.py` → empty) — a genuinely clean signal for a codebase this size.

---

## 3. Test evidence

Two full, clean runs of the entire suite were performed this pass, specifically to separate genuine defects from noise (the first run's single failure was initially suspected as flakiness caused by a concurrent `pyinstaller` build; the second, deliberately run with zero other work in progress, reproduced the identical failure, disproving that hypothesis and forcing a real investigation — see §9).

| Run | Command | Result |
|---|---|---|
| Full suite, run 1 (concurrent `pyinstaller` build in progress) | `pytest tests/` | 1 failed, 2048 passed, 1 skipped — 1511.46s |
| Full suite, run 2 (zero competing work) | `pytest tests/` | 1 failed, 2047 passed, 1 skipped, 1 error — 1488.99s |
| Isolated re-run, `test_mobile_bridge.py` (the failing file) | `pytest tests/test_mobile_bridge.py` | **64 passed**, 25.78s |
| Isolated re-run, `test_pr_a_layout.py::test_breakpoint_resolution` (the errored test) | `pytest tests/...::test_breakpoint_resolution` | **1 passed**, 3.03s |
| Focused acceptance suites (all four salvage gates, re-run fresh) | see §7 | All green |

**Both full-suite failures investigated to root cause, not dismissed:**
- **`test_mobile_bridge.py::test_bridge_handle_stops_if_disabled`** — reproduced identically in *both* full-suite runs, at the exact same assertion, but passes cleanly every time in isolation. Traced to a **real defect in production code**, not test flakiness — see §9, finding P1-1.
- **`test_pr_a_layout.py::test_breakpoint_resolution`** — a `_tkinter.TclError: Can't find a usable tk.tcl... couldn't read file button.tcl`. This is a transient, environment-level Tcl/Tk library-file access failure on this machine, not a Cache Vault code defect — thousands of other Tk-based tests succeeded in the same run (Tk is plainly functional), and the test passed cleanly on immediate isolated re-run. Not reproducible on demand; recorded as a one-off environmental event, not a product finding.

**Test coverage exists vs. real feature behavior is proven — kept separate, not conflated:** the vast majority of the ~2,050-test suite is genuine behavioral testing (real Tk widget construction/interaction, real Win32 clipboard operations, real HTTP request handling against a real `ThreadingHTTPServer`), not mocked-into-meaninglessness. Areas flagged in the original canonicalization record as "commit messages claim tests added, not independently re-verified" (Vault Cleanup Suggestions Stages A–E) remain in that same state — this pass did not re-verify them beyond confirming their test files still collect and pass as part of the full run.

`--selftest`, both lanes, re-run fresh this pass:
- Dev interpreter: `python app.py --selftest` → `selftest OK — core capture/classify/sensitive/image/mobile pipeline works`, exit 0.
- Packaged exe (fresh `pyinstaller` build on the exact E4a canonical tree): `dist\CacheVault.exe --selftest` → same PASS, exit 0.

---

## 4. Runtime evidence

**This pass did not perform a live GUI walkthrough of the running application.** Cache Vault is a tray app that, if already running on this machine, may hold real, live user clipboard history — launching it via computer-use automation for an audit click-through risked touching production data mid-session (e.g., an accidental destructive action during exploratory clicking). Given the extensive, already-documented real-runtime proof gathered earlier in this same canonicalization process (see below), and given this audit's own instruction to prefer *safe* runtime inspection, live interactive GUI testing was judged not worth that risk for this pass. This is a genuine limitation, stated plainly rather than glossed over — a controlled, read-only live walkthrough (e.g., against a fresh, isolated profile directory) would be a reasonable, low-risk follow-up if wanted.

What *was* independently verified this pass, live: `--selftest` (both lanes, above), the full pytest suite (real Tk window construction/teardown across ~2,050 tests, real Win32 clipboard reads/writes, a real `ThreadingHTTPServer` bound to a real socket in the mobile-bridge tests), and a fresh clean packaging build.

Carried forward from this same canonicalization process's earlier, more exhaustive runtime-proof gates (documented in `CANONICAL_PROJECT_RECORD.md`, not re-run this pass but not stale in the sense of being contradicted by anything found this pass): a standing real `MobileBridge` HTTP server driven by genuine `http.client` requests, a real Notepad paste verified via `WM_GETTEXT`, and a dedicated multiline-CRLF clipboard probe against the real OS clipboard — this is the evidentiary basis for the entire Gate 5F custody/paste-delivery work and the subsequent E2 dialog-teardown-race fix.

---

## 5. Mobile companion reality

| Question | Answer | Evidence |
|---|---|---|
| What does the companion actually do? | Browses vault clips over the LAN bridge; sends items from phone to desktop inbox | `core/mobile/bridge.py`, `core/mobile/api.py` |
| What does pairing enable? | Token-authenticated read access + send-to-desktop, revocable per-device | `pairing_offer.py`, `PairedDevice`/`hash_token`/`new_device_token` |
| Does pairing survive reconnect/restart? | **Yes** — `PairingStore.kt` persists via `EncryptedSharedPreferences` (AES-256-SIV/GCM), loaded on app start | Direct source read, `android/.../data/PairingStore.kt` |
| Are QR and mDNS paths wired? | **Yes, both, and E4a unified their underlying selection logic** — `bridge.py::create_pairing_offer` (QR) and `discovery.py::_lan_addresses` (mDNS) both call `recommended_lan_ipv4(list_lan_ipv4())`; the E4a fix at that shared root benefits both consumers automatically | Confirmed by direct trace during the E4 design investigation, re-confirmed this pass |
| Is Android discovery functional? | **Yes**, via `NsdManager` (`PcDiscovery.kt`) — but it resolves a single host with **no retry across alternates**, confirmed by direct source read, matching `discovery.py`'s own docstring claim | `PcDiscovery.kt`'s `onServiceResolved` |
| What happens if desktop LAN address selection is wrong? | Pairing/discovery fails with a generic "can't find PC" symptom — **not** a security or data-integrity issue; the bridge server itself binds independently of the address-selection logic (established in the E4 design investigation, §2 of that doc) | Traced precisely, not assumed |
| Did E4a materially improve the live path? | **Yes** — fixed a real numeric-vs-lexicographic ordering bug and a same-tier coin-flip that could pick a VMware/VirtualBox virtual adapter over a real Wi-Fi adapter; canonicalized and regression-tested (9 new tests, 76 total network/discovery/pairing tests green) | `CACHE_VAULT_SALVAGE_E4A_CANONICALIZATION_RECEIPT.md` |
| Is there evidence justifying reopening E4b? | **No.** No runtime evidence of real, current pairing failures caused by the remaining same-tier VPN/virtual-adapter ambiguity was found or looked for beyond what the E4 design investigation already established as a known, accepted, tested limitation. **E4b remains correctly deferred.** | — |
| Is companion functionality essential, optional, beta, or release-ready? | **Optional, opt-in, off by default**, and release-ready at the level this audit could verify (real signed APK, real pairing/discovery/bridge code, real persistence) — not essential to the core desktop product's value | README's own framing, matches source |

---

## 6. Data safety / trust

| Mechanism | Finding |
|---|---|
| Settings/JSON writes | Genuinely atomic: `atomic_write_text` writes to a temp file in the same directory, `fsync`s, then `os.replace`s — a crash mid-write cannot corrupt the live file (`os.replace` is atomic on the same filesystem) |
| Corrupt-file handling | `quarantine_corrupt` moves a bad file aside (preserving it for inspection) rather than silently deleting or overwriting it |
| Deletion (soft) | Two-tier: normal delete → Recently Removed (restorable), confirmed via README and `_sidebar_restore_selected`/`_sidebar_restore_all` |
| Deletion (permanent, selected) | Single confirmation dialog with **deliberate default-focus placement away from the confirm control**, specifically to prevent an accidental Enter-key confirmation — this is careful, not perfunctory, safety design |
| Deletion (permanent, all) | **Two-step** confirmation — a materially higher bar for the more destructive action |
| Export | Reference+metadata only by default for path clips; real file copies only on explicit opt-in; originals never moved or deleted (README claim, matches `export.py` source) |
| Import/recovery | Dedicated `clip_recovery.py`/`clip_recovery_import.py` — a freelist decoder for restoring cleared clips, not a stub |
| Crash recovery | Covered by the atomic-write + quarantine mechanisms above; `test_safe_io.py` exercises both directly |

**No reproducible defect found this pass that could cause a normal user action to silently lose clipboard history, destroy favorites, corrupt collections, overwrite data unexpectedly, permanently delete without sufficient confirmation, or produce an unreadable export.** This is a genuinely solid data-safety posture for a local Windows utility, evidenced by design (not merely asserted): the destructive paths are deliberately harder to trigger by accident than the non-destructive ones, and every write path this audit inspected uses a crash-safe pattern.

---

## 7. Claim vs. reality — the audit's most important finding

**`README.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, and `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` are all stale on canonical `master` right now**, despite `CANONICAL_PROJECT_RECORD.md`'s own §20 ("Finish Gate 4") claiming README.md and CHANGELOG.md were corrected. This is not a new problem this pass introduced — it is a real gap between what an earlier gate's own record asserts and what is actually committed, discovered by checking the committed content directly rather than trusting the record's claim:

```
git status --short README.md CHANGELOG.md docs/CACHE_VAULT_FREE_VS_FOUNDER.md
(empty — these files are tracked and clean; what's on disk IS what's committed)

git show HEAD:README.md | grep "v0.1.8"
230:## Honest scope & limitations (v0.1.8)

git log -1 --format="%H %ci %s" -- README.md
7193bebae3db1b1f3dad8b320839b59fc36a9eaa 2026-07-14 ... merge: promote integrated CacheVault application lineage (#61)
```

**Root cause, reconstructed from the record's own §28:** the Gate 4 README/CHANGELOG correction was real and was applied — but only to the working tree, and was never committed. When the Gate 5F canonicalization later hit a pre-existing dirty working tree and had to quarantine it (§28's "Category A: Known Gate 4 documented correction — already verified true, already on record"), that quarantine swept the *uncommitted* Gate 4 edit into the `preservation/pre-gate5f-dirty-2026-08-20` stash along with everything else, and it was never restored to a committed state afterward. `CANONICAL_PROJECT_RECORD.md §20`'s "DONE" classification is therefore now misleading when read against current git history — the fix genuinely happened, but not durably.

| Claim (as currently committed) | Reality | Classification |
|---|---|---|
| README.md: `## Honest scope & limitations (v0.1.8)` | Current version is `0.2.0`, two minor versions and 68+ commits (now +38 salvage-gate tests on top) past this label | **STALE** |
| README.md: "published mobile app (LAN bridge exists but no Android/iOS client app is published yet)" | **False as stated.** A production-signed `CacheVault-Mobile-v0.2.0-android.apk` is a live `v0.2.0` GitHub Release asset — reconfirmed via `gh release view` this pass. No iOS client exists, which *is* true, but the claim as written overstates the gap | **OVERSTATED / STALE** |
| README.md: `### Mobile LAN Bridge (Developer Mode)` / "No mobile app is published yet" | Same as above | **STALE** |
| CHANGELOG.md: `## Unreleased` / `_No unreleased changes yet._` | Committed `master` sits well past `v0.2.0` (68 unreleased commits before this audit's own 4 salvage gates added more) | **STALE** |
| `RELEASE_NOTES.md`: "no public artifacts have been built yet, and no tag has been created" | `v0.2.0` is tagged and has 3 public release artifacts (reconfirmed via `gh release view` this pass) | **STALE — flatly contradicted** |
| `docs/CACHE_VAULT_FREE_VS_FOUNDER.md`: `Mobile bridge | No | No | Not claimed | Do not ship in this SKU` | Contradicted by source: no `is_feature_enabled`/`_require_founder`/`is_founder_unlocked` gate exists anywhere in the mobile code path — the bridge is genuinely ungated today, matching the (also-quarantined, never-committed) 0.2.1-external-test policy correction documented in the original canonicalization pass | **STALE / OVERSTATED** |
| README trust doctrine: "No cloud account. No subscription. No ads, no telemetry." | **PROVEN** — matches source; no telemetry/analytics code found in any prior audit pass of this codebase | **PROVEN** |
| README: "Sensitive clips are masked and auto-expire" | **PROVEN** — `sensitive.py`, matches `--selftest`'s exercised pipeline | **PROVEN** |
| README: Proof Manifest / Stamped Receipts | **PROVEN** — `export.py`'s `document_type: proof_manifest`, `stamped_receipt.txt` | **PROVEN** |
| README: Quick Paste global hotkey behavior | **PROVEN, runtime-verified** — the entire E2 gate and the earlier Gate 5F custody work were built and measured against this exact feature's real-device timing | **PROVEN** |
| README: duplicate collapse | **IMPLEMENTED BUT NOT INDEPENDENTLY RUNTIME-PROVEN THIS PASS** — `duplicates.py` + Cleanup Suggestions exist, self-reported tested, not re-exercised live | **IMPLEMENTED, NOT RUNTIME-PROVEN** |
| README: "Local-first by default... local SQLite database" | **PROVEN** | **PROVEN** |
| Signing custody doc's public verification material | **PROVEN SAFE** — carried forward from Gate 3 of the original canonicalization pass, no new evidence found or sought this pass that would change that finding | **PROVEN (carried forward)** |

**This claim gap is a real release blocker for a "public free release" framing specifically — not for local personal use.** A stranger reading the current public-facing README today would be told the Android companion doesn't exist yet, when it demonstrably does, is signed, and is a public release asset. That is exactly the kind of thing that damages trust in a "Proof-first software" brand once discovered.

---

## 8. Packaging / distribution / stranger test

| Item | State | Classification |
|---|---|---|
| Build path (`pyinstaller packaging/cache_vault.spec`) | **PASS** — clean fresh build this pass on the exact E4a canonical tree | — |
| Packaged self-test | **PASS**, exit 0 | — |
| `verify_exe_metadata.py` | **PASS** — all 12 checks, version 0.2.0 throughout, correct product/company strings | — |
| `dist/SHA256SUMS.txt` | **Stale** — still only hashes an old `CacheVault-v0.1.9-windows.zip`, not the current build | **POLISH** — this is a leftover ad hoc local artifact, not the real release pipeline: `packaging/package_release.ps1` was independently verified (in the original canonicalization pass) to correctly regenerate a fresh `SHA256SUMS.txt` as part of the actual release-artifact production step. Not a release blocker. |
| Code signing (Windows) | **Not signed, by explicit, disclosed policy** (`docs/release/code-signing-plan.md`: "Cache Vault is not code-signed yet") | **NOT A BLOCKER for normal local use, per this audit's own instruction** — SmartScreen will warn, and the public download page's own FAQ already discloses exactly this and tells users to verify the checksum. Consistent, not misleading. |
| Android signing | Production-signed, `apksigner verify` confirmed (carried forward from the original signing-custody gate, not re-verified this pass) | — |
| Release artifacts (GitHub) | **Real** — `v0.2.0` release confirmed live via `gh release view`, 3 assets (APK, Windows zip, SHA256SUMS.txt) | — |
| GitHub Actions CI/Release automation | **Still externally blocked** at the account level (established in the original canonicalization pass's Gate 2; not re-verified this specific pass, carried forward as still-current unless the account holder has since changed anything) | **P0-adjacent but not repo-fixable** — same disposition as before: `BLOCKED — EXTERNAL REQUIREMENT`, an account-custody item, not a code defect |
| Website/download state | Not independently re-checked this pass (out of this audit's file-system scope); no new evidence found contradicting the original canonicalization pass's finding that the public landing page's own signing/mobile claims were accurate | — |
| `scan_secrets.py` | **13 findings, re-run fresh this pass** — all either inside the untracked `CANONICAL_PROJECT_RECORD.md` (not part of any release artifact), pre-existing known items already assessed as P2 hygiene (username paths in the signing-custody doc, Gate 3), or placeholder `.example` emails in QA scripts (false positives) | **No new findings; unchanged from prior assessment** |
| `scan_claims.py` | **8 findings, re-run fresh this pass** — 7 are the scanner matching the literal phrase "local-only" inside `CANONICAL_PROJECT_RECORD.md`'s own prose (untracked, not a product claim); 1 is the already-known `RELEASE_NOTES.md` stale line (§7 above) | **No new findings; unchanged from prior assessment** |
| README/onboarding | See §7 — real content exists, some of it is stale | See §7 |
| Android companion installation/distribution | Signed APK, sideload from GitHub Release (no Play Store listing) — matches every claim found in the code and public docs | — |

---

## 9. Release blockers found this pass

### P1-1 — Mobile bridge "security invariant" force-stop is asynchronous and unsynchronized (new finding, this pass)

**Evidence:** `cache_vault/core/mobile/bridge.py::handle()`, the code's own comment: `# Security invariant: if settings say disabled we MUST NOT be running. If we somehow are, force-stop immediately before processing.` The actual implementation:
```python
if not self.vault.settings.mobile_access_enabled:
    if self.is_running:
        import threading
        threading.Thread(target=self.stop, name="mobile-bridge-force-stop", daemon=True).start()
    ...
    return 503, {"error": "mobile_access_disabled", ...}
```
`handle()` spawns a background thread to call `self.stop()` and **returns immediately without waiting for it** — the 503 rejection response is sent to the client before the force-stop is guaranteed to have completed. `tests/test_mobile_bridge.py::test_bridge_handle_stops_if_disabled` asserts `is_running is False` synchronously, immediately after `handle()` returns, and **failed identically in two independent full-suite runs** (with and without competing background CPU load) at that exact assertion — while passing every time in isolation, where thread-scheduling pressure is far lower. This is a genuine, reproducible-in-realistic-conditions race, not test flakiness; confirmed structurally by reading the code, not merely inferred from the failure.

**Why it matters:** the comment explicitly frames this as a security boundary ("MUST NOT be running... immediately"). The real behavior has a measurable window — wider under system load — where the listener socket can still be accepting/processing connections after a client has already been told the bridge is disabled. Given `ThreadingHTTPServer` dispatches each connection on its own thread, a request that arrives inside that window is not guaranteed to be rejected the way the comment promises.

**Practical severity, stated precisely, not inflated:** the bridge is LAN-only, opt-in, off by default, and every substantive request path still requires a valid pairing token — this is not an authentication bypass. The exposure is narrow: a request landing in a millisecond-scale window during the specific moment mobile access is being disabled, on the same local network, from a device that would need separate valid credentials to do anything with the request anyway for most routes. This is a real correctness defect in code that calls itself a security invariant — worth fixing — not a critical, actively-exploitable vulnerability.

**Smallest likely correction:** make the force-stop synchronous (call `self.stop()` directly rather than dispatching it to a thread) before returning the 503, or block briefly on the spawned thread with a short join. Either closes the race the comment already promises is closed. Isolated to `bridge.py::handle()`; a self-contained, boundable fix.

**Can be handled as an isolated gate:** yes — same shape as E1–E4a (write a deterministic before/after test that doesn't depend on thread-scheduling luck, likely by making `stop()` injectable/awaitable in the test, apply the minimal synchronization fix, prove it, canonicalize).

### No other release blockers found this pass.

Everything else surfaced (§7's stale-doc findings, `dist/SHA256SUMS.txt` staleness, GitHub Actions still blocked) is either already-known, already-classified as non-blocking or externally-blocked in the original canonicalization record, or — for the stale-docs finding — a **documentation trust gap, not a code defect**, addressed separately below.

---

## 10. Important non-blockers

- **`dist/SHA256SUMS.txt` staleness** — cosmetic, local-only artifact; the real release pipeline (`package_release.ps1`) regenerates this correctly, independently verified in an earlier gate.
- **GitHub Actions still account-blocked** — not a repo defect, not fixable from this codebase; carried forward, unchanged.
- **Duplicate handling / Vault Cleanup Suggestions not independently re-exercised live this pass** — exists in source, self-reported tested, not a known defect, just not re-verified beyond "still collects and passes in the suite."
- **116/150 local branches with no remote backup, 52 worktrees** — historical hygiene, already fully triaged in the original canonicalization pass's Gate 5, requires a separately-authorized archive/prune decision; not a release blocker for the product itself.
- **No live GUI walkthrough performed this pass** (§4) — a real limitation of this specific pass, not evidence of a product defect; the app has extensive prior real-runtime proof from earlier in this process.
- **Code signing absent for the Windows build** — explicitly disclosed, publicly documented, not misleading; per this audit's own instruction, not treated as a blocker for normal local use.
- **Zero `TODO`/`FIXME` markers in UI source** — a positive, not a finding, but worth stating: nothing was found that reads as visibly-flagged unfinished work in the shipped UI.

---

## 11. UX / polish findings

Sourced from static inspection (dialog confirmation design, destructive-action safeguards, absence of dev-terminology markers) rather than a live click-through, per §4's stated limitation. Nothing found this pass rises to a defect:

- Destructive-action confirmation design (two-step for bulk delete, deliberate anti-accidental-Enter focus placement for single delete) reads as genuinely considered, not perfunctory.
- No internal/developer terminology found leaking into user-facing dialog text during source review (dialog title/button strings inspected read as plain-language: "Copy Again," "Move to Collection…," "Permanently Remove," etc.)
- The claim-vs-reality gap in §7 is itself a trust/UX issue as much as a documentation one — a new user reading the README before installing would form an inaccurate picture of what the product actually includes.

---

## 12. Scored product assessment (current canonical state, not potential)

| Dimension | Score /10 | Basis |
|---|---|---|
| Core utility | 8 | Real, working, evidence-backed clipboard vault with smart classification, search, Quick Paste, and export — the fundamentals are solid and independently verified this pass |
| Reliability | 8 | ~2,050 tests, 0 unexplained failures after proper investigation (1 real narrow race found and precisely scoped, 1 confirmed one-off environmental fluke); four independent salvage gates (E1–E4a) each found and fixed real, previously-undetected defects with rigorous before/after proof |
| Data safety | 9 | Atomic writes, quarantine-on-corrupt, two-tier soft/hard delete, deliberately-hardened destructive-action confirmations, honest export semantics — no reproducible data-loss path found |
| UX coherence | 7 | Careful destructive-action design and a clean, populated nav structure; docked slightly for the unverified live-walkthrough gap and the trust-damaging stale documentation |
| Feature discoverability | 7 | 7 well-organized nav groups, no dead/TODO surfaces found in source; not independently confirmed via live use this pass |
| Performance | 7 | Documented, measured render-perf work (row-pooling, viewport batching, first-content latency 593ms→220ms on a 1,609-clip vault per the changelog's own — currently unpublished — account); not independently re-measured this pass |
| Mobile integration | 7 | Genuinely real, signed, shipped companion with working pairing/discovery/persistence; docked for the one confirmed async-race defect in the bridge's disable path and Android's lack of multi-address fallback (a known, accepted limitation, not a defect) |
| Proof/receipt differentiation | 8 | A real, working, structurally distinct feature (Proof Manifests, stamped receipts, event log that never stores secrets) — this is a genuine differentiator, not marketing |
| Distribution readiness | 6 | Real signed Android artifact and real GitHub Releases exist; docked hard for the README/CHANGELOG/RELEASE_NOTES staleness that actively misrepresents the mobile companion's status to a stranger |
| **Overall product readiness** | **7** | A real, working, well-tested product let down by one narrow-but-real code defect and a documentation-trust gap that is disproportionately easy to fix relative to its damage |

### Direct answers

1. **Is Cache Vault already a real usable product?** Yes. The core pipeline, Quick Paste, search, organization, and export are all independently proven working, not just claimed.
2. **Is it an MVP?** No — it is well past MVP. It has receipts, mobile pairing, Safes, Macros, Command Center, and a real signed companion app; an MVP framing undersells what's actually built and tested.
3. **Is it good enough for a public free release?** **Not quite, as-is** — not because the product is unready, but because the public-facing README/RELEASE_NOTES actively misstate what it includes (understating a real, shipped capability). Fix the documented claims and this becomes yes.
4. **Is it good enough for a paid Founder version?** The gated features (exports, macros, custom Safes, advanced filters) are real and implemented; nothing found this pass undermines that gate's integrity. Yes, contingent on the same documentation fix.
5. **What would prevent recommending it to a stranger today?** Two things, both narrow: (a) the README would tell them the mobile companion doesn't exist, which is false and would need correcting before they discovered the truth themselves; (b) the mobile-bridge disable race (P1-1) is real, even if its practical exposure is small — a stranger relying on "disabling mobile access is immediate" deserves that to actually be true.
6. **Smallest remaining path to "finished enough to ship"?** Re-commit the already-written, already-verified-true README/CHANGELOG/RELEASE_NOTES/Free-Founder corrections (the content exists, quarantined in the preservation stash — this is a *recovery* task, not a rewrite), and fix the one narrow bridge race (P1-1). Both are small, bounded, already well-understood problems.

---

## 13. Recommended next bounded gate

**Two candidate P1 gates, either or both may be authorized independently — this audit does not pick one for you:**

**Gate A — Recommit the quarantined documentation truth correction.** Re-derive (not blindly reapply from the stash — verify each claim is still true against the *current*, post-E1–E4a canonical tree, since the tree has moved since Gate 4's original edit) and commit fixes to README.md, CHANGELOG.md, RELEASE_NOTES.md, and `docs/CACHE_VAULT_FREE_VS_FOUNDER.md`. This is documentation-only, zero source-code risk, and closes the single most release-relevant finding in this audit.

**Gate B — Fix the mobile-bridge disable-path race (P1-1).** Regression-first, matching the E1–E4a pattern exactly: a deterministic before/after test proving the race, a minimal synchronization fix in `bridge.py::handle()`, full mobile-bridge/pairing/discovery regression, `--selftest`, canonicalize.

Neither requires E4b, neither touches Android, and neither is a large surface. Given the audit's own finding that the documentation gap is the more visible, more trust-damaging issue for a "public free release" framing specifically, **Gate A is the higher-leverage first move if only one is authorized** — but this is a recommendation, not a decision made on the user's behalf.

---

## 14. Explicit list of areas that should NOT be reopened

- **E1 (sidebar/filter-nav crash), E2 (dialog teardown race), E3 (annotation/import correctness), E4a (LAN-IP selection correctness)** — all closed, canonical, proven. No reproducible regression was found against any of them this pass (their own focused suites all re-ran clean as part of the full-suite runs in §3).
- **E4b (Windows adapter/VPN discrimination)** — remains correctly deferred. No new evidence surfaced this pass justifying reopening it.
- **Command Center scope** — confirmed untouched since the original canonicalization pass (§2); frozen at Phase 1 by design, not by neglect.
- **Vault Lock / Safes encryption framing** — unchanged, not reopened, not touched by this audit.
- **Core capture/classify/sensitive pipeline logic** — proven working across every gate in this entire process; no defect found, ever, in this specific area.
- **GitHub Actions / account-level CI block** — not a repo-side problem; nothing here changes that finding.
- **Signing-custody doc's safety classification** — carried forward as `PROVEN SAFE — PUBLIC VERIFICATION MATERIAL ONLY` from the original Gate 3; not re-litigated this pass.
- **Preservation branch/stash and all four rollback tags** — untouched throughout this audit, confirmed clean at both the start and remain so now (this audit performed zero mutating git operations).

---

## Artifact hashes

Computed after this document and its companion JSON summary were finalized:

| File | SHA-256 |
|---|---|
| `CACHE_VAULT_POST_SALVAGE_RELEASE_READINESS_AUDIT.md` | *(computed and recorded in the final chat report — this file's own hash cannot include itself)* |
| `CACHE_VAULT_POST_SALVAGE_RELEASE_READINESS_SUMMARY.json` | *(computed and recorded in the final chat report)* |
