"""Vault dashboard summary includes editable-copy counts."""

from __future__ import annotations

import pytest

from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


@pytest.fixture
def vault_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return Vault(storage=VaultStorage(":memory:"), settings=Settings())


def test_dashboard_summary_includes_copy_counts(vault_env):
    summary = vault_env.dashboard_summary()
    assert "editable_copies" in summary
    assert "html_bundles" in summary
    assert "recent_pasted_count" in summary
