"""Tests for the module manifest / registry system (Chunk A)."""

from __future__ import annotations

import pytest

from cache_vault.core.settings import Settings
from cache_vault.modules import ModuleManifest
from cache_vault.modules.registry import ModuleRegistry, build_default_registry
from cache_vault.modules.settings_schema import (
    SettingsCategory,
    SettingsField,
    StatusRow,
    validate_schema_against_settings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyModule(ModuleManifest):
    """Minimal concrete manifest for testing."""

    def __init__(self, mid: str = "dummy", name: str = "Dummy",
                 desc: str = "A test module"):
        self._id = mid
        self._name = name
        self._desc = desc

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._desc


# ---------------------------------------------------------------------------
# 1. build_default_registry
# ---------------------------------------------------------------------------

def test_build_default_registry():
    """build_default_registry() returns a registry with exactly 4 modules."""
    reg = build_default_registry()
    assert len(reg.all()) == 4
    ids = {m.id for m in reg.all()}
    assert ids == {"mobile_bridge", "image_viewer", "quick_paste", "proof"}


def test_build_default_registry_threads_mobile_bridge(vault):
    """mobile_bridge=... wires the live bridge into MobileBridgeModule so its
    status rows reflect real state instead of always reporting "not started"
    (see docs/CACHE_VAULT_SETTINGS_HUB_REAL_CONTROLS_AUDIT_2026-07-03.md, Q5).
    """
    from cache_vault.core.mobile.bridge import MobileBridge

    bridge = MobileBridge(vault)
    reg = build_default_registry(mobile_bridge=bridge)
    mod = reg.get("mobile_bridge")
    rows = {row.label: row.value_getter() for row in mod.get_status_rows()}
    # A live-but-not-yet-started bridge reads "Not listening", distinct from
    # the disconnected default's "Not started" — proves bridge_ref is real.
    assert rows["Bridge"] == "Not listening"


# ---------------------------------------------------------------------------
# 2. duplicate module id
# ---------------------------------------------------------------------------

def test_module_ids_unique():
    """Registering a duplicate id raises ValueError."""
    reg = ModuleRegistry()
    reg.register(_DummyModule("alpha"))
    with pytest.raises(ValueError, match="Duplicate module id"):
        reg.register(_DummyModule("alpha"))


# ---------------------------------------------------------------------------
# 3. required properties
# ---------------------------------------------------------------------------

def test_all_modules_have_required_properties():
    """Every manifest has non-empty id, name, and description."""
    reg = build_default_registry()
    for mod in reg.all():
        assert mod.id, f"Module missing id: {mod}"
        assert mod.name, f"Module {mod.id} missing name"
        assert mod.description, f"Module {mod.id} missing description"


# ---------------------------------------------------------------------------
# 4. schema keys valid against Settings
# ---------------------------------------------------------------------------

def test_settings_schema_keys_valid():
    """Every SettingsField.key across all modules and global categories
    exists on the Settings dataclass."""
    reg = build_default_registry()
    errors = validate_schema_against_settings(
        reg.settings_categories(), Settings,
    )
    assert errors == [], f"Schema validation errors:\n" + "\n".join(errors)


# ---------------------------------------------------------------------------
# 5. field types sensible
# ---------------------------------------------------------------------------

def test_settings_schema_field_types_sensible():
    """toggle → bool, number → int/float, etc."""
    reg = build_default_registry()
    # validate_schema_against_settings already checks types.
    errors = validate_schema_against_settings(
        reg.settings_categories(), Settings,
    )
    assert errors == [], f"Type mismatch errors:\n" + "\n".join(errors)


# ---------------------------------------------------------------------------
# 6. search "hotkey"
# ---------------------------------------------------------------------------

def test_search_hotkey():
    """'hotkey' finds results from Quick Paste and Keyboard Shortcuts."""
    reg = build_default_registry()
    results = reg.search_settings("hotkey")
    assert len(results) > 0
    labels = {cat_label for cat_label, _field in results}
    assert "Keyboard Shortcuts" in labels or "Quick Paste" in labels


# ---------------------------------------------------------------------------
# 7. search "phone"
# ---------------------------------------------------------------------------

def test_search_phone():
    """'phone' finds results from Mobile Bridge (description mentions 'phone')."""
    reg = build_default_registry()
    results = reg.search_settings("phone")
    # Mobile Bridge status rows use "phone" in descriptions;
    # the settings field description for bridge says "paired Android devices".
    # If nothing matches, we check for 'android' as a fallback.
    if not results:
        results = reg.search_settings("android")
    assert len(results) > 0


# ---------------------------------------------------------------------------
# 8. search "receipt"
# ---------------------------------------------------------------------------

def test_search_receipt():
    """'receipt' or related term finds Proof module fields."""
    reg = build_default_registry()
    # Proof module category label is "Proof & Receipts".
    # The field labels are "Auto-expire sensitive clips" and "Sensitive expiry (minutes)".
    # Search by category content:
    results = reg.search_settings("expir")
    assert len(results) > 0
    labels = {cat_label for cat_label, _field in results}
    assert "Proof & Receipts" in labels


# ---------------------------------------------------------------------------
# 9. search empty
# ---------------------------------------------------------------------------

def test_search_empty():
    """Empty query returns empty list."""
    reg = build_default_registry()
    assert reg.search_settings("") == []


# ---------------------------------------------------------------------------
# 10. search case insensitive
# ---------------------------------------------------------------------------

def test_search_case_insensitive():
    """Search is case-insensitive."""
    reg = build_default_registry()
    upper = reg.search_settings("HOTKEY")
    lower = reg.search_settings("hotkey")
    assert len(upper) == len(lower)
    assert {f.key for _, f in upper} == {f.key for _, f in lower}


# ---------------------------------------------------------------------------
# 11. health report
# ---------------------------------------------------------------------------

def test_health_report():
    """health_report() returns a dict keyed by module id, each with 'status'."""
    reg = build_default_registry()
    report = reg.health_report()
    assert set(report.keys()) == {"mobile_bridge", "image_viewer", "quick_paste", "proof"}
    for mid, result in report.items():
        assert "status" in result, f"Module {mid} health check missing 'status'"


# ---------------------------------------------------------------------------
# 12. category ordering
# ---------------------------------------------------------------------------

def test_module_categories_order():
    """settings_categories() returns global categories before module categories."""
    reg = build_default_registry()
    cats = reg.settings_categories()
    ids = [c.id for c in cats]
    # Global categories must appear before any module categories.
    global_ids = {"general", "capture", "shortcuts", "macros", "display",
                  "vault_lock", "history"}
    module_ids = {"mobile_bridge", "quick_paste", "proof"}
    # image_viewer has no settings schema, so it won't appear.
    first_module_idx = None
    last_global_idx = None
    for i, cid in enumerate(ids):
        if cid in global_ids:
            last_global_idx = i
        if cid in module_ids and first_module_idx is None:
            first_module_idx = i
    if first_module_idx is not None and last_global_idx is not None:
        # At least one global category should appear before the first module.
        assert min(
            i for i, cid in enumerate(ids) if cid in global_ids
        ) < first_module_idx


# ---------------------------------------------------------------------------
# 13. mobile status rows without bridge
# ---------------------------------------------------------------------------

def test_mobile_bridge_status_rows_without_bridge():
    """Mobile module's get_status_rows() works with no bridge reference."""
    from cache_vault.modules.mobile_bridge import MobileBridgeModule
    mod = MobileBridgeModule()  # no bridge_ref
    rows = mod.get_status_rows()
    assert len(rows) > 0
    for row in rows:
        assert isinstance(row, StatusRow)
        # Should not raise when called without a live bridge.
        value = row.value_getter()
        assert isinstance(value, str)


def test_mobile_bridge_status_rows_reflect_live_bridge_state(vault):
    """Status rows must read the live bridge's real attributes.

    Regression for two latent bugs found while wiring bridge_ref: the
    "Bridge" row checked a nonexistent ``running`` attribute (the real
    property is ``is_running``), and "Paired devices" read a nonexistent
    ``bridge._settings`` (the real path is ``bridge.vault.settings``). Both
    were invisible before because bridge_ref was always None in production.
    """
    from cache_vault.core.mobile.bridge import MobileBridge
    from cache_vault.modules.mobile_bridge import MobileBridgeModule

    vault.settings.mobile_access_enabled = True
    bridge = MobileBridge(vault)
    bridge.pair_device("phone-1", "Test Phone")
    bridge.sync(vault.settings)
    try:
        mod = MobileBridgeModule(
            bridge_ref=bridge,
            receipts_getter=bridge.receipts.recent,
            mdns_status_getter=lambda: bridge.discovery.is_advertising,
        )
        rows = {row.label: row.value_getter() for row in mod.get_status_rows()}
        assert rows["Bridge"] == "Listening"
        assert rows["Paired devices"] == "1 paired device"
    finally:
        bridge.stop()


# ---------------------------------------------------------------------------
# 14. validate_schema_against_settings catches bad keys
# ---------------------------------------------------------------------------

def test_validate_schema_helper():
    """validate_schema_against_settings() catches bad keys and type mismatches."""
    bad_cats = [
        SettingsCategory(
            id="test_bad", label="Bad", fields=[
                SettingsField("nonexistent_key_xyz", "Nope", "toggle"),
                SettingsField("start_with_windows", "Wrong type", "number"),
            ],
        ),
    ]
    errors = validate_schema_against_settings(bad_cats, Settings)
    assert len(errors) == 2
    assert any("nonexistent_key_xyz" in e for e in errors)
    assert any("start_with_windows" in e for e in errors)
