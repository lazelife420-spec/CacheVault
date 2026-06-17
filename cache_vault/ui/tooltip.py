"""Hover tooltips for CustomTkinter widgets."""

from __future__ import annotations

import customtkinter as ctk

from .. import brand


def bind_tooltip(widget, text: str) -> None:
  """Show a small label below the widget on hover."""
  tip: ctk.CTkToplevel | None = None

  def hide(_e=None) -> None:
      nonlocal tip
      if tip is not None:
          tip.destroy()
          tip = None

  def show(_e=None) -> None:
      nonlocal tip
      hide()
      tip = ctk.CTkToplevel(widget)
      tip.wm_overrideredirect(True)
      tip.attributes("-topmost", True)
      ctk.CTkLabel(
          tip,
          text=text,
          fg_color=brand.IRON_GRAY,
          text_color=brand.RECEIPT_WHITE,
          corner_radius=4,
          padx=8,
          pady=4,
          wraplength=320,
          justify="left",
          font=ctk.CTkFont(size=11),
      ).pack()
      tip.update_idletasks()
      x = widget.winfo_rootx()
      y = widget.winfo_rooty() + widget.winfo_height() + 4
      tip.geometry(f"+{x}+{y}")

  widget.bind("<Enter>", show)
  widget.bind("<Leave>", hide)
