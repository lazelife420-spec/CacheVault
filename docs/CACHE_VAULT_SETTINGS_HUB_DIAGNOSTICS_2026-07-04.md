# Cache Vault — Settings Hub Diagnostics (12D)

Date: 2026-07-04
Branch: `fix/settings-hub-diagnostics`
Base: `release/v0.1.4-public-distribution` @ `bc287f4` (post-12C)
Type: **Code fix.** Implements 12D from
`docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md` (Q7/Q9),
scoped per explicit follow-up direction (see "Explicitly excluded" below).

## The gap

The audit's diagnostics table (section 7) named four real, already-existing
helpers with no UI surface in `SettingsHub`: `crashlog.log_path()` (crash
log, existence-checked), `self.vault.storage.db_path` (database path), and
`python app.py --selftest` (CLI-only by explicit rule — "must not become a
fake button"). Data folder and packaged-vs-source were also on that table
but are already fully covered by 12C's General category, so this pass adds
nothing for those two.

## The fix: a new "Diagnostics" category

A new `DiagnosticsModule` (`modules/diagnostics/__init__.py`) registers
under a **new** global category, `id="diagnostics"` (added to
`_GLOBAL_CATEGORIES` and `_CATEGORY_ORDER`, right after "General"), with
`fields=[]` — it carries no settings, only a Live Status card, mirroring
12C's `GeneralInfoModule` pattern exactly (module id matches the global
category id, so `_render_category_view()`'s existing lookup finds it with
zero `settings_hub.py` changes). Three status rows:

- **Crash log** — value is the real resolved path
  (`default_settings_path().parent / "crash.log"`, the exact same file
  `ui/crashlog.log_path()` writes to) when the file exists, or "No crashes
  recorded" when it doesn't. Action: **"Open Crash Log"**, present **only**
  when the file exists — the audit's rule is "not a fake button", so a
  log that has never been written gets no button at all rather than one
  that would fail or no-op. Unconditional (no external wiring needed) once
  a log exists; uses the existing `core/pathutil.open_file()`.
- **Database** — value is the live `vault.storage.db_path`, not a
  recomputed default (`core/storage.default_db_path()`), so a non-default
  database location would still show correctly. No action (informational —
  opening it lives one click away via the "Open Data Folder" button
  already on the General category, added in 12C). Read via a new
  `db_path_getter` kwarg threaded through `build_default_registry()` from
  `shell.py._open_settings()` (`lambda: str(self.vault.storage.db_path)`);
  reads "Unavailable" when omitted (e.g. registry built without a shell).
- **Selftest** — value is a plain instruction string, `"Run: python app.py
  --selftest (terminal only)"`. No action, ever — per the audit's explicit
  rule (Q9), this stays a copyable command, not a UI runner.

The crash log path is derived from `core/settings.default_settings_path()`
rather than importing `ui/crashlog.log_path()` directly — every module in
`cache_vault/modules/` stays free of any dependency on `cache_vault/ui/`
(the same reasoning as 12C's local `_version_line()` duplication). Both
resolve to the identical `%LOCALAPPDATA%\CacheVault\crash.log`.

## Explicitly excluded from this pass

- **Connection doctor / per-module health-check surfacing** — the audit
  flagged this as optional; not requested this time, left for a future
  pass if wanted.
- **Data folder / packaged-vs-source** — already real and already shipped
  in 12C's General category; not duplicated here.
- Any long-running diagnostics inside the UI (no runner, no progress bar —
  Selftest stays a CLI pointer only).
- About/Founder chrome reachability (deferred since 12C).
- Bulk Revoke All (deferred since 12A).
- The "Excluded apps" list-field bug (Q3) — tracked as its own separate
  fix, not folded into this diagnostics pass.
- Any broad Settings redesign, Android/APK change, or public/proof/release
  surface.

## Files changed

```
cache_vault/modules/diagnostics/__init__.py   — new: DiagnosticsModule (3 status rows)
cache_vault/modules/registry.py               — new "diagnostics" global category + order; build_default_registry(db_path_getter=...)
cache_vault/ui/shell.py                       — _open_settings() threads db_path_getter
tests/test_module_registry.py                 — registry tests + 3 pre-existing count/id-set/order-set fixes
tests/test_settings_hub_integration.py        — end-to-end: _open_settings() wires the real live db_path
```

No `settings_hub.py` changes. Not part of this PR: everything listed under
"Explicitly excluded" above.

## Tests added

- `test_build_default_registry_threads_db_path_getter` — registry-level:
  `db_path_getter` lands on the "Database" row; omitting it reads
  "Unavailable".
- `test_diagnostics_module_selftest_row_is_informational_only` — Selftest
  never carries an action, and `get_settings_schema()` is empty (no new
  sidebar entry beyond the global category itself).
- `test_diagnostics_module_crash_log_row` — value/action flip correctly
  between "file doesn't exist" and "file exists" states, proving no fake
  button is ever drawn for a log that was never written.
- `test_diagnostics_module_open_crash_log_action` — the action opens the
  real file via `pathutil.open_file`, verified with `monkeypatch`.
- `test_open_settings_wires_db_path_getter_into_registry` — end-to-end:
  `CacheVaultApp._open_settings()` hands `SettingsHub` a registry whose
  "Database" row reads the app's real, live `vault.storage.db_path`.

Three pre-existing tests were updated for the new sixth module and second
new global category: `test_build_default_registry`, `test_health_report`,
and `test_module_categories_order`'s `global_ids` set now include
`"diagnostics"`.

## Gates run

```
python -m pytest -q            → pass (full suite, including 5 new tests + 3 updated assertions)
python -m compileall cache_vault → pass, no syntax errors
python app.py --selftest        → selftest OK
```

## Verdict

Surfaces the crash log (existence-checked, never a fake button) and the
real live database path in `SettingsHub` for the first time, and points at
`--selftest` as plain informational text per the audit's hard CLI-only
rule. Connection-doctor/health-check surfacing, the Excluded-apps bug, and
all previously-deferred items (About/Founder, Revoke All) remain open,
tracked separately.
