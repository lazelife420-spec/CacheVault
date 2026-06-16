"""Left-hand filter navigation."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core import storage as S


# (filter constant, label) in display order. A None entry renders a separator.
FILTER_ITEMS = [
    (S.FILTER_ALL, "All"),
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
]


class FilterNav(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select: Callable[[str], None], **kw):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._active = S.FILTER_ALL
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._labels: dict[str, str] = {}

        title = ctk.CTkLabel(self, text="Cache Vault", anchor="w",
                             font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(fill="x", padx=8, pady=(6, 2))
        tagline = ctk.CTkLabel(self, text="Keep the cache worth keeping.",
                               anchor="w", text_color=("gray40", "gray60"),
                               font=ctk.CTkFont(size=11))
        tagline.pack(fill="x", padx=8, pady=(0, 10))

        for key, label in FILTER_ITEMS:
            if key is None:
                ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
                    fill="x", padx=10, pady=6)
                continue
            self._labels[key] = label
            btn = ctk.CTkButton(
                self, text=label, anchor="w", corner_radius=6,
                fg_color="transparent", text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
                command=lambda k=key: self._select(k),
            )
            btn.pack(fill="x", padx=6, pady=1)
            self._buttons[key] = btn
        self._highlight()

    def _select(self, key: str) -> None:
        self._active = key
        self._highlight()
        self._on_select(key)

    @property
    def active(self) -> str:
        return self._active

    def _highlight(self) -> None:
        for key, btn in self._buttons.items():
            if key == self._active:
                btn.configure(fg_color=("gray75", "gray30"))
            else:
                btn.configure(fg_color="transparent")

    def update_counts(self, counts: dict[str, int]) -> None:
        for key, btn in self._buttons.items():
            n = counts.get(key, 0)
            label = self._labels[key]
            btn.configure(text=f"{label}   ({n})" if n else label)
