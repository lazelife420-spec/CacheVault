# CacheVault Codebase Audit

> Generated: June 27, 2026
> Version: 0.1.4 | Branch: master | Platform: Windows 10
> Test suite: **545/545 passed** (40s)

---

## 1. Project Overview

**Cache Vault** is a local-first Windows clipboard vault built with Python, CustomTkinter (desktop GUI), SQLite (storage), and Win32 APIs (clipboard monitoring, hotkeys, paste delivery). It captures clipboard content, classifies it (links, code, commands, paths, emails, sensitive secrets), and provides search, favorites, collections, exports with proof manifests, and stamped receipts.

### Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.10+ |
| GUI | CustomTkinter (tkinter wrapper) |
| Storage | SQLite (single local DB) |
| Clipboard | Win32 `AddClipboardFormatListener` / polling fallback |
| Hotkeys | Win32 `RegisterHotKey` API |
| Tray | pystray + Pillow |
| Mobile Bridge | `http.server.ThreadingHTTPServer` + zeroconf mDNS |
| Licensing | Ed25519 offline license verification (cryptography lib) |
| Packaging | PyInstaller (one-file .exe) |
| Tests | pytest (545 tests, core-only, no GUI deps) |

### File Counts

| Directory | Files | Approx Lines |
|-----------|-------|-------------|
| `cache_vault/core/` | 30 .py files | ~8,000 |
| `cache_vault/core/mobile/` | 8 .py files | ~1,500 |
| `cache_vault/ui/` | 29 .py files | ~11,700 |
| `tests/` | 50+ .py files | ~8,000 |
| `scripts/` | 25+ .py files | ~3,000 |
| Entry point (`app.py`) | 1 file | ~120 |
| **Total source** | **~95 files** | **~32,000+** |

---

## 2. Architecture

```
app.py                          # Entry point (--selftest or GUI)
cache_vault/
  __init__.py                   # Version + metadata
  brand.py                      # All brand constants, colors, labels
  build_meta.py                 # Windows exe version info
  feature_gate.py               # Founder feature gating
  licensing.py                  # Ed25519 offline license verification
  core/                         # Pure Python, no UI imports, fully unit-tested
    models.py                   # Clip dataclass + 50+ event/action constants
    clipboard.py                # Windows clipboard monitor (event or polling)
    storage.py                  # SQLite repository (clips, events, assets)
    vault.py                    # Orchestration layer (main API for UI)
    settings.py                 # JSON settings (~70+ fields)
    events.py                   # Local event log (metadata only, no secrets)
    classify.py                 # Rule-based content classifiers
    search.py                   # Search query parser + date presets
    sensitive.py                # Sensitive detection, masking, expiry
    hotkey.py                   # Global hotkey listener (RegisterHotKey)
    export.py                   # Single/multi clip export (txt/md/html/json/zip)
    exports.py                  # Proof-backed exports (manifest, SHA256, receipts)
    safes.py                    # Named vault sections (Safes)
    safe_io.py                  # Atomic file writes + corrupt file recovery
    startup.py                  # Start with Windows (registry Run key)
    single_instance.py          # Mutex-based single instance
    pathutil.py                 # Safe Windows path handling
    duplicates.py               # Duplicate detection + resolution
    grouping.py                 # Clip grouping (by date/source/type/domain)
    smart_folders.py            # Smart folder SQL filters + counts
    clip_accents.py             # Visual accent colors for labels
    clip_metadata.py            # Title, URL, size, time bucket helpers
    editable_copies.py          # Editable working copies + HTML bundles
    copy_clean.py               # Clean copy formatters (plain text, markdown, etc.)
    paste_delivery.py           # Win32 paste simulation + keyboard typing
    drag_export.py              # Native Windows file drag-out (CF_HDROP)
    contextmenu.py              # Context menu builder (pure logic)
    command_center.py           # Hotkey-action system
    capture_rules.py            # Armed/ignore next copy modes
    capture_receipts.py         # File + event receipts for captures
    capture_debug.py            # Opt-in capture diagnostics
    app_receipt.py              # App proof receipt export
    vault_lock.py               # PIN/passphrase privacy lock (PBKDF2)
    vault_macros.py             # Macro/snippet storage + management
    macro_execute.py            # Macro execution engine
    macro_receipts.py           # Macro action receipts
    macro_shortcut_listener.py  # Low-level keyboard hook for text triggers
    macro_variables.py          # {date}, {time}, {clipboard} expansion
    image_assets.py             # Screenshot/image asset storage + DIB<->PNG
    lan_ip.py                   # LAN IPv4 detection for mobile pairing
    win_mouse.py                # Mouse side-button handler
    capabilities.py             # Feature capability registry
    mobile/
      api.py                    # Mobile API routes + clip serialization
      bridge.py                 # HTTP server for phone <-> PC
      connection_doctor.py      # Connectivity diagnostics
      discovery.py              # mDNS/Bonjour service advertisement
      inbox.py                  # Mobile-to-PC "Send to Desktop"
      models.py                 # PairedDevice + MobileAccessReceipt
      receipts.py               # Persistent mobile receipt log
  ui/                           # CustomTkinter desktop shell
    shell.py                    # Main app window (4,062 lines, god class)
    theme.py                    # Theme/styling factory
    clip_list.py                # List view for clips
    clip_grid.py                # Grid/tile view for clips
    preview.py                  # Detail preview pane
    filters.py                  # Sidebar filter panel
    dialogs.py                  # Settings, About, Edit, Safe, Collection dialogs
    toast.py                    # Auto-dismiss toast notifications
    tooltip.py                  # Hover tooltip system
    tray.py                     # System tray icon (pystray)
    icon.py                     # App icon loader
    scroll_patch.py             # Monkey-patch for CTk scroll fix
    win_scroll.py               # Windows smooth scrolling
    quick_paste.py              # Global hotkey paste picker
    command_center.py           # Hotkey action editor dialog
    home_dashboard.py           # Dashboard/stats view
    receipt_ledger.py           # Receipt browser dialog
    macro_dialogs.py            # Macro create/edit/template dialogs
    macro_picker.py             # Inline macro picker popup
    vault_lock.py               # Lock/unlock screen UI
    vault_screens.py            # Multi-tab vault management (816 lines)
    mobile_dialogs.py           # Mobile pairing dialogs
    pairing_help.py             # Pairing instruction text
    first_use_guide.py          # Onboarding guide
    founder.py                  # Founder license management UI
    guide_copy.py               # Onboarding text + forbidden claim checks
    crashlog.py                 # Crash logging to file
    duplicate_dialog.py         # Duplicate resolution dialog
```

