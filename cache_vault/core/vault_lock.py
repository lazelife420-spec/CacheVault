"""Local app privacy lock for the visible Cache Vault surface.

This is not Safe encryption. It prevents casual viewing of the open app until
the local PIN/passphrase is entered.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from . import models

LOCK_MODE_PIN = "pin"
LOCK_MODE_PASSPHRASE = "passphrase"
LOCK_MODES = (LOCK_MODE_PIN, LOCK_MODE_PASSPHRASE)

EVENT_VAULT_LOCKED = "vault_locked"
EVENT_VAULT_UNLOCKED = "vault_unlocked"
EVENT_VAULT_UNLOCK_FAILED = "vault_unlock_failed"
EVENT_VAULT_LOCK_SETTINGS_CHANGED = "vault_lock_settings_changed"

DEFAULT_ITERATIONS = 200_000
SALT_BYTES = 16

FORBIDDEN_LOCK_CLAIMS = (
    "encrypted Safes",
    "bank-grade encryption",
    "military-grade",
    "unbreakable",
    "blockchain",
    "cloud sync",
)


@dataclass(frozen=True)
class VaultLockConfig:
    enabled: bool
    mode: str
    lock_on_startup: bool
    lock_when_minimized: bool
    auto_lock_minutes: int
    has_secret: bool


def normalize_mode(mode: str | None) -> str:
    return mode if mode in LOCK_MODES else LOCK_MODE_PIN


def _hash_secret(secret: str, salt_hex: str, iterations: int) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        max(1, int(iterations or DEFAULT_ITERATIONS)),
    )
    return digest.hex()


def make_secret_hash(secret: str, *, iterations: int = DEFAULT_ITERATIONS) -> tuple[str, str, int]:
    if not secret:
        raise ValueError("Vault Lock credential cannot be blank.")
    salt_hex = os.urandom(SALT_BYTES).hex()
    return salt_hex, _hash_secret(secret, salt_hex, iterations), iterations


def set_lock_secret(settings, secret: str, *, mode: str | None = None) -> None:
    salt, digest, iterations = make_secret_hash(secret)
    settings.vault_lock_salt = salt
    settings.vault_lock_hash = digest
    settings.vault_lock_iterations = iterations
    settings.vault_lock_mode = normalize_mode(mode or settings.vault_lock_mode)
    settings.vault_lock_enabled = True


def clear_lock_secret(settings) -> None:
    settings.vault_lock_enabled = False
    settings.vault_lock_hash = ""
    settings.vault_lock_salt = ""
    settings.vault_lock_iterations = DEFAULT_ITERATIONS


def has_lock_secret(settings) -> bool:
    return bool(
        getattr(settings, "vault_lock_hash", "")
        and getattr(settings, "vault_lock_salt", "")
    )


def verify_secret(settings, candidate: str) -> bool:
    if not has_lock_secret(settings) or not candidate:
        return False
    expected = settings.vault_lock_hash
    actual = _hash_secret(
        candidate,
        settings.vault_lock_salt,
        int(settings.vault_lock_iterations or DEFAULT_ITERATIONS),
    )
    return hmac.compare_digest(expected, actual)


def lock_config(settings) -> VaultLockConfig:
    try:
        auto = max(0, int(getattr(settings, "vault_lock_auto_minutes", 0)))
    except (TypeError, ValueError):
        auto = 0
    return VaultLockConfig(
        enabled=bool(getattr(settings, "vault_lock_enabled", False) and has_lock_secret(settings)),
        mode=normalize_mode(getattr(settings, "vault_lock_mode", LOCK_MODE_PIN)),
        lock_on_startup=bool(getattr(settings, "vault_lock_on_startup", False)),
        lock_when_minimized=bool(getattr(settings, "vault_lock_when_minimized", False)),
        auto_lock_minutes=auto,
        has_secret=has_lock_secret(settings),
    )


def should_lock_on_startup(settings) -> bool:
    cfg = lock_config(settings)
    return cfg.enabled and cfg.lock_on_startup


def record_lock_event(events, event_type: str, *, mode: str | None = None,
                      reason: str | None = None) -> str:
    details: dict[str, str] = {}
    if mode:
        details["mode"] = normalize_mode(mode)
    if reason:
        details["reason"] = reason
    return events.record(event_type, None, details)


def no_forbidden_lock_claims(text: str) -> bool:
    low = text.lower()
    return not any(claim.lower() in low for claim in FORBIDDEN_LOCK_CLAIMS)


def safe_lock_settings_summary(settings) -> dict:
    cfg = lock_config(settings)
    return {
        "enabled": cfg.enabled,
        "mode": cfg.mode,
        "lock_on_startup": cfg.lock_on_startup,
        "lock_when_minimized": cfg.lock_when_minimized,
        "auto_lock_minutes": cfg.auto_lock_minutes,
        "has_secret": cfg.has_secret,
        "updated_at": models.now_iso(),
    }
