"""First-use guide, tooltips, and empty-state copy — plain language, no false claims."""

from __future__ import annotations

GUIDE_TITLE = "Welcome to Cache Vault"
GUIDE_SUBTITLE = (
    "Your local vault for copied text, links, files, phone shares, and proof receipts."
)

GUIDE_CARDS: list[tuple[str, str]] = [
    (
        "Save what matters",
        "Cache Vault keeps copied text, links, screenshots, files, "
        "and shared phone items in your local vault.",
    ),
    (
        "Organize with Safes",
        "Safes are local sections for keeping items organized. "
        "They are not encryption unless encryption is added later.",
    ),
    (
        "Receipts prove actions",
        "Every important action can stamp a receipt: saved, shared from phone, "
        "exported, edited, or removed.",
    ),
    (
        "Send from phone",
        "Use Cache Vault Mobile to share from Android and send items to your PC Inbox.",
    ),
    (
        "Export proof",
        "Proof exports bundle selected items with receipts and hashes "
        "so you can verify what happened later.",
    ),
]

GUIDE_BTN_START = "Start using Cache Vault"
GUIDE_BTN_RECEIPTS = "Show me receipts"
GUIDE_BTN_DISMISS = "Do not show again"
SETTINGS_SHOW_GUIDE_AGAIN = "Show first-use guide again"

TOOLTIP_STAMPED_RECEIPTS = (
    "Receipts are local proof records. They show what happened, when it happened, "
    "and which item was involved. Receipts do not need to store the full private content."
)
TOOLTIP_SAFES = (
    "Safes organize your vault items. They are local sections, not encryption."
)
TOOLTIP_MOBILE_INBOX = (
    "Items sent from your phone appear here after pairing. Each send can stamp a receipt."
)
TOOLTIP_EXPORT_PROOF = (
    "Creates a portable proof pack with selected items, receipts, manifest, and SHA256 hashes."
)
TOOLTIP_CAPTURE_ACTIVE = (
    "Cache Vault is watching allowed clipboard events according to your capture rules."
)
TOOLTIP_LOCAL_VAULT_ACTIVE = (
    "Your vault is stored locally on this PC unless you explicitly export or send items."
)
TOOLTIP_HASH_PROOF = (
    "Hashes help prove a file or item has not changed since the receipt/export was created."
)
TOOLTIP_VAULT_MACROS = (
    "Vault Macros let you paste reusable snippets by hotkey, shortcut, or picker. "
    "Macro actions can stamp receipts."
)

EMPTY_STAMPED_RECEIPTS = (
    "No receipts yet. Receipts appear when Cache Vault saves, receives, exports, "
    "edits, or removes items."
)
EMPTY_MOBILE_INBOX = (
    "Nothing from your phone yet. Pair Cache Vault Mobile, then tap Share on Android "
    "and choose Send to PC."
)
EMPTY_SAFES = (
    "Safes help organize your vault. Start with Default Safe, then add more when needed."
)
EMPTY_EXPORTS = (
    "No proof exports yet. Export a proof zip when you want a portable bundle "
    "with receipts and hashes."
)

NAV_TOOLTIPS: dict[str, str] = {
    "nav_stamped_receipts": TOOLTIP_STAMPED_RECEIPTS,
    "nav_exports": TOOLTIP_EXPORT_PROOF,
    "nav_mobile_inbox": TOOLTIP_MOBILE_INBOX,
    "nav_vault_macros": TOOLTIP_VAULT_MACROS,
}

FORBIDDEN_CLAIMS = (
    "cloud sync",
    "encrypted safes",
    "military grade",
    "blockchain",
    "notarized",
    "old person",
    "senior mode",
    "final release",
)

ALL_GUIDE_TEXT = "\n".join(
    [GUIDE_TITLE, GUIDE_SUBTITLE]
    + [f"{t} {b}" for t, b in GUIDE_CARDS]
    + [
        TOOLTIP_STAMPED_RECEIPTS,
        TOOLTIP_SAFES,
        TOOLTIP_MOBILE_INBOX,
        TOOLTIP_EXPORT_PROOF,
        TOOLTIP_CAPTURE_ACTIVE,
        TOOLTIP_LOCAL_VAULT_ACTIVE,
        TOOLTIP_HASH_PROOF,
        TOOLTIP_VAULT_MACROS,
        EMPTY_STAMPED_RECEIPTS,
        EMPTY_MOBILE_INBOX,
        EMPTY_SAFES,
        EMPTY_EXPORTS,
    ]
).lower()


def guide_copy_has_no_forbidden_claims() -> bool:
    return not any(claim in ALL_GUIDE_TEXT for claim in FORBIDDEN_CLAIMS)
