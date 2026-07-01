# Cache Vault v0.1.5-rc4 — Local EXE QA (Pre-R2)

**Date:** 2026-07-01
**Version:** 0.1.5-rc4 (Release Candidate, local diagnostic build — not published, not uploaded to R2)

## Source

- **Verification branch:** `verify/v0.1.5-rc4-ui-consistency`
- **Source commit (pre-bump):** `30b9a3c` — matches `origin/rc/v0.1.5-rc4-ui-consistency`
- **Version-bump commit:** `83c30d6` — `chore: bump Cache Vault to v0.1.5-rc4`
  - `cache_vault/__init__.py`: `__version__` 0.1.5-rc3 → 0.1.5-rc4
  - `pyproject.toml`: `version` 0.1.5-rc3 → 0.1.5-rc4
  - `tools/check_exe_version.py`: added `0.1.5-rc4` to the checked version list

## Gates (re-run after version bump)

| Gate | Result |
|---|---|
| `pytest -p no:xonsh` | **PASS** — 802 passed, 0 skipped |
| `python -m compileall cache_vault` | **PASS** — no syntax errors |
| `python app.py --selftest` | **PASS** — `selftest OK — core capture/classify/sensitive/image/mobile pipeline works` |

## Local EXE build

- **Build command:** `pyinstaller packaging\cache_vault.spec --noconfirm --clean`
- **Output:** `dist\CacheVault.exe`
- **Size:** 29,063,758 bytes
- **SHA256:** `f9b46c534a33091f6b72f4ba8ae196faeba2c8a6c3bb28e03f197a9ae816357b`
- **Version check (`tools/check_exe_version.py`):** `0.1.5-rc4 found as UTF-16LE at index: 315880`; no rc3/rc2/rc1/0.1.4/0.1.3 strings present
- **EXE `--selftest` exit code:** `0` (`selftest OK — core capture/classify/sensitive/image/mobile pipeline works`)
- **Working tree:** clean except gitignored `dist/`, `build/` artifacts

## Manual QA checklist (pending — human verification required)

This build has **not** been manually exercised in the GUI. The checklist below is
prepared for that pass; none of it should be treated as verified until a human
runs through it against `dist\CacheVault.exe`.

| # | Check | Result |
|---|---|---|
| 1 | All Clips mixed selection works: text + screenshot + link | ☐ PENDING |
| 2 | Screenshots/Images multi-select works | ☐ PENDING |
| 3 | Filtered search selection works | ☐ PENDING |
| 4 | Export screenshots from mixed selection writes only image files | ☐ PENDING |
| 5 | Export ZIP works with mixed selected items | ☐ PENDING |
| 6 | Copy Paths appears/works only when valid paths exist | ☐ PENDING |
| 7 | Text/link copy works from mixed selection | ☐ PENDING |
| 8 | Metadata shows local desktop time and origin consistently | ☐ PENDING |
| 9 | Screenshot cards show image/source context | ☐ PENDING |
| 10 | Main window resizes correctly | ☐ PENDING |
| 11 | Settings opens in front | ☐ PENDING |
| 12 | No crash during screenshot/photo flow | ☐ PENDING |
| 13 | `crash.log` and `crash_native.log` stay clean | ☐ PENDING |

## Verdict

**NOT YET VERIFIED.** Source is green, gates pass, EXE builds and reports the
correct version/selftest result. Manual GUI QA against `dist\CacheVault.exe`
is required before any R2 upload, `/proof` update, or `stable` designation.
