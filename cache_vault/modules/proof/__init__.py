"""Proof & Receipts module manifest.

Wraps the existing sensitive-expiry settings into a declarative schema.
Receipt export format and proof-pack destination will be added when those
settings land on the ``Settings`` dataclass.
"""

from __future__ import annotations

from .. import ModuleManifest
from ..settings_schema import SettingsCategory, SettingsField


class ProofModule(ModuleManifest):
    """Proof & Receipts — stamped receipts and proof-pack exports."""

    @property
    def id(self) -> str:
        return "proof"

    @property
    def name(self) -> str:
        return "Proof & Receipts"

    @property
    def description(self) -> str:
        return "Stamped receipts and proof-pack exports for vault actions"

    @property
    def category(self) -> str:
        return "proof"

    def get_settings_schema(self) -> list[SettingsCategory]:
        return [
            SettingsCategory(
                id="proof", label="Proof & Receipts", icon="\u2B22",
                fields=[
                    SettingsField(
                        "sensitive_expiry_enabled",
                        "Auto-expire sensitive clips", "toggle",
                        "Automatically expire clips detected as sensitive",
                        group="Sensitive Expiry",
                    ),
                    SettingsField(
                        "sensitive_expiry_minutes",
                        "Sensitive expiry (minutes)", "number",
                        "Minutes before a sensitive clip expires",
                        group="Sensitive Expiry", min_val=1, max_val=1440,
                    ),
                ],
            ),
        ]