---

## 3. What's Working (Green)

### Core Engine -- Fully Working
- **Clipboard monitoring** -- Event-based (`AddClipboardFormatListener`) with polling fallback. Captures text and image clipboard content reliably.
- **Smart classification** -- Rule-based classifier for links, code, commands, paths, emails, phone numbers. No AI, deterministic, well-tested.
- **Sensitive detection** -- Detects API keys, JWTs, private keys, credit cards (Luhn-checked), recovery codes, OTPs, high-entropy secrets. Auto-masking and auto-expiry.
- **SQLite storage** -- Full CRUD, soft-delete, filtering, sorting, migration support. Schema covers `clips`, `events`, `clip_assets` tables.
- **Search** -- Structured search with `type:`, `source:`, `sensitive:`, `pinned:` tokens + free text. Substring matching (`LIKE`).
- **Settings** -- 70+ configurable fields with JSON persistence, extensive validation, atomic writes.
- **Event log** -- Metadata-only local event recording. Never stores secrets.
- **Safe file I/O** -- Atomic writes via temp file + fsync + `os.replace`. Corrupt file quarantine with backup.
- **Single instance** -- Windows mutex prevents duplicate app launches.
- **Start with Windows** -- Registry Run key management (HKCU, no admin needed).

### Features -- Fully Working
- **Pin / Favorite / Collections** -- All CRUD operations work. Favorites survive pruning.
- **Recently Removed** -- Soft-delete with restore and permanent delete.
- **Export / Save As** -- Single clips (.txt/.md/.html/.json) and multi-clip (folder or zip with index.html, manifest.json, clips/).
- **Proof Manifests** -- SHA256SUMS.txt, manifest.json, stamped receipts in export packs. Verification functions included.
- **Safes** -- Named logical sections with custom icons and accents.
- **Smart Folders** -- 8 deterministic folders (Recent, Unused, From Phone, Plain Text, URLs, Images, Code, Manual Saves) with SQL filters.
- **Duplicate detection** -- Exact and possible (normalized hash) duplicate grouping with resolution actions.
- **Context menus** -- Full right-click menu with Copy Again, Favorites, Collections, Export, Open/Reveal, Remove.
- **Copy Clean** -- Multiple clean-copy formats (plain text, markdown link, title+link, phone, email, etc.).
- **Editable Copies** -- Immutable originals with versioned working copies. HTML bundle support with asset tracking.
- **Drag-and-drop export** -- Native Windows CF_HDROP file drag-out.
- **Image clipboard** -- DIB-to-PNG conversion, smart filenames, dimension detection.

