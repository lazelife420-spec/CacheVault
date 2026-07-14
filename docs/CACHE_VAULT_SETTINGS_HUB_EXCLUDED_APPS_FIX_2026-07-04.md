# Cache Vault — Settings Hub "Excluded Apps" Fake-Control Fix

Date: 2026-07-04
Branch: `fix/settings-hub-excluded-apps`
Base: `release/v0.1.4-public-distribution` @ `bafa0af` (post-12D)
Type: **Code fix.** Fixes the Q3 trust bug from
`docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md` (section
3): Settings shows "Excluded apps" as editable, but the edit is silently
discarded on save.

## The bug (two compounding defects)

`Settings.excluded_apps: list[str]` is declared as a `SettingsField` with
`field_type="text"`. `_FIELD_TYPE_TO_PYTHON["text"] = (str, list)` already
documents this as intentional (`# list[str] rendered as newline-separated
textarea`), and the field's own description already says "(one per line)"
— but the renderer never implemented that half of the contract:

1. **Render bug** — `_render_field_row()`'s `"text"` branch always built a
   single-line `CTkEntry` bound to `StringVar(value=str(current_val))`,
   regardless of the underlying type. For a list, `str(["a.exe"])`
   produces the raw Python repr (`"['a.exe']"`, brackets and quotes) in a
   box that looks like a normal text field.
2. **Collect bug** — `_collect_settings()` had an explicit no-op:
   `elif isinstance(orig_val, list): pass  # We don't support editing
   lists directly yet, but keep them`. Whatever the user typed was
   silently thrown away on Save, with zero indication anything went wrong.
   This is worse than missing polish: the UI implies the edit was saved.

`excluded_apps` is the only `SettingsField` in the current schema with a
`list`-typed value (`default_safe_id`, `vault_lock_accent`,
`mobile_access_bind_host` are the only other `"text"` fields and are all
plain strings), so this was fully isolated — one field, two functions.

## The fix: make it real

The settings model already supports list storage cleanly
(`excluded_apps: list[str] = field(default_factory=list)`, a plain
dataclass field with no special serialization needs), and the legacy
`SettingsDialog` (`ui/dialogs.py`) already ships a working precedent for
this exact field — a `CTkTextbox` seeded with `"\n".join(excluded_apps)`,
saved back via `[line.strip() for line in textbox.get(...).splitlines()
if line.strip()]`. This fix brings that same behavior into `SettingsHub`:

- `_render_field_row()`'s `"text"` branch now checks the underlying value's
  type. A `list` renders a `CTkTextbox` (newline-per-app); a `str` keeps
  the existing single-line `CTkEntry` — no change for `default_safe_id`,
  `vault_lock_accent`, or `mobile_access_bind_host`.
- `_collect_settings()`'s list branch now parses the textarea back into a
  list with the exact same `splitlines()` + strip + drop-blank-lines logic
  as the legacy dialog, instead of discarding the edit.
- A new `_ListTextVar` (get/set on a plain Python string) replaces the
  `StringVar` for this field. `CTkTextbox` has no `textvariable=` binding,
  so unlike every other field type its content does not automatically
  survive widget destruction — and `_clear_settings_area()` destroys every
  field widget on every category switch, while `_collect_settings()`
  unconditionally calls `.get()` on every field ever bound, regardless of
  which category is currently shown. `_ListTextVar` is kept in sync via
  `<KeyRelease>`/`<FocusOut>` bindings (through a new small
  `_sync_list_textarea()` method, mirroring the existing hotkey-hint
  binding pattern in this file) so in-progress edits survive category
  switches and `_collect_settings()` never touches a destroyed widget.

## Explicitly excluded from this pass

- No broad Settings redesign — only the two functions that had the bug,
  plus the one supporting helper class/method, changed.
- No diagnostics expansion (12D is closed).
- No About/Founder chrome work.
- No Android/public/proof/release changes.
- The legacy `SettingsDialog` in `ui/dialogs.py` was read as precedent
  only, not modified — `SettingsHub` is its replacement.

## Files changed

```
cache_vault/ui/settings_hub.py   — _ListTextVar, textarea rendering for list-typed "text" fields, _sync_list_textarea(), fixed _collect_settings() list branch
tests/test_settings_hub.py       — 5 new tests covering render, save, empty-save, category-switch preservation, and non-regression of plain-string "text" fields
```

## Tests added

- `test_excluded_apps_renders_as_textarea` — `excluded_apps` renders as a
  `CTkTextbox` pre-filled with the list joined by newlines, not a
  single-line entry showing a Python repr.
- `test_excluded_apps_collect_saves_edits` — editing the textarea and
  saving actually persists the new list, with blank/whitespace-only lines
  dropped (matches the legacy dialog's parsing exactly).
- `test_excluded_apps_collect_handles_empty_textarea` — clearing every
  line saves an empty list rather than silently keeping the old one.
- `test_excluded_apps_preserved_across_category_switch` — an in-progress
  edit survives switching categories away and back, and
  `_collect_settings()` does not crash on a binding whose widget has since
  been destroyed.
- `test_other_text_fields_unaffected_by_textarea_change` — `default_safe_id`
  (a plain string `"text"` field) still renders as a `CTkEntry`.

## Gates run

```
python -m pytest -q              → pass (full suite, including 5 new tests)
python -m compileall cache_vault tests → pass, no syntax errors
python app.py --selftest          → selftest OK
```

## Verdict

"Excluded apps" is now a real, working control: it renders the actual list
of excluded apps as an editable textarea, and Save genuinely persists
edits instead of silently discarding them. The Q3 trust bug is closed.
