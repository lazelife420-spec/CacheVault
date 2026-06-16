"""Shared dialogs — settings and the event-log viewer."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import startup
from ..core.settings import Settings
from . import theme


def _bring_to_front(win: ctk.CTkToplevel, master, *, modal: bool) -> None:
    """Raise a CustomTkinter toplevel above its parent and focus it.

    CTkToplevel defers its window draw (a withdraw/deiconify cycle), so an
    immediate lift() gets overridden and the dialog can appear *behind* the
    main window. Tying it to the parent with transient() and lifting/focusing
    after that cycle fixes the z-order; ``modal`` also grabs input.
    """
    win.transient(master)

    def _raise() -> None:
        try:
            win.deiconify()
            win.lift()
            win.focus_force()
            if modal:
                win.grab_set()
        except Exception:  # noqa: BLE001 - window may have closed
            pass

    win.after(200, _raise)


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title(f"About {brand.PRODUCT_NAME}")
        self.geometry("460x380")
        self.resizable(False, False)

        ctk.CTkLabel(self, text=brand.PRODUCT_NAME,
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(self, text=brand.PRODUCT_BYLINE, anchor="w",
                     text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20)
        ctk.CTkLabel(self, text=brand.PRODUCT_POSITIONING, anchor="w",
                     wraplength=400, justify="left",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=(10, 4))
        ctk.CTkLabel(self, text=brand.PRODUCT_PROMISE, anchor="w",
                     wraplength=400, justify="left", text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=20, pady=(0, 10))

        body = ctk.CTkTextbox(self, height=120, wrap="word")
        body.pack(fill="x", padx=20, pady=4)
        body.insert("1.0", brand.PRODUCT_ABOUT)
        body.configure(state="disabled")

        ctk.CTkLabel(self, text=brand.RECEIPT_NOTE, anchor="w",
                     text_color=brand.STAMP_GOLD,
                     font=ctk.CTkFont(size=11)
                     ).pack(anchor="w", padx=20, pady=(8, 4))
        ctk.CTkLabel(self, text=brand.STUDIO_FOOTER, anchor="w",
                     text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=20, pady=(0, 12))

        ctk.CTkButton(self, text="Close", command=self.destroy,
                      **theme.primary_button()).pack(anchor="e", padx=20, pady=(0, 16))
        _bring_to_front(self, master, modal=True)


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, on_save: Callable[[Settings], None]):
        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — Settings")
        self.geometry("440x560")
        self.resizable(False, True)
        self.minsize(440, 360)
        self._settings = settings
        self._on_save = on_save

        # --- title (fixed at top) ---
        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 8))

        # --- scrollable content ---
        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self._pause = ctk.CTkSwitch(body, text="Pause capture")
        self._pause.pack(anchor="w", padx=8, pady=6)
        self._pause.select() if settings.capture_paused else self._pause.deselect()

        self._sens = ctk.CTkSwitch(body, text="Auto-expire sensitive clips")
        self._sens.pack(anchor="w", padx=8, pady=6)
        self._sens.select() if settings.sensitive_expiry_enabled else self._sens.deselect()

        ctk.CTkLabel(body, text="Sensitive expiry (minutes):").pack(
            anchor="w", padx=8, pady=(10, 0))
        self._minutes = ctk.CTkEntry(body)
        self._minutes.insert(0, str(settings.sensitive_expiry_minutes))
        self._minutes.pack(anchor="w", padx=8, pady=4, fill="x")

        hk_row = ctk.CTkFrame(body, fg_color="transparent")
        hk_row.pack(fill="x", padx=8, pady=(10, 0))
        ctk.CTkLabel(hk_row, text="Quick-paste hotkey:").pack(side="left")
        self._hotkey = ctk.CTkEntry(hk_row, width=140)
        self._hotkey.insert(0, settings.quick_paste_hotkey)
        self._hotkey.pack(side="right")

        self._auto_paste = ctk.CTkSwitch(body, text="Auto-paste after choosing")
        self._auto_paste.pack(anchor="w", padx=8, pady=6)
        self._auto_paste.select() if settings.auto_paste else self._auto_paste.deselect()

        self._startup = ctk.CTkSwitch(body, text="Start Cache Vault with Windows")
        self._startup.pack(anchor="w", padx=8, pady=6)
        self._startup.select() if startup.is_enabled() else self._startup.deselect()

        ctk.CTkLabel(body, text="History limit (clips, 0 = unlimited):").pack(
            anchor="w", padx=8, pady=(10, 0))
        self._history_max = ctk.CTkEntry(body, width=80)
        self._history_max.insert(0, str(settings.history_max_clips))
        self._history_max.pack(anchor="w", padx=8, pady=4)
        ctk.CTkLabel(
            body,
            text="Oldest non-favorite clips move to Recently Removed when exceeded.\n"
                 "Favorites always survive pruning.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11)).pack(anchor="w", padx=8)

        ctk.CTkLabel(body, text="Excluded apps (one per line):").pack(
            anchor="w", padx=8, pady=(10, 0))
        self._excluded = ctk.CTkTextbox(body, height=80)
        self._excluded.insert("1.0", "\n".join(settings.excluded_apps))
        self._excluded.pack(fill="x", padx=8, pady=4)

        # --- fixed footer (never scrolls) ---
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(footer, text="Save", command=self._save,
                      **theme.primary_button()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Cancel", command=self.destroy,
                      **theme.secondary_button()).pack(side="right")

        _bring_to_front(self, master, modal=True)

    def _save(self) -> None:
        self._settings.capture_paused = bool(self._pause.get())
        self._settings.sensitive_expiry_enabled = bool(self._sens.get())
        try:
            self._settings.sensitive_expiry_minutes = max(1, int(self._minutes.get()))
        except ValueError:
            pass
        hotkey = self._hotkey.get().strip()
        if hotkey:
            self._settings.quick_paste_hotkey = hotkey
        self._settings.auto_paste = bool(self._auto_paste.get())
        self._settings.start_with_windows = bool(self._startup.get())
        try:
            self._settings.history_max_clips = max(0, int(self._history_max.get()))
        except ValueError:
            pass
        self._settings.excluded_apps = [
            line.strip() for line in self._excluded.get("1.0", "end").splitlines()
            if line.strip()
        ]
        self._on_save(self._settings)
        self.destroy()


class MoveToCollectionDialog(ctk.CTkToplevel):
    def __init__(self, master, current: str | None, existing: list[str],
                 on_save: Callable[[str | None], None]):
        super().__init__(master)
        self.title("Move to Collection")
        self.geometry("360x300")
        self._on_save = on_save

        ctk.CTkLabel(self, text="Move clip to collection",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))

        self._entry = ctk.CTkEntry(self, placeholder_text="Collection name")
        if current:
            self._entry.insert(0, current)
        self._entry.pack(fill="x", padx=16, pady=4)

        if existing:
            ctk.CTkLabel(self, text="Existing:", anchor="w",
                         text_color=("gray45", "gray60"),
                         font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16, pady=(8, 0))
            chips = ctk.CTkScrollableFrame(self, height=110, fg_color="transparent")
            chips.pack(fill="both", expand=True, padx=12, pady=4)
            for name in existing:
                ctk.CTkButton(chips, text=name, anchor="w", height=26,
                              fg_color=("gray85", "gray25"),
                              text_color=("gray10", "gray90"),
                              command=lambda n=name: self._fill(n)
                              ).pack(fill="x", padx=4, pady=2)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkButton(footer, text="Save", command=self._save
                      ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Remove from collection",
                      fg_color=("gray60", "gray35"), command=self._clear
                      ).pack(side="right")

        _bring_to_front(self, master, modal=True)

    def _fill(self, name: str) -> None:
        self._entry.delete(0, "end")
        self._entry.insert(0, name)

    def _save(self) -> None:
        name = self._entry.get().strip() or None
        self._on_save(name)
        self.destroy()

    def _clear(self) -> None:
        self._on_save(None)
        self.destroy()


class ExportViewDialog(ctk.CTkToplevel):
    """Choose how to export the currently shown clips (folder vs zip)."""

    def __init__(self, master, count: int,
                 on_export: Callable[[str, bool], None]):
        super().__init__(master)
        self.title(brand.TERM_EXPORT)
        self.geometry("400x280")
        self._on_export = on_export

        ctk.CTkLabel(self, text=f"{brand.TERM_EXPORT} — {count} clip(s)",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self, text=f"Includes {brand.TERM_PROOF_MANIFEST.lower()}, "
                       f"{brand.TERM_STAMPED_RECEIPTS.lower()}, and clip files.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11), wraplength=360,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self._kind = ctk.StringVar(value="folder")
        ctk.CTkRadioButton(self, text="Organized folder", variable=self._kind,
                           value="folder").pack(anchor="w", padx=16, pady=4)
        ctk.CTkRadioButton(self, text="Zip archive", variable=self._kind,
                           value="zip").pack(anchor="w", padx=16, pady=4)

        self._include = ctk.CTkSwitch(
            self, text="Include file copies (path clips only)")
        self._include.pack(anchor="w", padx=16, pady=(10, 4))
        ctk.CTkLabel(
            self, text="Off by default: path clips export a reference only.\n"
                       "Originals are never moved or deleted.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)

        ctk.CTkButton(self, text="Continue…", command=self._go,
                      **theme.primary_button()
                      ).pack(anchor="e", padx=16, pady=12)
        _bring_to_front(self, master, modal=True)

    def _go(self) -> None:
        kind = self._kind.get()
        include = bool(self._include.get())
        self.destroy()
        self._on_export(kind, include)


class EventLogDialog(ctk.CTkToplevel):
    def __init__(self, master, events: list[dict]):
        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — {brand.TERM_STAMPED_RECEIPTS}")
        self.geometry("520x460")
        ctk.CTkLabel(self, text=f"{brand.TERM_STAMPED_RECEIPTS} (local proof history)",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))
        box = ctk.CTkTextbox(self, wrap="none")
        box.pack(fill="both", expand=True, padx=12, pady=8)
        if not events:
            box.insert("1.0", "No events yet.")
        for e in events:
            ts = e["created_at"].replace("T", " ")[:19]
            box.insert("end", f"{ts}  {e['event_type']:<20} {e['clip_id'] or ''}\n")
        box.configure(state="disabled")

        _bring_to_front(self, master, modal=False)
