from __future__ import annotations

import json

from cache_vault.core.capabilities import CAPABILITIES, CORE, PLANNED_PRO, has_forbidden_claims
from cache_vault.core.safes import SAFE_WORDING, SafeRegistry
from cache_vault.core.settings import Settings
from cache_vault.ui.vault_lock import LOCK_STYLES, normalize_lock_style


def test_custom_safe_metadata_persists_without_encryption_claim():
    settings = Settings()
    registry = SafeRegistry(settings)

    safe = registry.create("Client Work")
    updated = registry.update_customization(
        safe.id,
        icon="CW",
        accent="#336699",
        description="Client material",
        favorite=True,
        receipt_label="Client receipt",
        visual_style="work",
    )

    assert updated is not None
    loaded = SafeRegistry(settings).resolve(safe.id)
    assert loaded is not None
    assert loaded.icon == "CW"
    assert loaded.accent == "#336699"
    assert loaded.description == "Client material"
    assert loaded.favorite is True
    assert loaded.receipt_label == "Client receipt"
    assert "not encryption" in SAFE_WORDING.lower()
    assert "encrypted safes" not in json.dumps(settings.user_safes).lower()


def test_lock_style_setting_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(
        vault_lock_style="graphite",
        vault_lock_accent="#444444",
        vault_lock_reduced_motion=False,
        vault_lock_show_local_only=False,
    )
    settings.save(path)

    loaded = Settings.load(path)

    assert loaded.vault_lock_style == "graphite"
    assert loaded.vault_lock_accent == "#444444"
    assert loaded.vault_lock_reduced_motion is False
    assert loaded.vault_lock_show_local_only is False
    assert normalize_lock_style("not-real") == "teal_classic"
    assert "Vault Door" in [style["label"] for style in LOCK_STYLES.values()]


def test_capability_registry_keeps_trust_features_core_and_pro_planned():
    assert CAPABILITIES["local_vault"].tier == CORE
    assert CAPABILITIES["basic_vault_lock"].tier == CORE
    assert CAPABILITIES["receipts"].tier == CORE
    assert CAPABILITIES["encrypted_safes"].tier == PLANNED_PRO
    assert CAPABILITIES["encrypted_safes"].available is False
    text = "\n".join(f"{cap.label} {cap.note}" for cap in CAPABILITIES.values())
    assert not has_forbidden_claims(text)
