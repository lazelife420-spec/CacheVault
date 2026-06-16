"""Left-hand filter navigation with grouped headings."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import storage as S
from . import theme

# Sidebar actions — open dialogs, not clip filters.
NAV_STAMPED_RECEIPTS = "nav_stamped_receipts"
NAV_MOBILE_ACCESS = "nav_mobile_access"
NAV_ACTION_KEYS = frozenset({NAV_STAMPED_RECEIPTS, NAV_MOBILE_ACCESS})

_NAV_ICONS: dict[str, str] = {
    S.FILTER_HOME: "⌂ ",
    S.FILTER_ALL: "▣ ",
    S.FILTER_FAVORITES: "★ ",
    S.FILTER_SCREENSHOTS: "▦ ",
    S.FILTER_SENSITIVE: "⚠ ",
    S.FILTER_DUPLICATES: "≡ ",
    NAV_STAMPED_RECEIPTS: "⬢ ",
    NAV_MOBILE_ACCESS: "◉ ",
}

FILTER_GROUPS: list[tuple[str | None, list[tuple[str, str]]]] = [
    ("VAULT", [
        (S.FILTER_HOME, "Home"),
        (S.FILTER_ALL, "All Clips"),
        (S.FILTER_FAVORITES, "Favorites"),
        (S.FILTER_SCREENSHOTS, "Screenshots / Images"),
    ]),
    ("SMART VIEWS", [
        (S.FILTER_LINKS, "Links"),
        (S.FILTER_FILES, "Files / Paths"),
        (S.FILTER_CODE, "Code"),
        (S.FILTER_COMMANDS, "Commands"),
        (S.FILTER_EMAILS, "Emails"),
        (S.FILTER_PHONES, "Phone Numbers"),
    ]),
    ("REVIEW", [
        (S.FILTER_SENSITIVE, "Sensitive"),
        (S.FILTER_DUPLICATES, "Duplicates"),
        (S.FILTER_RECENTLY_REMOVED, "Recently Removed"),
        (S.FILTER_EXPIRED, "Expired"),
    ]),
    ("PROOF & ACCESS", [
        (NAV_STAMPED_RECEIPTS, brand.TERM_STAMPED_RECEIPTS),
        (NAV_MOBILE_ACCESS, brand.TERM_MOBILE_ACCESS),
    ]),
    ("TIME", [
        (S.FILTER_TODAY, "Today"),
        (S.FILTER_WEEK, "This Week"),
        (S.FILTER_OLDER, "Older"),
    ]),
]


class FilterNav(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select: Callable[[str], None], **kw):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._active = S.FILTER_HOME
        self._rows: dict[str, ctk.CTkFrame] = {}
        self._labels: dict[str, ctk.CTkLabel] = {}
        self._counts: dict[str, ctk.CTkLabel] = {}
        self._labels_text: dict[str, str] = {}
        self._collection_rows: dict[str, ctk.CTkFrame] = {}

        title = ctk.CTkLabel(self, text=brand.PRODUCT_NAME, anchor="w",
                             font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(fill="x", padx=8, pady=(6, 0))
        byline = ctk.CTkLabel(self, text=brand.PRODUCT_BYLINE, anchor="w",
                              text_color=brand.PROOF_TEAL,
                              font=ctk.CTkFont(size=11))
        byline.pack(fill="x", padx=8, pady=(0, 2))
        tagline = ctk.CTkLabel(self, text=brand.VAULT_TAGLINE,
                               anchor="w", text_color=brand.MUTED_FG,
                               font=ctk.CTkFont(size=10), wraplength=200,
                               justify="left")
        tagline.pack(fill="x", padx=8, pady=(0, 2))
        promise = ctk.CTkLabel(self, text=brand.PRODUCT_PROMISE,
                               anchor="w", text_color=brand.MUTED_FG,
                               font=ctk.CTkFont(size=10), wraplength=200,
                               justify="left")
        promise.pack(fill="x", padx=8, pady=(0, 10))

        for heading, items in FILTER_GROUPS:
            if heading:
                ctk.CTkLabel(self, text=heading, anchor="w",
                             text_color=brand.STAMP_GOLD,
                             font=ctk.CTkFont(size=10, weight="bold")
                             ).pack(fill="x", padx=10, pady=(8, 4))
            for key, label in items:
                self._labels_text[key] = label
                display = _NAV_ICONS.get(key, "") + label
                self._rows[key] = self._nav_row(self, key, display)

        self._separator()
        ctk.CTkLabel(self, text="COLLECTIONS", anchor="w",
                     text_color=brand.STAMP_GOLD,
                     font=ctk.CTkFont(size=10, weight="bold")
                     ).pack(fill="x", padx=10, pady=(2, 4))
        self._collections_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._collections_frame.pack(fill="x")
        self._collections_empty = ctk.CTkLabel(
            self._collections_frame, text="(none yet)", anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11))
        self._collections_empty.pack(fill="x", padx=14, pady=2)

        self._highlight()

    def _separator(self) -> None:
        ctk.CTkFrame(self, height=1, fg_color=("#C8D0D4", "#263038")).pack(
            fill="x", padx=10, pady=6)

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
        if key in NAV_ACTION_KEYS:
            self._on_select(key)
            return
        self._active = key
        self._highlight()
        self._on_select(key)

    @property
    def active(self) -> str:
        return self._active

    def set_active(self, key: str) -> None:
        if key in NAV_ACTION_KEYS:
            return
        self._active = key
        self._highlight()

    def _highlight(self) -> None:
        all_keys = {**self._rows, **self._collection_rows}
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
            if cnt:
                cnt.configure(
                    text_color=(brand.FOUNDRY_BLACK, brand.STAMP_GOLD) if active else brand.MUTED_FG,
                )

    def update_counts(self, counts: dict[str, int]) -> None:
        for key, label in self._labels_text.items():
            if key == S.FILTER_HOME:
                self._counts[key].configure(text="")
                continue
            if key in NAV_ACTION_KEYS:
                n = counts.get(key, 0)
                self._counts[key].configure(text=str(n) if n else "")
                continue
            n = counts.get(key, 0)
            self._counts[key].configure(text=str(n) if n else "")

    def update_collections(self, collections: list[dict]) -> None:
        for row in self._collection_rows.values():
            row.destroy()
        self._collection_rows.clear()
        for key in list(self._labels):
            if key.startswith(S.COLLECTION_PREFIX):
                del self._labels[key]
                del self._counts[key]
        if not collections:
            self._collections_empty.pack(fill="x", padx=14, pady=2)
        else:
            self._collections_empty.pack_forget()
            for col in collections:
                key = S.COLLECTION_PREFIX + col["name"]
                row = self._nav_row(self._collections_frame, key, f"  {col['name']}")
                self._collection_rows[key] = row
                self._counts[key].configure(text=str(col["count"]))
        self._highlight()
