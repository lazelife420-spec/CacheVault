"""DEF-006 qualification test suite for in-memory stat-identity license caching."""

import base64
import json
import time
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from cache_vault import licensing as lic
from cache_vault.licensing import LicenseState, clear_license_cache, load_license, is_feature_enabled


def _sign(private: Ed25519PrivateKey, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(private.sign(raw)).decode("ascii")


def _make_doc(private: Ed25519PrivateKey, licensee: str = "Alice", features: list | None = None) -> dict:
    feat_list = features if features is not None else sorted(lic.FOUNDER_FEATURES)
    payload = {
        "product": "cache-vault",
        "edition": "founder",
        "licensee": licensee,
        "issued_at": "2026-06-19T00:00:00Z",
        "expires_at": None,
        "features": feat_list,
    }
    return {**payload, "signature": _sign(private, payload)}


def test_def006_licensing_cache_lifecycle(tmp_path: Path, monkeypatch) -> None:
    clear_license_cache()
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(lic, "_FOUNDER_PUBLIC_KEY_PEM", public_pem)

    lic_file = tmp_path / "license.json"

    # 1. Initial load on missing file
    st_missing = load_license(lic_file)
    assert st_missing.state == LicenseState.MISSING_LICENSE
    assert not is_feature_enabled("zip_export", lic_file)

    # 2. Write valid signed license document
    doc_valid = _make_doc(private, licensee="Alice", features=["zip_export", "exports_advanced"])
    lic_file.write_text(json.dumps(doc_valid), encoding="utf-8")

    st_valid = load_license(lic_file)
    assert st_valid.state == LicenseState.FOUNDER_VALID
    assert st_valid.licensee == "Alice"
    assert is_feature_enabled("zip_export", lic_file)

    # 3. Unchanged file cache hit
    st_hit = load_license(lic_file)
    assert st_hit is st_valid  # Exact object returned from cache

    # 4. Modify license file (revoke feature)
    time.sleep(0.01)  # Ensure mtime_ns changes
    doc_modified = _make_doc(private, licensee="Alice", features=["exports_advanced"])
    lic_file.write_text(json.dumps(doc_modified), encoding="utf-8")

    st_mod = load_license(lic_file)
    assert st_mod is not st_valid
    assert st_mod.state == LicenseState.FOUNDER_VALID
    assert not is_feature_enabled("zip_export", lic_file)  # Instantly observed
    assert is_feature_enabled("exports_advanced", lic_file)

    # 5. Atomic replacement of license file
    time.sleep(0.01)
    tmp_file = tmp_path / "temp_license.json"
    doc_replaced = _make_doc(private, licensee="Bob", features=["zip_export"])
    tmp_file.write_text(json.dumps(doc_replaced), encoding="utf-8")
    tmp_file.replace(lic_file)

    st_replaced = load_license(lic_file)
    assert st_replaced.state == LicenseState.FOUNDER_VALID
    assert st_replaced.licensee == "Bob"
    assert is_feature_enabled("zip_export", lic_file)

    # 6. Corrupt license file (must NOT reuse stale valid authorization)
    time.sleep(0.01)
    lic_file.write_text("{BAD_JSON_DATA", encoding="utf-8")

    st_corrupt = load_license(lic_file)
    assert st_corrupt.state == LicenseState.CORRUPT_LICENSE
    assert not is_feature_enabled("zip_export", lic_file)  # Feature revoked

    # 7. Delete license file
    lic_file.unlink()

    st_del = load_license(lic_file)
    assert st_del.state == LicenseState.MISSING_LICENSE
    assert not is_feature_enabled("zip_export", lic_file)

    clear_license_cache()
