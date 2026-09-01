# Cache Vault v0.2.3-rc1 — Version / Release-Candidate Identity Gate Report

**This is an identity/version gate.** The window-geometry tranche itself is already
proven (full product-tier Reality Gate 2090 passed / 0 failed / 1 skipped, receipt
`20260901-154943-product-662c5df`, verdict hash verified). This pass marks the
candidate identity the official artifact must carry, ahead of the canonical
build/proof gate. No tag, no GitHub Release, no publication, no Proof Foundry update.

---

## 1. Worktree path
`%USERPROFILE%\Projects\Active\CACHEVAULT_POST_V022` (absolute local path redacted —
username must not appear in committed text; see `scripts/scan_secrets.py` [abs-path-username] rule)

## 2. Branch and HEAD before changes
```text
Branch: codex/cache-vault-post-v0.2.2
HEAD:   662c5df2afa84923cd7aabb11bfcc828590c25a0   (= origin/codex/cache-vault-post-v0.2.2, push verified by owner + ls-remote)
Tree:   92d807421968898eab50bf04be10025148228339
```
This HEAD is the exact source proven by the product-tier run above.

## 3. Files changed (identity marking)
```text
 pyproject.toml                                   |  2 +-
 cache_vault/__init__.py                          |  2 +-
 README.md                                        |  2 +-
 CHANGELOG.md                                     | 40 +++++++++++++++
 RELEASE_NOTES.md                                 | 14 +++++++++
 CACHE_VAULT_v0.2.3rc1_VERSION_IDENTITY_GATE_REPORT_2026-09-01.md | new
```

## 4. Version surfaces

| Surface | Before | After | Notes |
|---|---|---|---|
| `pyproject.toml` | `version = "0.2.2"` | `"0.2.3-rc1"` | Package version, single source of truth alongside `__init__.py` |
| `cache_vault/__init__.py` | `__version__ = "0.2.2"` | `"0.2.3-rc1"` | Feeds PyInstaller FileVersion/ProductVersion via `build_meta.py`; `windows_version_tuple()` strips the `-rc1` suffix for the numeric quadruple `(0, 2, 3, 0)` |
| `cache_vault/__init__.py` | `__release_label__ = "Release Candidate"` | unchanged | Already accurate for a candidate (v0.2.2 never flipped it back); in-app claim stays truthful |
| `CHANGELOG.md` | top entry `v0.2.2` | new `v0.2.3-rc1` section above | House convention: own header; v0.2.2 entry preserved as history |
| `README.md` | "Honest scope & limitations (current, v0.2.2)" | "(current, v0.2.3-rc1)" | Cosmetic heading label |
| `RELEASE_NOTES.md` | top section `v0.2.2` | new `v0.2.3-rc1` section above | Explicitly names proven-not-published status |
| `packaging/cache_vault.spec`, `cache_vault/build_meta.py` | no literal version | unchanged | Read `__version__` at build time (confirmed) |
| `tests/test_build_meta.py`, `tests/test_module_registry.py` | relative assertions | unchanged | Assert `pyproject_version == __version__` — pass automatically |
| Android (`android/app/build.gradle.kts`) | `versionName "0.2.1"` / `versionCode 8` | **untouched** | Independently versioned companion, separate cadence (CANONICAL_PROJECT_RECORD precedent); this tranche changed no Android code |

## 5. Canonical gate binding
The canonical gate (`scripts/ci_local_full.ps1`) is run immediately after this identity
commit; its version-truth check requires the built exe to embed the pyproject version,
so the official artifact must be built fresh from this identity — a pre-bump build can
never pass as the candidate.

## 6. Explicitly not done in this pass
No build, no artifact hash (canonical gate output only), no tag, no GitHub Release,
no publication, no signing, no deploy, no launch of the windowed app, no touch of real
vault data, no Android version change.
