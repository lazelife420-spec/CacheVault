# Cache Vault — Gate A Documentation Recovery Receipt

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT
**Scope:** documentation truth only — no production source, no MobileBridge race fix, no E1–E4a reopen.

## Canonical starting SHA

The gate prompt specified `master` must begin exactly at:

```
45aac5f7c7a3d31187d27bbefc8f7efc491ae497
```

**Phase 0 found this true for HEAD, but the working tree was not clean** — 9 untracked process-record files sat on disk (the post-salvage release-readiness audit, `CANONICAL_PROJECT_RECORD.md`, and the E1–E4a salvage receipts), never committed to any branch. Surfaced to the user; they chose to commit these files first as pre-Gate-A housekeeping (no content authored by this gate — files taken as-is).

- Pre-housekeeping canonical: `45aac5f7c7a3d31187d27bbefc8f7efc491ae497`
- **Post-housekeeping effective baseline (new `master` HEAD): `921c5992f92869c35b41aa0fccfb94d1806e9511`**
- E1–E4a rollback tags confirmed intact: `pre-salvage-e1-filter-nav`, `pre-salvage-e2-dialog-teardown`, `pre-salvage-e3-annotation-import`, `pre-salvage-e4a-lan-ip`
- Gate A rollback tag created: `pre-gate-a-documentation-recovery-2026-08-21` (points at `921c599`)
- Dedicated branch: `docs/gate-a-documentation-recovery`

## Preservation source inspected

`preservation/pre-gate5f-dirty-2026-08-20` (`4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`) — read-only. Diffed against its merge-base with the original canonical tip (`27b68d606c58a493ae297e29f6660eb94f9365aa`) to isolate exactly what Gate 4 had drafted but never committed. **Not touched, not merged.** Confirmed unchanged after this gate: still `4f5b348...`.

Also cross-referenced `CANONICAL_PROJECT_RECORD.md` §20 ("Finish Gate 4 receipt"), whose own claim-by-claim table and recorded blob hashes (`README.md` `e026209→1e3884d`, `CHANGELOG.md` `2f86669→3b0d19a`) matched the preservation-branch diff exactly — high-confidence corroboration that the recovered text is what Gate 4 actually verified, even though it never landed.

## Exact files changed

| File | Classification | Recovered vs. re-derived |
|---|---|---|
| `README.md` | VERIFIED CURRENT | Recovered as-is from preservation diff; matches `CANONICAL_PROJECT_RECORD.md` §20's claim table exactly |
| `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` | VERIFIED CURRENT | Recovered as-is; independently re-confirmed no `is_feature_enabled`/`_require_founder`/`is_founder_unlocked` gate exists anywhere in `cache_vault/core/mobile/` or `cache_vault/core/vault.py` |
| `CHANGELOG.md` | VERIFIED CURRENT, RE-DERIVED for updated scope | Preservation diff only had `## Unreleased` empty→populated as a stub in the merge-base; the actual curated text came from `CANONICAL_PROJECT_RECORD.md`'s recorded description of what Gate 4 wrote. Re-derived: commit count updated 68→85, date range extended through 2026-08-21, and the four E1–E4a salvage fixes (filter-nav crash, dialog-teardown race, annotation/import correctness, LAN-IP tie-break) added — none of these existed when the original 68-commit draft was written |
| `RELEASE_NOTES.md` | NOT SUPPORTED (recovery) → RE-DERIVED from scratch | Never touched in the preservation branch at all. Only the flatly-contradicted top blockquote ("no public artifacts have been built yet, and no tag has been created") was corrected, independently re-verified via `gh release view v0.2.0` (live release, 3 assets: APK, Windows zip, `SHA256SUMS.txt`) |
| `CANONICAL_PROJECT_RECORD.md` | Corrected false DONE state | Annotated every place the record claimed Gate 4's doc fixes were `FIXED`/`DONE` when they were never actually committed (§7 items 3–4, §9 item 3–4, §12, §20 header, §1 cross-reference). Historical narrative preserved, not rewritten — correction notes added, dated and pointing at this receipt |

## Stale claims removed

- README.md: `v0.1.8`-pinned section header; "mobile LAN bridge (developer mode)"; "published mobile app... no Android/iOS client app is published yet"; "Mobile LAN Bridge (Developer Mode)" section title; "No mobile app is published yet."
- CHANGELOG.md: `_No unreleased changes yet._` while 85 real commits sat on `master`.
- docs/CACHE_VAULT_FREE_VS_FOUNDER.md: `Mobile bridge | No | No | Not claimed | Do not ship in this SKU` — contradicted by source (ungated).
- RELEASE_NOTES.md: "no public artifacts have been built yet, and no tag has been created" — flatly contradicted by a live, tagged, 3-asset GitHub Release.
- CANONICAL_PROJECT_RECORD.md: false `FIXED in Gate 4` / `DONE — Gate 4` claims across §7, §9, §12, §20.

