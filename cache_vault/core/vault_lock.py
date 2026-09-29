"""Local app privacy lock for the visible Cache Vault surface.

This is not Safe encryption. It prevents casual viewing of the open app until
the local PIN/passphrase is entered.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from enum import Enum

from . import models

LOCK_MODE_PIN = "pin"
LOCK_MODE_PASSPHRASE = "passphrase"
LOCK_MODES = (LOCK_MODE_PIN, LOCK_MODE_PASSPHRASE)

EVENT_VAULT_LOCKED = "vault_locked"
EVENT_VAULT_UNLOCKED = "vault_unlocked"
EVENT_VAULT_UNLOCK_FAILED = "vault_unlock_failed"
EVENT_VAULT_LOCK_SETTINGS_CHANGED = "vault_lock_settings_changed"

CANONICAL_EVENT_BY_STORAGE_NAME = {
    EVENT_VAULT_LOCKED: "vault.locked",
    EVENT_VAULT_UNLOCKED: "vault.unlocked",
    EVENT_VAULT_UNLOCK_FAILED: "vault.unlock_failed",
    EVENT_VAULT_LOCK_SETTINGS_CHANGED: "vault.lock_settings_changed",
}


class VaultLockState(str, Enum):
    DISABLED = "DISABLED"
    LOCKED = "LOCKED"
    UNLOCKED = "UNLOCKED"

DEFAULT_ITERATIONS = 200_000
MAX_ITERATIONS = 2_000_000
SALT_BYTES = 16
FAILURE_THRESHOLD = 5
FAILURE_STEP = 3
BASE_LOCKOUT_MS = 30_000
MAX_BACKOFF_EXPONENT = 4

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
    settings.vault_lock_on_startup = True
    reset_failed_unlocks(settings)


def clear_lock_secret(settings) -> None:
    settings.vault_lock_enabled = False
    settings.vault_lock_hash = ""
    settings.vault_lock_salt = ""
    settings.vault_lock_iterations = DEFAULT_ITERATIONS
    settings.vault_lock_failures = 0
    settings.vault_lock_locked_until_ms = 0


def has_lock_secret(settings) -> bool:
    try:
        salt = bytes.fromhex(getattr(settings, "vault_lock_salt", ""))
        digest = bytes.fromhex(getattr(settings, "vault_lock_hash", ""))
        iterations = int(getattr(settings, "vault_lock_iterations", DEFAULT_ITERATIONS))
    except (TypeError, ValueError):
        return False
    return (
        len(salt) == SALT_BYTES
        and len(digest) == 32
        and 0 < iterations <= MAX_ITERATIONS
    )


def verify_secret(settings, candidate: str, *, now_ms: int | None = None) -> bool:
    if unlock_wait_remaining_ms(settings, now_ms=now_ms) > 0:
        return False
    try:
        if not has_lock_secret(settings) or not candidate:
            raise ValueError("Vault Lock verifier is unavailable")
        expected = bytes.fromhex(settings.vault_lock_hash)
        actual = bytes.fromhex(_hash_secret(
            candidate,
            settings.vault_lock_salt,
            int(settings.vault_lock_iterations or DEFAULT_ITERATIONS),
        ))
        valid = hmac.compare_digest(expected, actual)
    except (AttributeError, TypeError, ValueError):
        valid = False
    if valid:
        reset_failed_unlocks(settings)
        return True
    _record_failed_unlock(settings, now_ms=now_ms)
    return False


def unlock_wait_remaining_ms(settings, *, now_ms: int | None = None) -> int:
    now = _now_ms() if now_ms is None else int(now_ms)
    try:
        until = max(0, int(getattr(settings, "vault_lock_locked_until_ms", 0)))
    except (TypeError, ValueError):
        until = 0
    return max(0, until - now)


def reset_failed_unlocks(settings) -> None:
    settings.vault_lock_failures = 0
    settings.vault_lock_locked_until_ms = 0


def _record_failed_unlock(settings, *, now_ms: int | None = None) -> None:
    try:
        failures = max(0, int(getattr(settings, "vault_lock_failures", 0))) + 1
    except (TypeError, ValueError):
        failures = 1
    delay = 0
    if failures >= FAILURE_THRESHOLD:
        exponent = min(MAX_BACKOFF_EXPONENT, (failures - FAILURE_THRESHOLD) // FAILURE_STEP)
        delay = BASE_LOCKOUT_MS * (1 << exponent)
    now = _now_ms() if now_ms is None else int(now_ms)
    settings.vault_lock_failures = failures
    settings.vault_lock_locked_until_ms = now + delay if delay else 0


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def lock_config(settings) -> VaultLockConfig:
    try:
        auto = max(0, int(getattr(settings, "vault_lock_auto_minutes", 0)))
    except (TypeError, ValueError):
        auto = 0
    enabled = bool(getattr(settings, "vault_lock_enabled", False))
    return VaultLockConfig(
        enabled=enabled,
        mode=normalize_mode(getattr(settings, "vault_lock_mode", LOCK_MODE_PIN)),
        lock_on_startup=enabled,
        lock_when_minimized=bool(getattr(settings, "vault_lock_when_minimized", False)),
        auto_lock_minutes=auto,
        has_secret=has_lock_secret(settings),
    )


def should_lock_on_startup(settings) -> bool:
    cfg = lock_config(settings)
    return cfg.enabled


def get_vault_lock_state(
    settings,
    *,
    runtime_locked: bool | None = None,
    unlocked: bool = False,
) -> VaultLockState:
    """Resolve configuration and active-session state in one place.

    An explicit runtime lock is authoritative even if configuration has since
    become inconsistent. The disabled state applies only when there is no
    active lock transition to preserve.
    """
    if runtime_locked is True:
        return VaultLockState.LOCKED
    if not bool(getattr(settings, "vault_lock_enabled", False)):
        return VaultLockState.DISABLED
    if (runtime_locked is False or unlocked) and has_lock_secret(settings):
        return VaultLockState.UNLOCKED
    return VaultLockState.LOCKED


def lock_state(settings, *, unlocked: bool = False) -> VaultLockState:
    """Compatibility wrapper for callers that only have config/unlocked state."""
    return get_vault_lock_state(settings, unlocked=unlocked)


def record_lock_event(events, event_type: str, *, mode: str | None = None,
                      reason: str | None = None, method: str | None = None,
                      enabled: bool | None = None,
                      policy: dict[str, object] | None = None) -> str:
    details: dict[str, object] = {}
    details["canonical_event"] = CANONICAL_EVENT_BY_STORAGE_NAME.get(event_type, event_type)
    details["platform"] = "windows"
    if mode:
        details["mode"] = normalize_mode(mode)
    if reason:
        details["reason"] = reason
    if method:
        details["method"] = method
    if enabled is not None:
        details["enabled"] = bool(enabled)
    if policy is not None:
        details["policy"] = policy
    return events.record(event_type, None, details)


def no_forbidden_lock_claims(text: str) -> bool:
    low = text.lower()
    return not any(claim.lower() in low for claim in FORBIDDEN_LOCK_CLAIMS)


def safe_lock_settings_summary(settings) -> dict:
    cfg = lock_config(settings)
    return {
        "enabled": cfg.enabled,
        "mode": cfg.mode,
        "lock_on_startup": cfg.enabled,
        "lock_when_minimized": cfg.lock_when_minimized,
        "auto_lock_minutes": cfg.auto_lock_minutes,
        "has_secret": cfg.has_secret,
        "updated_at": models.now_iso(),
    }
