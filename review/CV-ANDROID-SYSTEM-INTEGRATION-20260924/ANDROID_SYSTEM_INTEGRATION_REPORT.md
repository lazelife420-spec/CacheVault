# Android System Integration — Review Report

## Summary

```text
STATUS = READY_FOR_OWNER_REVIEW
BASE_MOBILE_UI_COMMIT = 16c11e86176077b3dbc5b7976abd7e30d754b80b
INTEGRATION_COMMIT = this commit (SHA recorded in final handoff)
BRANCH = ui/cv-ui2-product-polish
PRODUCTION_PACKAGE_UNTOUCHED = YES
```

Cache Vault now exposes its existing local-first actions through Android's Share Sheet, four launcher shortcuts, and explicit `cachevault://open/...` routes. Repeated share intents update the visible preview in place. The optional paired-PC foreground notification opens the Paired PC destination and retains its Stop action.

## Integration inventory

| Android surface | Current support / decision |
| --- | --- |
| Launcher | Existing launcher activity retained. |
| Launcher shortcuts | Dynamic Save, Search, Favorites, and Safes shortcuts; each targets its real route. |
| `ACTION_SEND` text | `text/plain` target opens preview and Safe selector; local save remains primary. |
| Shared URL | URL text is recognized as a LINK preview; no URL is saved or sent automatically. |
| `ACTION_SEND` image | `image/*` target opens image preview. Verified using a synthetic image through the app's non-exported FileProvider grant. |
| `ACTION_VIEW` | App-owned `cachevault://open/...` routes only. General web links are not claimed as an import format. |
| Photo picker | Existing Android Photo Picker action retained; opened and exited without selecting or inspecting a personal image. Fallback uses `GetContent`. |
| FileProvider | Existing non-exported provider retained for explicit content URI sharing. |
| QR camera | Existing CAMERA permission supports QR scanning and is requested by that flow. |
| Notifications | Optional foreground connection service only. It displays connection state, provides Stop, and opens Paired PC. No live PC was paired for notification exercise. |
| Clipboard | Read occurs only after tapping “Paste from clipboard” in the visible Add sheet. No monitor, polling, listener, Accessibility, or notification scraping. |
| Widgets | NOT_IMPLEMENTED_WITH_REASON — no sensitive content surface is needed; direct Add/Search/Safes access is provided by shortcuts. |
| Quick Settings tile | NOT_IMPLEMENTED_WITH_REASON — the tile must not read clipboard content in the background; clipboard paste stays an explicit foreground Add action. |
| Document picker / arbitrary files | NOT_IMPLEMENTED_WITH_REASON — arbitrary files do not map to the current text/link/image local item model. Image import uses the Photo Picker. |
| Android AppSearch | Not present; no system-search index is created. |
| Drag and drop | Not present; current app surfaces do not need a drop target. |

Declared permissions are limited to network and Wi-Fi discovery for paired-PC features, foreground service permissions for the optional connection service, notifications when the user enables it, and CAMERA for QR pairing. There is no broad media or storage permission. The instrumentation audit found no Accessibility-service or notification-listener service binding.

## Test matrix

Runs completed on Samsung Galaxy S23 (SM-S911W, Android 16/API 36) and AVD `cv_mobile_1` (Android 15/API 35), using only the debug application ID `com.prooffoundry.cachevaultmobile.cvmobile1.debug`.

