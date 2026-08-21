# Cache Vault — Release Closure Gate R2 Receipt: Version Identity Reconciliation

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT PROOF FOUNDRY
**Disposition:** Identity reconciled. Not built. Not published. Not canonicalized.

## Baseline SHA

`806d199a07e469ef294da1b7e9d0be0032fe0072` (canonical `master` — R2 branched fresh from here, not from R1's evidence branch, per instruction)

## Branch / rollback tag

- Branch: `release/closure-r2`
- Rollback tag: `pre-release-closure-r2-2026-08-21` → `806d199a07e469ef294da1b7e9d0be0032fe0072`

## Decision reconciled

**Desktop release identity: `v0.2.1`.** Set in `pyproject.toml` and `cache_vault/__init__.py`.

## Android disposition

- Tracked source (`android/app/build.gradle.kts`, canonical `master`): already declares `versionName "0.2.1"` / `versionCode 8` — left unchanged, nothing to reconcile.
- Confirmed protocol-compatible with current desktop (`PROTOCOL_VERSION = 1` matches `MOBILE_PROTOCOL_MIN/MAX = 1`; clears `MINIMUM_MOBILE_VERSION = "0.1.0"` floor).
- The only existing `CacheVault-Mobile-v0.2.1-android.apk` (in an abandoned worktree) is **declared non-authoritative** — its own git history is an ancestor of, not a divergence from, canonical `master` (dated 2026-06-27), and its provenance doesn't trace to any coherent commit.
- **A real `0.2.1` Android artifact does not yet exist and must be built from canonical source** — determined, not performed, in this gate.

## Files changed

`pyproject.toml`, `cache_vault/__init__.py`, `README.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `docs/releases/v0.2.0.md` (new). Full rationale for each in `CACHE_VAULT_RELEASE_CLOSURE_R2_AUDIT.md`. No test files, no other production source, no Android source touched.

## `docs/releases/v0.2.0.md` — created

The missing historical receipt for the actual `v0.2.0` release, closing the gap R1 found. Built entirely from evidence independently re-verified this gate via `gh release view v0.2.0` and `gh api` (asset SHA-256 digests, release body content) — no claim in it exceeds what the live GitHub Release itself already states.

## Website / download authoritative source

**Recommendation only, not executed:** `docs/index.html` (GitHub Pages, custom domain `theprooffoundry.com`) should be the authoritative source, because it is the only one of the three conflicting surfaces R1 found that is actually tracked in this repository. The Cloudflare Pages deployment's source could not be located anywhere in the repo. This needs the project owner's acceptance before any actual website change is made — no website content was touched in this gate.

## Validation

| Check | Command | Result |
|---|---|---|
| Version consistency | `tomllib` + `import cache_vault` | `pyproject.toml` and `cache_vault.__version__` both `0.2.1` |
| Whitespace | `git diff --check` | Clean |
| Sanity (no production behavior touched, checked anyway) | `python app.py --selftest` | PASS |
| Claims scanner | `python scripts/scan_claims.py` | Zero new findings in any file this gate edited |

## Production source confirmation

`cache_vault/__init__.py` was touched (version string only — one line). No other Python source, no Android/Kotlin source, no test files were modified. `git diff --stat` against `cache_vault/core/`, `cache_vault/ui/`, and `android/` (excluding `__init__.py`) is empty.

## Known limitations / deferred

- `cache_vault/core/mobile/compatibility.py`'s comment referencing a stale "0.2.0 as of this writing" was **noted, not fixed** — comment-only, zero behavior impact, but out of R2's authorized scope (production source file). Candidate for a small bounded follow-up.
- Android rebuild not performed — belongs to resumed Release Closure Phase 2/5.
- Website authoritative-source decision not executed — recommendation only, awaiting project-owner acceptance.

## Candidate SHA

Recorded in the final report below. Committed on `release/closure-r2`, branched from canonical `806d199...`. Not merged, not fast-forwarded to `master`, not pushed.

## Custody confirmation

- Working tree scoped to exactly the 6 files listed above.
- All prior rollback tags (E1–E4a, Gate A, Gate B, R1) remain untouched.
- `preservation/pre-gate5f-dirty-2026-08-20` not touched.
- `master` remains exactly `806d199a07e469ef294da1b7e9d0be0032fe0072`.