## Current claims restored / re-derived

- README honest-scope section retitled to reflect current version (v0.2.0) and accurately describes the mobile companion as production-signed and publicly distributed (GitHub Releases, not Play Store; no iOS client).
- CHANGELOG "Unreleased" now itemizes the real 85-commit gap, including the E1–E4a salvage work.
- Free/Founder doc restores the dated 2026-08-14 policy-correction note: mobile bridge is ungated/free for the 0.2.1 external-test release, explicitly scoped as non-permanent policy.
- RELEASE_NOTES.md now states the true, verified release-artifact facts for v0.2.0.

## Version corrections

- No version number itself was ambiguous: `pyproject.toml` and `cache_vault/__init__.py` both read `0.2.0`; Android is independently versioned `versionCode 8` / `versionName 0.2.1` (confirmed pre-existing, not touched or re-asserted as new).
- Commit-gap count corrected from the stale recovered draft's `68` to the current, re-counted `85` (`git log v0.2.0..HEAD --oneline | wc -l`), date range extended from `2026-07-16 → 2026-08-13` to `2026-07-16 → 2026-08-21`.

## Unsupported claims rejected / not attempted

- Did **not** touch the trailing Trust/Verification/Artifacts section at the bottom of `RELEASE_NOTES.md`, which still cites v0.1.6-era numbers (803 pytest, `CacheVault-v0.1.6-windows.zip`). This is real staleness but lower-confidence to fix within this bounded pass (would require re-verifying current pytest count, GH Actions matrix, and artifact naming for v0.2.0) — flagged in `CANONICAL_PROJECT_RECORD.md` as still open, not silently dropped.
- Did **not** re-measure the CHANGELOG's "593 ms → 220 ms" render-latency claim; kept the number (real, corroborated by row-pooling/viewport-batching work existing in the record and in branch history) but the CHANGELOG entry now explicitly discloses it is "not independently re-measured outside development," matching the audit's own hedge on this exact figure rather than presenting it as fully audited fact.
- Did **not** invent any future roadmap claims, did not touch Command Center framing, did not alter core clipboard/storage behavior claims (left as previously verified).

## Candidate commit

- Parent: `921c5992f92869c35b41aa0fccfb94d1806e9511` (post-housekeeping baseline)
- Candidate: `ecaa4d116d10f188f6cbdf294069a3cb75717c13` on branch `docs/gate-a-documentation-recovery`
- 5 files changed, 137 insertions(+), 19 deletions(-)

## Validation results

| Check | Result |
|---|---|
| `git status --porcelain` after commit | Clean |
| `git diff --check` (whitespace) | Clean |
| Grep for known stale strings (`v0.1.8`, `No unreleased changes yet`, the old RELEASE_NOTES blockquote, the old Free/Founder mobile-bridge row) | All gone from live content (one hit remains, inside the Free/Founder doc's own "Correction" section, intentionally quoting the old text for context) |
| `python scripts/scan_claims.py` | 10 findings — **all pre-existing, none in the 4 files this gate edited** except `RELEASE_NOTES.md:4` ("No cloud" intro line, pre-existing, untouched by this gate's edit at lines 7–10) |
| `python scripts/scan_secrets.py` | 13 findings — **all pre-existing**, none inside `README.md`, `CHANGELOG.md`, or `docs/CACHE_VAULT_FREE_VS_FOUNDER.md`; `CANONICAL_PROJECT_RECORD.md` hits are all at pre-existing lines this gate did not add |
| Production source (`cache_vault/`, `android/`) diff | Empty — confirmed untouched |
| `preservation/pre-gate5f-dirty-2026-08-20` | Unchanged: `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f` |
| E1–E4a rollback tags | All 4 present and unchanged |

## Rollback state

- `pre-gate-a-documentation-recovery-2026-08-21` tags the pre-Gate-A baseline (`921c599`).
- Housekeeping commit (`921c599`) is a separate, earlier commit directly on `master` — if it needs to be rolled back independently, `git reset --hard 45aac5f7c7a3d31187d27bbefc8f7efc491ae497` returns to the original pre-audit-file canonical.
- Gate A's own commit (`ecaa4d1`) lives only on `docs/gate-a-documentation-recovery`; `master` has not been advanced past `921c599`.

## Production source confirmation

**Confirmed: zero production Python or Android source files were touched in this gate.** `git diff --stat` against `cache_vault/` and `android/` is empty for both the housekeeping commit and the Gate A commit.

## Fast-forward eligibility

`git merge-base --is-ancestor master docs/gate-a-documentation-recovery` → **YES**. `docs/gate-a-documentation-recovery` is a single commit directly ahead of current `master` (`921c599`) — canonicalization can be a pure fast-forward merge, no rebase needed.

**Not pushed. Not merged. Not fast-forwarded to `master`.** Awaiting separate authorization.
