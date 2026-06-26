# Post-PR34 Package Proof

**Date:** 2026-06-26  
**Time:** ~20:58 UTC  
**Branch:** `build/post-pr34-package-proof`  
**Base commit:** `1fa49be` — master after PR #33, #34, #35, #36

---

## Commits included in this proof

| PR | Commit | Title |
|---|---|---|
| #33 | (merged to master) | safety / Command Center / CI hardening |
| #34 | `6459928` | multi-select completion |
| #35 | `0a45aa9` | public launch surface audit + fix public download path |
| #36 | `1fa49be` | ci: harden Tk headless skip guards for windows-2025-vs2026 runner |

---

## Commands run

```powershell
python -m pytest -p no:xonsh
python -m compileall cache_vault tests app.py
python app.py --selftest
pwsh scripts/ci_local_full.ps1
pwsh scripts/founder_package_smoke.ps1
```

---

## Results

| Check | Result |
|---|---|
| `pytest -p no:xonsh` | **545 passed** (0 failed, 0 skipped) |
| `compileall cache_vault tests app.py` | **PASS** (no errors) |
| `app.py --selftest` | **PASS** — `selftest OK — core capture/classify/sensitive/image/mobile pipeline works` |
| Local CI — full pytest | **PASS** — `545 passed, 2 warnings in 42.93s` |
| Local CI — founder-critical | **PASS** — `29 passed` |
| Local CI — command-center | **PASS** — `42 passed` |
| Local CI — quick-paste | **PASS** — `10 passed` |
| Local CI — receipts-export | **PASS** — `59 passed` |
| Local CI — compileall | **PASS** |
| Local CI — selftest | **PASS** |
| Local CI — smokes (command_center_runtime_proof) | **PASS** — `20/20 checks passed` |
| Local CI — secret scan | **PASS** — No secrets or privacy leaks detected |
| Local CI — claim tripwire | **PASS** — No risky public claims detected |
| Local CI — packaging (fresh build) | **PASS** |
| Founder package smoke | **PASS** — All 4 automated packaged smoke checks passed |

**CACHE VAULT LOCAL CI: PASS**  
**Known skips: 0**

---

## Build artifact

| Item | Value |
|---|---|
| Build command | `pwsh packaging/build_exe.ps1` (invoked by `ci_local_full.ps1`) |
| Fresh exe path | `dist\CacheVault.exe` |
| Fresh exe size | 41.1 MB (43,085,049 bytes) |
| Fresh exe SHA256 | `64673D4C79F1218F204D447EE4D61072D44CC6D12E14201045E9075B82A18B46` |
| Build timestamp (UTC) | 2026-06-26 20:57:49 |

---

## Comparison to previous released artifact

| Item | Previous release (v0.1.3-founder-mvp.2) | This build |
|---|---|---|
| File | `dist/release/v0.1.3-founder-mvp.2/CacheVault-v0.1.3-founder-mvp.2-windows.zip` | `dist/CacheVault.exe` (unzipped) |
| SHA256 (ZIP) | `CC59BB437461D0FC7CF60E1D912D7B0B202212D9A010F418269418F2039E0D49` | N/A (raw exe, not zipped) |
| SHA256 (exe) | `47F2B324A5151B4D4FF29F209EDAA0788EEA6D5FC4071DBB04DC613009340611` (from RELEASE_NOTES.md) | `64673D4C79F1218F204D447EE4D61072D44CC6D12E14201045E9075B82A18B46` |
| Artifact newer than previous? | — | **Yes** — built 2026-06-26 20:57:49 UTC, after PR #34–#36 merges |

The SHA256 differs from the previously released artifact. This is expected: the build incorporates commits from PR #34 (multi-select), PR #35 (docs/download fix), and PR #36 (CI stabilization — test-only changes). The CI stabilization and download-URL changes do not affect runtime behavior, but PyInstaller produces a deterministically different binary when any included source file changes.

---

## Founder smoke detail

```
PASS  Fresh launch / free selftest
PASS  Invalid license rejected
PASS  Production test Founder license accepted
PASS  Proof receipt export (no clipboard leak)
All automated packaged smoke checks passed.
```

---

## git status

```
git diff --check  → (no whitespace errors)
git status --short → (clean — only this receipt file is new)
```

---

## Stop condition met

This is a proof lane. No features added. No UI behavior changed. No public release updated. No tag created.
