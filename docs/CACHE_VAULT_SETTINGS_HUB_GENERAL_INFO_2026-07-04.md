# Cache Vault — Settings Hub General Info (12C)

Date: 2026-07-04
Branch: `fix/settings-hub-general-info`
Base: `release/v0.1.4-public-distribution` @ `a97f602` (post-12A)
Type: **Code fix.** Implements 12C from
`docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md` (Q6/Q7/Q9),
scoped per explicit follow-up direction (see "Explicitly excluded" below).

## The gap

The audit flagged that `SettingsHub`'s "General" category shows only
`start_with_windows` — there is no way to see the app version/release, tell
a packaged build from a source checkout, or reach the app's data folder.
All three exist today only in the old `SettingsDialog` fallback (footer
`version_line()` text, and a "Founder"/"About" chrome the Hub never
receives) or nowhere at all (packaged-vs-source, data folder).

## Design decision: why a module, not new `SettingsField`s

`validate_schema_against_settings()` requires every `SettingsField.key` to
be a real attribute on the `Settings` dataclass (checked against
`typing.get_type_hints(Settings)`). Version, release label, packaged-vs-
source, and the data folder path are **not** user settings — they are
constants and runtime/filesystem facts that must never round-trip through
`Settings.save()`/`load()`. There is no `readonly`-field path that doesn't
require inventing a fake `Settings` attribute for values that were never
meant to persist.

The clean fit reuses the exact machinery 12A just finished: a **status
card**. A new `GeneralInfoModule` (`modules/general_info/__init__.py`)
implements only `get_status_rows()` — `get_settings_schema()` stays at the
`ModuleManifest` ABC's default (`[]`), so it adds no sidebar entry of its
own. It registers with `id="general"`, the same id as the existing
**global** "General" category, so `_render_category_view()`'s existing
lookup (`module = next(m for m in registry.all() if m.id == category_id)`)
finds it automatically — the status card renders above the
`start_with_windows` toggle on the same page, with zero changes to
`settings_hub.py`. This required no new field type, no validator change,
and no renderer change; 12A's generic `row.action` button rendering is
reused as-is.

Version display reuses the existing `Version {X} · {label}` format from
`ui/dialogs.version_line()` verbatim, but the three-line formatting logic
is duplicated locally rather than imported — every module in
`cache_vault/modules/` is free of any dependency on `cache_vault/ui/`, and
this keeps it that way.

## The fix

`GeneralInfoModule.get_status_rows()` returns four rows:

- **Version** — `version_line()`-equivalent text (e.g. "Version 0.1.4 ·
  Public Release"). No action.
- **Running from** — "Packaged build" or "Running from source", from the
  same `getattr(sys, "_MEIPASS", None)` check already used by
  `ui/theme.py` and `ui/icon.py`. No action.
- **Data folder** — the real resolved path
  (`default_settings_path().parent`, i.e. `%LOCALAPPDATA%\CacheVault`).
  Action: **"Open Data Folder"**, unconditional (no external wiring
  needed — it creates the folder if missing and opens it via the existing
  `core/pathutil.open_path()`, the same helper the Mobile Access Receipts
  folder button already uses).
- **First-use guide** — a short description of what the guide covers.
  Action: **"Show first-use guide again"** (exact label reused from
  `ui/guide_copy.SETTINGS_SHOW_GUIDE_AGAIN`, hardcoded locally for the same
  modules-stay-independent-of-ui reason as `version_line()` above), wired
  only when the shell supplies `show_guide_action`; omitted, the row
  renders with no button.

`build_default_registry()` gained one new optional kwarg,
`show_guide_action`, threaded into `GeneralInfoModule`. `shell.py.
_open_settings()` passes its real, already-shipped
`self._open_first_use_guide_from_settings` — the same method the old
`SettingsDialog`'s `help={"show_guide": ...}` already calls.

## Scope decision: About / Founder reachability

The audit flagged About/Guide/Founder as unreachable from `SettingsHub`
and left the call open. Tracing the old dialog shows they are not uniform:
"Show first-use guide again" is normal General-tab content (a button among
Startup/History/Excluded-apps), which is why it fits the row pattern above.
"About" and "Founder" are dialog **chrome** in the old dialog — a
persistent footer button (About, next to `version_line()`) and a persistent
header block (Founder license import), not tab content. Folding those in
would mean adding new chrome regions to `SettingsHub` itself, not just
status rows — a bigger structural change than this pass's scope.

Per direction received while scoping this PR: fold in "Show first-use
guide again" only; **About and Founder reachability remain deferred** to
later, chrome-level work.

## Files changed

```
cache_vault/modules/general_info/__init__.py  — new: GeneralInfoModule (4 status rows)
cache_vault/modules/registry.py               — build_default_registry(show_guide_action=...)
cache_vault/ui/shell.py                       — _open_settings() threads show_guide_action
tests/test_module_registry.py                 — registry tests + 2 pre-existing count/id-set fixes
tests/test_settings_hub_integration.py        — end-to-end: _open_settings() wires the real guide method
```

No `settings_hub.py` changes — the renderer and category-lookup machinery
already supported this exactly as built for 12A/12B. Not part of this PR:
About/Founder reachability (deferred, see above), diagnostics fields like
database path (12D), any broad Settings redesign, bulk Revoke All, any
Android/APK change, any public/proof/release surface, version/build value
*changes* (only surfacing the existing `__version__`/`__release_label__`
constants, never editing them).

## Tests added

- `test_build_default_registry_threads_show_guide_action` — registry-level:
  `show_guide_action` lands on the "First-use guide" row with the correct
  label; other rows stay untouched; "Data folder"'s action is present
  unconditionally; omitting the kwarg reproduces the no-button default.
- `test_general_info_module_status_rows` — registry-level: Version/Running
  from/Data folder values are computed correctly, and
  `get_settings_schema()` is empty (no new sidebar entry).
- `test_general_info_module_open_data_folder_action` — the Data folder
  action creates the real settings folder if missing and opens it via
  `pathutil.open_path`, verified with `monkeypatch` (no dependency on
  external kwargs, unlike the mobile actions or `show_guide_action`).
- `test_open_settings_wires_show_guide_action_into_registry` — end-to-end:
  `CacheVaultApp._open_settings()` hands `SettingsHub` a registry whose
  "First-use guide" row action calls the app's real
  `_open_first_use_guide_from_settings`, not a placeholder.

Two pre-existing tests were updated for the new fifth module: exact
module-count/id-set assertions in `test_build_default_registry` and
`test_health_report` now include `"general"`.

## Gates run

```
python -m pytest -q            → pass (full suite, including 4 new tests + 2 updated assertions)
python -m compileall cache_vault → pass, no syntax errors
python app.py --selftest        → selftest OK
```

## Verdict

Surfaces version/release, packaged-vs-source, and the data folder (with a
working "Open Data Folder" action) in `SettingsHub` for the first time,
plus reconnects "Show first-use guide again", using only machinery that
already existed and was already tested (12A's action-button rendering,
the existing `id`-matched status-card lookup, `pathutil.open_path`). About
and Founder reachability remain open, deferred work.
