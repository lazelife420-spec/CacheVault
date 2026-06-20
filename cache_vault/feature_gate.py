"""Central Founder feature gate — use instead of scattered license checks."""

from __future__ import annotations

from typing import Callable

from . import licensing

# Human-readable labels for upgrade prompts.
FEATURE_LABELS: dict[str, str] = {
    "exports_advanced": "Advanced bulk exports",
    "zip_export": "ZIP bundle export",
    "proof_pack_export": "Proof-pack export",
    "html_bundle_export": "HTML bundle export",
    "editable_copies_advanced": "Editable copy workflows",
    "smart_filters_advanced": "Advanced review filters",
    "macros_advanced": "Vault Macros",
    "safes_advanced": "Custom Safes",
}


def requires_feature(feature_name: str, path=None) -> bool:
    """Return True when the feature is unlocked for this install."""
    return licensing.is_feature_enabled(feature_name, path)


def founder_feature_label(feature_name: str) -> str:
    return FEATURE_LABELS.get(feature_name, feature_name.replace("_", " ").title())


def check_feature(
    feature_name: str,
    *,
    on_blocked: Callable[[str], None] | None = None,
    path=None,
) -> bool:
    """Return True if allowed; optionally invoke *on_blocked* with feature key."""
    if requires_feature(feature_name, path):
        return True
    if on_blocked is not None:
        on_blocked(feature_name)
    return False
