# Cache Vault — Settings Hub StatusRow Action Buttons (12A)

Date: 2026-07-04
Branch: `fix/settings-mobile-bridge-live-status` (continued after 12B merge; PR
opened separately)
Base: `release/v0.1.4-public-distribution` @ `49d0fc6` (post-12B)
Type: **Code fix.** Implements 12A from
`docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md` (Q3/Q4),
scoped per explicit follow-up direction (see "Explicitly excluded" below).

## The gap

`StatusRow` (`settings_schema.py`) has declared `action` / `action_label`
fields since it was written, but `_render_status_card()` in `settings_hub.py`
only ever drew `row.label` and `row.value_getter()` — no module's status
row could ever become clickable, no matter what it set. Separately, the
real Mobile Bridge actions (Pair Android Device, Paired Devices, Mobile
Access Receipts) already exist as working `shell.py` methods, reachable
today only from the old `SettingsDialog` fallback and the main Mobile
Access screen — never from `SettingsHub`.

## The fix

1. **Renderer** (`ui/settings_hub.py`, `_render_status_card`): when
   `row.action is not None`, draw a `CTkButton` (`row.action_label` as its
   text, `theme.secondary_button()` styling) that calls `row.action` on
   click. Rows with no action render exactly as before — no widget added,
   no layout change.
2. **`MobileBridgeModule`** (`modules/mobile_bridge/__init__.py`): three new
   optional constructor kwargs, `pair_action` / `devices_action` /
   `receipts_action`. When set, they attach `action`/`action_label` to the
   **existing** "Bridge", "Paired devices", and "Last phone request" rows
   respectively — no new rows added. Labels reuse established terminology
   verbatim: "Pair Android Device" and "Paired Devices" match the buttons
   already shown on the Mobile Access screen; the receipts label reuses
   `brand.TERM_MOBILE_ACCESS_RECEIPTS` ("Mobile Access Receipts"), the same
   constant the old `SettingsDialog` already uses for the same action. When
   the kwargs are omitted (the default), all rows keep `action=None`,
   `action_label=""` — identical to pre-12A behavior.
3. **`build_default_registry()`** (`modules/registry.py`): three new
   optional kwargs, `mobile_pair_action` / `mobile_devices_action` /
   `mobile_receipts_action`, threaded straight through to
   `MobileBridgeModule`. Omitting them changes nothing for existing callers.
4. **`shell.py._open_settings()`**: passes the app's real, already-shipped
   `self._open_pair_android` / `self._open_paired_devices` /
   `self._open_mobile_receipts` methods as those three kwargs — the exact
   same callables the old `SettingsDialog` and the Mobile Access screen
   already call, wired with no new logic of their own.

## Design decision: why these 3 rows, and not a 4th "Revoke All" row

Three of the four Mobile-Access-adjacent actions map onto **existing**
status rows using already-shipped labels/behavior with zero new UI surface.
The fourth, bulk **Revoke All** (`_revoke_all_mobile_and_refresh`), has no
Settings-dialog precedent anywhere in the codebase — it has only ever
existed as its own separate, conditionally-shown, destructive-styled button
on the main Mobile Access screen. Surfacing it here would require inventing
a new status row (StatusRow carries one action each), which is explicitly
out of scope for this PR per direction received while scoping it:

- Render existing `StatusRow.action` / `action_label` buttons.
- Wire action buttons already declared by modules.
- Keep actions non-destructive or already-established.
- Do not invent new Mobile Bridge status rows.
- Do not add new destructive workflows.

**Bulk Revoke All remains intentionally deferred.** Per-device revoke
remains reachable through the "Paired Devices" button (which opens
`PairedDevicesDialog`, already wired to `on_revoke=self._revoke_mobile_device`
for one-at-a-time revocation), and bulk revoke remains available only where
already implemented (the main Mobile Access screen). It may get its own
row and its own PR later, with a confirmation flow, tests, and manual QA —
not folded into this one.

## Files changed

```
cache_vault/modules/registry.py               — build_default_registry(mobile_*_action=...)
cache_vault/modules/mobile_bridge/__init__.py — pair/devices/receipts action kwargs + row wiring
cache_vault/ui/settings_hub.py                — _render_status_card() draws row.action as a button
cache_vault/ui/shell.py                       — _open_settings() threads the 3 real shell actions
tests/test_module_registry.py                 — registry-level action-wiring test
tests/test_settings_hub.py                    — renderer tests (no-action / with-action + click)
tests/test_settings_hub_integration.py        — end-to-end: _open_settings() wires real methods
```

No other files touched. Not part of this PR: bulk Revoke All (deferred, see
above), General/version/build fields (12C), diagnostics (12D), the
"Excluded apps" list-field bug (Q3's other finding), About/Guide dialog
reachability, any Android/APK change, any public/proof/release surface.

## Tests added

- `test_build_default_registry_threads_mobile_actions` — registry-level:
  the three action kwargs land on the correct rows with the correct labels;
  untouched rows stay action-free; omitting all three reproduces exact
  pre-12A behavior (`action is None`, `action_label == ""`) on every row.
- `test_status_row_without_action_renders_no_button` — renderer-level, real
  `CTkButton` widget search: a registry built with no actions draws zero
  buttons in the Mobile Bridge category view.
- `test_status_row_action_renders_and_invokes_button` — renderer-level: a
  registry with all three actions draws exactly three buttons with the
  expected text, and clicking each (`.cget("command")()`) invokes the
  correct callable.
- `test_open_settings_wires_mobile_actions_into_registry` — end-to-end:
  `CacheVaultApp._open_settings()` itself hands `SettingsHub` a registry
  whose row actions call the app's real `_open_pair_android` /
  `_open_paired_devices` / `_open_mobile_receipts`, not placeholders.

## Gates run

```
python -m pytest -q            → pass (full suite, including 4 new/extended tests)
python -m compileall cache_vault → pass, no syntax errors
python app.py --selftest        → selftest OK
```

## Verdict

Closes the Q3/Q4 gap end-to-end (renderer → module → registry → shell) for
the three actions that already had a clean, precedented home. Revoke All
stays reachable exactly where it already was, with no new destructive UI
added in this pass.
