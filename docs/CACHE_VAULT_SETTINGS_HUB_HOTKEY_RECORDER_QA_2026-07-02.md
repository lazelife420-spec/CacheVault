# Cache Vault - Settings Hub Hotkey Recorder Consistency

- Date: 2026-07-02
- Lane: Settings Hub hotkey recorder consistency (narrowed from the broader "real controls" request)
- Branch: `fix/settings-hub-real-controls`
- Base decision: branched from `fix/settings-z-order-window-ownership` (NOT `release/v0.1.4-public-distribution`). Rationale below.

## Verdict

```text
Settings Hub hotkey recorder: PASS
Full Settings real-controls pass: DEFERRED / HOLD
```

This receipt covers only the Settings Hub hotkey recorder consistency work. It is NOT the full Settings redesign; the audit found real Settings problems that were intentionally deferred (see below).

## Implemented

- Settings Hub hotkey fields now use the shared `DialogHotkeyRecorder` (same recorder as Hotkey Actions and Macro setup). No second recorder was created.
- Recording state shows `Press keys now... Esc to cancel.`; the Record button toggles to `Recording...`.
- A recorded combo is written into the field.
- Esc cancels and does not record `esc`.
- Retry after cancel works.
- Invalid / duplicate / conflicting shortcuts are blocked with inline validation and Save is refused (footer error) until fixed.
- Close-while-recording is safe; category switch / search re-render / window close tear down recorders so no stale owner bindings or callbacks touch destroyed widgets.

## Not implemented (deferred / HOLD)

- Full Settings "real controls" pass.
- Mobile Bridge live-status fix (registry builds `MobileBridgeModule()` with no `bridge_ref`, so Settings says "Bridge not started" while the top bar says "Mobile: Paired"). Needs its own lane: "Settings Hub real controls / live status pass".
- Action-button rendering for `StatusRow` (`action` / `action_label` exist but the renderer ignores them).
- Version / build display in Settings.
- Diagnostics / settings expansion (General is sparse; Receipts & Diagnostics have no actions).

## Files changed (this lane, e84db47)

- `cache_vault/ui/settings_hub.py` (hotkey field render + validation + recorder lifecycle)
- `tests/test_settings_hub.py` (recorder tests)
- `docs/CACHE_VAULT_SETTINGS_HUB_HOTKEY_RECORDER_QA_2026-07-02.md` (this receipt)

Mobile bridge, registry, settings_schema, Android, /proof, and all release surfaces were NOT touched.

## Base-branch rationale

Stated base was `release/v0.1.4-public-distribution`, but the current branch carries `3bfdb34 "fix: keep settings hub owned and single-instance"` which modifies `settings_hub.py` (the exact file this lane edits) and is not on release. Branching from release would have edited a stale `settings_hub.py` and lost/conflicted that fix. Both the recorder (PR #9 `38a10b8`) and the single-instance fix are on the chosen base.

## Custody audit vs origin/release/v0.1.4-public-distribution

Commits after release (5): `3bfdb34` (code, single-instance/z-order), `1b9d5ba` + `a641f7b` (docs, z-order receipts), `f56c6ec` (docs, hotkey visible-regression receipt), `e84db47` (code, this lane).

- `3bfdb34` is included (confirmed ancestor of HEAD).
- Changed files are only Settings Hub code (`settings_hub.py`, `shell.py`), its tests (`test_settings_hub.py`, `test_settings_hub_integration.py`), and 3 docs receipts.
- Forbidden files: NONE present (no android/, mobile bridge, CNAME, docs/LANDING.md, docs/index-fallback.html, /proof, packaging/RELEASE_NOTES*, pyproject.toml, cache_vault/__init__.py, tools/check_exe_version.py, qa_artifacts/, visual_smoke/, dist/, release ZIPs).

## Architecture note (for future lanes)

The Settings Hub is registry-backed: `settings_hub.py` renders whatever `ModuleRegistry.settings_categories()` returns. The actual settings content lives in `cache_vault/modules/registry.py` and the module manifests. The deferred "real controls" work happens there, not only in `settings_hub.py`.

## Tests

Added to `tests/test_settings_hub.py` (`TestSettingsHubHotkeyRecorder`):
- hotkey field has a recorder
- record writes combo into field
- Esc cancels without recording `esc`
- retry after cancel records
- duplicate hotkey blocks save (on_save not called, footer error set)
- valid hotkeys allow save
- close while recording is safe
- category switch tears down recorders (no stale)

The recorder test class uses one shared class-scoped CTk root and skips (not fails) on transient Tcl runtime unavailability, matching the repo's `tk_root` / `probe_tk_ui` convention, to keep CI stable.

## Gates

| Gate | Result |
|------|--------|
| `pytest tests/test_settings_hub.py tests/test_settings_hub_integration.py tests/test_dialogs.py -q` | pass |
| `pytest -q` (full suite) | pass (1 unrelated Pillow deprecation warning) |
| `compileall cache_vault` | pass |
| `app.py --selftest` | `selftest OK` |

## PR status

Not pushed, no PR opened (holding per instruction). PR strategy pending decision; see session notes.