### Hotkey System -- Fully Working
- **Global quick-paste hotkey** -- `Ctrl+Shift+V` default, configurable, live re-registration.
- **Quick-paste picker** -- Floating overlay with keyboard nav, auto-paste with focus restoration.
- **Paste delivery** -- Win32 thread attachment, Ctrl+V simulation, keystroke typing mode.
- **Command Center** -- Multi-action hotkey system with conflict detection.

### Vault Macros -- Fully Working
- **Macro storage** -- JSON-persisted with Macro Safes, smart types, filtering, search.
- **Macro execution** -- Text shortcut triggers, hotkey triggers, menu-only mode. Clipboard-paste and keystroke output modes.
- **Macro variables** -- `{date}`, `{time}`, `{datetime}`, `{clipboard}`, `{safe_name}`, `{item_id}`, `{newline}`, `{tab}`.
- **Macro receipts** -- Execution logging with sensitive key scrubbing.

### Mobile Bridge -- Fully Working
- **HTTP server** -- ThreadingHTTPServer with token auth, device pairing/revocation.
- **mDNS discovery** -- Zeroconf service advertisement for auto-discovery.
- **Read-only API** -- Browse clips, copy, share, save from phone. No destructive operations allowed.
- **Send to Desktop** -- Text, URL, and image inbox from phone to PC.
- **Connection Doctor** -- Diagnostic reports for troubleshooting pairing issues.
- **Mobile receipts** -- Persistent audit log (500 entries, atomic writes).

### Security -- Fully Working
- **Vault Lock** -- PIN/passphrase with PBKDF2-HMAC-SHA256 (200K iterations), `hmac.compare_digest`.
- **Licensing** -- Ed25519 offline signature verification for Founder edition.
- **Sensitive scrubbing** -- Event log never stores secrets. Receipts strip forbidden keys.
- **Forbidden claims** -- Self-validation prevents marketing overclaims in guide text.

### UI -- Fully Working
- **Main shell** -- Sidebar nav, list/grid views, preview pane, dashboard.
- **Theme** -- Dark/light mode with consistent styling.
- **Tray icon** -- System tray with Show/Pause/Resume/Quit menu.
- **All dialogs** -- Settings, About, Edit, Safe, Collection, Export, Receipt, Founder, Pairing, Duplicates, Macros.
- **First-use guide** -- Onboarding cards on first launch.
- **Crash logging** -- Global exception hook writing to `crash.log`.

### Tests -- All Passing
- **545 tests, 0 failures, 0 errors** in 40 seconds.
- Core logic is fully unit-tested with no GUI dependencies.
- Coverage includes: storage, classify, search, sensitive, export, settings, hotkey, macros, mobile bridge, vault lock, and more.

---

## 4. Bugs Found (Red)

### BUG-1: `source_domain()` uses `.lstrip("www.")` instead of `.removeprefix("www.")`
- **File:** `cache_vault/core/clip_metadata.py`
- **Severity:** HIGH -- corrupts display data
- **Detail:** `host.lower().lstrip("www.")` strips individual characters `w`, `.` from the left, not the prefix `"www."`. Example: `"www.wikipedia.org"` becomes `"ikipedia.org"` instead of `"wikipedia.org"`.
- **Fix:** Change to `host.lower().removeprefix("www.")` (Python 3.9+).

### BUG-2: `storage.py` threading lock is created but never acquired
- **File:** `cache_vault/core/storage.py`
- **Severity:** HIGH -- data corruption risk
- **Detail:** `self._lock = threading.Lock()` is created in `__init__` but never used with `with self._lock:` anywhere. All DB operations are unprotected. The clipboard monitor runs on a separate thread and calls `add_clip()` concurrently with UI reads. SQLite in WAL mode may handle some concurrency, but the lack of locking could cause "database is locked" errors or data races.
- **Note:** The mobile bridge in `bridge.py` actually tries to acquire `self.vault.storage._lock` (accessing the private attribute), but since the lock is never held by storage itself, this is a no-op.

