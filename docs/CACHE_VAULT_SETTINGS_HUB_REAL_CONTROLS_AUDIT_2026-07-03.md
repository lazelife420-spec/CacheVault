# Cache Vault — Settings Hub Real Controls / Live Status Audit

Date: 2026-07-03
Branch: `audit/settings-hub-real-controls`
Base: `release/v0.1.4-public-distribution` @ `8bbdac9`
Type: **Audit only. No code changes.**

Already closed (context, not re-litigated here):
- PR #10 — Settings ownership / single-instance / z-order
- PR #11 — Settings Hub shared hotkey recorder
- `f56c6ec` stale-EXE receipt stayed excluded from release

---

## 1. Which Settings sections already exist?

`ModuleRegistry.settings_categories()` returns global categories (fixed list in
`cache_vault/modules/registry.py`) followed by per-module categories, ordered by
`_CATEGORY_ORDER`. Rendered sidebar today, in order:

| Category id | Label | Source | Fields |
|---|---|---|---|
| `general` | General | global | 1 (`start_with_windows`) |
| `capture` | Capture | global | 7 |
| `shortcuts` | Keyboard Shortcuts | global | 5 hotkeys |
| `quick_paste` | Quick Paste | `QuickPasteModule` | 4 |
| `macros` | Snippet Macros | global | 10 |
| `mobile_bridge` | Mobile Bridge | `MobileBridgeModule` | 3 + 5 status rows |
| `proof` | Proof & Receipts | `ProofModule` | 2 |
| `display` | Display | global | 2 |
| `image_viewer` | Images | `ImageViewerModule` | 0 (placeholder) |
| `vault_lock` | Vault Lock | global | 9 |
| `history` | History | global | 1 |

11 sections total. `image_viewer` is an intentional placeholder (its own
docstring: "Standalone launcher and gallery UI come in Chunk B").

## 2. Which controls are real and working?

Every rendered `toggle` / `number` / `text` (scalar) / `choice` field goes
through one generic, genuinely-wired pipeline:

`_render_field_row` binds a `Var` → `_collect_settings()` builds a new
`Settings` object → `_save()` → `on_save(new_settings)` → shell.py
`_apply_settings()` → `settings.save()` **plus real side-effect syncs**:
hotkey rebinds, macro rebinds, capture-hotkey rebinds, text-shortcut resync,
Windows scroll cache refresh, vault-lock screen update, and (in a background
thread) `self._mobile_bridge.sync(settings)`.

