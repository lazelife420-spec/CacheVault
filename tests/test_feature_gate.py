"""Central feature gate tests."""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import cache_vault.feature_gate as gate
import cache_vault.licensing as lic


@pytest.fixture
def unlocked_env(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(lic, "_FOUNDER_PUBLIC_KEY_PEM", public_pem)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    payload = {
        "product": "cache-vault",
        "edition": "founder",
        "licensee": "test@example.com",
        "issued_at": "2026-06-19T00:00:00Z",
        "expires_at": None,
        "features": sorted(lic.FOUNDER_FEATURES),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    doc = {**payload, "signature": base64.b64encode(private.sign(raw)).decode("ascii")}
    path = tmp_path / "CacheVault" / "license.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_requires_feature_free_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert not gate.requires_feature("proof_pack_export")


def test_requires_feature_when_unlocked(unlocked_env):
    assert gate.requires_feature("proof_pack_export", unlocked_env)
    assert gate.requires_feature("macros_advanced", unlocked_env)


def test_check_feature_invokes_blocked_callback(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    blocked = []

    allowed = gate.check_feature(
        "zip_export",
        on_blocked=lambda name: blocked.append(name),
    )
    assert not allowed
    assert blocked == ["zip_export"]


def test_check_feature_passes_when_unlocked(unlocked_env):
    assert gate.check_feature("zip_export", path=unlocked_env)
