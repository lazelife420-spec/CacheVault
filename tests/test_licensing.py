"""Founder license verification tests."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import cache_vault.licensing as lic


@pytest.fixture
def keypair():
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private, public_pem


@pytest.fixture
def license_env(tmp_path, keypair, monkeypatch):
    private, public_pem = keypair
    monkeypatch.setattr(lic, "_FOUNDER_PUBLIC_KEY_PEM", public_pem)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return private, tmp_path / "CacheVault" / "license.json"


def _sign(private: Ed25519PrivateKey, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(private.sign(raw)).decode("ascii")


def _founder_doc(private: Ed25519PrivateKey, **overrides) -> dict:
    payload = {
        "product": "cache-vault",
        "edition": "founder",
        "licensee": "buyer@example.com",
        "issued_at": "2026-06-19T00:00:00Z",
        "expires_at": None,
        "features": sorted(lic.FOUNDER_FEATURES),
    }
    payload.update(overrides)
    return {**payload, "signature": _sign(private, payload)}


def test_missing_license_returns_free(license_env):
    _, path = license_env
    status = lic.load_license(path)
    assert status.state == lic.LicenseState.MISSING_LICENSE
    assert not lic.is_founder_unlocked(path)
    assert not lic.is_feature_enabled("proof_pack_export", path)


def test_valid_founder_license_unlocks(license_env):
    private, path = license_env
    doc = _founder_doc(private)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

    status = lic.load_license(path)
    assert status.state == lic.LicenseState.FOUNDER_VALID
    assert lic.is_founder_unlocked(path)
    assert lic.is_feature_enabled("proof_pack_export", path)
    assert lic.is_feature_enabled("zip_export", path)


def test_bad_signature_rejected(license_env):
    private, path = license_env
    doc = _founder_doc(private)
    doc["signature"] = base64.b64encode(b"invalid-signature-bytes").decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

    status = lic.load_license(path)
    assert status.state == lic.LicenseState.INVALID_SIGNATURE
    assert not lic.is_founder_unlocked(path)


def test_wrong_product_rejected(license_env):
    private, path = license_env
    doc = _founder_doc(private, product="other-product")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

    status = lic.load_license(path)
    assert status.state == lic.LicenseState.WRONG_PRODUCT


def test_corrupt_json_rejected(license_env):
    _, path = license_env
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    status = lic.load_license(path)
    assert status.state == lic.LicenseState.CORRUPT_LICENSE


def test_expired_license_rejected(license_env):
    private, path = license_env
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = _founder_doc(private, expires_at=expired)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

    status = lic.load_license(path)
    assert status.state == lic.LicenseState.EXPIRED_LICENSE
    assert not lic.is_founder_unlocked(path)


def test_feature_lookup_returns_correct_booleans(license_env):
    private, path = license_env
    payload = {
        "product": "cache-vault",
        "edition": "founder",
        "licensee": "partial@example.com",
        "issued_at": "2026-06-19T00:00:00Z",
        "expires_at": None,
        "features": ["proof_pack_export", "zip_export"],
    }
    doc = {**payload, "signature": _sign(private, payload)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")

    assert lic.is_feature_enabled("proof_pack_export", path)
    assert lic.is_feature_enabled("zip_export", path)
    assert not lic.is_feature_enabled("macros_advanced", path)


def test_install_license_from_file(license_env, tmp_path):
    private, dest = license_env
    src = tmp_path / "incoming.json"
    src.write_text(json.dumps(_founder_doc(private)), encoding="utf-8")

    status = lic.install_license_from_file(src, dest)
    assert status.state == lic.LicenseState.FOUNDER_VALID
    assert dest.is_file()
    assert lic.is_founder_unlocked(dest)


def test_install_license_from_text(license_env):
    private, dest = license_env
    text = json.dumps(_founder_doc(private))

    status = lic.install_license_from_text(text, dest)
    assert status.state == lic.LicenseState.FOUNDER_VALID
    assert dest.is_file()


def test_install_rejects_invalid_license(license_env, tmp_path):
    private, dest = license_env
    doc = _founder_doc(private)
    doc["signature"] = "AAAA"
    src = tmp_path / "bad.json"
    src.write_text(json.dumps(doc), encoding="utf-8")

    status = lic.install_license_from_file(src, dest)
    assert status.state == lic.LicenseState.INVALID_SIGNATURE
    assert not dest.is_file()