### BUG-3: `safes.py` `rename()` loses all customization
- **File:** `cache_vault/core/safes.py`
- **Severity:** MEDIUM -- user data loss
- **Detail:** When renaming a Safe, a new `Safe` object is created with only `id`, `name`, `builtin`, `created_at`. All customization fields (icon, accent, description, visual_style, etc.) are reset to defaults.
- **Fix:** Copy all fields from the old Safe when creating the renamed version.

### BUG-4: Duplicate `toggle_favorite` context menu key
- **File:** `cache_vault/core/contextmenu.py`
- **Severity:** MEDIUM -- UI dispatch ambiguity
- **Detail:** Two `MenuItem` objects use the key `"toggle_favorite"` -- one for the actual favorite toggle and one for "Mark Keep". The UI dispatcher can't distinguish them.
- **Fix:** Give the second item a distinct key like `"mark_keep"`.

### BUG-5: `macro_shortcut_listener.py` `stop()` doesn't exit message loop
- **File:** `cache_vault/core/macro_shortcut_listener.py`
- **Severity:** MEDIUM -- thread leak
- **Detail:** `stop()` unhooks the keyboard hook but doesn't post `WM_QUIT` to break the `GetMessageW` loop in `_run()`. The thread hangs until process exit.
- **Fix:** After unhooking, post `WM_QUIT` to the hook thread's message queue.

### BUG-6: `win_mouse.py` uses `SetWindowLong` on 64-bit
- **File:** `cache_vault/core/win_mouse.py`
- **Severity:** MEDIUM -- potential crash on 64-bit Python
- **Detail:** Uses `SetWindowLong` / `GetWindowLong` which can't handle pointer-sized values on 64-bit. Should use `SetWindowLongPtrW` / `GetWindowLongPtrW`.

### BUG-7: `duplicate_dialog.py` crashes on None attributes
- **File:** `cache_vault/ui/duplicate_dialog.py`
- **Severity:** LOW-MEDIUM -- crash on edge case
- **Detail:** Lines 55-58 use `min(c.created_at ...)`, `max((c.date_used or c.created_at) ...)`, `sum(c.use_count ...)` which will raise `TypeError` if any clip has `None` for `created_at`, `date_used`, or `use_count`.

### BUG-8: `first_use_guide.py` closing always triggers "start" action
- **File:** `cache_vault/ui/first_use_guide.py`
- **Severity:** LOW -- minor UX issue
- **Detail:** Closing the guide window (X button) always fires `_on_action("start")`, even if the user didn't intend to start. May not be a problem in practice.

---

## 5. Performance Concerns (Yellow)

### PERF-1: `licensing.py` reads + verifies license from disk on every call
- **File:** `cache_vault/licensing.py`
- **Impact:** Every `is_feature_enabled()` / `is_founder_unlocked()` call does file I/O + Ed25519 crypto. No caching. Called via `feature_gate.py` which could be invoked per-clip or per-render.
- **Fix:** Cache the license status with a TTL or check-once-per-session.

### PERF-2: `vault.py` `macros` property creates a new `MacroStore()` every access
- **File:** `cache_vault/core/vault.py`
- **Impact:** Every call to `self.macros` instantiates a fresh `MacroStore`, which reads the macros JSON file from disk.
- **Fix:** Cache the `MacroStore` instance on the `Vault` object.

### PERF-3: `vault_macros.py` `macro_filter_counts()` is O(n*m*n)
- **File:** `cache_vault/core/vault_macros.py`
- **Impact:** Calls `apply_macro_filter()` for every filter key, and many filters call `macro_issues()` which iterates all macros. Slow with many macros.

### PERF-4: `command_center.py` `HotkeyActionStore` reads/writes full JSON on every operation
- **File:** `cache_vault/core/command_center.py`
- **Impact:** `get()`, `upsert()`, `delete()` all call `load_all()` (full file read) every time.

### PERF-5: Mobile receipt log has O(n) per-write cost
- **File:** `cache_vault/core/mobile/receipts.py`
- **Impact:** Every `record()` reads the entire file, appends one entry, rewrites the whole file. Acceptable at 500-entry cap but could cause I/O contention under load.

