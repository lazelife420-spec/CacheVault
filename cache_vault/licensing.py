"""Offline Founder license verification — public-key only in the app.

License files are stored under ``%LOCALAPPDATA%\\CacheVault\\license.json``.
The signing private key never ships with the application.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

PRODUCT_ID = "cache-vault"
EDITION_FOUNDER = "founder"

# Embedded public key — private counterpart kept outside the repository.
_FOUNDER_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAwcd2DCZRMlUs3DO93lZZgmiiigt88j+IR1Zv6JiePhU=
-----END PUBLIC KEY-----"""

FOUNDER_FEATURES: frozenset[str] = frozenset({
    "exports_advanced",
    "zip_export",
    "proof_pack_export",
    "html_bundle_export",
    "editable_copies_advanced",
    "smart_filters_advanced",
    "macros_advanced",
    "safes_advanced",
})


class LicenseState(str, Enum):
    FREE = "FREE"
    FOUNDER_VALID = "FOUNDER_VALID"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    WRONG_PRODUCT = "WRONG_PRODUCT"
    CORRUPT_LICENSE = "CORRUPT_LICENSE"
    EXPIRED_LICENSE = "EXPIRED_LICENSE"
    MISSING_LICENSE = "MISSING_LICENSE"


@dataclass(frozen=True)
class LicenseStatus:
    state: LicenseState
    edition: str = "free"
    licensee: str = ""
    issued_at: str | None = None
    expires_at: str | None = None
    features: frozenset[str] = field(default_factory=frozenset)
    message: str = ""


def default_license_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "license.json"


def _public_key() -> Ed25519PublicKey:
    return serialization.load_pem_public_key(_FOUNDER_PUBLIC_KEY_PEM)


def _canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_license(payload: dict[str, Any], signature_b64: str) -> bool:
    """Return True when *signature_b64* validates *payload*."""
    try:
        sig = base64.b64decode(signature_b64, validate=True)
        _public_key().verify(sig, _canonical_payload_bytes(payload))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _status_from_doc(doc: dict[str, Any]) -> LicenseStatus:
    if not isinstance(doc, dict):
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="License is not a JSON object.")

    payload = {k: v for k, v in doc.items() if k != "signature"}
    signature = doc.get("signature")
    if not isinstance(signature, str) or not signature.strip():
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="Missing license signature.")

    product = payload.get("product")
    if product != PRODUCT_ID:
        return LicenseStatus(
            LicenseState.WRONG_PRODUCT,
            message=f"License product mismatch (expected {PRODUCT_ID!r}).",
        )

    if not verify_license(payload, signature):
        return LicenseStatus(LicenseState.INVALID_SIGNATURE, message="License signature is invalid.")

    edition = str(payload.get("edition") or "").lower()
    if edition != EDITION_FOUNDER:
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="Unknown license edition.")

    expires_at = payload.get("expires_at")
    if expires_at is not None:
        exp = _parse_iso8601(str(expires_at))
        if exp is None:
            return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="Invalid expires_at value.")
        now = datetime.now(timezone.utc)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            return LicenseStatus(
                LicenseState.EXPIRED_LICENSE,
                edition=edition,
                expires_at=str(expires_at),
                message="License has expired.",
            )

    raw_features = payload.get("features") or []
    if not isinstance(raw_features, list):
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="Invalid features list.")

    features = frozenset(str(f) for f in raw_features if str(f) in FOUNDER_FEATURES)
    return LicenseStatus(
        state=LicenseState.FOUNDER_VALID,
        edition=edition,
        licensee=str(payload.get("licensee") or ""),
        issued_at=str(payload.get("issued_at") or "") or None,
        expires_at=str(expires_at) if expires_at is not None else None,
        features=features,
        message="Founder Edition active.",
    )


def load_license(path: Path | None = None) -> LicenseStatus:
    license_path = path or default_license_path()
    if not license_path.is_file():
        return LicenseStatus(
            LicenseState.MISSING_LICENSE,
            message="No license installed — using Free edition.",
        )
    try:
        raw = license_path.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="License file is unreadable.")

    return _status_from_doc(doc)


def is_founder_unlocked(path: Path | None = None) -> bool:
    return load_license(path).state == LicenseState.FOUNDER_VALID


def is_feature_enabled(feature_name: str, path: Path | None = None) -> bool:
    status = load_license(path)
    if status.state == LicenseState.FOUNDER_VALID:
        return feature_name in status.features
    return False


def install_license_from_file(source: Path, dest: Path | None = None) -> LicenseStatus:
    dest_path = dest or default_license_path()
    try:
        raw = source.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="Could not read license file.")

    status = _status_from_doc(doc)
    if status.state != LicenseState.FOUNDER_VALID:
        return status

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return load_license(dest_path)


def install_license_from_text(text: str, dest: Path | None = None) -> LicenseStatus:
    dest_path = dest or default_license_path()
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return LicenseStatus(LicenseState.CORRUPT_LICENSE, message="License text is not valid JSON.")

    status = _status_from_doc(doc)
    if status.state != LicenseState.FOUNDER_VALID:
        return status

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return load_license(dest_path)
