"""The Proof Foundry™ brand constants — single source of truth.

Used by UI chrome, export surfaces, and documentation. No runtime deps.
"""

from __future__ import annotations

# --- Studio -----------------------------------------------------------------
STUDIO_NAME = "The Proof Foundry™"
STUDIO_SHORT = "Proof Foundry"
STUDIO_TAGLINE = "Proof-first software forged for builders."
STUDIO_FOOTER = "Forged by The Proof Foundry™ — Build it. Prove it. Ship it."
STUDIO_MOTTO = "Build it. Prove it. Ship it."

# --- Product ----------------------------------------------------------------
PRODUCT_NAME = "Cache Vault™"
PRODUCT_BYLINE = "A Proof Foundry product"
PRODUCT_POSITIONING = (
    "A modern clipboard vault from The Proof Foundry."
)
PRODUCT_PROMISE = (
    "Capture everything. Auto-organize it. Save what matters. "
    "Export with receipts."
)
PRODUCT_ABOUT = (
    "Cache Vault does not pretend to be magic. It captures clipboard history, "
    "helps organize what matters, and exports saved clips with timestamps, "
    "Proof Manifests, and Stamped Receipts."
)

WINDOW_TITLE = f"{PRODUCT_NAME} — {PRODUCT_BYLINE}"

# --- Canonical UI terms -----------------------------------------------------
TERM_EXPORT = "Export / Save As"
TERM_PROOF_MANIFEST = "Proof Manifest"
TERM_STAMPED_RECEIPTS = "Stamped Receipts"
TERM_RECENTLY_REMOVED = "Recently Removed"
TERM_FAVORITES = "Favorites"
TERM_COLLECTIONS = "Collections"

MOBILE_PRODUCT_NAME = "Cache Vault Mobile"
MOBILE_BYLINE = "A Proof Foundry companion app"
MOBILE_PROMISE = "Access your saved clips. Keep the receipt."
TERM_MOBILE_ACCESS = "Mobile Access"
TERM_MOBILE_ACCESS_RECEIPTS = "Mobile Access Receipts"

RECEIPT_NOTE = "If it matters, keep the receipt."

# --- Palette ----------------------------------------------------------------
FOUNDRY_BLACK = "#0B0F14"
IRON_GRAY = "#1C232B"
PROOF_TEAL = "#00D1B2"
PROOF_TEAL_HOVER = "#00B89C"
RECEIPT_WHITE = "#F4F7F8"
STAMP_GOLD = "#D6A84F"
WARNING_RED = "#E5484D"
WARNING_RED_HOVER = "#C93D42"
MUTED_TEXT = "#8A939C"

# CustomTkinter tuples: (light_mode, dark_mode) — app defaults to dark.
PANEL_BG = (RECEIPT_WHITE, FOUNDRY_BLACK)
SURFACE_BG = ("#E8ECED", IRON_GRAY)
ROW_BG = ("#E0E4E6", IRON_GRAY)
ROW_SELECTED_BG = ("#D0D8DA", "#263038")
MUTED_FG = ("#5C6670", MUTED_TEXT)
