# Cache Vault v0.1.5-rc1 — Release Candidate Receipt

**Date:** 2026-06-30
**Status:** Release Candidate — not yet published as public artifact

---

## Branch & Commit

| Field | Value |
|---|---|
| **Branch** | `ux/mobile-image-polish-local` |
| **Base commit** | `e6fe972 chore: reconcile Cache Vault public release proof surface` |
| **Top commit** | `715be92 test: align version checks with v0.1.5-rc1` |
| **Commit range** | `e6fe972..715be92` (10 commits) |

---

## Version Surfaces Changed

| Surface | Old Value | New Value |
|---|---|---|
| `cache_vault/__init__.py` `__version__` | `0.1.4` | `0.1.5-rc1` |
| `cache_vault/__init__.py` `__release_label__` | `Public Release` | `Release Candidate` |
| `pyproject.toml` `version` | `0.1.4` | `0.1.5-rc1` |

---

## Artifact

| Field | Value |
|---|---|
| **ZIP path** | `dist/release/v0.1.5-rc1/CacheVault-v0.1.5-rc1-windows.zip` |
| **ZIP SHA256** | `31a82ba5c84f31f0faa002f8b02f61c3af0b0ff316cf9458588834c98800e88e` |
| **ZIP size** | 42,849,262 bytes (40.86 MB) |
| **EXE path** | `dist/CacheVault.exe` |
| **EXE SHA256** | `1FAEE93F706AEC91A2EE12376C3F83B885CAFF2358E3A88E6C42CB3FB637FFDB` |
| **EXE size** | 43,178,137 bytes (41.18 MB) |
| **SHA256SUMS** | `dist/release/v0.1.5-rc1/SHA256SUMS.txt` |

---

## Commands Run

```
pytest -p no:xonsh                    # 784 passed, 1 skipped
python -m compileall cache_vault      # PASS
python app.py --selftest              # PASS (selftest OK)
pwsh packaging/build_exe.ps1          # Built dist/CacheVault.exe
pwsh packaging/package_release.ps1 -Tag v0.1.5-rc1 -NotesPath packaging/RELEASE_NOTES-v0.1.5-rc1.md
```

---

## Test Results

| Gate | Result |
|---|---|
| **pytest** | **784 passed, 1 skipped** (unusable init.tcl / tk.tcl on the host system, which is an expected environmental skip) |
| **compileall** | **PASS** |
| **selftest** | **PASS** |
| **Integration tests** | **25/25 passed** (`tests/test_workflow_integration.py`) |
| **PyInstaller build** | **PASS** (EXE built and version-validated by package_release.ps1) |
| **Package script** | **PASS** (stale-exe guard, version truth, binary version check all passed) |

---

## Visual QA Receipts Referenced

| Receipt | File |
|---|---|
| Selected item paste QA | `docs/SELECTED_ITEM_PASTE_QA_2026-06-30.md` |
| Copy-to-Safe workflow QA | `docs/COPY_TO_SAFE_WORKFLOW_QA_2026-06-30.md` |
| Do Not Save Next Copy QA | `docs/DO_NOT_SAVE_NEXT_COPY_QA_2026-06-30.md` |
| Date stamp / image viewer QA | `docs/DATESTAMP_IMAGE_VIEWER_POLISH_QA_2026-06-30.md` |
| Menu / settings cleanup QA | `docs/MENU_SETTINGS_CLEANUP_QA_2026-06-30.md` |
| Workflow integration RC audit | `docs/CACHE_VAULT_WORKFLOW_INTEGRATION_RC_AUDIT_2026-06-30.md` |
| Public surface audit | `docs/CACHE_VAULT_PUBLIC_SURFACE_AUDIT_2026-06-30.md` |

---

## Known Holds

1. **No public Proof Foundry `/proof` receipt update was made** because this RC is not yet published as a public artifact.
2. **No git tag created** — awaiting user approval after reviewing this receipt.
3. **Branch name** `ux/mobile-image-polish-local` does not reflect full scope — acceptable for RC.
4. **1 skipped test** is an expected environmental skip (Tcl/Tk runtime initialization on the host environment), NOT version-related. All version-specific tests have been aligned.

---

## Final RC Verdict

### **RC-READY**

The v0.1.5-rc1 package artifact has been built, hashed, and verified. All gates pass. Stale version-sensitive tests have been reconciled to read version dynamically. No unexpected skips remain.

**Next steps (user decision):**
- Approve tag: `git tag -a cache-vault-v0.1.5-rc1 -m "Cache Vault v0.1.5-rc1"`
- Publish artifact if desired
- Update Proof Foundry `/proof` only after public artifact exists
