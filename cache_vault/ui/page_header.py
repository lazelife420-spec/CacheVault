"""Unified page header for CacheVault screens."""

from __future__ import annotations

import customtkinter as ctk

from . import theme
from .. import brand


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        
        # Title and Subtitle area — stacked vertically so the subtitle gets
        # its own full-width line to wrap within instead of competing with
        # the title for horizontal space (which just clipped past the
        # window edge at compact width rather than wrapping).
        self._title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._title_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        self._title_frame.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(
            self._title_frame,
            text="",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        )
        self._title_label.grid(row=0, column=0, sticky="w")

        self._subtitle_label = ctk.CTkLabel(
            self._title_frame,
            text="",
            text_color=brand.MUTED_FG,
            font=theme.body_font(13),
            anchor="w",
            justify="left",
            wraplength=480,
        )
        self._subtitle_label.grid(row=1, column=0, sticky="w")
        
        # Actions area (Primary + Secondary)
        self._actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._actions_frame.grid(row=0, column=1, sticky="e", padx=8, pady=(8, 0))
        
        # Placeholder for dynamic buttons
        self._primary_btn = None
        self._secondary_btn = None
        
        # Status chips area
        self._status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._status_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 8))

        # Small non-blocking indicator for an in-flight background refresh
        # (or a failed one). Uses .place() rather than grid/pack so it's
        # never touched by set_actions()/set_status_chips() destroying and
        # rebuilding their own children -- otherwise a refresh landing
        # mid-flight could destroy this widget out from under a still-
        # pending set_refreshing() call. Deliberately not a full loading
        # skeleton: existing page content stays visible and interactive
        # while this shows.
        self._refreshing_label = ctk.CTkLabel(
            self,
            text="",
            text_color=brand.MUTED_FG,
            font=theme.body_font(11),
        )

        # "All N matching items selected" banner (Ctrl+Shift+A). Same
        # .place() pattern as _refreshing_label so it survives
        # set_status_chips()/set_actions() rebuilding their own children.
        self._selection_notice_label = ctk.CTkLabel(
            self,
            text="",
            text_color=brand.PROOF_TEAL,
            font=theme.body_font(11),
        )

    def set_selection_notice(self, text: str | None) -> None:
        if not text:
            self._selection_notice_label.place_forget()
            return
        self._selection_notice_label.configure(text=text)
        self._selection_notice_label.place(relx=0.0, rely=1.0, anchor="sw", x=8, y=-6)

    def set_refreshing(self, active: bool, *, error: bool = False) -> None:
        if not active and not error:
            self._refreshing_label.place_forget()
            return
        self._refreshing_label.configure(
            text="Refresh failed — showing previous results" if error else "Refreshing…",
            text_color="#E6A23C" if error else brand.MUTED_FG,
        )
        self._refreshing_label.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

    def set_content(self, title: str, subtitle: str = ""):
        self._title_label.configure(text=title)
        self._subtitle_label.configure(text=subtitle)
        if subtitle:
            self._subtitle_label.grid(row=1, column=0, sticky="w")
        else:
            self._subtitle_label.grid_remove()
            
    def set_actions(self, primary_text: str = "", primary_cmd=None, secondary_text: str = "", secondary_cmd=None):
        for widget in self._actions_frame.winfo_children():
            widget.destroy()
            
        if secondary_text and secondary_cmd:
            self._secondary_btn = ctk.CTkButton(
                self._actions_frame, text=secondary_text, command=secondary_cmd, 
                **theme.secondary_button()
            )
            self._secondary_btn.pack(side="left", padx=4)
            
        if primary_text and primary_cmd:
            self._primary_btn = ctk.CTkButton(
                self._actions_frame, text=primary_text, command=primary_cmd,
                **theme.primary_button()
            )
            self._primary_btn.pack(side="left", padx=4)
            
    def set_status_chips(self, chips: list[str]):
        for widget in self._status_frame.winfo_children():
            widget.destroy()
            
        for text in chips:
            chip = ctk.CTkLabel(
                self._status_frame, 
                text=text, 
                text_color=brand.MUTED_FG,
                font=theme.body_font(11)
            )
            chip.pack(side="left", padx=(0, 8))
