"""A small, self-dismissing on-screen notification.

Used to confirm a quick-paste without stealing focus — borderless, topmost,
bottom-center, gone after a short delay. Never shows sensitive contents.
"""

from __future__ import annotations

import customtkinter as ctk


class Toast(ctk.CTkToplevel):
    def __init__(self, master, text: str, duration_ms: int = 1600):
        super().__init__(master)
        # self.after(duration_ms, self.destroy) below has no id tracked or
        # cancelled anywhere, so a Toast destroyed early -- directly, or via
        # its owning CacheVaultApp cascading destroy() at the Tcl level,
        # which never calls a Python-level destroy() on children at all --
        # leaves that job pending. Tk raises "invalid command name" once it
        # fires against the now-destroyed widget (issue #86). <Destroy> is
        # Tk's own event, fired for both a direct .destroy() call and a
        # parent-cascade teardown, at a point where after_cancel can still
        # succeed -- unlike overriding destroy() alone, which a cascade
        # never invokes.
        self._destroy_job: str | None = None
        self.bind("<Destroy>", self._cancel_destroy_job, add="+")
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
        self._destroy_job = self.after(duration_ms, self._fire_destroy)

    def _fire_destroy(self) -> None:
        self._destroy_job = None
        if self.winfo_exists():
            self.destroy()

    def _cancel_destroy_job(self, event=None) -> None:
        # <Destroy> bound on a Toplevel fires for every descendant too (this
        # Toast's own CTkFrame/CTkLabel), as each is torn down in the same
        # cascade -- filter to this widget's own event so a child's teardown
        # can't be mistaken for the Toast's own.
        if event is not None and str(event.widget) != self._w:
            return
        if self._destroy_job is not None:
            try:
                self.after_cancel(self._destroy_job)
            except Exception:  # noqa: BLE001 - already fired/invalid, fine
                pass
            self._destroy_job = None
