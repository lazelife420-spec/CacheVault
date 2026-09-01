"""Reality Gate — tiered validation control plane for Cache Vault.

Phase 1: four validation tiers (fast / engineering / product / canonical)
selected via a checked-in change-map. The canonical tier delegates to the
existing ``scripts/ci_local_full.ps1`` unchanged, so canonical coverage
semantics stay authoritative.
"""
from __future__ import annotations

__version__ = "0.1.0"
