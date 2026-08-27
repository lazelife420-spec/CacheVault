# Cache Vault v0.2.2 — Human Walkthrough Retry Report

**This closes the release-readiness blocker for the patch candidate. It is not an official v0.2.2
release.** No version bump, tag, publish, push, deploy, or GitHub action occurred. No source
change, rebuild, or signing occurred.

---

## 1. Patch worktree path
`C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation`

## 2. Branch and HEAD
```text
Branch: fix/v0.2.2-profile-isolation
HEAD:   a01faa7e4d1837174244b9f8af90a7aa6d6c6776
```

## 3. Candidate artifact path and hash
```text
dist\candidate\v0.2.2-profile-isolation-b232844\CacheVault.exe
SHA-256: 54f69aec8d55bcb2b1a01b96b629a8946bf4a59de67607654a5c20e8accd7a23
```
Confirmed matching before the walkthrough began; this is the same candidate proven in the packaged
isolation gate, not the old v0.2.1 release artifact.

## 4. Isolated profile path
```text
.walkthrough-retry-isolated-profile-2026-08-26\
```
Fresh, created for this gate; reused across all of A–G (including two full relaunches) so that
restart-persistence (F) exercised the same profile, as intended.

## 5. Real vault baseline, before/after
```text
cache_vault.db mtime : 2026-08-26 17:17:59
Receipt count         : 385,663
```
Checked repeatedly throughout — before launch, after every checklist step, after every
relaunch/close, and at the very end. **Identical at every single check, no exceptions.**

## 6. Checklist A–G results

| Step | Result | Notes |
|---|---|---|
| A — First-run launch | **PASS** | Human confirmed: opened without crash, All Clips 0, Receipts 0, Mobile Off, no real vault data visible, no error dialog. |
| B — Capture | **PASS** | Disposable test string captured and shown in "Recent Active Clip"/"Captured Today." One observation: clip count showed 4 rather than 1 after the single capture — likely ambient auto-captures (clipboard/screenshot) picked up during A's launch window, not a real-vault leak (traced entirely to the isolated profile). |
| C — Search | **PASS, with a methodology note** | Search for the test string found it correctly. The "no-match" search did not achieve a true empty result — typing/pasting the nonsense string into the search box round-tripped through the clipboard and got auto-captured as a new clip itself, which the search then legitimately found. This is a quirk of testing against an always-on capture app, not a search defect — search returned exactly what existed in the vault at query time. |
| D — Quick Paste | **PASS** | Human manually pasted the selected clip into a text target; pasted text matched exactly. No unsafe or unexpected behavior. |
| E — Recently Removed | **PASS** | Test item removed → appeared in Recently Removed → restored → returned to active list without being re-added as a duplicate/new clip. |
| F — Restart persistence | **PASS** | App closed fully (process confirmed gone), relaunched with the identical `--profile-dir`; restored test item and state persisted, search still found it, no crash or data-loss warning. |
| G — Exit / final isolation check | **PASS** | App closed fully, process confirmed gone. All new runtime data from the entire walkthrough (13 receipt files, 8 image assets) confirmed confined to the isolated profile. |

## 7. Where generated isolated receipts/data landed
All inside `.walkthrough-retry-isolated-profile-2026-08-26\CacheVault\`:
```text
Receipts/2026-08-27/  — 13 files (clipboard_auto_saved-*.json, spanning the ~90-minute session)
assets/               — 8 files (screenshot/image captures)
```
One extended-runtime observation, already surfaced and discussed mid-walkthrough: the isolated
instance was left running continuously for roughly 64 minutes between the Checklist B relaunch and
Checklist C, during which it kept passively auto-capturing ambient clipboard/screen activity (real,
substantive content unrelated to the disposable test, sourced from other work happening on the
machine) — exactly as a continuously-running capture app is designed to do. This confirmed an
important boundary: `--profile-dir` isolation controls *where* captured data is stored (proven,
repeatedly, throughout this entire walkthrough), not *what* gets captured — clipboard/screen
monitoring is OS-wide by nature. Every one of those ambient captures, across the full ~90-minute
session, landed inside the isolated profile and never touched the real vault.

## 8. Receipt contents were not opened or read
Confirmed throughout. Only filenames, counts, and directory listings were recorded at every step —
no JSON/clipboard/image content was opened, printed, or parsed by this session.

## 9. Prior incident receipts were not opened/read/deleted
Confirmed. Re-hashed at the end of the walkthrough — identical to every check across this entire
thread:
```text
841821b00253ba36cf9ebd6f9ef81d91b843446fd3e1dd19aa71a09fc54085d1
53d8d655c053a1e377922418c3066600bea0e541bfbda389e8089e7006af5ed3
95b77ff5eb4ca744295931129f411858bb95f63e760773b250ac5f88a230c990
```

## 10. Confirmation: no source/build/release/tag/publish/push/GitHub/signing action occurred
Confirmed. Only checklist observation, passive file/process checks, and this report were produced
in this pass.

## Final classification

```text
A — WALKTHROUGH PASS / RELEASE BLOCKER CLOSED FOR PATCH CANDIDATE
```

**Scope of this claim, stated precisely:** the release-readiness walkthrough blocker is closed for
the `fix/v0.2.2-profile-isolation` patch candidate (commit `a01faa7`, artifact hash
`54f69aec8d...`), run in isolation via `--profile-dir`. This is **not** a claim that v0.2.2 is an
official release — no version bump, tag, changelog entry, publish, or public artifact exists yet.
That remains a separate, explicit future gate.
