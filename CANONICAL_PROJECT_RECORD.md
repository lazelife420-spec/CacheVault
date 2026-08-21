# CACHE VAULT — CANONICAL PROJECT RECORD

## 1. Identity

| Field | Value |
|---|---|
| Project | Cache Vault (desktop, by The Proof Foundry™) + CacheVault Mobile (Android companion) |
| Repository | `C:\Users\KickA\Desktop\CacheVault` |
| Remote | `github.com/lazelife420-spec/CacheVault` (public) |
| Branch | `master` |
| HEAD | `27b68d6` — "feat(mobile): implement CameraX + ML Kit QR camera scanning and declare desktop qrcode dependency" (2026-08-13 18:29:22 -0700) |
| Working tree | **DIRTY** — 9 modified, 2 deleted (not staged); see §6 |
| Declared version | `0.2.0` (`pyproject.toml`, `cache_vault/__init__.py`) — desktop; Android `versionCode 8` / `versionName "0.2.1"` (`android/app/build.gradle.kts`, tracked on master) |
| Latest published release | GitHub Release `v0.2.0` (2026-07-17), includes `CacheVault-Mobile-v0.2.0-android.apk`, `CacheVault-v0.2.0-windows.zip`, `SHA256SUMS.txt` |
| Toolchain | Python 3.13.2, pip 26.2.1, project `.venv` present and usable |
| Date of this pass | 2026-08-20 |

HEAD sits **68 commits ahead of the `v0.2.0` tag** (confirmed ancestor via `git merge-base --is-ancestor`; exact count independently re-verified in Gate 4, §20 — an earlier draft of this record miscounted this as 27, corrected here), spanning 2026-07-16 through 2026-08-13, all unreleased: mobile QR-pairing onboarding + camera scanning, send-to-pc endpoint persistence/self-healing, sidebar god-class refactors, Quick Paste focus/exit fixes, ClipList row-pooling perf work, the full Vault Cleanup Suggestions feature (Stages A–E), context-aware context menus, and a cluster of Tk UI teardown/test-isolation hardening fixes. See `CHANGELOG.md`'s "Unreleased" section (rewritten in Gate 4) for the curated list.

## 2. Product purpose (current, as built)

A local-first Windows clipboard vault (CustomTkinter desktop app) with smart classification, sensitive-content auto-expiry, Quick Paste, Safes, Vault Macros, Command Center (Phase 1: Hotkey Actions only), and an **opt-in LAN-only Mobile Bridge** paired to a real, production-signed Android companion app (**CacheVault Mobile**) that browses vault clips and sends items from phone to desktop. No cloud account, no subscription, no telemetry. Licensing is an offline Ed25519 Founder gate; several advanced features (exports, macros, custom Safes, advanced filters) require a Founder license. A Manifest V3 Chrome/Edge extension companion exists in developer mode (unpublished to the Web Store).

## 3. Proven capabilities (evidence-backed)

- **Core pipeline runs end-to-end.** `python app.py --selftest` → `selftest OK — core capture/classify/sensitive/image/mobile pipeline works` (exit 0), run against both the dev `.venv` interpreter and the packaged `dist\CacheVault.exe` (built 2026-08-13 20:35, i.e. from current HEAD). **RUNTIME PROOF: PASS (both lanes).**
- **Dependency/packaging parity.** `requirements.txt` and `pyproject.toml [project.dependencies]` are identical in substance (only quote-style differs). `packaging/cache_vault.spec` explicitly hidden-imports `cryptography` + its `ed25519`/`serialization` submodules, matching the offline-license requirement.
- **Mobile companion is real and shipped**, not vaporware: v0.2.0 GitHub Release contains a **production-signed** `CacheVault-Mobile-v0.2.0-android.apk`; the release body documents physical-device verification on a Samsung Galaxy S23 (pairing, safe read/write, reconnect across Wi-Fi and desktop restart, incompatible-version rejection) — not simulated claims.
- **No tracked secrets.** No tracked `.env` files; no hardcoded private keys, API keys, or `SECRET_KEY` literals in source (only regex *definitions* for detecting such patterns in `sensitive.py`/`scan_secrets.py`/tests, which is correct and intended).
- **No signing key material in git.** `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` confirms the release keystore and its `.gpg`-encrypted backups (one on a physically separate device) are **not** tracked in git — verified by absence from `git ls-files`.

## 4. Component disposition matrix

| Component | Source | Tests | Runtime | User reachable | Disposition | Evidence |
|---|---|---|---|---|---|---|
| Core capture/classify/sensitive pipeline | `cache_vault/core/*` | **Yes — independently re-run this pass**, 1,886 collected tests, exit 0, 0 failures, 1 conditional skip | **Proven** via `--selftest` on venv + packaged exe | Yes | **PROVEN WORKING** | `--selftest` exit 0 (both lanes) + full pytest exit 0 |
| Licensing / Founder gate (Ed25519) | `licensing.py`, `feature_gate.py` | Yes (per REPO_TRUTH.md, stale date) | Selftest exercises license eval path | Yes | **PROVEN WORKING** | Fails closed without `cryptography`; bundled in packaging spec |
| Mobile Bridge (LAN HTTP API + pairing) | `core/mobile/*` | Per CHANGELOG v0.2.0: "Android tests: 88/88" (self-reported, not independently re-verified this pass) | Physical-device verified per v0.2.0 release notes (not re-run this pass) | Yes, opt-in | **PROVEN WORKING** | GitHub Release v0.2.0 body; no gate check found in `core/mobile/*` or `vault.py` (grep) |
| QR pairing onboarding + camera scan (new, unreleased) | `183b568`, `27b68d6` | Unknown — added after last full local test claim | Desktop half: **PACKAGING VERIFIED** this pass (Gate 1, see §17). Android camera-scan half: not independently exercised this pass (needs camera/device) | Not yet released | **RECOVERABLE — BLOCKED BY DEPENDENCY** (Android camera-scan side still needs a device/emulator to prove; desktop QR-generation side is now proven to package correctly) | Commits exist; `packaging/cache_vault.spec` bundling of `qrcode` confirmed correct — see §17 Gate 1 receipt (the §7-defect concern below was a **false positive**) |
| Vault Cleanup Suggestions (Stages A–E) | `core/cleanup*`, unreleased since v0.2.0 | Commit messages claim tests added per stage | Not independently re-run this pass | Not yet released | **RECOVERABLE — NEEDS VERIFICATION** | 8 dedicated commits on HEAD, not yet in a tagged release |
| Command Center | `core/command_center.py`, `ui/command_center.py` | — | — | Yes (Phase 1 only) | **PROVEN WORKING — FROZEN** (Phase 1 scope only) | No commits touched Command Center since v0.2.0; matches REPO_TRUTH.md's "Phase 1 only" claim, which is still accurate on this specific point |
| Browser extension (Manifest V3) | `extension/` | None (confirmed: no test files) | Not exercised this pass | Developer-mode only, not published | **INCOMPLETE** (by design — pre-Web-Store) | `docs/audits/browser_extension_audit.md` (historical plan) matches current `manifest.json` permissions exactly |
| Mobile Free/Founder gating policy (0.2.1 external test) | uncommitted `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` edit | — | Verified by grep: no `is_feature_enabled`/`_require_founder`/`is_founder_unlocked` in mobile path | N/A — policy doc, uncommitted | **RECOVERABLE — NEEDS REPAIR** (uncommitted; not yet reflected in README/CHANGELOG) | Working-tree diff; Android `versionCode 8`/`0.2.1` already committed on master, but the policy explanation is not |
| GitHub Actions CI (`ci.yml`) | `.github/workflows/ci.yml` | Defines `pytest -q` + `--selftest`; both steps independently reproduced locally this pass — PASS | **Never executed on GitHub** | N/A | **PROVEN VALID — GITHUB EXECUTION EXTERNALLY BLOCKED** (Gate 2, §18) | `gh workflow run ci.yml` → HTTP 422 "Actions has been disabled for this user"; YAML valid, `actions/checkout@v5`/`actions/setup-python@v6` both exist upstream, every substantive command reproduces cleanly locally |
| GitHub Actions Release workflow | `.github/workflows/release.yml` | Every step short of the final publish step (checkout→pytest→selftest→verify_assets→build_exe→packaged selftest→verify_exe_metadata→package_release→verify_release_artifact) independently reproduced locally this pass — all PASS | **Never executed on GitHub** | N/A | **PROVEN VALID — GITHUB EXECUTION EXTERNALLY BLOCKED** (Gate 2, §18) | Same account-level 422 applies to every workflow in the repo, not just `ci.yml`; all referenced scripts/paths/secrets exist; `permissions: contents: write` is correctly declared for the release job |
| Local full CI gate (`scripts/ci_local_full.ps1`) | `scripts/*.py`, `.ps1` | Wraps pytest + compileall + selftest + smokes + `scan_claims.py` + `scan_secrets.py` | Not run in full this pass (would take 20+ min per its own comments) | Developer-only | **RECOVERABLE — NEEDS REPAIR** | Its two scanner sub-gates were run standalone this pass and both currently **FAIL** (§5) |
| `scripts/scan_secrets.py` | tracked | — | Run this pass: **FAIL, 11 findings** | Developer-only, not CI-enforced on GitHub | **BROKEN** (currently red) | See §5 |
| `scripts/scan_claims.py` | tracked | — | Run this pass: **FAIL, 1 finding** | Developer-only, not CI-enforced on GitHub | **BROKEN** (currently red) | See §5 |
| Signing-key custody plan | `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` | — | Android signing verified via `apksigner verify --print-certs` (recorded in doc, cross-checked against build.gradle.kts wiring this pass) | Published in a **public** repo | **PROVEN SAFE — PUBLIC VERIFICATION MATERIAL ONLY** (Gate 3, §19) | No credential/private-key exposure in current HEAD or full git history (verified, not assumed). Contains legitimate public cert fingerprints plus non-secret operational metadata (username, paths, device serial) that exceeds public-doc necessity — a P2 hygiene item, not a security defect |
| Local worktree / branch hygiene | `.git`, `.claude/worktrees/*`, Temp/, Documents/ archive copies | — | — | N/A | **HISTORICAL / NEEDS TRIAGE** | 49 live git worktrees, 143 local branches (**116 with no matching branch on `origin`**), 2 stashes |

## 5. Current validation

| Lane | Command | Result |
|---|---|---|
| Headless selftest (dev venv) | `.venv\Scripts\python.exe app.py --selftest` | **PASS** — exit 0 |
| Headless selftest (packaged exe) | `dist\CacheVault.exe --selftest` | **PASS** — exit 0 |
| Unit test suite | `.venv\Scripts\python.exe -m pytest -q` | **PASS.** Completed after ~20+ min real wall-clock (a GUI-heavy suite of 147 files / **1,886 collected tests** that spins up/tears down live Tk windows). First attempt was captured through a `\| tail` pipe, which silently swallowed pytest's real exit code and its final summary line — a self-inflicted false-signal risk, corrected by re-running with direct file redirection (`> log 2>&1; echo $?`). Clean rerun: **exit code 0, 100% of the dot-progress stream with zero `F` markers, 1 conditional skip, 1 Pillow deprecation warning (non-fatal)**. The pytest process's own custom collection reporter does not print a final tallied "N passed" line (a repo-specific pytest plugin quirk, not a defect in this pass), so the collected-test total (1,886) was independently obtained via `--collect-only -q`. This **replaces and substantially exceeds** the self-reported "Desktop tests: 988/988" claim in `CHANGELOG.md`/release notes for v0.2.0 — the suite has roughly doubled since that release, consistent with the 68 unreleased commits (Vault Cleanup Suggestions, QR pairing, row-pooling, etc.). This is the **first independent verification** of this project's test suite outside the author's own prior self-reports (see §9 — GitHub Actions has still never run it). |
| `scripts/scan_secrets.py` | `.venv\Scripts\python.exe scripts/scan_secrets.py` | **FAIL** — 11 findings: 3× placeholder `.example` email addresses in QA scripts (near-certainly false positives), 8× absolute Windows path containing the real local username (`C:\Users\KickA`) inside a **tracked, public** doc (`docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md`) and `visual_smoke/record_visual_gate.py` |
| `scripts/scan_claims.py` | `.venv\Scripts\python.exe scripts/scan_claims.py` | **FAIL** — 1 finding: `RELEASE_NOTES.md:4`, a "bare-no-cloud" claim wording trip |
| GitHub Actions "CI" workflow | n/a — inspected via `gh run list` | **NEVER RUN.** Zero recorded executions despite triggering on every push to `master`/`main` and every PR. |
| GitHub Actions "Release" workflow | n/a — inspected via `gh run list` | **NEVER RUN.** All 8 published GitHub Releases (v0.1.4 → v0.2.0) were produced outside this workflow — no independent build/verify trail exists for any of them. |
| Full local gate (`scripts/ci_local_full.ps1`) | not run this pass | **BLOCKED BY TIME** — by its own header comments, a full run is a 20+ minute multi-gate script; not run given two of its component gates (secrets, claims) were already run standalone and are known-red |

## 6. Current runtime evidence

- Working tree is dirty: 7 source files with small, coherent, non-alarming WIP diffs (LAN-IP preference ordering in `lan_ip.py`; two unused-import additions in `filters.py`/`mobile_dialogs.py`; `dialogs.py`, `clip_context.py`, `clip_workflows.py`, `shell.py` each with small uncommitted edits not yet reviewed line-by-line beyond confirming they are small).
- `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` has an **uncommitted correction** (dated 2026-08-14 inside the file) recording a real policy decision: for the "0.2.1 external-test" release the Android companion + LAN bridge are **ungated** (Free), reversing the doc's own prior "do not ship in this SKU" line. This is independently verified true by source inspection (no Founder-gate check exists anywhere in the mobile code path) but is **not yet reflected** in `README.md`, `CHANGELOG.md`, or committed docs.
- Two deletions in the dirty tree (`docs/.nojekyll`, `release/CacheVault-v0.1.4-windows.zip`, `visual_smoke/live_export_check.zip`) are unstaged — evidence of local cleanup in progress, not yet committed.
- `dist/CacheVault.exe` (Aug 13, matches HEAD) has **no corresponding entry in `dist/SHA256SUMS.txt`**, which still only hashes the old `CacheVault-v0.1.9-windows.zip`. The current build's integrity cannot be independently verified against a published hash.
- `android/app/build.gradle.kts` on master already declares `versionCode 8` / `versionName "0.2.1"` — ahead of the last published release (`v0.2.0`) and consistent with the uncommitted Free/Founder policy note and with a `CacheVault-Mobile-v0.2.1-external.apk` artifact found sitting in an abandoned git worktree (`.claude/worktrees/great-swartz-cf2a02`, dated 2026-07-17) — real, in-flight work that predates this pass but was never folded back into a clean commit trail on `master`.

