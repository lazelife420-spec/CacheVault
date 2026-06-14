# Windows Clean-Machine Smoke Checklist

Use this checklist on a fresh Windows user profile or disposable VM before
tagging a public release.

## Extract and launch

- Download the release zip and extract it to a new folder such as `C:\Tools\CacheVault`.
- Confirm the extracted folder contains `CacheVault.exe` and `RELEASE_NOTES.md`.
- Launch `CacheVault.exe`.
- Expected: the app starts without a Python console window.

## Tray behavior

- Confirm the teal tray icon appears after launch.
- Close the main window.
- Expected: the app hides to the tray and stays running.
- Open the tray menu and choose **Quit**.
- Expected: the tray icon disappears and the process exits cleanly.

## Hotkey behavior

- Relaunch the app.
- Copy a few short text snippets in another app.
- Press `Ctrl+Shift+V`.
- Expected: the quick-paste picker opens and shows recent clips.
- Choose a clip with `Enter`.
- Expected: the selected clip is copied and auto-pasted when auto-paste is enabled.

## Startup behavior

- Open Settings and enable **Start Cache Vault with Windows**.
- Sign out and sign back in, or inspect `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- Expected: the `CacheVault` Run entry exists and points at the packaged exe.
- Disable **Start Cache Vault with Windows** after the check unless the test machine is dedicated to startup testing.

## Local data path

- Use the app long enough to capture at least one clip and save settings.
- Confirm local data is created under `%LOCALAPPDATA%\CacheVault\`.
- Expected files:
- `cache_vault.db`
- `settings.json`

## Cleanup expectations

- If startup was enabled, disable it in Settings before deleting the extracted folder.
- Quit the app from the tray menu before cleanup.
- Delete the extracted release folder manually. There is no MSI uninstaller or Add/Remove Programs entry for the zip build.
- Delete `%LOCALAPPDATA%\CacheVault\` manually only if you want to remove the local database and settings.
- Expected: deleting the folder removes the app binaries; deleting `%LOCALAPPDATA%\CacheVault\` removes the local app data.
