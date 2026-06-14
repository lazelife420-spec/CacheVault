"""A small, self-dismissing on-screen notification.

Used to confirm a quick-paste without stealing focus — borderless, topmost,
bottom-center, gone after a short delay. Never shows sensitive contents.
"""

from __future__ import annotations

import customtkinter as ctk


class Toast(ctk.CTkToplevel):
    def __init__(self, master, text: str, duration_ms: int = 1600):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.97)
        except Exception:  # noqa: BLE001 - alpha unsupported on some setups
            pass

        frame = ctk.CTkFrame(self, corner_radius=12,
                             fg_color=("gray85", "gray18"),
                             border_width=1, border_color=("gray70", "gray35"))
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=12),
                     wraplength=360, justify="left").pack(padx=16, pady=10)

        # Size to content, then place bottom-center.
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 220)
        h = self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - w) // 2
        y = sh - h - 80
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Don't take focus away from the app being pasted into.
        try:
            self.attributes("-disabled", True)
        except Exception:  # noqa: BLE001
            pass
        self.after(duration_ms, self.destroy)
