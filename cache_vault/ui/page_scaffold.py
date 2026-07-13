"""Unified page layout scaffold and state widgets for CacheVault."""

from __future__ import annotations

import customtkinter as ctk
from . import theme
from .. import brand


class PageScaffold(ctk.CTkFrame):
    """Unified page layout layout enforcing header, optional toolbar, content, and footer."""

    def __init__(
        self,
        master,
        header: ctk.CTkFrame | None = None,
        toolbar: ctk.CTkFrame | None = None,
        content: ctk.CTkFrame | None = None,
        footer: ctk.CTkFrame | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.header = header
        self.toolbar = toolbar
        self.content = content
        self.footer = footer

        current_row = 0
        if self.header:
            self.header.grid(row=current_row, column=0, sticky="ew")
            current_row += 1

        if self.toolbar:
            self.toolbar.grid(row=current_row, column=0, sticky="ew")
            current_row += 1

        if self.content:
            self.content.grid(row=current_row, column=0, sticky="nsew")
            self.grid_rowconfigure(current_row, weight=1)
            current_row += 1

        if self.footer:
            self.footer.grid(row=current_row, column=0, sticky="ew")
            current_row += 1


class LoadingState(ctk.CTkFrame):
    """Premium pulsing skeleton cards loader."""

    def __init__(self, master, mode: str = "list", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)

        # Draw a set of skeleton cards simulating clips
        for i in range(4):
            card = ctk.CTkFrame(
                self,
                fg_color=brand.SURFACE_BG,
                height=72,
                corner_radius=8,
            )
            card.pack(fill="x", pady=6, padx=12)
            card.pack_propagate(False)

            # Left side content placeholder
            text_frame = ctk.CTkFrame(card, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True, padx=12, pady=10)

            # Pulsing header simulation
            title_bar = ctk.CTkFrame(
                text_frame,
                fg_color=brand.PANEL_BG,
                height=14,
                width=120 + (i % 3) * 40,
                corner_radius=4,
            )
            title_bar.pack(anchor="w", pady=(0, 6))
            title_bar.pack_propagate(False)

            # Pulsing body simulation
            body_bar = ctk.CTkFrame(
                text_frame,
                fg_color=brand.PANEL_BG,
                height=10,
                width=200 + (i % 2) * 80,
                corner_radius=3,
            )
            body_bar.pack(anchor="w")
            body_bar.pack_propagate(False)


class EmptyState(ctk.CTkFrame):
    """Premium unified empty layout."""

    def __init__(
        self,
        master,
        title: str = "Empty",
        description: str = "Nothing to display.",
        icon: str = "📭",
        actions: list[tuple[str, callable, bool]] | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(expand=True, fill="both", pady=40)

        # Premium Large Icon
        self._icon_lbl = ctk.CTkLabel(
            self._container,
            text=icon,
            font=ctk.CTkFont(size=44),
        )
        self._icon_lbl.pack(pady=(0, 8))

        # Title
        self._title_lbl = ctk.CTkLabel(
            self._container,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=brand.PROOF_TEAL,
        )
        self._title_lbl.pack(pady=4)

        # Description
        self._desc_lbl = ctk.CTkLabel(
            self._container,
            text=description,
            text_color=brand.MUTED_FG,
            font=theme.body_font(12),
            wraplength=420,
            justify="center",
        )
        self._desc_lbl.pack(pady=(4, 16))

        # Actions buttons
        if actions:
            self._actions_frame = ctk.CTkFrame(self._container, fg_color="transparent")
            self._actions_frame.pack(pady=4)
            for text, command, is_primary in actions:
                btn_style = theme.primary_button() if is_primary else theme.secondary_button()
                btn = ctk.CTkButton(
                    self._actions_frame,
                    text=text,
                    command=command,
                    height=28,
                    **btn_style,
                )
                btn.pack(side="left", padx=4)


class ErrorState(ctk.CTkFrame):
    """Premium unified error layout."""

    def __init__(
        self,
        master,
        title: str = "Error Encountered",
        description: str = "An unexpected error occurred.",
        retry_cmd: callable | None = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(expand=True, fill="both", pady=40)

        self._icon_lbl = ctk.CTkLabel(
            self._container,
            text="⚠️",
            font=ctk.CTkFont(size=44),
        )
        self._icon_lbl.pack(pady=(0, 8))

        self._title_lbl = ctk.CTkLabel(
            self._container,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=brand.WARNING_RED,
        )
        self._title_lbl.pack(pady=4)

        self._desc_lbl = ctk.CTkLabel(
            self._container,
            text=description,
            text_color=brand.MUTED_FG,
            font=theme.body_font(12),
            wraplength=420,
            justify="center",
        )
        self._desc_lbl.pack(pady=(4, 16))

        if retry_cmd:
            self._retry_btn = ctk.CTkButton(
                self._container,
                text="Retry Action",
                command=retry_cmd,
                height=28,
                **theme.primary_button(),
            )
            self._retry_btn.pack(pady=4)


class UnavailableState(ctk.CTkFrame):
    """Premium offline/unavailable layout."""

    def __init__(
        self,
        master,
        title: str = "Feature Unavailable",
        description: str = "This section is currently unavailable.",
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(expand=True, fill="both", pady=40)

        self._icon_lbl = ctk.CTkLabel(
            self._container,
            text="🛇",
            font=ctk.CTkFont(size=44),
        )
        self._icon_lbl.pack(pady=(0, 8))

        self._title_lbl = ctk.CTkLabel(
            self._container,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=brand.STAMP_GOLD,
        )
        self._title_lbl.pack(pady=4)

        self._desc_lbl = ctk.CTkLabel(
            self._container,
            text=description,
            text_color=brand.MUTED_FG,
            font=theme.body_font(12),
            wraplength=420,
            justify="center",
        )
        self._desc_lbl.pack(pady=(4, 16))
