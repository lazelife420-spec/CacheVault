# Cache Vault — Settings Hub Mobile Bridge Live Status (12B)

Date: 2026-07-03
Branch: `fix/settings-mobile-bridge-live-status`
Base: `release/v0.1.4-public-distribution` @ `7943e24`
Type: **Code fix.** Implements 12B from
`docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md` (Q5).

## The bug

The top bar / Home dashboard read Mobile Access status from the app's one
live `MobileBridge` instance (`self._mobile_bridge`). Settings Hub, on every
`_open_settings()` call, built a **brand-new, disconnected**
`MobileBridgeModule()` with no bridge reference, so its status rows always
said "Bridge not started" / "Bridge not started" regardless of the real
bridge's state — visibly contradicting the top bar (e.g. "Paired").

## The fix

`build_default_registry()` (`cache_vault/modules/registry.py`) now accepts
an optional `mobile_bridge` keyword. When provided, it constructs
`MobileBridgeModule` with `bridge_ref`, `receipts_getter`, and
`mdns_status_getter` pointed at the real bridge instead of leaving them
`None`. `shell.py._open_settings()` passes `mobile_bridge=self._mobile_bridge`.
Callers that don't pass it (existing tests, module CLI entry points) are
unaffected — default is still `None`, identical to prior behavior.

## Two additional bugs found and fixed

Both were latent and invisible before this fix, because `bridge_ref` was
always `None` in every real code path — wiring a live bridge exposed them
immediately via the new tests:

1. **`_bridge_status()` checked `bridge.running`, which doesn't exist.**
   `MobileBridge` exposes `is_running` (a property). The old
   `getattr(self._bridge, "running", False)` silently fell back to `False`
   forever, so even a fully wired, running bridge would have shown
   "Not listening". Fixed to read `is_running`. Same bug existed in
   `run_health_check()`'s `bridge_listening=...` argument; fixed there too.

2. **`_paired_count()` and `run_health_check()` read `bridge._settings`,
   which doesn't exist.** `MobileBridge` stores no `_settings` attribute —
   only `self.vault` (from which `.settings.paired_devices` is reachable,
   the same source `Vault.dashboard_summary()` uses for the top bar's
   paired count). Added `MobileBridgeModule._bridge_settings()` to look up
   `bridge.vault.settings` correctly, and both call sites now use it.

## Files changed

```
cache_vault/modules/registry.py               — build_default_registry(mobile_bridge=...)
cache_vault/modules/mobile_bridge/__init__.py — is_running fix, _bridge_settings() helper
cache_vault/ui/shell.py                       — _open_settings() threads self._mobile_bridge
tests/test_module_registry.py                 — 2 new tests (wiring + live-state correctness)
tests/test_settings_hub_integration.py        — 1 new end-to-end regression test
```

No other files touched. Not part of this PR: StatusRow action buttons (12A,
a hard prerequisite for wiring Pair/Devices/Revoke/Receipts as clickable
actions — deferred), General/version/build fields (12C), diagnostics (12D),
the "Excluded apps" list-field bug (Q3), and the About/Guide dialog
reachability gap — all flagged in the audit, none addressed here.

## Tests added

- `test_build_default_registry_threads_mobile_bridge` — proves
  `build_default_registry(mobile_bridge=...)` produces a "Not listening"
  (live, connected) status instead of the disconnected default's
  "Not started".
- `test_mobile_bridge_status_rows_reflect_live_bridge_state` — proves the
  `is_running` and `bridge.vault.settings` fixes against a real, running
  `MobileBridge` with a paired device ("Listening", "1 paired device").
- `test_open_settings_wires_live_mobile_bridge_into_registry` — end-to-end:
  captures the registry `CacheVaultApp._open_settings()` actually hands to
  `SettingsHub` and asserts its mobile module reads "Not listening", proving
  the real app wiring (not just the registry function in isolation).

## Gates run

```
python -m pytest -q            → pass (full suite, including 3 new tests)
python -m compileall cache_vault → pass, no syntax errors
python app.py --selftest        → selftest OK
```

## Verdict

Fixes the Q5 trust bug end-to-end (registry → module → status rows) plus
two previously-dormant attribute-name bugs that would have undermined the
fix if left in place. Scope held to exactly what 12B specifies.
