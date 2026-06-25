# Fail-Safes and Recovery

How Cache Vault protects your data when things go wrong, and how to recover.

---

## Where Cache Vault stores data

All files live under `%LOCALAPPDATA%\CacheVault\` (typically
`C:\Users\<you>\AppData\Local\CacheVault\`).

| File | Contains |
|------|----------|
| `settings.json` | All user preferences (hotkeys, capture rules, mobile access, vault lock) |
| `settings.json.bak` | Last-known-good settings backup |
| `command_center.json` | Hotkey action definitions |
| `command_center.json.bak` | Last-known-good command center backup |
| `command_run_log.json` | Run log for hotkey actions (status, result, timestamp) |
| `macros.json` | Vault macro definitions |
| `macros.json.bak` | Last-known-good macros backup |
| `mobile_access_receipts.json` | Audit log of every mobile API call (last 500 entries) |

No clipboard content is stored in these files. Clip data lives in the SQLite
vault database (`cache_vault.db` in the same directory).

---

## Atomic writes — how we protect against crashes

All critical JSON files are written atomically:

1. Data is written to a temporary file in the same directory.
2. The file is flushed and fsync'd to disk.
3. `os.replace` atomically swaps the temp file into place.

A crash mid-write can never leave a half-written file. Readers see either the
old content or the new content — never a truncated mix.

The app also keeps a `.bak` (last-known-good copy) for settings, command
center actions, and macros. If a save produces a corrupt file, the `.bak`
from the *previous* successful save is still intact.

---

## Corrupt file recovery

If a JSON file becomes unreadable (bad JSON, disk error):

1. **The app does not crash on startup.** It falls back to safe defaults.
2. **The corrupt file is quarantined** — moved to
   `<name>.corrupt-<YYYYMMDD-HHMMSS>` (e.g.,
   `settings.json.corrupt-20260625-181500`).
3. **The corrupt data is preserved** for inspection. It is never silently
   overwritten.

### Manual recovery from a corrupt settings file

1. Close Cache Vault.
2. Go to `%LOCALAPPDATA%\CacheVault\`.
3. Look for `settings.json.corrupt-*`. This is your broken file.
4. If `settings.json.bak` exists, rename it to `settings.json` to restore the
   last-known-good settings.
5. If no `.bak` exists, delete or rename `settings.json` and restart — the app
   will create a fresh one with safe defaults.

---

## How to recover from broken hotkeys

If a global hotkey stops working:

1. Open Cache Vault → Settings → Hotkeys.
2. Check whether the hotkey field shows a red warning (conflict with another
   app).
3. Try a different key combination.
4. If the entire hotkey system seems broken, reset hotkeys individually in
   Settings.

### Nuclear hotkey reset

If hotkeys are completely unresponsive:

1. Close Cache Vault.
2. Open `%LOCALAPPDATA%\CacheVault\settings.json`.
3. Find and delete the hotkey entries (or rename the file to regenerate
   defaults).
4. Restart Cache Vault.

---

## How to reset settings safely

### Reset specific settings

Open Cache Vault → Settings and change individual values. All changes are
written atomically with a `.bak` backup.

### Full settings reset

1. Close Cache Vault.
2. Rename `%LOCALAPPDATA%\CacheVault\settings.json` to
   `settings.json.old`.
3. Restart Cache Vault — a fresh `settings.json` is created with safe
   defaults.
4. If you need to recover old settings, the `.old` file is still there.

---

## How to disable Mobile Bridge

Mobile Bridge is **off by default**. It never starts without your action.

### To disable after it was enabled

1. Open Cache Vault → Settings → Mobile Access.
2. Turn off "Enable Mobile Access."
3. If paired devices exist, the app will ask for confirmation ("You have N
   paired device(s). Disabling Mobile Access will stop the local bridge and
   devices will no longer connect.").
4. Click Yes.
5. Save settings.

The bridge stops immediately, and all internal server/thread state is cleared.
Paired device tokens remain stored (in `settings.json`) until you manually
remove them, but the bridge cannot be reached while disabled.

---

## What to do if an export fails

### If you see an error during export

1. The app writes a failure receipt — look for a JSON file in
   `%LOCALAPPDATA%\CacheVault\receipts\` with `"success": false`.
2. The temporary staging directory is automatically cleaned up (no partial
   files left behind).
3. The failure receipt records the exact error so you can diagnose the
   problem (disk full, permission denied, etc.).

### If the zip is corrupt or incomplete

1. Re-run the export.
2. Use `SHA256SUMS.txt` inside the zip to verify file integrity after
   extraction.
3. If hash verification fails, the zip was not written correctly — delete it
   and export again.

---

## What Cache Vault does NOT protect against

Cache Vault is a local-first clipboard vault. It is honest about its limits:

| Limitation | Detail |
|------------|--------|
| **No file encryption** | Safes organize clips; they do not encrypt them. Vault Lock is a UI privacy lock, not file encryption. |
| **No cloud backup** | There is no cloud sync or remote storage. Back up your `%LOCALAPPDATA%\CacheVault\` folder manually if needed. |
| **No tamper-proof receipts** | Stamped Receipts record what Cache Vault observed locally. They are not cryptographically notarized, not blockchain-anchored, and not externally verifiable. |
| **No network security guarantee** | The optional Mobile Bridge runs on your local Wi-Fi. It uses token-based pairing but does not implement TLS. Keep Mobile Bridge off if you are on an untrusted network. |
| **No malware protection** | Cache Vault cannot protect clipboard data from malware already running on your machine. |