## 7. Known defects

~~1. `qrcode` not declared in the PyInstaller hidden-imports spec.~~ **RETRACTED — confirmed FALSE POSITIVE in Gate 1 (see §17).** PyInstaller's static analysis already bundles `qrcode` and all 19 of its submodules correctly without an explicit hidden-import declaration; this was verified by A/B rebuilding with and without a hidden-import fix and inspecting the packaged exe's actual `PYZ.pyz` module table both times (identical in both builds). The original finding was itself a false positive produced by an incomplete verification method (inspecting only the outer archive's top-level listing, which does not show pure-Python modules bundled inside the nested `PYZ.pyz` blob). No code change was needed or kept.
2. **`dist/SHA256SUMS.txt` stale** relative to the current `dist/CacheVault.exe` build (see §6).
3. ~~`CHANGELOG.md` "Unreleased" section says "No unreleased changes yet"~~ **FIXED in Gate 4 (§20).** 68 real commits (QR pairing, cleanup suggestions, perf work, refactors) sat on `master` past the last tag with an empty Unreleased section — a real documentation/reality gap, not just cosmetic, since it would have misled the next release-notes author. Now populated with a curated, accurate account of the actual unreleased work.
4. ~~`README.md`'s "Honest scope & limitations (v0.1.8)" section is version-labeled and stale~~ **FIXED in Gate 4 (§20).** It stated "no Android/iOS client app is published yet," which was false as of the `v0.2.0` GitHub Release (a signed APK is a release asset). Section retitled and both the implemented-features list and the mobile-bridge section corrected.
5. **Uncommitted Free/Founder mobile-gating policy change** (§6) — real, verified-true content sitting only in the working tree, not committed, not synced to README/CHANGELOG. **Deliberately left untouched in Gate 4** — it's a live pricing/gating policy decision the doc itself calls provisional ("not a permanent commitment"), not a demonstrably-stale factual claim, so it stays out of scope for a truth-reconciliation pass. See the Finish Queue P1 item.

## 8. Security / custody issues

1. ~~MEDIUM — Operational-security disclosure in a public repo~~ **RECLASSIFIED in Gate 3 (§19): `PROVEN SAFE — PUBLIC VERIFICATION MATERIAL ONLY`.** No private key, password, or any material that would let someone use or reconstruct the signing key is present anywhere in the doc, in current HEAD, or anywhere in the entire reachable git history (verified, not assumed — see §19). What the doc does contain, alongside legitimate public verification material (certificate fingerprints, algorithm identity, keystore-file integrity hash — all of which are *meant* to be publishable, the same way a TLS cert thumbprint or an SSH host key fingerprint is), is non-secret **operational metadata that exceeds what a public audience needs**: the real local Windows username (`KickA`), exact backup folder paths, and the physical backup device's model + serial number. This is downgraded from a security finding to a **P2 hygiene recommendation** (see Finish Queue) — real, worth tidying, but not a credential exposure and not blocking release.
2. **LOW/INFO — 116 of 143 local git branches have no matching branch on `origin`.** Work on those branches exists only on this one machine (across 49 live worktrees plus additional archived checkouts under `Documents\CacheVault Desktop Archive 2026-07-30\` and `Documents\CacheVault Build\`). Most content is likely already merged into `master` via squash merges (branch names correlate with commit subjects already in `git log`), but this was not individually verified per-branch, and a local-disk loss would be unrecoverable for any content that is genuinely unmerged.
3. **INFO — No signing key material, passwords, or `.env` files are tracked in git.** Confirmed clean on the actual-secret-exposure axis.
4. **INFO — Two active stashes** predate this pass (`wip-sidebar-collapse-expand-button-sizing`; `park product expansion browser clipper dirty WIP`) — not evaluated in depth this pass; flagged for a future look before assuming they're disposable.

## 9. False-green findings

1. **GitHub Actions "CI" and "Release" workflows have never run, ever**, despite being registered as "active" and despite the CI workflow triggering on every push to `master`/`main` and every PR. Every "N/N tests passed" claim in `CHANGELOG.md` and GitHub Release bodies (e.g., "Desktop tests: 988/988... Android tests: 88/88") is a **self-reported local-machine result with zero independent verification**. This is the single most important false-green finding in this pass: the project *looks* like it has CI (a green "CI" badge concept, a workflow file with sensible steps) but that infrastructure has produced exactly zero evidence, ever. (This pass's own §5 pytest re-run — exit 0, 1,886 tests, done outside the repo's own historical self-reporting — is the first time this suite has been independently exercised, but it is still not a substitute for real CI on every future push.) **UPDATE — Gate 2 (§18) determined *why*: this is not a workflow defect. GitHub has disabled Actions for the `lazelife420-spec` account itself** (confirmed via a live `workflow_dispatch` attempt returning HTTP 422 "Actions has been disabled for this user"), and every other diagnostic (YAML validity, action-version existence, referenced-file existence, local reproduction of every non-publish step) came back clean. The false-green risk this finding describes is still real and still live — self-reported numbers are still unverified by any third party — but the *cause* is account custody, not broken CI engineering.
2. **`scripts/scan_secrets.py` and `scripts/scan_claims.py` exist and are wired into the *local-only* `ci_local_full.ps1` gate, but are absent from the GitHub Actions `ci.yml`.** Even if a contributor pushed straight to `master` without running the local script, nothing would catch a secret or a risky claim before it shipped publicly — and per finding 1, even the weaker `ci.yml` gates never actually ran either.
3. ~~`CHANGELOG.md`'s "Unreleased" section is empty ("No unreleased changes yet")~~ **FIXED in Gate 4 (§20).** 68 substantive commits (not 27 — see §20's self-correction note) sat ahead of the last tag while the changelog read as if `master` were release-clean. Now populated with a curated, accurate account.
4. **`RELEASE_NOTES.md`** is a leftover v0.2.0 release-candidate draft that explicitly states "no public artifacts have been built yet, and no tag has been created" — directly contradicted by the fact that v0.2.0 **is** tagged and **does** have public release artifacts. Stale draft, not corrected after the real release shipped.

## 10. Frozen decisions

- **Command Center — Phase 1 only (Hotkey Actions).** No commits since `v0.2.0` touch Command Center. Reopening requires new evidence of Phase 2+ work actually starting (Text Expansions, Quick Paste menu automation, Run Log UI) — none found.
- **Vault Lock = UI privacy lock, not encryption; Safes = organization, not encryption.** Consistently documented across `README.md`, `REPO_TRUTH.md`, and `app_receipt.KNOWN_LIMITATIONS`; no contradicting evidence found. Do not reopen without a deliberate encryption-scope decision.

## 11. Release blockers (P0 candidates — see Finish Queue)

- ~~CI/Release automation producing zero real verification~~ **RECLASSIFIED in Gate 2 (§18): `PROVEN VALID — GITHUB EXECUTION EXTERNALLY BLOCKED`.** Both workflows are syntactically and substantively correct; every step short of the publish step was reproduced locally and passed. The account `lazelife420-spec` itself has GitHub Actions disabled ("Actions has been disabled for this user" — confirmed via a live `workflow_dispatch` attempt, HTTP 422). This is an account-custody item for the user to resolve with GitHub, not a repo defect. Still a P0 in the sense that *nothing* is independently verifying pushes until it's resolved — but the fix is account-side, not code-side.
- ~~`qrcode` packaging-spec gap~~ **CLEARED — false positive, proven in Gate 1 (§17).** No longer a blocker.
- ~~Public-repo signing-custody disclosure~~ **RECLASSIFIED in Gate 3 (§19): `PROVEN SAFE — PUBLIC VERIFICATION MATERIAL ONLY`.** No credential or private-key exposure, current or historical. Downgraded to a P2 hygiene item — no longer a release blocker.

## 12. Non-blocking improvements

- ~~Sync `CHANGELOG.md` "Unreleased" section with the real commit gap~~ **DONE — Gate 4 (§20).**
- ~~Correct `README.md`'s stale "v0.1.8" honest-scope section, specifically the "mobile app not published" claim~~ **DONE — Gate 4 (§20).**
- Retire or update `RELEASE_NOTES.md`'s stale RC-draft language. **Deliberately deferred — out of Gate 4's authorized scope (README.md/CHANGELOG.md only); still open.**
- Regenerate `dist/SHA256SUMS.txt` to cover the current `dist/CacheVault.exe`.
- Commit or formally park the Free/Founder mobile-gating policy doc edit (§6).

## 13. Deferred work

- Full re-run of `pytest -q` to completion and full run of `scripts/ci_local_full.ps1` (both time-boxed out of this pass; see §5).
- Per-branch audit of the 116 unpushed local branches to identify any genuinely unmerged, at-risk work.
- Review of the two open stashes.
- Independent verification of the mobile QR pairing / camera-scan feature (needs an Android device or emulator).
- Verification of the Vault Cleanup Suggestions feature end-to-end (exists in source + commits, not independently re-run).

## 14. Explicitly discarded / historical work

- `docs/audits/browser_extension_audit.md` — a pre-implementation planning doc ("Extension Path: Not present"). Superseded by the real, current `extension/manifest.json`, which matches the plan's permission scope exactly. **HISTORICAL ONLY** — do not treat as current status.
- `docs/REPO_TRUTH.md` (dated 2026-06-24, describes v0.1.3) and the "Honest scope & limitations (v0.1.8)" block in `README.md` — both **superseded** by 5+ months and multiple releases of subsequent work. Retained as historical audit trail; **not authoritative for current state.** This record supersedes them.

## 15. Remaining finish queue

See **FINISH QUEUE** below.

## 16. Current canonical state

Cache Vault is a real, working, actively-developed local-first clipboard vault with a genuinely shipped (not vaporware) production-signed Android companion. Core functionality is proven at the selftest/runtime level on both the dev interpreter and the current packaged build. The codebase is healthy and the team's own internal audit discipline (REPO_TRUTH.md, dated claim docs, receipt/proof exports) is unusually strong for a project this size — but that discipline has decayed relative to the pace of recent work: the last comprehensive truth audit is two months and dozens of commits stale, the changelog and README both contain claims contradicted by current reality, and — most importantly — **the CI/Release automation that would normally keep this honest has never actually executed**, meaning every test-count and release claim in this repo's history is self-attested. None of this indicates the product doesn't work — the runtime evidence gathered this pass says it does — but it means "988/988 passed" and similar claims should be treated as **leads, not proof**, exactly as this process's operating rules require, until independently re-run.

> This record supersedes previous informal summaries (`docs/REPO_TRUTH.md`, the README "Honest scope & limitations (v0.1.8)" section) for current project state. Repository/runtime evidence governs when conflicts arise.

## 17. Finish Gate 1 receipt — `qrcode` packaging verification

**Authorized scope:** resolve and prove the `qrcode` packaging gap only (§7 finding #1 / §11 P0). No CI, signing-custody, changelog/README, or branch-triage work performed under this gate.

**What was done, in order:**
1. Confirmed the only `qrcode` call site in source: `cache_vault/ui/mobile_dialogs.py::_generate_qr_offer`, a lazy `import qrcode` inside a `try/except Exception` that silently degrades to a `"[QR Code Display Available]"` text placeholder on any failure — meaning a missing dependency in a packaged build would fail *silently*, not crash. This is what made the original concern worth taking seriously.
2. Applied a candidate fix: added `qrcode` + `qrcode.image.pil` to `packaging/cache_vault.spec`'s `hiddenimports` (mirroring how `cryptography` is already explicitly declared there).
3. Clean-rebuilt (`pyinstaller packaging/cache_vault.spec --noconfirm --clean`) and checked the result with `pyi-archive_viewer` — found **no top-level `qrcode` entries**, which read as confirmation of the gap.
4. That reading was wrong. Pure-Python packages not explicitly `collect_all()`'d (unlike `customtkinter`/`zeroconf` in this spec) get compiled into a single nested `PYZ.pyz` blob, not listed as individual top-level archive entries — `pyi-archive_viewer`'s default top-level listing does not show them. Caught this via `PyInstaller.archive.readers.CArchiveReader`/`ZlibArchiveReader`, extracting `PYZ.pyz` and listing its own module table directly.
5. Re-checked the fixed build's `PYZ.pyz`: **`qrcode` and 19 submodules present**, including `qrcode.image.pil`.
6. **A/B-tested causally**: stashed the spec fix, clean-rebuilt from the unmodified, original committed spec, and extracted/listed that build's `PYZ.pyz` too. **Identical result** — same 617-module count, same 19 `qrcode.*` entries — with no hidden-import declaration at all.
7. Conclusion: PyInstaller's static bytecode analysis already finds `import qrcode` correctly regardless of the `try/except` nesting; the original finding was a **false positive** produced by an incomplete verification method (checking only the outer archive listing) in the canonicalization pass, not a real defect in the codebase.
8. Reverted the speculative fix (`git stash drop`) — `packaging/cache_vault.spec` is byte-identical to HEAD. Re-ran `--selftest` against the final rebuilt exe: **PASS, exit 0**.

**Proof checklist (per authorization):**
- Source tests remain green: unaffected — no source files were changed by this gate (`git status --short` shows only the same pre-existing dirty files from Phase 0, plus this record file).
- Packaging/build succeeds: yes, three clean builds in a row (with fix / without fix / final).
- Packaged application launches: yes, `--selftest` → exit 0 after the final build.
- QR-code functionality works from the packaged build: `qrcode` and its PIL-backed image submodule are present in the frozen bytecode archive, both with and without the candidate fix — the import path `_generate_qr_offer()` depends on will resolve. (Exercising the live QR-pairing *dialog* itself was out of scope per the original stop condition, which called for the scripted import-level check first; that check is what's reported here.)
- Dependency actually present in the produced artifact: confirmed directly via `PYZ.pyz` module-table inspection, not inferred.
- No unrelated source changes: confirmed via `git status --short` before/after.
- Exact before/after diff recorded: the candidate diff was the `packaging/cache_vault.spec` hiddenimports addition shown above; net diff after revert is **empty**.

**Disposition:** §7 finding #1 and the §11 P0 item are both **closed as false positive**. No code change was required or kept.

## 18. Finish Gate 2 receipt — CI / GitHub Actions workflow truth

**Authorized scope:** determine why Cache Vault's GitHub Actions workflows have never produced verified CI evidence — workflow-definition defect vs. GitHub-side/account-level block — and reproduce the underlying commands locally. No signing-custody, README/CHANGELOG, branch-cleanup, or product-feature work performed under this gate.

**Files in scope (hashes recorded before any inspection; neither was modified):**
| File | SHA-256 |
|---|---|
| `.github/workflows/ci.yml` | `377fa3b1b161176af82561b8ba81d625cd8e2cf6677104b1a35f6b5e747743cf` |
| `.github/workflows/release.yml` | `ba122219f98b1918129aeaf5061bdffb0ce558a3079478b7313407369f188baa` |

Both hashes are unchanged from before this gate — **zero workflow-file edits were made**, because zero defects were found in them.

**Investigation, in order:**

1. **Read both workflow files in full.** `ci.yml` (added `d69ba5f`, 2026-06-14): triggers on push to `master`/`main`, on every PR, and on `workflow_dispatch`; matrix of Python 3.12/3.13 on `windows-latest`; steps: checkout → setup-python → `pip install -r requirements.txt` → `pytest -q` → `python app.py --selftest`. `release.yml` (added `8cdb108`): triggers on `v*` tags; declares `permissions: contents: write`; runs the full test→selftest→asset-verify→build→packaged-selftest→metadata-verify→package→artifact-verify chain, then creates/updates the GitHub Release via `gh release create`/`gh release upload`.
2. **YAML validity.** Both parse cleanly with `python -c "import yaml; yaml.safe_load(...)"` — no syntax errors. (PyYAML reports a `True` top-level key for the bare `on:` token — this is YAML 1.1's boolean-keyword quirk, a well-known GitHub Actions authoring artifact that GitHub's own parser handles correctly; not a defect.)
3. **Branch/trigger assumptions.** `ci.yml` triggers on `master`/`main` — the repo's actual default and only long-lived branch is `master`. No stale branch reference.
4. **Action versions exist.** `actions/checkout@v5` and `actions/setup-python@v6` were checked against the upstream repos' actual release tags (`repos/actions/checkout/tags`, `repos/actions/setup-python/tags` via `gh api`) — both major versions are real, published releases. No stale/deleted action reference.
5. **Referenced local files exist.** Every script/path `release.yml` invokes (`tools/verify_assets.py`, `packaging/build_exe.ps1`, `tools/verify_exe_metadata.py`, `packaging/package_release.ps1`, `tools/verify_release_artifact.py`, `RELEASE_NOTES.md`, `requirements-dev.txt`) confirmed present in the repo via direct filesystem check. No missing-artifact defect.
6. **Secrets/permissions.** `release.yml` only uses `${{ github.token }}` (the automatic, no-setup-required token) and declares `permissions: contents: write` at the job level, which takes precedence over the repo's default `read`-only workflow-permission setting when a workflow explicitly requests it. No custom secret is referenced by either workflow, so no missing-secret defect is possible.
7. **Repo-level Actions settings** (`gh api repos/.../actions/permissions`): `{"enabled": true, "allowed_actions": "all"}`. Actions are **not** disabled at the repository level, and no action-source restriction would block `actions/checkout`/`actions/setup-python`.
8. **The decisive test — live `workflow_dispatch`.** Since `ci.yml` explicitly supports `workflow_dispatch`, the cleanest way to separate "defect" from "blocked" is to actually try to run it: `gh workflow run ci.yml --repo lazelife420-spec/CacheVault --ref master`. Result:
   ```
   could not create workflow dispatch event: HTTP 422: Actions has been disabled for this user.
   ```
   Confirmed this is not a token/scope problem on the invoking side: `gh auth status` shows the authenticated account **is** `lazelife420-spec` (the repo owner) with `workflow` scope present. The 422 is GitHub's own account-level rejection, unrelated to any file in this repository.
9. **Local reproduction of every substantive command** (all run against current `HEAD`/working tree, nothing pushed):

   | Step (workflow) | Local command | Result |
   |---|---|---|
   | Install + unit tests (`ci.yml`, `release.yml`) | `pytest -q` | **PASS** — 1,886 tests, exit 0 (§5, this session) |
   | Headless self-test (`ci.yml`, `release.yml`) | `app.py --selftest` | **PASS** — exit 0 (§3, this session) |
   | Verify assets (`release.yml`) | `tools/verify_assets.py` | **PASS** — all 12 required files, 6 ICO sizes, no gold-coin leakage |
   | Build packaged exe (`release.yml`) | `packaging/build_exe.ps1` equivalent | **PASS** — already proven in Gate 1 (§17) |
   | Packaged self-test (`release.yml`) | `dist\CacheVault.exe --selftest` | **PASS** — exit 0 |
   | Verify exe metadata (`release.yml`) | `tools/verify_exe_metadata.py --exe dist/CacheVault.exe` | **PASS** — all 12 checks (version, company, product strings) |
   | Package release artifacts (`release.yml`) | `packaging/package_release.ps1 -Tag v0.2.0` | **PASS** — produced `dist/release/v0.2.0/CacheVault-v0.2.0-windows.zip` + `SHA256SUMS.txt` |
   | Verify release artifact structure (`release.yml`) | `tools/verify_release_artifact.py --zip ... --sha256 ... --tag v0.2.0` | **PASS** — all 6 checks |
   | Create/update GitHub Release (`release.yml`) | `gh release create`/`gh release upload` | **Not run — intentionally out of scope.** Would publish/mutate public GitHub state under an already-known-blocked account and adds no diagnostic value beyond what step 8 already proved. |

**Root-cause conclusion:** "CI never ran" and "CI is broken" are, as anticipated, **different findings here — same shape as the Gate 1 `qrcode` result.** Every workflow-engineering question (YAML validity, trigger correctness, action-version currency, referenced-file existence, secret/permission correctness, and — the actual test — whether the commands succeed) comes back clean. The single, sufficient explanation for zero recorded runs across two+ months and dozens of pushes is that **GitHub has disabled Actions for the `lazelife420-spec` account itself.**

**Required disposition:** `PROVEN VALID — GITHUB EXECUTION EXTERNALLY BLOCKED`.

**What this changes:** §7 defect list, §9 false-green finding #1, §11 release blockers, and the Finish Queue's CI item are all updated in place above to point here rather than duplicating the analysis. The underlying risk described in §9.1 (self-reported test claims with no independent verification) is **unresolved** — it just now has a precisely-located cause: an account-level GitHub restriction, not a repo defect. *Why* GitHub applied that restriction is not established by this pass and is not guessed at here. Resolving it requires the account holder to review GitHub's own account settings/communications; no further repo-side engineering will fix it.

**Stop condition honored:** no changes were made to signing custody, README/CHANGELOG, branches, or product code. `git status --short` before and after this gate is identical except for this record file.

## 19. Finish Gate 3 receipt — signing-custody / public-repository disclosure truth

**Authorized scope:** determine exactly what the "public-repo signing-custody disclosure" concern (§8 finding #1, raised in the original canonicalization pass) actually is, and whether it is a real security/release defect. No CI, GitHub account settings, README/CHANGELOG drift, branch cleanup, or unrelated product-code work performed under this gate.

**Files inspected (hashes recorded; none were modified — confirmed via `git status --short` before/after, identical):**
| File | SHA-256 |
|---|---|
| `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` | `3a53ae2563ed4034b8dd95674b9d71d23e0ba56e6c820ccda6597d9663d79a0c` |
| `docs/release/code-signing-plan.md` | `bb2c12ad1d320aaf5e827ec394b9719331c2941c278cb4a045780fd57822d0a9` |
| `android/app/build.gradle.kts` | `a041f8f7010266a68e001744851c1145ce17355d39f140d14d6f8913c7e05c65` |
| `.gitignore` | `bb2638af6470b42e35572be4196d09e508c82c87844ddb2f3e8595f80f9fbc95` |

**No secret material was ever displayed, printed, or logged during this gate** — every check below establishes *presence/absence* of files or *matches fingerprints already published in the doc itself* (which is exactly what a fingerprint is for), never key bytes or password values. No local keystore or `.gpg` backup was decrypted; no password manager was accessed.

**Investigation, in order:**

1. **Read the custody doc in full.** It documents an Android release-signing identity: RSA 4096 key, PKCS12 keystore, alias `cachevault-mobile-release`, with a certificate SHA-256/SHA-1 fingerprint, distinguished name, and validity dates — all standard, expected-to-be-public verification material (the same category of information as a TLS certificate thumbprint or an SSH host-key fingerprint; publishing it is how a verifier confirms a build's identity, not a vulnerability). It also documents where the keystore file and its encrypted backups live, and states explicitly "No secrets in this document. Passwords are never recorded here or anywhere in this repository."
2. **What signing mechanism is actually used, today, confirmed from source — not just the doc's claim.** `android/app/build.gradle.kts` reads three values exclusively via `System.getenv("CACHEVAULT_RELEASE_KEYSTORE"/"_STORE_PASSWORD"/"_KEY_ALIAS")`, with **no hardcoded fallback value of any kind**. A `releaseSigningAvailable` boolean gates whether the `release` signing config is attached to the `release` build type at all; when any env var is absent, AGP produces its normal unsigned output — the code does not fail, and does not silently fall back to a debug key. This matches the doc's description exactly.
3. **Public vs. private, explicitly separated.** Public/non-secret: certificate SHA-256 (`C2:EB:5C:...`) and SHA-1 fingerprints, distinguished name, algorithm identity, validity window, and a keystore-*file* integrity SHA-256 (a hash of the encrypted local file, not the key itself — cannot be used to reconstruct or use the key). Never present anywhere: the store/key password, the keystore file's contents, or any private-key byte material.
4. **Proved no private signing material is tracked in current HEAD.** `git ls-files | grep -iE '\.jks$|\.keystore$|\.p12$|\.pfx$|storepass|keypass|keystore\.properties|\.pem$|\.crt$|\.cer$'` → **empty**. `.gitignore` additionally covers `*.jks`, `*.keystore`, `*.p12`, `*.pfx`, `android/keystore.properties` as defense-in-depth.
5. **Inspected the entire reachable git history**, not just HEAD: `git log --all --full-history --diff-filter=A --name-only -- '*.jks' '*.keystore' '*.p12' '*.pfx' '**/keystore.properties' '*.pem'` → **empty** — no such file was ever added at any point in this repository's history. Same check for password-file naming patterns (`*.storepass`, `*.keypass`, `*storepass*`, `*keypass*`) → **empty**. No historical exposure found.
6. **Where signing material actually lives:** local-only, on the account holder's machine — a primary keystore copy, two additional local GPG-AES-256-encrypted backups, and one GPG-encrypted backup verified byte-for-byte on a physically separate device (a phone). The store/key password was migrated out of a plaintext file into a password manager entry on 2026-07-16 per the doc's own dated log — plaintext password files no longer exist. None of this — primary, backups, or password — is tracked in git; this was independently confirmed in step 4/5, not just asserted by the doc.
7. **Are release artifacts actually signed, hashed, or unsigned — checked both platforms, not assumed:**
   - **Android:** the doc's own "Verified output" section records an `apksigner verify --print-certs` run against the actual built APK, confirming a v2-scheme signature whose certificate SHA-256 matches the identity documented above. This is genuine, verifiable Android app signing — not a claim taken on faith.
   - **Windows:** `docs/release/code-signing-plan.md` states outright, in its first line: **"Cache Vault is not code-signed yet."** The desktop `.exe` is distributed hash-only (`SHA256SUMS.txt`), with no Authenticode signature. This is a documented, intentional, current-and-accurate state — not an oversight.
8. **Compared public-facing marketing/docs against actual behavior — checked, not assumed.** `landing.html` / `docs/index.html` (the live public download pages) both carry a FAQ entry, *"Is the app code-signed?"* → *"No. The release notes explicitly state that the Windows executable is currently unsigned, so SmartScreen may warn. Verify the ZIP checksum before running it."* — this matches reality precisely. The same page's mobile-download section advertises the Android APK with a real SHA256 hash and correctly describes the debug-to-production signing-key migration users must uninstall/reinstall for. **No false or misleading signing claim was found anywhere checked** (README.md, `landing.html`, `docs/index.html`, `CHANGELOG.md`).
9. **Re-examined the original §8 finding itself.** What it actually flagged was never a secret — it was that the custody doc, while entirely accurate and containing zero exploitable material, discloses more *non-secret operational/identifying detail* than a public document strictly needs: a real local username, exact backup folder paths, and a physical device's model + serial number. This is real and worth tidying (see Finish Queue P2), but it is categorically different from a credential leak and was overstated as "MEDIUM" security severity in the original pass.

**Root-cause conclusion:** Same shape as Gates 1 and 2. The original P0 framing ("signing-custody disclosure") suggested a possible secret exposure. Deeper, verified inspection — of current HEAD, of the *entire* git history, of the actual Gradle signing wiring, and of the public-facing docs — found none. What's actually present is legitimate public verification material plus a modest amount of excess non-secret operational metadata, and an honestly-disclosed unsigned-Windows-build status that matches every public claim about it.

**Required disposition:** `PROVEN SAFE — PUBLIC VERIFICATION MATERIAL ONLY`.

**What this changes:** §8 finding #1, §11 release blockers, and the Finish Queue's signing-custody item are all updated in place above. A new P2 hygiene item replaces the retired P0.

**Stop condition honored:** no CI, GitHub account, README/CHANGELOG, branch, or unrelated product-code changes were made under this gate. No secret was displayed, decrypted, or accessed. `git status --short` before and after this gate is identical except for this record file.

## 20. Finish Gate 4 receipt — README / CHANGELOG / version truth

**Authorized scope:** reconcile `README.md` and `CHANGELOG.md` against current proven behavior; remove/correct stale test-count claims; verify version truth across `pyproject.toml`, `cache_vault/__init__.py`, `android/app/build.gradle.kts`, and any other discovered version source; correct only demonstrably stale/inaccurate/misleading/undersold claims; preserve historically-accurate changelog entries; no new features; no CI/branch/signing-custody/website/release-artifact work.

**Self-correction found and applied before doc edits:** re-verifying `git log v0.2.0..HEAD --oneline | wc -l` for this gate returned **68**, not the "27" this record had stated in §1 Identity and elsewhere since the original canonicalization pass. That was **my own transcription error**, most likely conflating the HEAD SHA prefix (`27b68d6…`) with a commit count — not something the repository or its docs ever claimed. Every instance of "27" describing this commit gap has been corrected to 68 throughout this record (§1, §5, §7, §12) as part of this gate's version-truth work, since letting my own error stand while auditing the project's claims for accuracy would be exactly the kind of unverified-number problem this whole process exists to catch.

**Files changed (git blob hashes from the diff header, not recomputed separately — git's own content-addressing is the authoritative before/after identity here):**
| File | Before (blob) | After (blob) |
|---|---|---|
| `README.md` | `e026209` | `1e3884d` |
| `CHANGELOG.md` | `2f86669` | `3b0d19a` |

No other tracked file was touched. `git status --short` before and after this gate is identical except for these two files plus this record.

**Version truth — every source checked:**
| Source | Value | Note |
|---|---|---|
| `pyproject.toml` `[project].version` | `0.2.0` | Desktop |
| `cache_vault/__init__.py` `__version__` | `0.2.0` | Matches `pyproject.toml` — consistent |
| `android/app/build.gradle.kts` `versionName`/`versionCode` | `0.2.1` / `8` | Android companion — **independently versioned from desktop**, already ahead of it |
| Any other `__version__` constant in `cache_vault/*.py` | none found | Single source of truth confirmed via `grep -rn "__version__\s*="` |

**This is not a defect.** Desktop and the Android companion are separate deliverables with separate release cadences (confirmed by the `v0.2.1` mobile APK already being live on the public landing page while the desktop side is still at `v0.2.0`) — nothing in README or CHANGELOG claims the two must share a version number, and no claim anywhere was found asserting otherwise. Recorded here as the version-truth check the gate asked for, not corrected because there is nothing inconsistent to correct.

**Claim-by-claim corrections made:**

| # | File | Before | After | Why |
|---|---|---|---|---|
| 1 | `README.md` | Section header `## Honest scope & limitations (v0.1.8)` | `## Honest scope & limitations (current, v0.2.0)` | Version-pinned to a release two minor versions and 68+ commits stale |
| 2 | `README.md` | Implemented list: `mobile LAN bridge (developer mode)` | `an opt-in LAN-only mobile bridge with a published, production-signed Android companion (**CacheVault Mobile**)` | Undersold current reality — the companion is production-signed and publicly distributed, not a dev-mode curiosity |
| 3 | `README.md` | Not-implemented list: `published mobile app (LAN bridge exists but no Android/iOS client app is published yet)` | `an app-store mobile listing (the Android companion — CacheVault Mobile — is published as a signed APK attached to GitHub Releases, not on the Play Store; no iOS client exists)` | The original claim was **demonstrably false** — a production-signed APK is a `v0.2.0` GitHub Release asset (confirmed in Gate 0 via `gh release view`). The corrected claim is narrower and accurate: no *app-store* listing exists, which is true. |
| 4 | `README.md` | Section header `### Mobile LAN Bridge (Developer Mode)` | `### Mobile LAN Bridge` | Same "developer mode" mischaracterization as #2 |
| 5 | `README.md` | `No mobile app is published yet. The bridge is documented for developers building a client.` | `**CacheVault Mobile**, the Android companion, is published as a production-signed APK attached to [GitHub Releases](...) — it is not on the Play Store, and no iOS client exists.` | Same false claim as #3, corrected the same way |
| 6 | `CHANGELOG.md` | `## Unreleased` / `_No unreleased changes yet._` | Populated with dated context (2026-07-16 → 2026-08-13) and curated Added/Fixed/Changed sections covering the real 68-commit gap (Vault Cleanup Suggestions, context menus v1, mobile QR pairing, All Clips UX, deleted-clip recovery, Android image viewer, a cluster of Tk teardown/test-isolation fixes, continued render-perf work, and the `shell.py` god-class refactor) | The claim was flatly false — real, substantial, multi-week feature work sat unreleased with the changelog asserting nothing had changed |

**What was deliberately left alone (not "corrected," because it isn't demonstrably stale):**
- The `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` uncommitted diff (mobile Free/Founder gating policy) — the doc's own text calls the policy provisional ("not a permanent commitment"), so there is no settled fact to reconcile README/CHANGELOG against yet. Untouched, per the existing Finish Queue P1 item, which still stands.
- `RELEASE_NOTES.md`'s stale RC-draft claim ("no tag has been created") — real, but outside this gate's named scope (README.md/CHANGELOG.md only).
- Every dated section of `CHANGELOG.md` below `## Unreleased` (v0.2.0 and all prior releases) — untouched. Historical entries, including the self-reported "988/988"/"88/88" test counts, describe what was asserted true *at the time of that release* and are preserved as historical record, per the explicit instruction not to rewrite history just because current counts are larger.

**Validation run after editing:**
| Check | Command | Result |
|---|---|---|
| Claims scanner | `python scripts/scan_claims.py` | `README.md` and `CHANGELOG.md`: **zero findings** (the tool's 4 remaining findings are all pre-existing and out of scope: 3 are the scanner matching the literal words "local-only" inside this record's own prose describing tooling, not a product claim; 1 is the already-known, deliberately-untouched `RELEASE_NOTES.md` line) |
| Secrets scanner | `python scripts/scan_secrets.py` | No new findings introduced by either edited file |
| Diff review | `git diff -- README.md CHANGELOG.md` | 2 files changed, 63 insertions(+), 7 deletions(-) — full diff preserved above this table's evidence chain (also directly reviewable via `git diff` against the recorded blob hashes) |

**Root-cause note:** unlike Gates 1–3, this gate did not "discover" that a P0 was a false positive — the stale claims were real and are now fixed. What it did surface is a **new instance of the exact failure mode this whole process exists to prevent**: this record itself had carried an unverified number (27 vs. the real 68) forward across three prior gates without anyone re-deriving it. Caught and corrected here, in the open, rather than quietly.

**Stop condition honored:** no new product features were added; no CI, branch, signing-custody, or website work was performed; `RELEASE_NOTES.md` and the Free/Founder policy doc were consciously left untouched and are called out above rather than silently skipped.

## 21. Finish Gate 5 receipt — branch custody / triage

**Authorized scope:** classify every local branch's custody/merge status without deleting, merging, cherry-picking, rebasing, or force-pushing anything. Preservation-first. Full inventory in [`CACHE_VAULT_BRANCH_TRIAGE_GATE_5.md`](CACHE_VAULT_BRANCH_TRIAGE_GATE_5.md) (human-readable, all 142 non-master branches) and [`CACHE_VAULT_BRANCH_TRIAGE_GATE_5.json`](CACHE_VAULT_BRANCH_TRIAGE_GATE_5.json) (machine-readable, full per-branch data including every field computed).

**The "116" number, re-derived, not assumed:** `git branch --list | wc -l` → **143 total local branches** (unchanged from the original pass). Independently re-counting "branches with no matching `origin/<name>` ref" via a fresh per-branch script returned **exactly 116** — the original canonicalization pass's number **holds up under re-derivation**. Unlike the commit-count error corrected in Gate 4, this particular number was right. (Cross-derived two ways for confidence: directly, and as `143 − 27` branches-with-a-live-origin-ref, both agree.)

**Labeling clarification (explicitly named, so this can't drift into a 27-vs-68-style ambiguity later):** **143** and **116** are two *different metrics*, not a total-vs-subset pair that could be confused for each other — **143 = total local branches** (every ref under `refs/heads`, including `master`); **116 = the subset of those 143 with no currently-live `origin/<branch-name>` remote ref** (i.e., branches with zero remote-side backup under their own name — this says nothing by itself about merge status; a branch can be fully merged into `master` *and* be one of the 116, or be genuinely unique *and* be one of the 27 that do have a remote ref). Any future reference to "116" in this record should read "116 branches with no matching origin ref," not "116 unmerged branches" or "116 total branches" — those are different numbers (53 and 143, respectively).

**Step 2 — full re-derived counts:**
| Metric | Command | Count |
|---|---|---|
| Total local branches | `git branch --list \| wc -l` | 143 |
| Merged into `master` (topological ancestor) | `git branch --merged master \| wc -l` | 90 |
| NOT merged into `master` (topological) | `git branch --no-merged master \| wc -l` | 53 |
| Branches with an upstream configured | `git for-each-ref --format='%(upstream)'` | 64 |
| Branches whose upstream is marked `[gone]` | `git for-each-ref --format='%(upstream:track)'` | 28 |
| Branches with a live matching `origin/<name>` ref | per-branch `git rev-parse --verify origin/<name>` | 27 |
| Branches with **no** matching `origin/<name>` ref | same, inverted | **116 — confirms original estimate** |

**Methodology (Steps 3–7):** a script computed, per branch: tip SHA, merge-base with `master`, ahead/behind counts, upstream/remote status, and `git cherry master <branch>` output (patch-ID equivalence — distinguishes "truly unique diff" from "same net change already in master under a different SHA," which catches rebases/squashes/cherry-picks that a plain SHA-ancestry check would miss). This alone reclassified many nominally-"unmerged" branches as duplicates rather than unique work. A second pass cross-checked each remaining candidate's commit subjects against every subject in `master`'s own log (catching same-content-different-metadata cases) and flagged every group of branches sharing an identical tip SHA (pure duplicate pointers).

**A major structural finding, verified with direct evidence (not inferred from branch names):** a single commit, **`7193beb` — "merge: promote integrated CacheVault application lineage (#61)"** (2026-07-14) — **is a large squash-merge, confirmed an ancestor of current HEAD**, whose commit body contains the squashed history of PRs **#38, #41, #49, #50, #53, #59** (each independently confirmed present via `git log master --grep`). This single commit absorbed a whole family of prior integration/checkpoint branches — explaining why patch-ID matching alone didn't catch them as merged (squashing changes the diff shape even when the net content converges). Directly confirmed for the largest cluster by diffing `cache_vault/core/mobile/compatibility.py` between `master` and `feat/mobile-version-compatibility`: master's current file is a strictly more-evolved version of the same version-handshake concept the branch introduced. **26 branches were classified `STALE / SUPERSEDED` on this kind of direct evidence** (squash-merge absorption, superseding clean commit already on master, or being an RC/QA checkpoint for an already-shipped, now-many-versions-old release) — none on branch-name inference alone.

**Duplicate tip-SHA groups found:** 13 groups, 35 branches total, where multiple branch names point at the exact same commit (e.g., `backup/integration-before-promotion` and `ux/pr-a-shell-page-template` are both literally `74320b3e`). These are pure naming duplicates, not independent history.

**Genuinely unique work, checked, not assumed:**
- **1 branch, `repair/pre-tester-reliability`, is confirmed `UNIQUE — VALUABLE`** by direct diff: one real, well-tested commit (`f70265a`, 2026-08-14 — **after** current HEAD's 2026-08-13) implementing "deliver mobile shares while capture is paused and show local time," touching both the Android companion and desktop core, with 3 dedicated new/updated test files (327 lines of new tests). Not reachable from `master`. **This is real, current, stranded work.**
- **15 branches are `UNIQUE — NEEDS REVIEW`** (44 total patch-unique commits) — genuinely not ancestors of master, not found to be patch- or subject-equivalent, but **not individually diff-verified this gate** beyond file-scope and date. Per this gate's own instruction ("do not force uncertain branches into a stronger classification"), these are left exactly as uncertain — neither cleared as superseded nor promoted to confirmed-valuable. Mostly small, late-July clipboard/Tk-teardown fix branches whose themes closely resemble fixes that did ship in the 68-commit unreleased range, but that resemblance was not converted into proof.
- **8 of these unique-content branches have zero remote protection** (never pushed, `remote_exists: no`) — including the one confirmed-valuable branch. These 8 are the actual custody risk: real content that exists only on this one machine.

**Answers to the gate's required questions:**
> **Is any meaningful Cache Vault work currently stranded outside canonical master?**
**YES.** At minimum `repair/pre-tester-reliability`'s fix, confirmed by direct diff. Additionally **UNKNOWN** for the 15 needs-review branches — not ruled out, not confirmed; a "NO" cannot honestly be claimed until those are individually reviewed.

> **Would deleting all non-master branches today lose meaningful engineering history or functionality?**
**YES.** The confirmed-valuable branch's fix would be permanently lost (local-only, no backup). Separately, even the 26 `STALE/SUPERSEDED` branches — whose *functional* content is believed absorbed into master — represent real engineering history (the actual step-by-step evolution of the M1/A3 integration and several QA audit trails) that a mass-delete would erase as raw, inspectable git history, independent of whether the end-state code survives.

**Required disposition:** `PASS — UNIQUE WORK FOUND AND PRESERVATION REQUIRED`.

**What must survive any future cleanup gate:** the 1 `UNIQUE — VALUABLE` branch and the 15 `UNIQUE — NEEDS REVIEW` branches (16 total) — none of these should be deleted, force-pushed over, or pruned until individually reviewed or explicitly superseded with evidence. The 26 `STALE/SUPERSEDED` branches are lower-risk to eventually prune (their functional content is believed to already be on `master`) but still carry historical value worth a deliberate archive-not-delete decision in a later gate, not a silent removal.

**Stop condition honored:** zero branches deleted, merged, cherry-picked, rebased, or force-pushed. `git status --short` shows only the two new inventory files plus this record as new content — no branch refs were touched.

## 22. Finish Gate 5B receipt — unique-branch preservation

**Authorized scope:** preserve the 16 branches Gate 5 could not clear (1 `UNIQUE — VALUABLE` + 15 `UNIQUE — NEEDS REVIEW`) into a verified git bundle before any future cleanup gate touches them. No merge, delete, rebase, or branch modification.

**Step 1–3 — per-branch metadata (branch, tip SHA, merge base, unique-commit count, tree hash):**
| Branch | Tip SHA | Merge base | Unique commits | Tree hash |
|---|---|---|---|---|
| `brand/proof-founder-assets` | `2c8fbc2d8f` | `c5c6c88dac` | 3 | `fdc431d959` |
| `claude/romantic-matsumoto-f32d08` | `231abb38f5` | `83019a652d` | 5 | `366ae5e0ff` |
| `docs/local-hygiene-audit` | `4b9cc7cb5e` | `c5c6c88dac` | 1 | `9756c0fee6` |
| `feature/context-aware-context-menus-v1-clean` | `0643e6a51d` | `d9d4898c72` | 3 | `2223319c09` |
| `feature/settings-hotkeys-polish` | `d307bc4ee5` | `e340d03d36` | 1 | `111a2cd7c1` |
| `feature/tk-context-menu-master-port` | `98cff9c899` | `e430068812` | 1 | `783c49d9f2` |
| `fix/buyer-sim-restore-localappdata` | `a91d4374e8` | `f45078194e` | 2 | `fbc4b88dcc` |
| `fix/clipboard-custody-correction` | `525c0f14b7` | `bac987eeba` | 4 | `9e3311fdb2` |
| `fix/copy-combined-native-self-capture` | `a6f5df4eba` | `bac987eeba` | 5 | `d938629e7a` |
| `fix/native-acceptance-remediation` | `d650c7e061` | `bac987eeba` | 2 | `097e2ee448` |
| `fix/quick-paste-clipboard-restoration` | `fdcbaa5261` | `bac987eeba` | 9 | `391955dde8` |
| `fix/tk-main-thread-pump-teardown` | `274246ed0b` | `8f4df0bbeb` | 1 | `9c6d09630f` |
| `fix/tk-window-titlebar-teardown` | `b776aae11d` | `8f4df0bbeb` | 3 | `6e0ff358d9` |
| `recovery/tk-context-menu-final` | `6b2d374318` | `e430068812` | 2 | `138e7145fe` |
| **`repair/pre-tester-reliability`** *(the confirmed-valuable one)* | `f70265a357` | `27b68d606c` | 1 | `8668645528` |
| `wip/park-cachevault-release-docs` | `1623031765` | `cb4a4aee07` | 1 | `f20b330c1f` |

Full machine-readable copy: [`CACHE_VAULT_BRANCH_PRESERVATION/preserve_16_metadata.json`](CACHE_VAULT_BRANCH_PRESERVATION/preserve_16_metadata.json).

**Steps 4–8 — bundle creation, verification, restoration proof, hashing:**
1. **Created:** `git bundle create CACHE_VAULT_BRANCH_PRESERVATION/cachevault-unique-branches-gate5b.bundle refs/heads/<each of the 16>` — 58,566,536 bytes.
2. **Verified:** `git bundle verify` → `"is okay"`, lists all 16 expected refs at their exact recorded tip SHAs, **"The bundle records a complete history"** (self-contained — every object needed to reconstruct all 16 branches' full history back to their respective roots is inside the bundle, no external repo required).
3. **Restored:** `git clone` the bundle file into a fresh, empty temp directory (`%TEMP%\cachevault_bundle_restore_test`) — succeeded (the only warning was the expected "remote HEAD refers to nonexistent ref," normal for a bundle of feature branches with no designated default branch, and harmless — it doesn't affect any ref's presence).
4. **Confirmed reachable:** all 16 recorded tip SHAs individually checked with `git cat-file -e <sha>` inside the restored clone — **16/16 REACHABLE**.
5. **Temp clone deleted** after the check (it was a disposable verification copy, not a preservation copy — the bundle file itself, still in the repo, is the actual preserved artifact).
6. **SHA-256:** `952d2337bb80fd65c7231d9e581c717c0e503ebf7d6f97bd754491d35be7c880`

**Extension (per explicit request — "if practical," and it was): a second bundle for the 26 `STALE / SUPERSEDED` branches**, since their step-by-step engineering history has standalone value even where their end-state content already lives on `master`:
- **Created:** `cachevault-historical-superseded-branches-gate5b.bundle` — 60,370,740 bytes, all 26 refs.
- **Verified:** `git bundle verify` → `"is okay"`, all 26 refs confirmed present at recorded tips, "records a complete history."
- **SHA-256:** `395e826dbac8a5351fc0792b882c8dd0484d4aec6ccfc640ffb03bba2159c744`
- **Not** put through the same full clone-and-reachability-check as the 16-branch bundle (that step was this gate's explicit requirement for the confirmed/needs-review set specifically) — `git bundle verify`'s own "complete history" confirmation is still real, independent evidence the bundle is structurally sound, just one step short of the deeper proof given to the higher-priority set.

**Where the artifacts live:**
- `CACHE_VAULT_BRANCH_PRESERVATION/cachevault-unique-branches-gate5b.bundle` (the 16 branches requiring review)
- `CACHE_VAULT_BRANCH_PRESERVATION/cachevault-historical-superseded-branches-gate5b.bundle` (the 26 superseded branches, historical value)
- `CACHE_VAULT_BRANCH_PRESERVATION/preserve_16_metadata.json` (per-branch metadata for the 16)

**Custody note:** both bundle files are, for now, sitting on the same single machine as everything else in this repo's local-only branch inventory — they are a **structural** preservation (independent of any one branch ref surviving, and independent of the specific `.git` internal layout) but **not yet an off-machine backup**. The same "local-only" risk flagged throughout this whole canonicalization pass (§8) applies to these bundle files too until a copy exists somewhere else. Recommended next step, not performed automatically here: copy both `.bundle` files to at least one location off this machine (matches the same 3-2-1 logic already documented for the Android signing keystore in §19).

**Disposition:** both bundles created, verified, and (for the priority 16) restoration-proven. **Zero branches deleted, merged, rebased, cherry-picked, or force-pushed** — `git status --short` and `git branch --list | wc -l` (still 143) are unchanged from before this gate; the only new content is the `CACHE_VAULT_BRANCH_PRESERVATION/` directory and this record.

## 23. Finish Gate 5C receipt — deep review of the 15 `UNIQUE — NEEDS REVIEW` branches

**Authorized scope:** read-only diff-level classification of the 15 branches Gate 5 left unresolved, before deciding whether to integrate `repair/pre-tester-reliability`. No merges, rebases, cherry-picks, deletions, resets, or source edits. Every branch forced into an evidence-backed final disposition — none left as "needs review" this time.

**Method:** for each branch, pulled the full commit message + `--stat` file list for every `git cherry`-confirmed unique commit, then directly tested the specific hypothesis that mattered for that branch: does the file/concept it introduces exist on `master` today, and if so, in what shape? Checked via `git cat-file -e` (existence), line-count comparison, `diff` (byte-level equivalence), and `grep -c` for the introduced concept/terminology on `master`. No disposition below rests on branch name or commit count alone.

**Result — all 15 resolved, none left `UNKNOWN`:**

| Branch | Gate 5C disposition | Key evidence |
|---|---|---|
| `fix/quick-paste-clipboard-restoration` | **`UNIQUE — VALUABLE`** | `cache_vault/core/clipboard_custody.py` **confirmed absent from master**; master's `paste_delivery.py` is 304 lines vs. this branch's 443; `grep -ic "self_capture\|custody"` on master's `clipboard.py` returns **0**. 9 commits, 6 dedicated test files, ~1,900 new test lines. Addresses named bug classes (clipboard self-capture, paste-restoration races) that master currently has no defense against. |
| `fix/clipboard-custody-correction` | `UNIQUE — VALUABLE (subsumed)` | Confirmed a strict 4-commit prefix of `fix/quick-paste-clipboard-restoration`'s 9. Same subsystem, earlier checkpoint — adds nothing beyond it. |
| `fix/copy-combined-native-self-capture` | `UNIQUE — VALUABLE (subsumed)` | Confirmed a strict 5-commit prefix of the same lineage. |
| `fix/native-acceptance-remediation` | `UNIQUE — VALUABLE (subsumed)` | Confirmed a strict 2-commit prefix of the same lineage. |
| `feature/context-aware-context-menus-v1-clean` | `STALE / SUPERSEDED` | `cache_vault/core/permanent_delete.py` is **byte-identical** to master's (459/459 lines, 0 diff). `sidebar_menu_context.py` present on master in a further-evolved form. Landed via `396cd78` (already on master). |
| `feature/settings-hotkeys-polish` | `STALE / SUPERSEDED` | Its `hotkey_settings.py` is absent from master, but master has since grown a full Settings Hub (`settings_hub.py`, `hotkey_recording.py`, dedicated tests) built ~2 weeks later — a superseding, more complete implementation, not a gap. |
| `feature/tk-context-menu-master-port` | `STALE / SUPERSEDED` | Its one commit is the shared prefix of `recovery/tk-context-menu-final` (see below), independently confirmed superseded. |
| `fix/tk-main-thread-pump-teardown` | `STALE / SUPERSEDED` | Master's `shell.py` has 11 matches for "pump"; `tests/test_shell_pump_teardown.py` exists on master. |
| `fix/tk-window-titlebar-teardown` | `STALE / SUPERSEDED` | Shares its leading commit with the pump-teardown branch above (also superseded); master's `first_use_guide.py` has 9 matches for "titlebar"/"teardown". |
| `recovery/tk-context-menu-final` | `STALE / SUPERSEDED` | Its final commit (`6b2d3743`, Aug 4 14:10:04, "make Tk context menus activate on first click") is the **direct, same-day precursor** to master's `d602253` (Aug 4 14:33:40 — 23 minutes later), which explicitly lists "first-click activation" among its completed fixes and touches the identical files. |
| `brand/proof-founder-assets` | `EXPERIMENTAL / ABANDONED` | Adds a distinct "Proof Founder" avatar/logo brand direction (2026-06-21). Master's current live assets are confirmed exclusively `cache-vault-*` (the documented teal-vault-dial identity) — zero trace of the "proof-founder-*" naming anywhere on master. An abandoned early branding concept, not lost functionality. |
| `wip/park-cachevault-release-docs` | `EXPERIMENTAL / ABANDONED` | An explicit `wip:` scratch dump (30 files) whose contents are a superset of material already individually classified above (the same abandoned brand assets, the same historical hygiene-audit doc) plus misc PR-draft `tmp/` text files. No independent content. |
| `claude/romantic-matsumoto-f32d08` | `HISTORICAL / RELEASE` | 5 docs-only commits correcting the v0.1.4 release page/checksums (2026-06-29) — moot; v0.1.4 has been superseded by 7 later releases. |
| `docs/local-hygiene-audit` | `HISTORICAL / RELEASE` | A single dated audit doc, superseded in spirit by every later audit pass including this one. |
| `fix/buyer-sim-restore-localappdata` | `HISTORICAL / RELEASE` | 101 files, nearly all binary QA screenshots from one dated buyer-simulation proof run — evidence artifact, not source functionality. |

**Overlap/conflict check against `repair/pre-tester-reliability`:** explicitly checked every one of the 15 branches' touched files against that branch's (`cache_vault/core/clip_metadata.py`, `cache_vault/core/vault.py`, and three Android files). **No live conflicts found.** One *historical* file-level overlap noted for transparency: `feature/context-aware-context-menus-v1-clean` also touched `vault.py`, but its content already landed on master (via `396cd78`) before `repair/pre-tester-reliability` was ever written on top of current HEAD — so there is nothing to reconcile, the history is already linear. The confirmed-valuable clipboard-custody lineage touches an entirely different file set (`clipboard.py`/`clipboard_custody.py`/`paste_delivery.py`) with zero overlap.

**Integration guidance for the one real find, `fix/quick-paste-clipboard-restoration`:** **test first, not blind-merge.** Strong automated coverage exists (6 dedicated test files), but no runtime/manual QA evidence (no `docs/qa/*` record, unlike some other shipped features) was found for this specific work. It touches the core Win32 clipboard read/write path — exactly the kind of surface where unit tests can stay green against mocks while real OS clipboard behavior still differs. Recommend a manual runtime verification pass before merge, matching the QA discipline this project already applies elsewhere (e.g., the physical-device verification behind the v0.2.0 mobile release).

**Inventory updated:** `CACHE_VAULT_BRANCH_TRIAGE_GATE_5.md`/`.json` now carry `[Gate 5C]`-tagged dispositions and evidence for all 15 branches, superseding their prior generic "needs review" entries in place (not overwritten silently — the JSON retains both the original Gate 5 `final_disposition`/`final_note` fields and the new `gate_5c_disposition`/`gate_5c_evidence` fields side by side).

**Disposition:** classification complete for all 15 — **1 confirmed valuable** (plus 3 redundant checkpoints of the same work), **6 superseded**, **3 historical**, **2 abandoned**, **0 unresolved**. Zero merges, rebases, cherry-picks, deletions, or source edits performed. `git status --short` and `git branch --list | wc -l` (still 143) unchanged except for the updated inventory files and this record.

## 24. Finish Gate 5D receipt — clipboard-custody runtime qualification

**Authorized scope:** runtime-qualify `fix/quick-paste-clipboard-restoration` in an isolated worktree against **real Windows clipboard behavior**, not mocks. No merge. Stop after disposition.

**Setup:** `git worktree add %TEMP%\cv_gate5d_clipboard_custody fix/quick-paste-clipboard-restoration` — an isolated checkout, no changes to the main working tree.

**Part 1 — the six dedicated test files + the broader clipboard/Quick Paste suite, run in the isolated worktree:**
`test_clipboard_custody.py`, `test_clipboard_custody_race.py`, `test_clipboard_self_capture.py`, `test_clipboard_open_retry.py`, `test_clipboard_image_fingerprint.py`, `test_copy_combined_native_custody.py` — **all PASSED** (verbose `-rA` run, every individual test line confirmed PASSED, none skipped or xfailed). Plus the broader suite: `test_clipboard_refresh.py`, `test_image_clipboard.py`, `test_paste_delivery.py`, `test_quick_paste.py` — **all 20 tests PASSED**.

**Part 2 — real, non-mocked Win32 runtime proof.** Read the actual source (`clipboard_custody.py`, `clipboard.py`, `paste_delivery.py`, `ui/clipboard_write.py`) to confirm the module is genuinely Win32-backed by default (`_default_set_text`/`_default_set_image`/`default_clipboard_sequence` call real `win32clipboard`/`ctypes` APIs; mocking only happens via explicit dependency injection in unit tests) and that the app wires one shared `ClipboardWriteSuppressor` at the composition root (`cache_vault/ui/shell.py:359-360`). Built a standalone harness (`CACHE_VAULT_BRANCH_PRESERVATION/gate5d_5e_5fa_evidence/gate5d_runtime_proof.py`) instantiating the real classes directly against the actual OS clipboard — saving and restoring this machine's real clipboard content around the run. **10/10 real checks passed:**

| # | Check | Result |
|---|---|---|
| 1 | External copy captured exactly once | PASS |
| 2 | App's own write via `ClipboardWriter` NOT self-captured | PASS |
| 3 | Duplicate self-writes (same text twice) both suppressed | PASS |
| 4 | Later genuine identical **external** re-copy IS captured again (one-shot consumption) | PASS |
| 5 | 8 rapid-fire internal writes — zero leaked into capture | PASS |
| 6 | Pause blocks capture | PASS |
| 7 | Resume restores capture | PASS |
| 8 | Paste → restore roundtrip (snapshot/restore custody path), original clipboard content verified restored | PASS |
| 9 | Real PNG image written via `ClipboardWriter.write_image`, confirmed present as `CF_DIB` on the actual clipboard, not self-captured | PASS |
| 10 | **Real target window**: launched an actual Notepad process, delivered a real synthetic Ctrl+V via `paste_delivery.deliver_ctrl_v`, read Notepad's edit control back via `WM_GETTEXT` — the exact test string was found inside real Notepad | PASS |

Full results: `CACHE_VAULT_BRANCH_PRESERVATION/gate5d_5e_5fa_evidence/gate5d_results.json`. The user's real clipboard content, saved before the run, was restored at the end.

**Part 3 — proving what the branch actually fixes.** An initial ad hoc attempt to reproduce the "identical recopy swallowed" bug directly against current master's real clipboard did **not** reproduce it in that specific run (an intermediate clipboard write meant master's simpler `_last_text` marker had already been overwritten by the time of the later copy — reported honestly rather than forcing a predetermined result; see `gate5d_master_comparison_result.json`). The branch's **own regression test suite**, however, provides precise, controlled, and already-independently-reconfirmed proof of the exact bug class: `test_regression_pre_slice_a_self_capture_race` instantiates the real (unsuppressed) `ClipboardMonitor` — the same class shipped on master today — under a realistic event-before-marker race, and the assertion **`captures == ["internal write"]`** shows the app's own write genuinely gets recaptured as if external. `test_regression_pre_slice_a_identical_recopy_swallowed` reproduces the exact swallowed-recopy defect with precise sequencing. `test_slice_a_fixes_both_symptoms` proves the branch's `ClipboardWriteSuppressor`/`ClipboardWriter` resolve both. All three were run and confirmed PASSED as part of the Part 1 test run above — this is not a claim taken on faith, it was independently re-executed. Master's actual current defense (`ClipboardMonitor.note_local_copy()`, `cache_vault/core/clipboard.py:158-166`) is confirmed to be a simple persistent "last known text" comparison with no one-shot consumption and no TTL — structurally exactly the design the branch's own module docstring says it replaces.

**Part 4 — compatibility with the 68 commits since.** A real merge attempt in a disposable worktree/branch (`git merge --no-commit --no-ff fix/quick-paste-clipboard-restoration` against current `master`, then `git merge --abort` — nothing kept) found **8 files with real content conflicts, 24 conflict blocks total**: `cache_vault/ui/shell.py` (12 blocks — expected, given the god-class refactor extracting sidebar/bulk-action logic in the 68-commit range touched this file heavily), `cache_vault/core/paste_delivery.py` (5 blocks — genuine structural divergence, master's version is 139 lines shorter), `cache_vault/ui/batch_actions.py` (2), and one block each in `dialogs.py`, `founder.py`, `mobile_dialogs.py`, `vault_screens.py`, `tests/test_macro_execute.py`. **The new subsystem itself is conflict-free** — `clipboard_custody.py` and all 6 dedicated test files merge cleanly as pure additions (master never had them, so there's nothing to conflict with). The conflicts are entirely in "wiring" files that both this branch and the subsequent 68 commits independently touched — not evidence of a flawed design, but real integration work that has to happen before a merge.

**Required disposition: `NEEDS REBASE/ADAPTATION`.**

Not `PROVEN INTEGRATION CANDIDATE` — 8 files do not merge cleanly against current master, and that has to be resolved (mechanically, not conceptually — the conflicts are in surrounding code that moved, not in competing designs) before this can land. Not `REJECT` — the runtime proof is unambiguous: 10/10 real Win32 checks pass, the specific bug classes it fixes are independently confirmed both by its own regression tests (re-run and reconfirmed) and by reading master's actual current (weaker) defense mechanism, and the core new subsystem carries zero merge conflicts of its own.

**Recommendation, not a decision — this gate stops here per the authorization:** if/when this proceeds toward integration, resolve the 8 conflicts on a rebase, re-run the same 26 tests (Part 1) plus the 10 real-clipboard checks (Part 2) against the rebased tip, and follow this project's own precedent for the manual/physical QA pass it applies before shipping other core-behavior changes (e.g., the physical-device verification behind the v0.2.0 mobile release) before merging to `master`.

**Cleanup:** the isolated worktree, the merge-probe worktree, and the disposable `gate5d-merge-probe` branch were all removed after use. `git branch --list | wc -l` is still 143. `git status --short` on the main checkout shows only the pre-existing dirty state plus the new evidence files under `CACHE_VAULT_BRANCH_PRESERVATION/gate5d_5e_5fa_evidence/` and this record. **No merge was performed.**

## 25. Finish Gate 5E receipt — `repair/pre-tester-reliability` runtime qualification

**Authorized scope:** runtime-qualify `repair/pre-tester-reliability` in an isolated worktree, re-derive its delta, prove the intended contract at runtime, check compatibility, and explicitly re-verify zero overlap with the clipboard-custody branch. No merge. Stop after disposition.

**Setup:** re-used a worktree already present on this machine from before this session (`C:\Users\KickA\Documents\CacheVault Build\repair-pre-tester`, confirmed at the correct tip `f70265a3`) rather than creating a duplicate — verified clean (one pre-existing, unrelated dirty file matching the same pattern seen throughout the main repo).

**Delta re-derived (not assumed):** `git log master..repair/pre-tester-reliability` and `git cherry -v master repair/pre-tester-reliability` both confirm **still exactly 1 commit** (`f70265a3`, 2026-08-14 12:46:35), unchanged since Gate 5. 8 files, 605 insertions / 97 deletions.

**Intended contract, read directly from the commit message and diff** (not taken on faith — the commit itself makes verifiable claims, cross-checked below): three defects fixed together, found while diagnosing a real "share to Cache Vault does nothing" failure on a physical S23:
1. `Vault.capture_mobile_share` and the mobile-image path returned `None` whenever `capture_paused` was set — an authenticated, explicit send from a paired phone was being vetoed by a setting meant only for *passive* clipboard monitoring. Fix: removed the veto from both paths; ordinary (non-mobile) capture's pause check is untouched.
2. Stored UTC timestamps were rendered as if local (`human_timestamp`, `date_group_header`, `format_captured_at` all formatted the raw stored value). Fix: added `clip_metadata.to_local()`/`_local_view()`, applied in all three formatters; storage stays UTC.
3. Repeated taps on the Android share button (no in-flight/success feedback) created duplicate byte-identical vault items. Fix: `SendPhase` + a `blocksNewSend` invariant on the Android side (Kotlin, UI-layer — not independently runtime-testable without a physical device/emulator, consistent with this whole pass's existing Android-hardware limitation).

**Part 1 — focused tests, run unchanged first:** `test_d2_polish.py`, `test_local_timestamp_display.py`, `test_mobile_send_ignores_capture_pause.py` — **27/27 PASSED** (verbose `-rA`, every test line individually confirmed). Broader relevant suite (every test file referencing the touched functions/modules: `test_clip_labels_grouping.py`, `test_clip_list_row_pool.py`, `test_d3_5_compatibility.py`, `test_d3_mobile_model.py`, `test_home_dashboard.py`, `test_ux_rescue.py`, `test_mobile_bridge.py`, `test_mobile_inbox.py`, `test_mobile_image_inbox.py`, `test_mobile_pairing.py`) — **100% pass, no failures** (~195 additional tests). Same proportionate approach as Gate 5D's Part 1 (focused files + everything demonstrably relevant, not the full 1,886-test suite, which would add wall-clock time without adding signal for a change this narrowly scoped).

**Part 2 — real runtime proof, one level beyond what the existing tests already do.** The project's own tests already "drive the real bridge" (per `test_mobile_send_ignores_capture_pause.py`'s own docstring) rather than pure mocks — so the uplift here was to go one step further: a standalone harness (`CACHE_VAULT_BRANCH_PRESERVATION/gate5d_5e_5fa_evidence/gate5e_runtime_proof.py`) that binds an **actual TCP socket** via `MobileBridge._start()`, and drives it with **genuine HTTP requests over a real socket connection** (`http.client`, not in-process function calls), against a real (isolated, in-memory-SQLite) `Vault` — not the user's real profile. **10/10 real checks passed:**

| # | Check | Result |
|---|---|---|
| 1 | Real HTTP server actually binds and accepts loopback connections | PASS |
| 2 | Real device pairing | PASS |
| 3 | **Mobile share succeeds over a real HTTP POST while `capture_paused=True`** (status 200, clip created) | PASS |
| 4 | `capture_paused` state itself unaffected by the delivery | PASS |
| 5 | The new clip is well-formed (correct content, valid id) — vault/history not corrupted | PASS |
| 6 | **Ordinary (non-mobile) capture is still correctly blocked while paused** — confirms the fix did not weaken normal pause semantics | PASS |
| 7 | Normal capture works again after `capture_paused=False` | PASS |
| 8 | Two real, distinct authenticated sends (simulating a double-tap) both land cleanly at the desktop layer with no corruption — with the explicit caveat that true duplicate-tap *prevention* is the Android `SendPhase` UI fix, not exercisable without a device | PASS |
| 9 | **Authentication is still enforced while paused** (bad token → real 401, not silently accepted) — confirms the pause-bypass didn't accidentally weaken auth | PASS |
| 10 | Real UTC→host-local timestamp conversion: a synthetic `18:42 UTC` clip renders at `11:42 local` on this machine (matches the real host's `-7h` offset) | PASS |

Full results: `CACHE_VAULT_BRANCH_PRESERVATION/gate5d_5e_5fa_evidence/gate5e_results.json`. Restart/persistence behavior was judged not independently relevant to this change and not separately tested — the fix touches only runtime pause-check logic and a pure display-formatting function, neither of which alters what's written to or read from disk; noted explicitly rather than silently skipped.

**Part 3 — compatibility with current master.** A real merge attempt in a disposable worktree/branch (`git merge --no-commit --no-ff repair/pre-tester-reliability`, then `git merge --abort` — nothing kept): **"Automatic merge went well; stopped before committing as requested."** Confirmed genuinely clean — `git status --short` showed only clean `M`/`A` entries (no `U` unmerged paths), and an explicit `grep` for conflict markers across the merged tree found none. Re-ran the focused + broader test subset (above) against the merged-but-uncommitted tree as an extra semantic check beyond git's purely textual merge — **all passed there too.**

**Part 4 — overlap with the clipboard-custody branch, checked precisely, not assumed.** Computed the exact file sets touched by each branch (`git diff --name-only` from each branch's own merge-base) and intersected them programmatically: **`repair/pre-tester-reliability`** touches `ShareAssistantActivity.kt`, `SimpleShareScreen.kt`, `SendPhaseTest.kt`, `clip_metadata.py`, `vault.py`, and 3 test files. **`fix/quick-paste-clipboard-restoration`** touches `clipboard.py`, `clipboard_custody.py`, `paste_delivery.py`, `image_assets.py`, `macro_execute.py`, `batch_actions.py`, `clipboard_write.py`, `dialogs.py`, `founder.py`, `mobile_dialogs.py`, `shell.py`, `vault_screens.py`, and 7 test files. **Intersection: empty set. Zero overlap, confirmed by computation, not recollection.**

**Superseded check:** confirmed master still has both desktop-side bugs today — `capture_mobile_share` still contains the `capture_paused` veto (unchanged), and `clip_metadata.py` still has **zero** `to_local` function. Not superseded by any later master work.

**Required disposition: `PROVEN INTEGRATION CANDIDATE`.**

A meaningfully different result from Gate 5D's clipboard-custody branch: this one merges genuinely cleanly (0 conflicts vs. 24 conflict blocks), every test passes both standalone and against the merged tree, the real-HTTP-server runtime proof is 10/10, the fix addresses a real, well-documented, reproducible defect (the commit's own "5/5 failed with pause on, 4/4 succeeded with it off" intervention numbers on a physical device match the shape of what this pass independently reproduced in code), and there is zero overlap with the other confirmed-valuable branch — the two can be evaluated and integrated fully independently.

**Cleanup:** the merge-probe worktree and disposable `gate5e-merge-probe` branch were removed after use. `git branch --list | wc -l` is still 143. **No merge was performed**; the pre-existing `repair-pre-tester` worktree was left exactly as found (read-only use — tests were run there, nothing was edited).

## 26. Finish Gate 5F-A receipt — controlled integration of `repair/pre-tester-reliability`

**Authorized scope:** integrate the runtime-qualified, non-superseded, cleanly-mergeable `repair/pre-tester-reliability` into a **new integration branch** (not canonical `master`), with history preserved (real merge commit, not a squash), then run every applicable validation lane against the integrated tree. Stop before merging the result into `master` — deliver the receipt and diff first. `fix/quick-paste-clipboard-restoration` untouched.

**Integration branch and merge:**
- Created `integration/gate5f-a-pretester-reliability` from `master` (`27b68d606c58a493ae297e29f6660eb94f9365aa`), checked out into an isolated worktree.
- `git merge --no-ff repair/pre-tester-reliability` — a real merge commit, **history preserved**, not squashed.
- **Integrated tip SHA: `1d5e701ceb3acdee569eea36f75be4e9ec07f201`**
- **Merge ancestry — two parents, both confirmed:** `27b68d606c58a493ae297e29f6660eb94f9365aa` (master) and `f70265a35723cd2763c5e579311a29732d1ba326` (repair/pre-tester-reliability). `git merge-base --is-ancestor` confirms both are ancestors of the new tip.

**Diff verification — exactly the expected changes, nothing else:** `git diff master..HEAD --stat` against the integrated tip shows **precisely the same 8 files, same line counts** as the isolated branch's own diff (§25): `ShareAssistantActivity.kt`, `SimpleShareScreen.kt`, `SendPhaseTest.kt` (new), `clip_metadata.py`, `vault.py`, `test_d2_polish.py`, `test_local_timestamp_display.py` (new), `test_mobile_send_ignores_capture_pause.py` (new) — 605 insertions, 97 deletions. No scope creep, no unrelated files.

**Validation lanes, all run against the integrated tree:**

| Lane | Result |
|---|---|
| Focused tests (`test_d2_polish.py`, `test_local_timestamp_display.py`, `test_mobile_send_ignores_capture_pause.py`) + broader relevant suite (10 more files) | **All PASSED** (same 27 + ~195 as Gate 5E, re-run fresh on the merged tree) |
| Real `MobileBridge` TCP/HTTP runtime harness (same 10-check harness as Gate 5E, retargeted at the integrated worktree) | **10/10 PASSED** — paused-capture share success, pause-state integrity, well-formed clip, ordinary-capture-still-blocked, resume-works, repeated-send desktop-side integrity, auth-still-enforced (401), UTC→local conversion |
| Android Gradle unit tests (`./gradlew testDebugUnitTest`) | **BUILD SUCCESSFUL. 111 tests, 0 skipped, 0 failures, 0 errors** (aggregated directly from the JUnit XML reports, not just the console summary) — independently confirms the commit's own self-reported "Android unit suite 111 passed / 0 failures" claim |
| Physical-device `SendPhase` duplicate-tap prevention | **Still explicitly unverified** — Kotlin UI logic, requires a real device/emulator, consistently flagged since Gate 0. Not resolved by this integration; noted here again rather than silently dropped. |
| Full Python suite (`pytest -q`, direct file redirect — not the tail-pipe mistake from earlier gates) | **Exit code 0. 1,905 collected tests** (1,886 baseline + exactly 19 new — 10 in `test_local_timestamp_display.py`, 9 in `test_mobile_send_ignores_capture_pause.py` — accounted for precisely, no unexplained drift). Dot-progress: 100% complete, **zero `F` markers**, one `s` (the same single conditional skip as baseline). The suite's own teardown reported one unrelated Windows-icon-cache cleanup quirk ("all tests passed, but the sandbox could not be fully removed") — a filesystem-lock artifact of Explorer, not a test failure. |
| Packaged build (`pyinstaller ... --clean`) | Builds cleanly from the integrated tree |
| Packaged self-test (`dist\CacheVault.exe --selftest`) | **PASS**, exit 0 |
| `tools/verify_exe_metadata.py` | **PASS** — all 12 checks (version 0.2.0 throughout, correct product/company strings) |

**Before/after repository comparison:** `git status --short` on the main checkout is unchanged except for this record; `git branch --list | wc -l` went from 143 to **144** (the one new, intentional `integration/gate5f-a-pretester-reliability` branch — not a stray). **`master`'s HEAD is confirmed unchanged** (`27b68d606c58a493ae297e29f6660eb94f9365aa`), and `git merge-base --is-ancestor integration/gate5f-a-pretester-reliability master` confirms the integration branch is **not** merged into `master` — exactly the controlled, non-canonical integration this gate asked for.

**Required disposition: `PROVEN INTEGRATED CANDIDATE`.**

Every applicable validation lane passed, with no scope creep, no regressions, and one limitation (physical-device Android UI verification) stated plainly rather than glossed over. This is ready for a human decision to fast-forward `master` to this tip — that decision was explicitly not made here.

**Evidence:** `CACHE_VAULT_BRANCH_PRESERVATION/gate5d_5e_5fa_evidence/gate5fa_results.json` (runtime harness), `gate5fa_gradle_test.log` (Android). The integration worktree (`%TEMP%\cv_gate5fa_integration`) and branch (`integration/gate5f-a-pretester-reliability`) were **left in place**, not deleted, since this gate's own instructions call for stopping before the `master` merge decision — deleting the candidate now would defeat the purpose.

**Stop condition honored:** no merge into canonical `master` was performed. `fix/quick-paste-clipboard-restoration` was not touched. No Gate 6 work was performed.

---

## 27. Finish Gate 5F-B receipt — adaptation of `fix/quick-paste-clipboard-restoration` onto the Gate 5F-A baseline

**Authorized scope:** adapt the clipboard-custody branch onto the already-validated `integration/gate5f-a-pretester-reliability` baseline, on a new integration branch, resolving all merge conflicts deliberately (reasoning through behavioral/timing/correctness implications, never blindly picking a side), then re-validating fully before reporting a disposition. Canonical `master` stays frozen throughout — no merge into it without a separate future authorization.

**Integration branch and merge:**
- Created `integration/gate5f-b-clipboard-custody` from `integration/gate5f-a-pretester-reliability`'s tip (`1d5e701ceb3acdee569eea36f75be4e9ec07f201`), checked out into an isolated worktree (`%TEMP%\cv_gate5fb_integration`).
- `git merge --no-ff fix/quick-paste-clipboard-restoration` — a real merge commit, **history preserved**, not squashed.
- **Merge commit SHA: `88807139c7d00b54f6b68ce012a52193eaa336ec`**
- **Merge ancestry — two parents, both confirmed:** `1d5e701ceb3acdee569eea36f75be4e9ec07f201` (gate5f-a tip) and `fdcbaa5261eb2dab28887d7d5d17eefeda9dd0d0` (`fix/quick-paste-clipboard-restoration` tip, confirmed unaltered by this gate). `git merge-base --is-ancestor` confirms both are ancestors of the integration branch's final tip.
- **Follow-up fix commit (post-merge validation): `bcfca9d081ed754e5fa7b54e6ff203c879116654`** — see below; the merge itself did not fully resolve the conflicts correctly on the first pass, and this record says so plainly rather than presenting the merge commit alone as the finished result.
- **Final integrated tip: `bcfca9d081ed754e5fa7b54e6ff203c879116654`.**

**Diff vs. the Gate 5F-A baseline:** 21 files changed, 4,214 insertions, 134 deletions — `cache_vault/core/{clipboard.py, clipboard_custody.py (new, 647 lines), image_assets.py, macro_execute.py, paste_delivery.py}`, `cache_vault/ui/{batch_actions.py, clipboard_write.py, dialogs.py, founder.py, mobile_dialogs.py, shell.py, vault_screens.py}`, and 8 test files (3 new: `test_clipboard_custody.py`, `test_clipboard_custody_race.py`, `test_clipboard_image_fingerprint.py`; the rest — `test_clipboard_custody_retry.py`, `test_clipboard_open_retry.py`, `test_clipboard_self_capture.py`, `test_copy_combined_native_custody.py`, `test_quick_paste_clipboard_restore.py` — pre-existing baseline files adapted for the new custody architecture). No unexplained files.

**Conflicts resolved deliberately — not by picking a side:**
1. **`paste_delivery.py`:** adopted the branch's `ClipboardWriteOutcome`/shared `_write_clipboard_text` architecture (a real capability the baseline lacked), but restored the baseline's CRLF canonicalization specifically for the *set* path (`_set_clipboard_text_outcome`) while keeping the *restore* path (`_restore_clipboard_text_outcome`) byte-exact — these are genuinely asymmetric, not an oversight either side made. Reconciled two independently-tuned OpenClipboard retry budgets (branch: 5×15ms; baseline: 20×20ms) to 10×20ms, the smallest value that satisfies both sides' own tests (see fix commit below).
2. **`clipboard_custody.py` (`ClipboardWriter.write_text`):** fixed to fingerprint the canonical-CRLF form of the text, not the raw pre-write text — the branch's own design had a real, previously-silent bug here: self-capture suppression was broken for all multiline text, since the monitor fingerprints what it actually reads back off the real clipboard (canonical CRLF), not the caller's raw string.
3. **`shell.py` (`_do_paste` / `_schedule_clipboard_restore`):** the most significant resolution. A first-pass merge would have discarded the baseline's 400ms-deferred, payload-verified, retried restore (built and measured against a real, documented "restore races the paste, 5/5 trials" regression) in favor of the branch's simpler ~160-240ms immediate restore — which would almost certainly have reproduced that exact bug. Caught via a pre-existing baseline test file (`test_quick_paste_clipboard_restore.py`, 11 tests, predates the branch's own 6-file scope) that started failing post-merge. Fixed by restoring the full timing/verification/retry mechanism, routed through the custody-protected write path.
4. 12 further conflict blocks in `shell.py`/`founder.py`/`dialogs.py`/`mobile_dialogs.py`/`vault_screens.py`/`batch_actions.py` switching call sites from the baseline's `clipboard_out.write_via_tk`/`note_local_copy` to the branch's custody-aware `_writer_write_text`/`_writer_restore_text`, with one deliberate exception (a `skip_delivery` restore-condition guard) kept on the baseline's side because its fix addressed a different, still-relevant sibling bug.

**Defects found and fixed during post-merge validation (not present in either side alone — surfaced only by combining them):** see fix commit `bcfca9d` for the full list with evidence. In summary:
- Multiline self-capture-suppression fingerprint bug (item 2 above).
- `_writer_write_text`'s no-writer fallback reported stale (pre-canonicalization) text to `note_local_copy`, causing a bare-LF/CRLF mismatch at multiline clip-join boundaries.
- The deferred-restore retry loop conflated "content never reached the clipboard" (worth retrying) with "content landed but the transaction didn't close cleanly" (must not be retried, per `_write_clipboard_text`'s own documented contract) — retrying the latter caused a redundant second `SetClipboardData` call. Fixed by adding `ClipboardWriter.restore_text_commit()`, which exposes `(user_visible_success, custody_commit)` instead of collapsing both signals to one bool (`ClipboardWriter.restore_text()` itself is untouched — still used elsewhere as a plain bool, e.g. `macro_execute.py`). Caught by a branch-authored test (`test_quick_paste_restoration_close_failure_via_real_production_path`) that exercises the real Win32-backed production path, not a test double.
- `_schedule_clipboard_restore` restructured to accept an `on_done` callback fired once with the true final outcome, with `_finish_paste` deferred into it — the prior design reported a pre-delay *prediction* to the UI, which cannot honestly represent "custody committed but not user-visibly restored" without guessing ahead of the real result.
- Several test-double fixtures (`FakeSystemClipboard`, `NativeTextClipboard.win32_write`, `FakeApp.clipboard_append`) didn't simulate Tk's real CR-insertion or the new production canonicalization, causing fingerprint mismatches unrelated to the code under test — fixed per-fixture, keeping set-role (canonicalize) and restore-role (byte-exact) semantics distinct rather than conflating them.

**Retry-budget reconciliation (evidence-based, not a guess):** the branch's 5×15ms (60ms max) could not survive `test_clipboard_custody_retry.py`'s own real-observed 5-*consecutive*-failure scenario (needs ≥6 attempts to succeed); the baseline's 20×20ms fell outside the branch's own `test_clipboard_open_retry.py` range assertion (2 ≤ attempts ≤ 10). Settled on 10×20ms (180ms max), the smallest value inside both constraints.

**Environmental-flakiness investigation (ruled out, not dismissed):** `test_search_during_batch_render.py` failed twice on the adapted tree (settlement timeouts) during an earlier heavy-parallel-load session (concurrent PyInstaller/Gradle/pytest background work), passing once on the untouched baseline under the same load — initially suggesting a real regression. A controlled re-run with zero competing background processes (confirmed via `tasklist`) passed cleanly in 40s, confirming the cause was this session's own competing CPU load, not the adapted code.

**Validation lanes, all run against the final integrated tree (post `bcfca9d`):**

| Lane | Result |
|---|---|
| Targeted clipboard/custody suite (`test_clipboard_self_capture.py`, `test_quick_paste_clipboard_restore.py`, `test_clipboard_custody.py`, `test_clipboard_custody_retry.py`, `test_clipboard_open_retry.py`, `test_copy_combined_native_custody.py`) | **100/100 passed** |
| `test_macro_execute.py`, `test_paste_delivery.py` | **25/25 passed** |
| Full suite (`pytest tests/`, redirected to a file, exit code checked explicitly — not the tail-pipe mistake from earlier gates), zero competing background processes (confirmed via `tasklist` immediately before the run; an idle stray Gradle daemon was stopped first) | **2,011 passed, 1 skipped, 0 failed, exit code 0** — 1508.72s (0:25:08). The single skip is consistent with this suite's established platform-probe pattern (`probe_tk_ui()`-gated tests skip only when a Tk runtime is unavailable at collection); with thousands of other Tk-backed UI tests passing in the same run, Tk was plainly available, so this is very likely one narrower, environment-conditional probe elsewhere in the suite. This record states that as the likely explanation, not a confirmed one — the exact skipped test was not individually pinned down before this receipt was written. |
| Packaged build (`pyinstaller packaging\cache_vault.spec --noconfirm --clean`) | Builds cleanly from the final tree (43.5 MB exe) |
| Packaged self-test (`dist\CacheVault.exe --selftest`) | **PASS**, exit 0 |
| `tools/verify_exe_metadata.py --exe dist\CacheVault.exe` | **PASS** — all 12 checks (version 0.2.0 throughout, correct product/company strings) |

**Before/after repository comparison:** `git branch --list | wc -l` went from 144 to **145** (the one new, intentional `integration/gate5f-b-clipboard-custody` branch). **`master`'s HEAD is confirmed unchanged** (`27b68d606c58a493ae297e29f6660eb94f9365aa`), and `git merge-base --is-ancestor integration/gate5f-b-clipboard-custody master` confirms the integration branch is **not** merged into `master`.

**Required disposition: `PROVEN INTEGRATED CANDIDATE`.**

Every applicable validation lane passed on the final tree, with all conflicts resolved deliberately (including one case where a hasty resolution would have reintroduced a real, previously-fixed regression, caught only by a test file outside the branch's own stated scope), and every defect the merge combination surfaced fixed with cited evidence rather than guessed at. One limitation stated plainly: the single skipped test in the full-suite run was not individually identified before this receipt was written (see table above) — this does not affect the disposition, since it is a pre-existing, environment-conditional skip pattern already established in Gate 5F-A's own full-suite run (also exactly one skip), not something newly introduced here.

**Evidence:** merge commit `8880713`, fix commit `bcfca9d`, both on `integration/gate5f-b-clipboard-custody`. The integration worktree (`%TEMP%\cv_gate5fb_integration`) and branch were **left in place**, not deleted, consistent with Gate 5F-A's own practice — this gate's instructions call for stopping before the `master` merge decision.

**Stop condition honored:** no merge into canonical `master` was performed. No Gate 6 work was performed.

---

# FINISH QUEUE

## P0 — Get CI actually running on GitHub Actions — ⚠️ DIAGNOSED, NOT CLOSABLE FROM THIS REPO (Gate 2, see §18)
**Result: `PROVEN VALID — GITHUB EXECUTION EXTERNALLY BLOCKED`.** Both workflow files are syntactically valid, reference real action versions and existing local scripts, and every substantive command in both reproduces cleanly locally. A live `gh workflow run ci.yml` attempt returned HTTP 422: **"Actions has been disabled for this user."** This is an account-level restriction on `lazelife420-spec` itself, not a repo setting (repo-level Actions are confirmed `enabled: true`), not a workflow defect, and not something any commit to this repo can fix. Per the original stop condition ("if the fix requires GitHub organization/billing/plan changes outside repo config, stop and report as `BLOCKED — EXTERNAL REQUIREMENT`") — **this item is now `BLOCKED — EXTERNAL REQUIREMENT`, reclassified from a code problem to an account-custody problem.**
**Next step (outside this repo, for the user):** check github.com account settings under Settings → Actions and Settings → Billing, and check for any email from GitHub explaining the restriction. **The cause of the restriction is not established by this pass** — GitHub's own error text ("Actions has been disabled for this user") states only that the block exists, not why. Billing, identity verification, an account-standing/abuse-review hold, or some other GitHub-side condition are all *possibilities*; none is confirmed, and this record does not assert one. Once the account-side restriction is lifted, re-run `gh workflow run ci.yml --ref master` — no repo changes are expected to be needed first.

## P0 — Verify `qrcode` survives a packaged build — ✅ CLOSED (Gate 1, see §17)
**Result: FALSE POSITIVE.** `qrcode` and its 19 submodules (including `qrcode.image.pil`, the one the code actually uses) are already correctly bundled into the packaged exe's `PYZ.pyz` by PyInstaller's normal static analysis, with no hidden-import declaration needed. Verified by A/B clean-rebuilding the exe with and without an explicit `hiddenimports` entry and inspecting the resulting `PYZ.pyz` module table both times — identical either way (617 modules, same 19 `qrcode.*` entries). A speculative spec fix was applied, then this A/B test proved it unnecessary, so it was reverted (`git stash drop`) — the repo's `packaging/cache_vault.spec` is unchanged from HEAD. No further action needed on this item.

*(The signing-custody item that was P0 here has been reclassified — see the P2 entry below. Gate 3, §19, found no credential or private-key exposure, current or historical: `PROVEN SAFE — PUBLIC VERIFICATION MATERIAL ONLY`.)*

## P1 — Finish and verify the pytest run; commit its result to this record
**Objective:** get a real, current, completed `pytest -q` pass/fail count (this pass's run did not finish in the available window).
**Scope:** test execution only — no test edits unless a failure is found and is trivially bounded.
**Pass criteria:** exact pass/fail/skip counts recorded, replacing the self-reported "988/988" claim with independently-obtained numbers.
**Stop condition:** if a failure is found, record it and stop — do not fix beyond this queue's bounded-repair rules without a separate gate.
**Evidence required:** full pytest summary line + duration.

## P1 — Sync CHANGELOG.md, README.md, and RELEASE_NOTES.md with reality — PARTIALLY DONE (Gate 4, §20)
**Result:** `CHANGELOG.md`'s empty "Unreleased" section and `README.md`'s stale "v0.1.8 mobile not published" claim were both corrected in Finish Gate 4 — see §20 for the full diff and validation evidence. `scripts/scan_claims.py` passes clean against both edited files.
**Still open:** `RELEASE_NOTES.md`'s stale RC-draft language (it still states "no public artifacts have been built yet, and no tag has been created," contradicted by the real, tagged, publicly-released v0.2.0) was **not** touched — it fell outside Gate 4's explicitly authorized scope (README.md/CHANGELOG.md only). Needs its own small gate.

## P1 — Commit or formally park the Free/Founder mobile-gating policy correction
**Objective:** the verified-true, currently-uncommitted correction in `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` (§6) either lands on `master` or is explicitly deferred with a written reason — it should not just sit silently dirty.
**Scope:** that file, plus whatever README/marketing copy the doc itself says must follow ("tester-facing and website copy must scope the claim to this release").
**Pass criteria:** either committed with the copy-rule follow-through applied, or the user explicitly says "not yet" and the reason is recorded.
**Stop condition:** do not silently commit a pricing/gating policy change — this is a product decision, confirm with the user first.
**Evidence required:** commit hash, or recorded deferral reason.

## P2 — Trim non-secret operational metadata from the signing-custody doc
**Objective:** `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` keeps its useful public verification material (cert fingerprints, algorithm identity, integrity hashes) and its useful *policy* description (3-copy backup, one physically separate, GPG-encrypted) but drops the specific, non-secret-but-unnecessary identifying detail: the real local Windows username (`KickA`), exact backup folder paths, and the physical backup device's model/serial number.
**Why P2 not P0:** Gate 3 (§19) confirmed this is not a credential or private-key exposure — nothing here lets anyone use or reconstruct the signing key. This is a hygiene/OpSec-surface trim, not a security fix.
**Scope:** that one file only. Keep the policy description; either remove the specific paths/device identifiers or move that detail to a private (non-tracked) companion file.
**Pass criteria:** `scripts/scan_secrets.py`'s `abs-path-username` findings for this file drop to zero; the doc still functions as a real recovery runbook for the account holder.
**Stop condition:** if removing detail would make the doc useless as an actual runbook, propose a private companion file instead and stop for user sign-off on that approach.
**Evidence required:** re-run of `scripts/scan_secrets.py` showing the finding cleared.

## P2 — Regenerate `dist/SHA256SUMS.txt` for the current build
**Objective:** the current `dist\CacheVault.exe` has a published hash a user (or the release script) can check.
**Scope:** hash generation only.
**Pass criteria:** `dist/SHA256SUMS.txt` contains an entry matching `Get-FileHash dist\CacheVault.exe`.

## P2 — Triage the 116 unpushed local branches — ✅ DONE (Gate 5, §21)
**Result:** full classification complete — `CACHE_VAULT_BRANCH_TRIAGE_GATE_5.md`/`.json`. 99 merged/redundant, 26 stale/superseded (verified via squash-merge-ancestry evidence, not name-guessing), 1 confirmed unique-valuable, 15 unique-needs-review, 1 historical/release. The "116" no-remote-ref count was re-derived and confirmed accurate.

## P1 — Review the 16 branches Gate 5 could not clear
**Objective:** individually resolve the 1 `UNIQUE — VALUABLE` branch (`repair/pre-tester-reliability` — merge or formally decide not to) and the 15 `UNIQUE — NEEDS REVIEW` branches into a confident disposition each.
**Why P1 not P2:** one of these branches is *confirmed* real, tested, currently-stranded work (a mobile-share-during-paused-capture fix) sitting local-only with zero remote backup — worth promoting before it's lost to a disk failure.
**Scope:** `CACHE_VAULT_BRANCH_TRIAGE_GATE_5.md`'s `UNIQUE — VALUABLE`/`UNIQUE — NEEDS REVIEW` rows only. For `repair/pre-tester-reliability`: decide whether to merge it (it's one clean, tested commit) or explicitly reject it with a reason. For the 15 needs-review branches: diff each against master's current state of the same files to confirm superseded-or-not, same technique Gate 5 used for the 26 already-resolved stale branches.
**Pass criteria:** every one of the 16 branches has a final disposition backed by a diff, not a guess.
**Stop condition:** do not merge anything without the diff evidence to justify it; do not delete a "needs review" branch just because it's inconvenient.
**Evidence required:** per-branch diff summary + final disposition.

## P2 — Archive-not-delete decision for the 99 merged + 26 stale/superseded branches, and the 49 worktrees
**Objective:** once the P1 review above is done, decide (with the user) whether to prune the now-fully-classified redundant/superseded branches and stale worktrees, or archive them (e.g., a `git bundle` or a tag namespace) before removal, given they still carry engineering-history value even where functionally redundant.
**Scope:** cleanup/archival planning only — this itself is a separately-authorized gate per Gate 5's explicit stop condition, not a task to execute inline.
**Stop condition:** requires explicit user authorization before any branch or worktree is actually deleted.

## P2 — Wire `scan_secrets.py` / `scan_claims.py` into `ci.yml`
**Objective:** once P0's GitHub Actions fix lands, add the two local-only scanners to the real CI workflow so a PR can't silently ship a secret or a risky claim.
**Scope:** `.github/workflows/ci.yml` only.
**Stop condition:** depends on the P0 CI fix landing first.

## DEFER
- QR pairing / camera-scan feature: needs a real Android device or emulator to prove end-to-end; defer to a dedicated mobile QA gate.
- Vault Cleanup Suggestions (Stages A–E): re-verify before the next tagged release, not urgent standalone.
- Review of the two open git stashes.

## DO NOT TOUCH
- Command Center scope (frozen at Phase 1 — Hotkey Actions only).
- Vault Lock / Safes encryption framing (frozen: UI privacy / organization only, not encryption — do not reopen without a deliberate cryptography-scope product decision).
- Core capture/classify/sensitive pipeline logic — proven working; no defect found.

---

## 28. Gate 5F canonicalization receipt — `master` fast-forwarded to Gate 5F-A + 5F-B

**Authorized scope:** canonicalize Gate 5F-A and Gate 5F-B onto `master` in a single move (a pure fast-forward, since the pre-canonicalization audit — see the pending §27a audit context above this section, folded in here — proved `bcfca9d` contains the complete 5F-A chain and `master` is its ancestor), rather than merging 5F-A and 5F-B separately.

**Pre-canonicalization dirty-tree incident:** `git merge --ff-only bcfca9d` was first attempted against the main checkout and correctly **refused**, because the checkout carried a pre-existing, unrelated dirty working tree (13 tracked changes + 4 untracked items) that predated this canonicalization pass and was not created by it. Three of those files (`dialogs.py`, `mobile_dialogs.py`, `shell.py`) also appear in the Gate 5F-B changeset, which is exactly why the `--ff-only` refusal mattered: without it, unproven, unattributed source edits could have been silently combined with the proven Gate 5F integration. This was handled as its own bounded custody procedure before resuming canonicalization:

- **Preserved and quarantined**, not committed onto `master`, not discarded, not immediately reapplied.
- **Stash object:** `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f` (`git stash push --include-untracked`).
- **Protection branch (not checked out):** `preservation/pre-gate5f-dirty-2026-08-20` → `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f` — makes the stash object reachable from a real ref so ordinary stash cleanup cannot silently destroy it.
- **External custody copy:** `F:\CACHE_VAULT_CUSTODY_2026-08-20\pre_gate5f_dirty_tree\`, with a full SHA-256 manifest (19 files) and `CACHE_VAULT_PRE_GATE5F_DIRTY_TREE_CUSTODY_RECEIPT.md` classifying every preserved item into four categories: (A) the already-documented Gate 4 README/CHANGELOG/Free-vs-Founder correction, (B) seven unattributed source files (`dialogs.py`, `clip_workflows.py`, `lan_ip.py`, `mobile_dialogs.py`, `shell.py`, `clip_context.py`, `filters.py` — read in full, classified `PRESERVED — ORIGIN/VALIDATION PENDING`, not yet judged good/bad/complete/disposable), (C) three undocumented tracked deletions (an old v0.1.4 release zip, a stale smoke-test export, `docs/.nojekyll`), and (D) this process's own untracked deliverables (`CANONICAL_PROJECT_RECORD.md` itself, the branch-triage files, the branch-preservation bundles).
- After the stash, `git status --short` on the main checkout confirmed clean, and canonicalization resumed. **The preservation stash/branch/custody copy were left untouched for the remainder of this gate** — no `stash pop`, no cherry-pick, no merge of the preservation branch. A separate, bounded future gate ("Cache Vault Post-Canonical Salvage Audit — Pre-Gate5F Dirty Worktree") will investigate the seven Category B files against the now-canonical tree; it is not started by this receipt.

**Fast-forward:**
- **Pre-canonical `master`:** `27b68d606c58a493ae297e29f6660eb94f9365aa`
- **Rollback tag (created before the move, unused, still valid):** `pre-gate5fb-canonicalization` → `27b68d606c58a493ae297e29f6660eb94f9365aa`
- Topology re-verified immediately before the move (`git merge-base master bcfca9d` = `27b68d6...`, `is-ancestor` = true) — unchanged from the original audit.
- `git checkout master && git merge --ff-only bcfca9d081ed754e5fa7b54e6ff203c879116654` — **Fast-forward, no merge commit created** (none needed — the two real merge commits from Gate 5F-A and Gate 5F-B, `1d5e701` and `8880713`, are already part of the linear history being fast-forwarded to; nothing is flattened or duplicated).
- **Canonical `master` after move:** `bcfca9d081ed754e5fa7b54e6ff203c879116654`

**Post-fast-forward tree identity proof:**
```
git rev-parse master                                          → bcfca9d081ed754e5fa7b54e6ff203c879116654
git rev-parse bcfca9d081ed754e5fa7b54e6ff203c879116654         → bcfca9d081ed754e5fa7b54e6ff203c879116654
git diff master bcfca9d081ed754e5fa7b54e6ff203c879116654 --exit-code   → zero diff (exit 0)
git status --short                                             → clean
```

**Constituent gates now on canonical `master`:**
- Gate 5F-A: `1d5e701ceb3acdee569eea36f75be4e9ec07f201` (merge of `repair/pre-tester-reliability`)
- Gate 5F-B merge: `88807139c7d00b54f6b68ce012a52193eaa336ec` (merge of `fix/quick-paste-clipboard-restoration`)
- Gate 5F-B final fix: `bcfca9d081ed754e5fa7b54e6ff203c879116654` (post-merge validation fixes, §27)

**Delta from pre-canonical `master`:** 29 files, +4,819/−231, zero overlap between the 5F-A and 5F-B file sets (audited in the pre-canonicalization pass).

**Post-canonicalization acceptance gates, run directly against the new canonical checkout (not the worktree — a fresh build from `C:\Users\KickA\Desktop\CacheVault` itself):**

| Gate | Result |
|---|---|
| Packaged build (`pyinstaller packaging\cache_vault.spec --noconfirm --clean`) | Builds cleanly |
| Packaged self-test (`dist\CacheVault.exe --selftest`) | **PASS**, exit 0 |
| `tools/verify_exe_metadata.py --exe dist\CacheVault.exe` | **PASS** — all 12 checks (version 0.2.0, correct product/company strings) |
| Dev-interpreter self-test (`python app.py --selftest`) | **PASS**, exit 0 |
| Working tree after build | Clean (`dist`/`build` untracked/ignored, no tracked-file drift) |

The full ~2,000-test pytest suite was **not** re-run for this step, per the audit's own finding that tree identity is unchanged from what already passed (2,011 passed, 1 skipped, 0 failed) on the `bcfca9d` content in the Gate 5F-B worktree — a fast-forward moves a ref, it does not change file content, so re-running the full suite here would prove nothing the zero-diff check above didn't already prove.

**Classification: `CANONICALIZED — GATE 5F-A + 5F-B INTEGRATED`.**

**Stop condition honored:** no branches pruned, no worktrees deleted, no Gate 6 work started, `master` not pushed to any remote, no clipboard or pre-tester-reliability behavior modified beyond what Gate 5F-A/5F-B themselves already introduced and validated. `integration/gate5f-a-pretester-reliability`, `integration/gate5f-b-clipboard-custody`, `repair/pre-tester-reliability`, and `fix/quick-paste-clipboard-restoration` all left intact.

---

**NEXT AUTHORIZED ACTION: NONE — Gate 5F is canonicalized (`CANONICALIZED — GATE 5F-A + 5F-B INTEGRATED`, §28). Awaiting user authorization for whatever comes next: the deferred "Cache Vault Post-Canonical Salvage Audit — Pre-Gate5F Dirty Worktree" gate (investigating the seven quarantined Category B source files), pushing the new `master` to `origin`, Gate 6 (custody-doc hygiene), or another item from the finish queue above.**