---

## 6. Dead Code & Unused Imports (Gray)

| File | Issue |
|------|-------|
| `core/hotkey.py` | `import time` -- unused |
| `core/hotkey.py` | `import win32api` -- imported but never used in this module |
| `core/exports.py` | `verify_export_pack = None` on line 37 -- overwritten by function def on line 606 |
| `core/single_instance.py` | Visibility/iconic check in `_enum` callback -- dead branch, no effect |
| `core/app_receipt.py` | `import os` -- unused |
| `core/copy_clean.py` | `COPY_ADDRESS` action -- always returns `None`, never in available actions |
| `core/copy_clean.py` | `COPY_RECEIPT_SUMMARY` constant -- defined but never handled in dispatch |
| `core/paste_delivery.py` | `Optional` and `Callable` from `typing` -- unused (code uses `X \| None`) |
| `core/mobile/api.py` | `INBOX_GET_ROUTES` frozenset -- defined but never referenced |
| `core/mobile/api.py` | `FILTER_SEARCH_ALL` import -- unused in this file |
| `core/mobile/models.py` | `field` from `dataclasses` -- imported but never used |
| `core/mobile/discovery.py` | `import threading` -- unused |

---

## 7. Code Quality Concerns (Orange)

### QUALITY-1: God class -- `shell.py` is 4,062 lines
- The main app window class handles everything from clipboard capture to macro execution to mobile bridge management. Should be split into controllers/presenters.

### QUALITY-2: ~50+ broad `except Exception: pass` blocks across UI layer
- While many are intentional (Tk widget lifecycle), some could mask real bugs. Most are annotated with `# noqa: BLE001`.

### QUALITY-3: Private attribute access across widget boundaries
- `shell.py` accesses `_clip`, `_image_ready`, `_toggle_section`, `_screens` on child widgets via `# noqa: SLF001`. These should be public APIs.

### QUALITY-4: Dynamic attribute injection in `vault_screens.py`
- 8 instances of `parent._refresh = reload  # type: ignore[attr-defined]` -- fragile duck-typing.

### QUALITY-5: Vault capture pipeline duplicated 4 times
- `vault.py` has near-identical code in `capture()`, `capture_mobile_share()`, `capture_image()`, `capture_mobile_image_share()` (~400 lines of duplication).

### QUALITY-6: `FORBIDDEN_CLAIMS` lists duplicated in 5+ files
- `clip_accents.py`, `copy_clean.py`, `vault_lock.py`, `drag_export.py`, `capabilities.py`, `guide_copy.py` all define their own forbidden-claims lists. Should be one source of truth.

### QUALITY-7: Inconsistent ID generation
- `safes.py` uses `uuid.uuid4().hex` directly while `models.new_id()` provides the same functionality. Should use `new_id()` everywhere.

### QUALITY-8: `SAFE_PREFIX = "safe:"` defined in both `safes.py` and `storage.py`

### QUALITY-9: Inconsistent type hint style
- Mixes `Optional[str]` (old style) and `str | None` (new style) within the same files.

---

## 8. Thread Safety Concerns

| Area | Risk | Detail |
|------|------|--------|
| `storage.py` | HIGH | Lock exists but is never acquired. Clipboard thread writes while UI thread reads. |
| `mobile/receipts.py` | MEDIUM | Concurrent `record()` calls can cause lost updates (read-append-write race). |
| `mobile/bridge.py` | MEDIUM | `_touch_device()` calls `settings.save()` outside any lock. `ThreadingHTTPServer` means concurrent requests. |
| `macro_shortcut_listener.py` | LOW | `_handle_key()` modifies `_buffer` on hook thread while `update()` modifies `_macros` on main thread. |

---

## 9. Security Notes

| Area | Status |
|------|--------|
| Vault Lock | Good -- PBKDF2 with 200K iterations, `hmac.compare_digest` for timing-safe comparison |
| License verification | Good -- Ed25519 with graceful fallback when `cryptography` missing |
| Sensitive detection | Good -- Conservative but catches keys, JWTs, private keys, credit cards, OTPs |
| Event log | Good -- Never stores secret content. `_FORBIDDEN_DETAIL_KEYS` strips sensitive keys |
| Mobile API | Good -- Bearer token auth, destructive routes blocked, receipt logging |
| Token hashing | OK -- SHA-256 without salt. Acceptable given 256-bit token entropy |
| Secrets in logs | Good -- Clipboard contents never written to logs or console |
| Base64 secrets with `/` | Gap -- `_high_entropy_secret()` excludes strings containing `/`, but base64 commonly has `/` |

