"""Left-hand filter navigation."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core import storage as S


# (filter constant, label) in display order. A None entry renders a separator.
FILTER_ITEMS = [
    (S.FILTER_ALL, "All Clips"),
    (S.FILTER_FAVORITES, "Favorites"),
    (None, None),
    (S.FILTER_LINKS, "Links"),
    (S.FILTER_FILES, "Files / Paths"),
    (S.FILTER_CODE, "Code"),
    (S.FILTER_COMMANDS, "Commands"),
    (S.FILTER_EMAILS, "Emails"),
    (S.FILTER_PHONES, "Phone numbers"),
    (None, None),
    (S.FILTER_SENSITIVE, "Sensitive"),
    (S.FILTER_DUPLICATES, "Duplicates"),
    (None, None),
    (S.FILTER_TODAY, "Today"),
    (S.FILTER_WEEK, "This Week"),
    (S.FILTER_EXPIRED, "Expired"),
    (S.FILTER_RECENTLY_REMOVED, "Recently Removed"),
]


class FilterNav(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select: Callable[[str], None], **kw):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._active = S.FILTER_ALL
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._labels: dict[str, str] = {}     # fixed filters only
        self._collection_buttons: dict[str, ctk.CTkButton] = {}

        title = ctk.CTkLabel(self, text="Cache Vault", anchor="w",
                             font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(fill="x", padx=8, pady=(6, 2))
        tagline = ctk.CTkLabel(self, text="Keep the cache worth keeping.",
                               anchor="w", text_color=("gray40", "gray60"),
                               font=ctk.CTkFont(size=11))
        tagline.pack(fill="x", padx=8, pady=(0, 10))

        for key, label in FILTER_ITEMS:
            if key is None:
                self._separator()
                continue
            self._labels[key] = label
            self._buttons[key] = self._nav_button(self, key, label)

        # Collections section (populated dynamically from the database).
        self._separator()
        ctk.CTkLabel(self, text="Collections", anchor="w",
                     text_color=("gray40", "gray60"),
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(fill="x", padx=10, pady=(2, 2))
        self._collections_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._collections_frame.pack(fill="x")
        self._collections_empty = ctk.CTkLabel(
            self._collections_frame, text="  (none yet)", anchor="w",
            text_color=("gray55", "gray50"), font=ctk.CTkFont(size=11))
        self._collections_empty.pack(fill="x", padx=10)

        self._highlight()

    # --- helpers -----------------------------------------------------------
    def _separator(self) -> None:
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=10, pady=6)

    def _nav_button(self, parent, key: str, label: str) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=label, anchor="w", corner_radius=6,
            fg_color="transparent", text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray25"),
            command=lambda k=key: self._select(k),
        )
        btn.pack(fill="x", padx=6, pady=1)
        return btn

    def _select(self, key: str) -> None:
        self._active = key
        self._highlight()
        self._on_select(key)

    @property
    def active(self) -> str:
        return self._active

    def _highlight(self) -> None:
        for key, btn in {**self._buttons, **self._collection_buttons}.items():
            btn.configure(fg_color=("gray75", "gray30") if key == self._active
                          else "transparent")

    def update_counts(self, counts: dict[str, int]) -> None:
        for key, label in self._labels.items():
            n = counts.get(key, 0)
            self._buttons[key].configure(text=f"{label}   ({n})" if n else label)

    def update_collections(self, collections: list[dict]) -> None:
        """Rebuild the dynamic collection buttons (name + count)."""
        for btn in self._collection_buttons.values():
            btn.destroy()
        self._collection_buttons.clear()
        if not collections:
            self._collections_empty.pack(fill="x", padx=10)
        else:
            self._collections_empty.pack_forget()
            for col in collections:
                key = S.COLLECTION_PREFIX + col["name"]
                btn = self._nav_button(
                    self._collections_frame, key,
                    f"  {col['name']}   ({col['count']})")
                self._collection_buttons[key] = btn
        self._highlight()
