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
    "Capture everything. Keep what matters. Export with receipts."
)
VAULT_TAGLINE = "Local saved-clips vault"
VAULT_STATUS_ACTIVE = "Local Vault Active"
VAULT_STATUS_NOTE = (
    "Your saved clips stay on this PC unless you export or enable Mobile Access."
)
MOBILE_ACCESS_HONEST = (
    "Mobile Access is off by default. Pair a phone only when you choose."
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
MOBILE_PROMISE = "Saved on your PC. Ready on your phone. Keep the receipt."
TERM_MOBILE_ACCESS = "Mobile Access"
TERM_MOBILE_ACCESS_RECEIPTS = "Mobile Access Receipts"
TERM_COMMAND_CENTER = "Command Center"
TERM_EDITABLE_COPIES = "Editable Copies / Revisions"
TERM_HTML_BUNDLES = "HTML Bundles"
TERM_EXPORTS = "Exports"

# Vault / proof language (subtle, businesslike)
LABEL_ORIGINAL_PROTECTED = "Original protected"
LABEL_EDITABLE_COPY = "Editable copy"
LABEL_HTML_BUNDLE_COPY = "HTML bundle copy"
LABEL_RECEIPT_STAMPED = "Receipt stamped"
LABEL_HASH_VERIFIED = "Hash verified"
LABEL_LOCAL_ONLY = "Local only"
LABEL_MOBILE_PAIRED = "Mobile paired"
LABEL_PHASE5_MANIFEST = "Manifest / SHA export — Phase 5"
LABEL_MANIFEST_INCLUDED = "Included in proof export zip"
LABEL_SHA256SUMS_INCLUDED = "Included in proof export zip"

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