Specifically verified as fully real, end to end:
- **Hotkey fields** (`shortcuts` category): real `DialogHotkeyRecorder`,
  duplicate/conflict validation blocks Save (PR #11).
- **`start_with_windows`**: `cache_vault/core/startup.py` does real
  `winreg` `HKEY_CURRENT_USER\...\Run` key writes/deletes; `shell.py`
  (`_apply_settings`) calls `startup.sync(settings.start_with_windows)` on
  every save, regardless of which settings dialog was used.
- **Mobile Access enable / port / bind host**: saving these fields does
  reach the real bridge — `shell.py._apply_settings()` calls
  `self._mobile_bridge.sync(settings)` when `needs_sync()` is true. The
  *controls* work; only the *status display* for them is broken (see Q5).
- **Vault Lock, Display/scroll, Capture, Macro, Quick Paste, Proof/expiry,
  History fields**: all are genuine `Settings` dataclass fields consumed
  elsewhere in the app (vault_lock module, scroll patch, macro executor,
  capture controller, sensitive-expiry sweep) and pass the same
  generic/type-checked save pipeline. Not individually re-traced end-to-end
  in this pass, but nothing found that fakes them.

## 3. Which controls are missing from the renderer?

- **`StatusRow.action` / `action_label` are never rendered.** The dataclass
  (`settings_schema.py`) declares both fields, but `_render_status_card()` in
  `settings_hub.py` only draws `row.label` and `row.value_getter()` — there
  is no button/action code path at all, so even a module that populated
  `action`/`action_label` today would get no UI for it.
- **No field type renders a standalone action button** that isn't a Settings
  value (e.g. "Open Data Folder"). Current `field_type`s are `toggle`,
  `text`, `number`, `choice`, `hotkey`, `readonly` — all value-bound.
- **Confirmed live bug — "Excluded apps" (`capture` category) silently
  discards edits.** `excluded_apps: list[str]` renders as a **`text`**
  field (`_FIELD_TYPE_TO_PYTHON["text"]` permits `list`), so the CTkEntry
  shows `str(list_value)` (Python list repr, e.g. `[]`) and *looks*
  editable. But `_collect_settings()` has:
  ```python
  elif isinstance(orig_val, list):
      # We don't support editing lists directly yet, but keep them
      pass
  ```
  Any text the user types into that field is **thrown away on Save** — the
  original list value is kept. This is a real fake-control bug already in
  production, not a hypothetical. No other list-typed `Settings` field
  (`user_safes`, `paired_devices`, `user_macro_safes`,
  `sidebar_collapsed_sections`) is declared as a `SettingsField`, so this is
  isolated to `excluded_apps`.

## 4. Which StatusRow actions exist but are not rendered?

None are populated yet — `MobileBridgeModule.get_status_rows()` (the only
module that returns any status rows) sets `action`/`action_label` on none
of its 5 rows (Bridge, LAN discovery, LAN IP, Last phone request, Paired
devices). Combined with Q3, the capability is doubly inert: nothing sets an
action, and the renderer couldn't draw one if something did.

The *real* mobile actions a user would expect here already exist as working
shell.py methods, but are wired only to the **old** `SettingsDialog`
fallback (`mobile={"pair": ..., "devices": ..., "receipts": ...}`), and are
**not passed to `SettingsHub` at all**:
- `_open_pair_android()` — real pairing flow
- `_open_paired_devices()` — real paired-devices dialog
- `_revoke_all_mobile_and_refresh()` — real revoke-all flow
- `_open_mobile_receipts()` — real receipts dialog
- `_mobile_doctor_report()` — real connection-doctor diagnostics

`SettingsHub.__init__` only receives `(master, settings, registry, on_save,
on_close)` — there is currently no channel for shell.py to hand these
callables (or the live bridge) into the Hub.

## 5. Why does Mobile Bridge status say "Bridge not started" while the top bar says "Paired"?

Root cause, fully traced:

- `CacheVaultApp.__init__` creates **one real, live** bridge:
  `self._mobile_bridge = MobileBridge(self.vault)`. The top bar / Home
  dashboard / mobile-access screen all read status from *this* instance
  directly (`_mobile_access_report()` uses `self._mobile_bridge.is_running`,
  `.discovery.is_advertising`, `.receipts`; pairing counts come from
  `self.vault.dashboard_summary()`).
- `shell.py._open_settings()` builds a **brand-new, disconnected** registry
  on every single Settings open:
  ```python
  registry = build_default_registry()
  self._settings_window = SettingsHub(self, self.vault.settings, registry, ...)
  ```
- `build_default_registry()` (`modules/registry.py`) does
  `reg.register(MobileBridgeModule())` — **no arguments**. `MobileBridgeModule.__init__`
  defaults `bridge_ref=None`, `receipts_getter=None`, `mdns_status_getter=None`.
- Every status closure in `MobileBridgeModule.get_status_rows()` starts with
  `if self._bridge is None: return "Not started"` / `"Bridge not started"`.
  Since `self._bridge` is always `None` for the registry built in
  `_open_settings()`, Settings **always** shows the off state, independent
  of whether the real bridge is running or has paired devices.

The two code paths (app-level live `MobileBridge` vs. Settings-Hub-level
disposable `MobileBridgeModule`) never share state. Nothing currently wires
`bridge_ref=self._mobile_bridge` (or `receipts_getter` /
`mdns_status_getter`) through to the module when the registry is built.

## 6. Where can version/build info come from?

- `cache_vault/__init__.py`: `__version__ = "0.1.4"`,
  `__release_label__ = "Public Release"` — both already imported and used
  today by `AboutDialog` (`ui/dialogs.py`, `Version {__version__}`) and by
  the mobile bridge's `/mobile/v1/status` API response
  (`cache_vault_version: __version__`).
- No separate build number/date exists — only the semantic version string
  and the release label.
- Packaged-vs-source detection: the codebase already uses
  `getattr(sys, "_MEIPASS", None)` in `ui/theme.py` and `ui/icon.py` to
  detect a PyInstaller-frozen runtime; the same check is safe to reuse for
  a "Running from: packaged build / source" readonly row.

## 7. Which diagnostics actions are already callable?

| Action | Existing helper | Notes |
|---|---|---|
| Open data folder | `default_settings_path().parent` + `pathutil.open_path()` | Already used by `shell.py._open_receipts_folder()` |
| Open crash log | `crashlog.log_path()` (`%LOCALAPPDATA%\CacheVault\crash.log`) + `pathutil.open_file()` | File may not exist yet — needs an existence check, not a fake button |
| Database path | `self.vault.storage.db_path` | Real attribute, not surfaced in any UI today |
| Per-module health check | `registry.health_report()` / `ModuleManifest.run_health_check()` | Real and implemented (mobile_bridge has a real check via `connection_doctor_report`); currently only invoked from each module's own `python -m cache_vault.modules.<name>` CLI entry point, never from the running app |
| Connection doctor report | `shell.py._mobile_doctor_report()` | Real, comprehensive; currently only feeds `PairAndroidDialog` |
| Selftest | `python app.py --selftest` | **CLI-only.** Per your own rule, this must not become a fake button — show as a copyable command instead if surfaced at all |

## 8. Which settings should remain deferred?

- **Theme selector** — no persisted theme setting exists anywhere on
  `Settings`; do not add.
- **Cloud/sync options** — no such settings or backing code exist.
- **Backup/export-settings** — the existing "export" features
  (`_export_view`, `_export_clip_proof`) export clip/proof data, not
  app configuration; no settings-export mechanism exists.
- **Retention rules beyond `history_max_clips`** — already exposed
  (History category); no other retention config exists.
- **`image_viewer` module settings** — explicitly out of scope per its own
  docstring (standalone gallery is future work).
- **Module health-check surfacing in the UI** — real and callable (Q7), but
  touches every module's category; treat as an optional, separate
  diagnostics decision rather than folding it into 12A–12D by default.
- **Fixing "Excluded apps" (Q3 bug)** — needs an explicit decision: either a
  real multi-line list editor, or (minimally) making it `readonly` until a
  real editor exists, so it stops silently discarding user input. Recommend
  folding the minimal fix into whichever PR touches the `capture` category
  first, or its own tiny bugfix PR — flagging here rather than fixing now
  since this branch is audit-only.

## 9. Recommended split PRs

Your proposed split matches what the audit found and is sound as-is:

- **12A — StatusRow action rendering**: teach `_render_status_card` to draw
  a button from `row.action` / `row.action_label` when present; add tests.
  No module needs to populate an action yet for this PR to be correct and
  testable (render nothing when absent, as today).
- **12B — Mobile Bridge live status**: thread `bridge_ref` (and ideally
  `receipts_getter` / `mdns_status_getter`) from `self._mobile_bridge` into
  `MobileBridgeModule` at `_open_settings()` time; wire Paired
  Devices / Pair / Revoke-All / Receipts as real StatusRow actions (built on
  12A). This is the fix for Q5.
- **12C — General/version/build/data-folder**: add `__version__` /
  `__release_label__` as `readonly` fields, "Open Data Folder" using the
  existing helper, packaged-vs-source via the existing `_MEIPASS` pattern.
  `start_with_windows` is already real — no work needed there beyond
  keeping it.
- **12D — Diagnostics actions**: "Open Crash Log" (existence-checked),
  database path (readonly), and optionally connection-doctor / health-check
  surfacing. Selftest stays CLI-only per your rule — do not add a button
  for it.
- **12E — polish**: only after the above land; copy/density/labels only, no
  new features, per your forbidden list.

One item outside your five buckets: **About / First-Use Guide / Founder
license dialogs are currently unreachable from `SettingsHub`** — they're
wired only into the old `SettingsDialog` fallback via the `help={...}` dict
that `_open_settings()` never passes to `SettingsHub`. This is a gap, not
a fake control (nothing renders and fails), so it doesn't block any of
12A–12E, but you may want to fold "About / version" access into 12C's scope
explicitly, or defer it. Flagging for your call, not deciding here.

## 10. Final verdict

**AUDIT_ONLY / NO_CODE_CHANGES.**

This branch and this document contain no modifications to
`cache_vault/`, `tests/`, or any runtime file. Findings above are ready to
drive 12A–12E as separate, small PRs per your custody rules.
