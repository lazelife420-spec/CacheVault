# Cache Vault v0.2.3-rc2 — Version / Release-Candidate 2 Identity Gate Report

**Date:** 2026-09-14  
**Parent Commit:** `fa29cd618ea8ba7931986c414747a1792145bdb0`  
**Identity Bump:** `v0.2.3-rc1` → `v0.2.3-rc2`  

---

## 1. Version Surfaces Reconciled

| Surface | Before | After | Notes |
|---|---|---|---|
| `pyproject.toml` | `"0.2.3-rc1"` | `"0.2.3-rc2"` | Package version |
| `cache_vault/__init__.py` | `__version__ = "0.2.3-rc1"` | `__version__ = "0.2.3-rc2"` | Feeds PyInstaller metadata |
| `CHANGELOG.md` | `v0.2.3-rc1` top | `v0.2.3-rc2` header added | Documents SettingsHub first-paint repair |
| `RELEASE_NOTES.md` | `v0.2.3-rc1` top | `v0.2.3-rc2` header added | Release candidate 2 identity |
| `android/app/build.gradle.kts` | `versionName "0.2.1"` | **untouched** | Held/unpublished companion, separate cadence |

---

## 2. Commit Binding

This identity bump is committed on top of `fa29cd618ea8ba7931986c414747a1792145bdb0` as a new explicit commit.
Parent commit is strictly `fa29cd618ea8ba7931986c414747a1792145bdb0`.