| Check | Result |
| --- | --- |
| SHARE_TEXT | PASS on S23 and emulator. |
| SHARE_URL | PASS on S23 and emulator; preview is labeled LINK. |
| SHARE_IMAGE | PASS on S23 and emulator with a synthetic FileProvider image; preview and MIME type are visible. |
| LAUNCHER_SHORTCUT_ADD | PASS; Save shortcut publication and cold `cachevault://open/save` route verified. |
| LAUNCHER_SHORTCUT_SEARCH | PASS; opens the Vault search field with keyboard. |
| LAUNCHER_SHORTCUT_SAFES | PASS; opens Safes directly. |
| LAUNCHER_SHORTCUT_FAVORITES | PASS; opens the Favorites filter. |
| QUICK_SETTINGS_ENTRY | NOT_IMPLEMENTED_WITH_REASON — see inventory. |
| HOME_WIDGET | NOT_IMPLEMENTED_WITH_REASON — see inventory. |
| SYSTEM_PHOTO_PICKER | PASS on both devices; opened and returned with Back, no photo selected. |
| DOCUMENT_PICKER | NOT_IMPLEMENTED_WITH_REASON — arbitrary files are outside the current item model. |
| COLD_START_DEEP_LINK | PASS on both devices. |
| WARM_APP_DEEP_LINK | PASS on both devices, including Add and Safes. |
| BACK_STACK | PASS — Safes returns to Vault; Share “Done” returns to MainActivity; picker Back returns to the app. |
| HOME / TASK SWITCHING | PASS on emulator — Home then re-entry opened Search in the existing task. |
| REPEATED_SHARE_INTENT | PASS on both devices — second payload replaced first preview without stale text. |
| NO_BACKGROUND_CLIPBOARD_MONITOR | PROVEN by source audit: the only clipboard read is inside the explicit Add-sheet paste callback. |
| NO_ACCESSIBILITY_SERVICE | PROVEN by manifest/service audit and instrumentation check. |
| NO_NOTIFICATION_LISTENER | PROVEN by manifest/service audit and instrumentation check. |
| PRODUCTION_PACKAGE_UNTOUCHED | YES — only the isolated debug package was installed or updated. The production package remained installed. |

Three integration instrumentation tests passed on each device. They verify shortcut routes, Share Sheet and deep-link intent resolution, and permission/service boundaries. Unit tests: 167 passed. `lintDebug`: 0 errors. `assembleDebug`: passed.

## Evidence

- `SYSTEM_INTEGRATION_CONTACT_SHEET.png` — marker-verified screenshots of Search, Save/Add, Safes, and text, URL, and image share previews on both devices.
- Individual `*_S23.png` and `*_EMULATOR.png` screenshots have paired UI marker XML files.
- `capture_marker_verified.ps1` records the capture and verifies the expected visible marker before accepting a screenshot. Launcher long-press gestures were not automated; the system ShortcutManager registration was inspected on-device, and each exact shortcut URI was launched through cold/warm activity tests.

## Deliberate limits

No Quick Settings tile, home widget, arbitrary document import, or broad file-manager behavior was added. The paired-PC notification intent now targets the Paired PC route, but a live foreground connection and its actual notification were not exercised because no PC was paired. No production package was installed, changed, or removed.

---

## Addendum (2026-09-30) — capture-surface supersession

This report is a snapshot of the app as of its base commit (2026-09-24), before
phone-side capture existed. The following rows describe that snapshot and are
superseded on unreleased master by the owner-accepted capture surface (decision
record: [../CV-MOBILE-CAPTURE-TM-20260930/THREAT_MODEL_AMENDMENT.md](../CV-MOBILE-CAPTURE-TM-20260930/THREAT_MODEL_AMENDMENT.md)):

- **"Clipboard — no monitor, polling, listener…"** — the accepted capture
  feature adds a clipboard-change listener that posts a save notification, plus
  an on-open focus drain. It still performs **no background clipboard reads**
  (platform-enforced) and reads no content without window focus, as measured in
  [../CV-VL2-A-HW1-20260929/results_emulator_accessibility.json](../CV-VL2-A-HW1-20260929/results_emulator_accessibility.json).
- **NO_BACKGROUND_CLIPBOARD_MONITOR** — superseded in the same way:
  monitoring-to-notify now exists; background *reading* remains impossible.
- **Declared permissions** — capture adds `RECEIVE_BOOT_COMPLETED` and
  `READ_MEDIA_IMAGES`; see `docs/MOBILE_THREAT_MODEL.md` for the updated table.

Rows that remain true: **NO_ACCESSIBILITY_SERVICE** (the 2026-09-29
accessibility attempt was measured and reverted), **NO_NOTIFICATION_LISTENER**,
and all share/deep-link/widget rows.
