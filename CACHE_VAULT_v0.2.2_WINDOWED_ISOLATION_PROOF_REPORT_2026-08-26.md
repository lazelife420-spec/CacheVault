# Cache Vault v0.2.2 — Windowed Isolation Proof Report

**This proves the patched source windowed path only — it does not prove packaged
(`CacheVault.exe`) isolation.** No build occurred in this pass; that is explicitly a later,
separate gate. No capture/search/Quick Paste/Recently Removed test was performed. No source
change, commit, tag, push, publish, or GitHub action occurred.

---

## Command used
```text
cd C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation
python.exe app.py --profile-dir "C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation\.windowed-proof-isolated-profile-2026-08-26"
```
Run from source, in the fresh patch worktree (`fix/v0.2.2-profile-isolation` @ `b232844`). Not the
packaged binary.

## Pre-launch baseline (real vault, passive/metadata only)
```text
cache_vault.db mtime : 2026-08-26 17:17:59  (unchanged from every prior gate in this thread)
Receipt count         : 385,663
```

## Launch observation
- Process started (PID 21476), window title confirmed as `Cache Vault™ — Product by The Proof
  Foundry™`.
- Human operator visually confirmed the window's state as **"fresh"** — an empty/first-run vault,
  no real data visible.
- No error dialog was reported.
- No "already running" collision dialog appeared — the profile-scoped mutex claimed successfully
  on first attempt.

## Isolated profile directory — proof the redirect actually took effect this time
```text
.windowed-proof-isolated-profile-2026-08-26/CacheVault/
  cache_vault.db          (77,824 bytes, created/written during this run)
  settings.json           (created during this run)
  settings.json.bak
  Receipts/2026-08-27/
    clipboard_auto_saved-48d53da0ac5940e9a65721bec588458e-20260827-011041.json
    clipboard_auto_saved-72dcb62d0d5f4b71a963eb27ede54cca-20260827-011133.json
    clipboard_sensitive_not_auto_saved-25e1e4c5-20260827-011034.json
```
This is the single most important finding: the app's normal background clipboard-capture behavior
was **not** disabled for this run (unlike `--selftest`, no `CACHE_VAULT_DISABLE_TRAY` or capture
suppression was set), and it did fire — three real capture events happened during this launch,
matching the operator's own precautionary clipboard-set beforehand. **Every one of them landed
inside the isolated profile's own `Receipts/` folder, not the real vault's.** This is exactly the
failure mode the incident exposed, now demonstrably contained. File contents were not opened or
read, per the clipboard-contents safety rule — only their existence, names, and location were
recorded.

## Real vault — unchanged throughout
```text
cache_vault.db mtime : 2026-08-26 17:17:59   (identical, before and after)
Receipt count         : 385,663              (identical, before and after)
```
Checked immediately after launch (while the process was still running) and again after the process
fully exited — no change at either point.

## Shutdown
Closing the window did **not** immediately terminate the process — its `MainWindowTitle` changed
to the bare console title (`C:\Python313\python.exe`), consistent with the app minimizing to a
system-tray icon rather than exiting, since tray behavior was not disabled for this launch. The
human operator located and used the tray icon's exit path; the process (PID 21476) is now
confirmed fully gone (`tasklist` shows no matching PID, and no `python.exe` process at all).

## Confirmations
- No packaged `CacheVault.exe` was launched — source only, via `python.exe`.
- No capture/search/Quick Paste/Recently Removed test was performed.
- No mobile pairing changes; no paired devices were shown or created.
- No source file was edited, no commit, no build, no tag/push/publish/GitHub action occurred.
- The prior incident's three receipt files were not opened, read, or deleted (not touched at all
  in this pass).
- Real vault `cache_vault.db` mtime and receipt count are identical to the start of this gate and
  to every prior check across this entire thread.

## Final classification

```text
A — WINDOWED SOURCE ISOLATION PROOF PASS / READY FOR PACKAGED BUILD ISOLATION GATE
```

One operational note for whoever scopes the next gate: a plain window-close minimizes this app to
tray rather than exiting the process, by design (tray was not disabled for this run). That's not a
patch defect — just something the next gate (or a future walkthrough) should account for explicitly
when defining what "closed" means.
