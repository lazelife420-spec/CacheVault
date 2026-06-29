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
    "Everything you copy. Secured. Proved."
)
VAULT_TAGLINE = "Your data. Your vault. Your proof."
VAULT_HERO = VAULT_TAGLINE
VAULT_STATUS_ACTIVE = "Local Vault Active"
LABEL_VAULT_SEALED = "Vault sealed"
LABEL_CAPTURE_ACTIVE = "Capture Active"
LABEL_RECEIPTS_AVAILABLE = "Receipts Available"
LABEL_READY_EXPORT = "Ready to export proof"
LABEL_SAFE_ASSIGNED = "Safe assigned"
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
TERM_SNIPPET_MACROS = "Snippet Macros"
TERM_CAPTURE_RULES = "Capture Rules"
TERM_VAULT_STATUS = "Vault Status"
TERM_CUSTODY_SUMMARY = "Custody Summary"
TERM_RECENT_ACTIVITY = "Recent Activity"
TERM_QUICK_ACTIONS = "Quick Actions"
TERM_MOBILE_INBOX = "Mobile Inbox"
TERM_INCOMING_FROM_PHONE = "Incoming from Phone"
TERM_VAULT_ITEM = "Vault Item"
TERM_INSPECTOR_SEAL = "Item seal / status"
TERM_QUICK_PASTE = "Quick Paste"
LABEL_COPY_TO_CLIPBOARD = "Copy to Clipboard"
LABEL_COPY_IMAGE_TO_CLIPBOARD = "Copy Image to Clipboard"
QUICK_PASTE_HEADER = "◈ Quick Paste — pull from your vault"
QUICK_PASTE_HINT = "search · ↑/↓ select · Enter copy · Ctrl+Enter copy & stay · Esc close"
SELECTION_HINT = "Ctrl/Shift-click to select multiple"
TOAST_VAULT_IMAGE_COPIED = "◈ Screenshot copied to clipboard — paste wherever you need it"

# Vault / proof language (subtle, businesslike)
LABEL_ORIGINAL_PROTECTED = "Original protected"
LABEL_EDITABLE_COPY = "Editable copy"
LABEL_HTML_BUNDLE_COPY = "HTML bundle copy"
LABEL_RECEIPT_STAMPED = "Receipt stamped"
LABEL_HASH_VERIFIED = "Hash verified"
LABEL_LOCAL_ONLY = "Local only"
LABEL_MOBILE_PAIRED = "Mobile paired"
LABEL_PHASE5_MANIFEST = "Included in proof export zip"
LABEL_MANIFEST_INCLUDED = "Included in proof export zip"
LABEL_SHA256SUMS_INCLUDED = "Included in proof export zip"

RECEIPT_NOTE = "If it matters, keep the receipt."

# --- Palette ----------------------------------------------------------------
# Dark graphite / black-metal with restrained teal accents.
FOUNDRY_BLACK = "#06080A"
GRAPHITE = "#12161C"
IRON_GRAY = "#1A1F26"
BLACK_METAL = "#0E1218"
PROOF_TEAL = "#1A9E8C"
PROOF_TEAL_HOVER = "#147A6C"
PROOF_TEAL_DIM = "#0F5C52"
RECEIPT_WHITE = "#E8ECED"
STAMP_GOLD = "#C9A24D"
WARNING_RED = "#C93D42"
WARNING_RED_HOVER = "#A83238"
MUTED_TEXT = "#7A848E"
VAULT_BORDER = "#2A323C"

# CustomTkinter tuples: (light_mode, dark_mode) — app defaults to dark.
PANEL_BG = (RECEIPT_WHITE, GRAPHITE)
SURFACE_BG = ("#D8DEE2", IRON_GRAY)
ROW_BG = ("#D0D6DA", BLACK_METAL)
ROW_SELECTED_BG = ("#C0C8CE", "#222830")
MUTED_FG = ("#5C6670", MUTED_TEXT)
VAULT_CARD_BORDER = ("#B8C0C6", VAULT_BORDER)