---

## 10. Not Implemented (By Design)

These are explicitly documented as out of scope for v0.1.4 MVP:

- Cloud sync / remote backup
- User accounts / subscription
- Browser extension
- Standalone mobile app (phone companion only via LAN bridge)
- OCR
- AI classification
- Full-text search index (uses substring `LIKE` matching)
- Content encryption at rest (schema supports future addition)
- Cross-platform (Windows-only)

---

## 11. Dependency Map

```
Runtime:
  customtkinter >= 5.2.0      # Desktop GUI framework
  pystray >= 0.19.0            # System tray icon
  Pillow >= 10.0.0             # Image handling (DIB<->PNG, tray icon)
  pywin32 >= 306               # Win32 APIs (clipboard, hotkeys, paste)
  zeroconf >= 0.131.0          # mDNS for mobile discovery
  cryptography >= 42.0.0       # Ed25519 license verification
  pyperclip >= 1.8.0           # Cross-platform clipboard fallback

Dev:
  pytest >= 8.0                # Test runner
  pyinstaller >= 6.0           # Exe packaging
```

---

## 12. Quick Reference -- File Responsibility Map

| If you need to change... | Look at... |
|--------------------------|-----------|
| Clipboard capture logic | `core/clipboard.py`, `core/vault.py` (capture methods) |
| Content classification | `core/classify.py` |
| Sensitive detection | `core/sensitive.py` |
| Database schema/queries | `core/storage.py` |
| Search parsing | `core/search.py` |
| Settings fields | `core/settings.py` |
| Export formats | `core/export.py` (single/multi), `core/exports.py` (proof packs) |
| Hotkey registration | `core/hotkey.py` |
| Paste simulation | `core/paste_delivery.py` |
| Quick-paste picker UI | `ui/quick_paste.py` |
| Macro system | `core/vault_macros.py` (storage), `core/macro_execute.py` (engine) |
| Mobile bridge | `core/mobile/bridge.py` (server), `core/mobile/api.py` (routes) |
| Phone pairing | `core/mobile/bridge.py`, `ui/mobile_dialogs.py` |
| Main app window | `ui/shell.py` (warning: 4,062 lines) |
| Vault lock | `core/vault_lock.py` (logic), `ui/vault_lock.py` (UI) |
| Licensing | `licensing.py`, `feature_gate.py` |
| Brand constants | `brand.py` |
| Tray icon | `ui/tray.py` |
| Onboarding | `ui/first_use_guide.py`, `ui/guide_copy.py` |

---

## 13. Summary Scorecard

| Category | Status | Notes |
|----------|--------|-------|
| Core engine | WORKING | All capture, classify, store, search, export flows operational |
| Test suite | PASSING | 545/545 tests pass |
| Smart classification | WORKING | 7 content types, deterministic rules |
| Sensitive handling | WORKING | Detection, masking, auto-expiry all functional |
| Quick-paste hotkey | WORKING | Global hotkey + picker + auto-paste |
| Vault Macros | WORKING | Full CRUD, triggers, execution, receipts |
| Mobile Bridge | WORKING | HTTP server, pairing, inbox, receipts, mDNS |
| Export / Proof Packs | WORKING | Manifests, SHA256SUMS, stamped receipts |
| Vault Lock | WORKING | PBKDF2, timing-safe verification |
| Licensing | WORKING | Ed25519 offline verification |
| Thread safety | NEEDS FIX | Storage lock unused, mobile receipt races |
| `source_domain()` | BUG | `.lstrip("www.")` corrupts domains |
| Safe rename | BUG | Loses customization |
| Context menu keys | BUG | Duplicate key prevents dispatch |
| God class (shell.py) | TECH DEBT | 4,062 lines, needs decomposition |
| Code duplication | TECH DEBT | Capture pipeline x4, forbidden claims x5+ |
| Performance | ACCEPTABLE | License/macro reads hit disk each time but tolerable at MVP scale |
