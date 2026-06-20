# Cache Vault Founder MVP — Release Receipt

Release title: **Cache Vault Founder MVP v0.1.3**  
Git tag: `v0.1.3-founder-mvp`  
Branch: `release/cache-vault-founder-mvp`  
Commit: see git tag `v0.1.3-founder-mvp` (release commit on this branch)  
Date: 2026-06-20

## Version truth

| Field | Value |
|---|---|
| Package / app version | `0.1.3` |
| Display label | Founder MVP |
| Git tag | `v0.1.3-founder-mvp` |
| `pyproject.toml` | `0.1.3` |
| `cache_vault/__init__.py` | `0.1.3` + `__release_label__ = "Founder MVP"` |
| Exe ProductVersion / FileVersion | `0.1.3` (tuple `0.1.3.0`) |

## Test commands

```powershell
python -m pytest -p no:xonsh
python -m compileall cache_vault tools tests -q
python tools\verify_exe_metadata.py --exe dist\CacheVault.exe
pwsh scripts\founder_package_smoke.ps1
```

## Test results

```text
pytest: 440 passed, 1 skipped
compileall: OK
verify_exe_metadata: ProductVersion/FileVersion 0.1.3 PASS (README/RELEASE_NOTES markers pending update in commit 6)
founder_package_smoke.ps1: All automated packaged smoke checks passed
```

## Package

| Artifact | Path |
|---|---|
| Executable | `dist\CacheVault.exe` |
| Release zip | `dist\release\v0.1.3-founder-mvp\CacheVault-v0.1.3-founder-mvp-windows.zip` |
| Checksums | `dist\release\v0.1.3-founder-mvp\SHA256SUMS.txt` |

**SHA256 (zip):**

```text
279d181513e0c4653911d7803d62d5c924b0b15a5b009c5bbb0b8a8f0e0a0316  CacheVault-v0.1.3-founder-mvp-windows.zip
```

Build commands:

```powershell
pwsh packaging\build_exe.ps1
pwsh packaging\package_release.ps1 -Tag v0.1.3-founder-mvp -NotesPath packaging\RELEASE_NOTES-v0.1.3-founder-mvp.md
```

## Packaged smoke checklist

| Check | Result |
|---|---|
| Fresh launch / free selftest (packaged EXE) | PASS |
| Free mode (no license) | PASS |
| Capture/classify pipeline (selftest) | PASS |
| Invalid license rejected (packaged EXE) | PASS |
| Production test Founder license accepted (packaged EXE) | PASS |
| Ed25519 / cryptography in frozen build | PASS |
| Proof receipt export | PASS |
| Receipt does not leak clipboard contents | PASS |
| Package SHA256 generated | PASS |
| Search / favorite / copy (UI) | Manual — core paths unchanged; not re-run in this gate |
| Founder page opens (UI) | Manual |
| Locked advanced feature upgrade prompt (UI) | Manual |
| Founder status persists after restart (UI) | Manual — license file persistence tested via unit + packaged selftest |
| No cloud/mobile/sync marketing claims | PASS (release notes + landing copy audited) |

License test file (outside repo, not committed):

```text
C:\secure\cachevault-keys\founder-test-license.json
```

Production keys (outside repo, not committed):

```text
C:\secure\cachevault-keys\cachevault_founder_private.pem
C:\secure\cachevault-keys\cachevault_founder_public.pem
```

## Known limitations

- No cloud sync.
- No mobile bridge claim in Founder MVP SKU.
- No account system.
- No automatic license server.
- Founder licenses are manually issued in this MVP.
- Windows executable is unsigned.
- Advanced features were free in prior releases; this build gates them behind Founder license.

## Do not claim

- Cloud sync
- AI-powered features
- Mobile access (Founder MVP marketing)
- Team collaboration
- Automatic backup
- Encrypted safes
- Military/bank-grade encryption
- In-app payment or subscription billing

## Production key handling

- Private key generated outside repo at `C:\secure\cachevault-keys\`
- Only public PEM embedded in `cache_vault/licensing.py`
- No private key, test license, or local secrets in git status/diff
