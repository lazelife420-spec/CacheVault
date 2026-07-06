"""Left-hand filter navigation with grouped headings."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from .. import licensing
from ..core import storage as S
from ..core.settings import Settings
from ..core.smart_folders import SMART_FOLDER_NAV
from . import theme
from .guide_copy import EMPTY_SAFES, NAV_TOOLTIPS, TOOLTIP_SAFES
from .tooltip import bind_tooltip

# Sidebar screens and actions
NAV_QUICK_PASTE = "nav_quick_paste"
NAV_STAMPED_RECEIPTS = "nav_stamped_receipts"
NAV_EXPORTS = "nav_exports"
NAV_EDITABLE_COPIES = "nav_editable_copies"
NAV_HTML_BUNDLES = "nav_html_bundles"
NAV_MOBILE_ACCESS = "nav_mobile_access"
NAV_MOBILE_INBOX = "nav_mobile_inbox"
NAV_VAULT_MACROS = "nav_vault_macros"
NAV_HOTKEY_ACTIONS = "nav_hotkey_actions"
NAV_FOUNDER = "nav_founder"
NAV_SETTINGS = "nav_settings"

NAV_DIALOG_ONLY = frozenset({NAV_QUICK_PASTE, NAV_FOUNDER})
NAV_SCREEN_KEYS = frozenset({
    NAV_STAMPED_RECEIPTS,
    NAV_EXPORTS,
    NAV_EDITABLE_COPIES,
    NAV_HTML_BUNDLES,
    NAV_MOBILE_ACCESS,
    NAV_MOBILE_INBOX,
    NAV_VAULT_MACROS,
    NAV_HOTKEY_ACTIONS,
})

_NAV_ICONS: dict[str, str] = {
    S.FILTER_HOME: "⌂ ",
    S.FILTER_ALL: "▣ ",
    S.FILTER_FAVORITES: "★ ",
    S.FILTER_SCREENSHOTS: "▦ ",
    S.FILTER_SENSITIVE: "⚠ ",
    S.FILTER_DUPLICATES: "≡ ",
    NAV_QUICK_PASTE: "⎘ ",
    NAV_STAMPED_RECEIPTS: "⬢ ",
    NAV_EXPORTS: "↗ ",
    NAV_EDITABLE_COPIES: "⎘ ",
    NAV_HTML_BUNDLES: "🌐 ",
    NAV_MOBILE_ACCESS: "◈ ",
    NAV_MOBILE_INBOX: "↓ ",
    NAV_VAULT_MACROS: "⚡ ",
    NAV_HOTKEY_ACTIONS: "⌨ ",
    NAV_FOUNDER: "◆ ",
    NAV_SETTINGS: "⚙ ",
}

FILTER_GROUPS: list[tuple[str | None, list[tuple[str, str]]]] = [
    ("COMMAND", [
        (S.FILTER_HOME, brand.TERM_COMMAND_CENTER),
        (NAV_QUICK_PASTE, "Quick Paste"),
        (NAV_VAULT_MACROS, brand.TERM_SNIPPET_MACROS),
        (NAV_HOTKEY_ACTIONS, "Hotkey Actions"),
    ]),
    ("VAULT", [
        (S.FILTER_ALL, "All Clips"),
        (S.FILTER_FAVORITES, "Favorites"),
        (S.FILTER_SCREENSHOTS, "Screenshots / Images"),
        (S.FILTER_LINKS, "Links"),
        (S.FILTER_FILES, "Files / Paths"),
        (S.FILTER_CODE, "Code"),
        (S.FILTER_COMMANDS, "Commands"),
        (S.FILTER_EMAILS, "Emails"),
        (S.FILTER_PHONES, "Phone Numbers"),
    ]),
    ("SMART FOLDERS", list(SMART_FOLDER_NAV)),
    ("REVIEW", [
        (S.FILTER_SENSITIVE, "Sensitive"),
        (S.FILTER_DUPLICATES, "Duplicates"),
        (S.FILTER_RECENTLY_REMOVED, "Recently Removed"),
        (S.FILTER_EXPIRED, "Expired"),
    ]),
    ("PROOF", [
        (NAV_STAMPED_RECEIPTS, brand.TERM_STAMPED_RECEIPTS),
        (NAV_EXPORTS, brand.TERM_EXPORTS),
        (NAV_EDITABLE_COPIES, brand.TERM_EDITABLE_COPIES),
        (NAV_HTML_BUNDLES, brand.TERM_HTML_BUNDLES),
    ]),
    ("ACCESS", [
        (NAV_MOBILE_INBOX, brand.TERM_MOBILE_INBOX),
        (NAV_MOBILE_ACCESS, brand.TERM_MOBILE_ACCESS),
        (NAV_SETTINGS, "Settings"),
    ]),
    ("TIME", [
        (S.FILTER_TODAY, "Today"),
        (S.FILTER_WEEK, "This Week"),
        (S.FILTER_OLDER, "Older"),
    ]),
]


class FilterNav(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        on_select: Callable[[str], None],
        *,
        settings: Settings | None = None,
        on_safe_context: Callable[[dict, int, int], None] | None = None,
        on_collection_context: Callable[[str, int, int], None] | None = None,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_safe_context = on_safe_context
        self._on_collection_context = on_collection_context
        self._settings = settings
        self._collapsed = set(getattr(settings, "sidebar_collapsed_sections", []) or [])
        self._active = S.FILTER_HOME
        self._rows: dict[str, ctk.CTkFrame] = {}
        self._labels: dict[str, ctk.CTkLabel] = {}
        self._counts: dict[str, ctk.CTkLabel] = {}
        self._labels_text: dict[str, str] = {}
        self._collection_rows: dict[str, ctk.CTkFrame] = {}
        self._safe_rows: dict[str, ctk.CTkFrame] = {}
        self._safe_meta: dict[str, dict] = {}
        self._section_frames: dict[str, ctk.CTkFrame] = {}
        self._section_buttons: dict[str, ctk.CTkButton] = {}

        title = ctk.CTkLabel(self, text=f"◈ {brand.PRODUCT_NAME}", anchor="w",
                             text_color=brand.PROOF_TEAL,
                             font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(fill="x", padx=8, pady=(6, 0))
        byline = ctk.CTkLabel(self, text=brand.VAULT_TAGLINE, anchor="w",
                              text_color=brand.MUTED_FG,
                              font=ctk.CTkFont(size=11), wraplength=200,
                              justify="left")
        byline.pack(fill="x", padx=8, pady=(0, 2))
        seal = ctk.CTkLabel(
            self, text=f"{brand.LABEL_VAULT_SEALED} · {brand.LABEL_LOCAL_ONLY}",
            anchor="w", text_color=brand.STAMP_GOLD,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        seal.pack(fill="x", padx=8, pady=(0, 10))

        # Always visible — license import must not hide behind collapsed ACCESS.
        self._labels_text[NAV_FOUNDER] = "Founder"
        founder_label = _NAV_ICONS.get(NAV_FOUNDER, "") + "Founder"
        self._rows[NAV_FOUNDER] = self._nav_row(self, NAV_FOUNDER, founder_label)
        self._separator()

        for heading, items in FILTER_GROUPS:
            parent = self
            if heading:
                parent = self._section(heading, default_open=False)
            for key, label in items:
                self._labels_text[key] = label
                display = _NAV_ICONS.get(key, "") + label
                self._rows[key] = self._nav_row(parent, key, display)

        self._separator()
        self._collections_frame = self._section("COLLECTIONS", default_open=False)
        self._collections_empty = ctk.CTkLabel(
            self._collections_frame, text="(none yet)", anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11))
        self._collections_empty.pack(fill="x", padx=14, pady=2)

        self._separator()
        self._safes_frame = self._section("SAFES", default_open=False)
        safes_heading = self._section_buttons["SAFES"]
        bind_tooltip(safes_heading, TOOLTIP_SAFES)
        self._safes_empty = ctk.CTkLabel(
            self._safes_frame, text=EMPTY_SAFES, anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
            wraplength=200, justify="left",
        )
        self._safes_empty.pack(fill="x", padx=14, pady=2)

        self._highlight()

    def _separator(self) -> None:
        ctk.CTkFrame(self, height=1, fg_color=("#C8D0D4", "#263038")).pack(
            fill="x", padx=10, pady=6)

    def _section(self, heading: str, *, default_open: bool) -> ctk.CTkFrame:
        # default_open only tweaks this button's top padding; actual initial
        # visibility comes from settings.sidebar_collapsed_sections via
        # self._collapsed, so a fresh profile's real default lives there.
        frame = ctk.CTkFrame(self, fg_color="transparent")
        self._section_frames[heading] = frame
        btn = ctk.CTkButton(
            self,
            text=self._section_label(heading),
            anchor="w",
            height=24,
            command=lambda h=heading: self._toggle_section(h),
            fg_color="transparent",
            hover_color=theme.nav_hover_bg(),
            text_color=brand.STAMP_GOLD,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self._section_buttons[heading] = btn
        btn.pack(fill="x", padx=6, pady=(8 if default_open else 2, 4))
        if heading not in self._collapsed:
            # No after= needed here: this is the frame's first-ever pack
            # call, immediately following its own button in this same
            # construction sequence, so it already lands in the right spot.
            frame.pack(fill="x")
        return frame

    def _section_label(self, heading: str) -> str:
        return ("▸ " if heading in self._collapsed else "▾ ") + heading

    def _toggle_section(self, heading: str) -> None:
        frame = self._section_frames[heading]
        if heading in self._collapsed:
            self._collapsed.remove(heading)
            # Anchor after our own heading button — a bare pack() would
            # append to the end of the whole sidebar's sibling list instead
            # of restoring this section's original position.
            frame.pack(fill="x", after=self._section_buttons[heading])
        else:
            self._collapsed.add(heading)
            frame.pack_forget()
        self._section_buttons[heading].configure(text=self._section_label(heading))
        if self._settings is not None:
            self._settings.sidebar_collapsed_sections = sorted(self._collapsed)
            self._settings.save()

    def _nav_row(self, parent, key: str, label: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=6)
        row.pack(fill="x", padx=4, pady=1)
        row.grid_columnconfigure(0, weight=1)
        lbl = ctk.CTkLabel(row, text=label, anchor="w",
                           font=ctk.CTkFont(size=12))
        lbl.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=6)
        cnt = ctk.CTkLabel(row, text="", anchor="e", width=36,
                           font=ctk.CTkFont(size=11),
                           text_color=brand.MUTED_FG)
        cnt.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._labels[key] = lbl
        self._counts[key] = cnt
        tip = NAV_TOOLTIPS.get(key)
        if tip:
            bind_tooltip(row, tip)
            bind_tooltip(lbl, tip)
        for w in (row, lbl, cnt):
            w.bind("<Button-1>", lambda _e, k=key: self._select(k))
            w.configure(cursor="hand2")
        row.bind("<Enter>", lambda _e, r=row: self._hover_row(r, key, True))
        row.bind("<Leave>", lambda _e, r=row: self._hover_row(r, key, False))
        return row

    def _hover_row(self, row: ctk.CTkFrame, key: str, inside: bool) -> None:
        if key == self._active:
            return
        if inside:
            row.configure(fg_color=theme.nav_hover_bg())
        else:
            row.configure(fg_color="transparent")

    def _select(self, key: str) -> None:
        if key in NAV_DIALOG_ONLY:
            self._on_select(key)
            return
        self._active = key
        self._highlight()
        self._on_select(key)

    @property
    def active(self) -> str:
        return self._active

    def set_active(self, key: str) -> None:
        if key in NAV_DIALOG_ONLY:
            return
        self._active = key
        self._highlight()

    def _highlight(self) -> None:
        all_keys = {**self._rows, **self._collection_rows, **self._safe_rows}
        for key, row in all_keys.items():
            active = key == self._active
            row.configure(fg_color=theme.nav_active_bg() if active else "transparent")
            lbl = self._labels.get(key)
            if lbl:
                lbl.configure(
                    text_color=(brand.FOUNDRY_BLACK, brand.PROOF_TEAL) if active else brand.MUTED_FG,
                    font=ctk.CTkFont(size=12, weight="bold" if active else "normal"),
                )
            cnt = self._counts.get(key)
            # Founder's slot is a license-status badge, not an item count —
            # its color is owned by update_founder_status(), not the active
            # row highlight (Founder can never be "active", it's dialog-only).
            if cnt and key != NAV_FOUNDER:
                cnt.configure(
                    text_color=(brand.FOUNDRY_BLACK, brand.STAMP_GOLD) if active else brand.MUTED_FG,
                )

    def update_counts(self, counts: dict[str, int]) -> None:
        for key, label in self._labels_text.items():
            if key == S.FILTER_HOME:
                self._counts[key].configure(text="")
                continue
            if key == NAV_FOUNDER:
                continue  # owned by update_founder_status(), not a count.
            n = counts.get(key, 0)
            self._counts[key].configure(text=str(n) if n else "")

    def update_founder_status(self, status: licensing.LicenseStatus) -> None:
        badge = self._counts.get(NAV_FOUNDER)
        if not badge:
            return
        if status.state == licensing.LicenseState.FOUNDER_VALID:
            badge.configure(text="FOUNDER", text_color=brand.STAMP_GOLD)
        elif status.state == licensing.LicenseState.MISSING_LICENSE:
            badge.configure(text="FREE", text_color=brand.MUTED_FG)
        elif status.state == licensing.LicenseState.EXPIRED_LICENSE:
            badge.configure(text="EXPIRED", text_color=brand.WARNING_RED)
        else:
            badge.configure(text="ISSUE", text_color=brand.WARNING_RED)

    def update_collections(self, collections: list[dict]) -> None:
        for row in self._collection_rows.values():
            row.destroy()
        self._collection_rows.clear()
        for key in list(self._labels):
            if key.startswith(S.COLLECTION_PREFIX):
                del self._labels[key]
                if key in self._counts:
                    del self._counts[key]
        if not collections:
            self._collections_empty.pack(fill="x", padx=14, pady=2)
        else:
            self._collections_empty.pack_forget()
            for col in collections:
                name = col["name"]
                key = S.COLLECTION_PREFIX + name
                row = self._nav_row(self._collections_frame, key, f"  {name}")
                self._collection_rows[key] = row
                self._counts[key].configure(text=str(col["count"]))
                # Right-click on a collection row → context menu
                row.bind("<Button-3>", lambda e, n=name: self._collection_context(e, n))
                for child in row.winfo_children():
                    child.bind("<Button-3>", lambda e, n=name: self._collection_context(e, n))
        self._highlight()

    def _collection_context(self, event, name: str) -> None:
        if self._on_collection_context is None:
            return
        self._on_collection_context(name, event.x_root, event.y_root)

    def update_safes(self, safes: list[dict]) -> None:
        for row in self._safe_rows.values():
            row.destroy()
        self._safe_rows.clear()
        self._safe_meta.clear()
        for key in list(self._labels):
            if key.startswith(S.SAFE_PREFIX):
                del self._labels[key]
                del self._counts[key]
        shown = [s for s in safes if s.get("count", 0) > 0 or s.get("builtin")]
        if not shown:
            self._safes_empty.pack(fill="x", padx=14, pady=2)
        else:
            self._safes_empty.pack_forget()
            for safe in shown:
                key = S.SAFE_PREFIX + safe["id"]
                row = self._nav_row(self._safes_frame, key, f"  {safe['name']}")
                self._safe_rows[key] = row
                self._safe_meta[key] = dict(safe)
                row.bind("<Button-3>", lambda e, k=key: self._safe_context(e, k))
                for child in row.winfo_children():
                    child.bind("<Button-3>", lambda e, k=key: self._safe_context(e, k))
                self._counts[key].configure(text=str(safe.get("count", 0)))
        self._highlight()

    def _safe_context(self, event, key: str) -> None:
        if self._on_safe_context is None:
            return
        safe = self._safe_meta.get(key)
        if safe:
            self._on_safe_context(safe, event.x_root, event.y_root)
