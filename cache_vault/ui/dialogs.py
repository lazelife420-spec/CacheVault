"""Shared dialogs — settings and the event-log viewer."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core import startup
from ..core.settings import Settings


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, on_save: Callable[[Settings], None]):
        super().__init__(master)
        self.title("Cache Vault — Settings")
        self.geometry("420x460")
        self.resizable(False, True)
        self.minsize(420, 420)
        self._settings = settings
        self._on_save = on_save

        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 8))

        self._pause = ctk.CTkSwitch(self, text="Pause capture")
        self._pause.pack(anchor="w", padx=16, pady=6)
        self._pause.select() if settings.capture_paused else self._pause.deselect()

        self._sens = ctk.CTkSwitch(self, text="Auto-expire sensitive clips")
        self._sens.pack(anchor="w", padx=16, pady=6)
        self._sens.select() if settings.sensitive_expiry_enabled else self._sens.deselect()

        ctk.CTkLabel(self, text="Sensitive expiry (minutes):").pack(
            anchor="w", padx=16, pady=(10, 0))
        self._minutes = ctk.CTkEntry(self)
        self._minutes.insert(0, str(settings.sensitive_expiry_minutes))
        self._minutes.pack(anchor="w", padx=16, pady=4, fill="x")

        hk_row = ctk.CTkFrame(self, fg_color="transparent")
        hk_row.pack(fill="x", padx=16, pady=(10, 0))
        ctk.CTkLabel(hk_row, text="Quick-paste hotkey:").pack(side="left")
        self._hotkey = ctk.CTkEntry(hk_row, width=140)
        self._hotkey.insert(0, settings.quick_paste_hotkey)
        self._hotkey.pack(side="right")

        self._auto_paste = ctk.CTkSwitch(self, text="Auto-paste after choosing")
        self._auto_paste.pack(anchor="w", padx=16, pady=6)
        self._auto_paste.select() if settings.auto_paste else self._auto_paste.deselect()

        self._startup = ctk.CTkSwitch(self, text="Start Cache Vault with Windows")
        self._startup.pack(anchor="w", padx=16, pady=6)
        # Reflect the *actual* registry state, not just the saved flag.
        self._startup.select() if startup.is_enabled() else self._startup.deselect()

        ctk.CTkLabel(self, text="Excluded apps (one per line):").pack(
            anchor="w", padx=16, pady=(10, 0))
        self._excluded = ctk.CTkTextbox(self, height=80)
        self._excluded.insert("1.0", "\n".join(settings.excluded_apps))
        self._excluded.pack(fill="x", padx=16, pady=4)

        ctk.CTkButton(self, text="Save", command=self._save).pack(
            anchor="e", padx=16, pady=12)

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
        self._settings.excluded_apps = [
            line.strip() for line in self._excluded.get("1.0", "end").splitlines()
            if line.strip()
        ]
        self._on_save(self._settings)
        self.destroy()


class EventLogDialog(ctk.CTkToplevel):
    def __init__(self, master, events: list[dict]):
        super().__init__(master)
        self.title("Cache Vault — Event Log")
        self.geometry("520x460")
        ctk.CTkLabel(self, text="Event Log (local proof history)",
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
