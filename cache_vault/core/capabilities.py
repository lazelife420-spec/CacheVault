"""Feature capability registry for future Core/Pro split.

This module is declarative only. It does not implement payments, licensing,
checkout UI, or shipped paid claims.
"""

from __future__ import annotations

from dataclasses import dataclass


CORE = "core"
PLANNED_PRO = "planned_pro"


@dataclass(frozen=True)
class Capability:
    key: str
    tier: str
    label: str
    available: bool
    note: str


CAPABILITIES: dict[str, Capability] = {
    "local_vault": Capability(
        "local_vault", CORE, "Local vault access", True,
        "Users can access their own saved vault data.",
    ),
    "basic_safes": Capability(
        "basic_safes", CORE, "Default Safe and custom Safes", True,
        "Safes organize local vault items. They are not encryption.",
    ),
    "basic_vault_lock": Capability(
        "basic_vault_lock", CORE, "Basic Vault Lock", True,
        "App privacy lock for the local UI.",
    ),
    "receipts": Capability(
        "receipts", CORE, "Stamped Receipts", True,
        "Local proof records for vault actions.",
    ),
    "send_to_pc": Capability(
        "send_to_pc", CORE, "Send to PC", True,
        "Paired phone shares can be sent to the desktop inbox.",
    ),
    "copy_clean_basic": Capability(
        "copy_clean_basic", CORE, "Copy Clean basics", True,
        "Built-in clean copy formats.",
    ),
    "premium_safe_themes": Capability(
        "premium_safe_themes", PLANNED_PRO, "Premium Safe themes/icons", False,
        "Planned cosmetic packs only; not required for access.",
    ),
    "premium_lock_animations": Capability(
        "premium_lock_animations", PLANNED_PRO, "Custom lock animations", False,
        "Planned visual polish. Lock security claims remain unchanged.",
    ),
    "saved_copy_clean_presets": Capability(
        "saved_copy_clean_presets", PLANNED_PRO, "Saved Copy Clean presets", False,
        "Planned workflow convenience.",
    ),
    "advanced_proof_templates": Capability(
        "advanced_proof_templates", PLANNED_PRO, "Advanced proof-pack templates", False,
        "Planned export template customization.",
    ),
    "encrypted_safes": Capability(
        "encrypted_safes", PLANNED_PRO, "Encrypted Safes", False,
        "Only available after real encrypted storage is implemented.",
    ),
}


FORBIDDEN_PAID_CLAIMS = (
    "paid features are shipped",
    "checkout",
    "payment",
    "cloud sync",
    "encrypted safes are available",
    "military-grade",
    "bank-grade encryption",
    "final release",
)


def has_forbidden_claims(text: str) -> bool:
    low = text.lower()
    return any(claim in low for claim in FORBIDDEN_PAID_CLAIMS)
