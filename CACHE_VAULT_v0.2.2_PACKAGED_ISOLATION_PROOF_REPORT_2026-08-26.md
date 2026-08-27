# Cache Vault v0.2.2 — Packaged Build Isolation Proof Report

**This is a candidate-build isolation proof, not a release.** No tag, publish, push, deploy,
upload, GitHub mutation, or signing occurred. The built artifact is explicitly a local proof
candidate, not the official v0.2.2 release artifact.

---

## 1. Patch worktree path
`C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation`

## 2. Branch and HEAD
```text
Branch: fix/v0.2.2-profile-isolation
HEAD:   3c06c7215c581ae1c7b13d65c77ff32b0313f806
        (patch commit b232844 + source-windowed proof commit 3c06c72, both included)
```

## 3. Build mechanism used
The repository's own existing mechanism — no new packaging path was invented:
- `packaging/cache_vault.spec` (PyInstaller spec, unchanged)
- Invoked directly with PyInstaller 6.16.0 (matches the spec's `pyinstaller>=6.0` requirement),
  rather than via `packaging/build_exe.ps1`, only to redirect the output location — the build
  *logic* (same spec file, same hidden-imports, same version-info embedding) is identical to what
  that script runs; the script itself just doesn't expose a distpath override.
- `customtkinter==6.0.0` installed, matching the pinned `requirements.txt` version exactly (no
  substitution).

## 4. Build command
```powershell
python -m PyInstaller packaging/cache_vault.spec --noconfirm --clean `
  --distpath "dist/candidate/v0.2.2-profile-isolation-b232844" `
  --workpath "build/candidate-v0.2.2-profile-isolation-b232844"
```

## 5. Candidate artifact path
```text
C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation\dist\candidate\v0.2.2-profile-isolation-b232844\CacheVault.exe
```
Clearly marked as a candidate, under a path distinct from any release convention. The main
checkout's actual v0.2.1 release artifacts (`C:\Users\KickA\Desktop\CacheVault\dist\release\v0.2.1\`)
are in a completely separate worktree/directory and were not touched, read, or overwritten.

## 6. Artifact size and SHA-256
```text
Size:   43,575,094 bytes
SHA-256: 54f69aec8d55bcb2b1a01b96b629a8946bf4a59de67607654a5c20e8accd7a23
```

## 7. Version identity — not changed
No version file was edited. `cache_vault/__init__.py`'s `__version__ = "0.2.1"` was left exactly
as committed. Confirmed via the built exe's own Windows version resource:
```text
FileVersion    : 0.2.1
ProductVersion : 0.2.1
ProductName    : Cache Vault
CompanyName    : refundghost
```
This candidate honestly still identifies as 0.2.1 internally — it does not claim to be an official
v0.2.2 release, exactly as required.

## 8. Isolated profile path
```text
C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation\.packaged-proof-isolated-profile-2026-08-26
```
Freshly created, empty, immediately before launch.

## 9. Real vault baseline, before and after
```text
Before: cache_vault.db mtime 2026-08-26 17:17:59, receipt count 385,663
After:  cache_vault.db mtime 2026-08-26 17:17:59, receipt count 385,663   (identical)
```
Checked immediately before launch, during the run, and again after the process fully exited — no
change at any point.

## 10. Packaged launch observations (human-confirmed)
- Command: `CacheVault.exe --profile-dir <isolated dir>`
- Window opened cleanly, no crash, no error dialog.
- A genuine **"Welcome to Cache Vault"** first-run onboarding modal appeared — this only ever
  shows on a truly empty/first-run profile, strong independent confirmation of isolation.
- Behind it, Command Center showed: **All Clips 0, Favorites 0, Screenshots 0, Duplicate 0,
  Receipts 0**.
- Top status bar showed **`Mobile: Off`** — no paired devices at all (contrast with the incident,
  which showed `Mobile: Paired (2)`).
- No real vault data, counts, or content were visible anywhere in the window.

## 11. Where generated receipts landed
One `clipboard_auto_saved-*.json` receipt (matching the disposable safety-clipboard text set
beforehand) and one image asset were created — both **inside the isolated profile's own
`Receipts/`/`assets/` folders**:
```text
.packaged-proof-isolated-profile-2026-08-26/CacheVault/Receipts/2026-08-27/clipboard_auto_saved-61d99222892c49cc81219d5c1e4eff12-20260827-022339.json
.packaged-proof-isolated-profile-2026-08-26/CacheVault/assets/61d99222892c49cc81219d5c1e4eff12.png
```
Nothing landed in the real vault's `Receipts/` folder.

## 12. Receipt contents were not opened or read
Confirmed. Only filenames, paths, and directory listings were recorded — no JSON/clipboard content
was opened, printed, or parsed at any point in this pass.

## 13. Prior incident receipts remain untouched
Re-hashed all three; identical to every previous check in this thread:
```text
841821b00253ba36cf9ebd6f9ef81d91b843446fd3e1dd19aa71a09fc54085d1
53d8d655c053a1e377922418c3066600bea0e541bfbda389e8089e7006af5ed3
95b77ff5eb4ca744295931129f411858bb95f63e760773b250ac5f88a230c990
```

## 14. Confirmation: no official artifact/tag/push/publish/GitHub action occurred
Confirmed. `git status` in the patch worktree shows no source changes — `dist/` and `build/` are
gitignored, so the candidate build itself never appeared as untracked either. No `git tag`, no
`git push`, no GitHub interaction, no signing, no deploy occurred.

## 15. Remaining work before human walkthrough retry
- The candidate build and this proof are uncommitted (report only, pending approval).
- The human walkthrough (Checklist A–G from the original gate) can now reasonably be retried
  against this packaged candidate with `--profile-dir` — both the source and packaged paths have
  now independently proven isolation holds, including under real background auto-capture activity.
- No version bump, changelog entry, tag, or official release has been made; this stays a local
  proof candidate until a separate, explicit release gate is run.

## Final classification

```text
A — PACKAGED ISOLATION PROOF PASS / READY FOR HUMAN WALKTHROUGH RETRY
```
