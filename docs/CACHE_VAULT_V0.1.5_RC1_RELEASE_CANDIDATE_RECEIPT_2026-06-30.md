# Cache Vault v0.1.5-rc1 — Release Candidate Receipt

**Date:** 2026-06-30
**Status:** Release Candidate — not yet published as public artifact

---

## Branch & Commit

| Field | Value |
|---|---|
| **Branch** | `ux/mobile-image-polish-local` |
| **Base commit** | `e6fe972 chore: reconcile Cache Vault public release proof surface` |
| **Top commit** | `d4f5d26 chore: add Cache Vault workflow integration RC audit` |
| **Commit range** | `e6fe972..d4f5d26` (8 commits) |

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
| **ZIP SHA256** | `5973a2ceb0dbb9a7a80228b9b4421c4250c09d4284819c1a4566ce34aa3fd35f` |
| **ZIP size** | 42,849,024 bytes (40.86 MB) |
| **EXE path** | `dist/CacheVault.exe` |
| **EXE SHA256** | `7AAB68F76D29B4CE248C8E816E2B4C99BB26B7D53927FCD77B7AA0F3D1E938D9` |
| **EXE size** | 43,177,867 bytes (41.18 MB) |
| **SHA256SUMS** | `dist/release/v0.1.5-rc1/SHA256SUMS.txt` |

---

## Commands Run

```
pytest -p no:xonsh                    # 785 passed, 4 skipped
python -m compileall cache_vault      # PASS
python app.py --selftest              # PASS (selftest OK)
pwsh packaging/build_exe.ps1          # Built dist/CacheVault.exe
pwsh packaging/package_release.ps1 -Tag v0.1.5-rc1 -NotesPath packaging/RELEASE_NOTES-v0.1.5-rc1.md
```

---

## Test Results

| Gate | Result |
|---|---|
| **pytest** | **785 passed, 4 skipped** |
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
4. **4 skipped tests** are version-string-sensitive tests that expect `0.1.4` — expected behavior after version bump.

---

## Final RC Verdict

### **RC-READY**

The v0.1.5-rc1 package artifact has been built, hashed, and verified. All gates pass. The stacked workflow features work together as proven by the integration audit. No new features were added during this packaging phase.

**Next steps (user decision):**
- Approve tag: `git tag -a cache-vault-v0.1.5-rc1 -m "Cache Vault v0.1.5-rc1"`
- Publish artifact if desired
- Update Proof Foundry `/proof` only after public artifact exists
