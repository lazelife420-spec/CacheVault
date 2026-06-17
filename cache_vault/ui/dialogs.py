"""Shared dialogs — settings and the event-log viewer."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import startup, vault_lock
from ..core.settings import Settings
from . import theme
from .guide_copy import EMPTY_STAMPED_RECEIPTS, SETTINGS_SHOW_GUIDE_AGAIN


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
    def __init__(self, master, settings: Settings, on_save: Callable[[Settings], None],
                 *, mobile: dict | None = None, help: dict | None = None):
        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — Settings")
        self.geometry("520x720")
        self.resizable(False, True)
        self.minsize(520, 600)
        self._settings = settings
        self._on_save = on_save
        self._mobile = mobile or {}
        self._help = help or {}

        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))

        # Mobile Access — pinned above scroll so pairing is visible without scrolling.
        self._mobile_section = self._build_mobile_section(settings)

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=8, pady=(4, 4))
        self._scroll_body = body

        def section(title: str) -> None:
            ctk.CTkFrame(body, height=1, fg_color=("#C8D0D4", "#263038")).pack(
                fill="x", padx=8, pady=(14, 6))
            ctk.CTkLabel(body, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=brand.PROOF_TEAL).pack(anchor="w", padx=8, pady=(0, 4))

        section("Capture")
        self._pause = ctk.CTkSwitch(body, text="Pause capture")
        self._pause.pack(anchor="w", padx=8, pady=6)
        self._pause.select() if settings.capture_paused else self._pause.deselect()

        section("Capture Rules")
        self._auto_capture = ctk.CTkSwitch(
            body, text="Save normal clipboard copies automatically",
        )
        self._auto_capture.pack(anchor="w", padx=8, pady=6)
        if settings.auto_capture_enabled:
            self._auto_capture.select()

        safe_row = ctk.CTkFrame(body, fg_color="transparent")
        safe_row.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(safe_row, text="Default Safe ID:").pack(side="left")
        self._default_safe = ctk.CTkEntry(safe_row, width=140)
        self._default_safe.insert(0, settings.default_safe_id)
        self._default_safe.pack(side="right")

        def _hk_row(label: str, value: str) -> ctk.CTkEntry:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(6, 0))
            ctk.CTkLabel(row, text=label).pack(side="left")
            entry = ctk.CTkEntry(row, width=140)
            entry.insert(0, value)
            entry.pack(side="right")
            return entry

        self._manual_hk = _hk_row("Manual save hotkey:", settings.manual_save_hotkey)
        self._arm_hk = _hk_row("Save next copy hotkey:", settings.arm_next_copy_hotkey)
        self._ignore_hk = _hk_row("Ignore next copy hotkey:", settings.ignore_next_copy_hotkey)

        self._picker_on_manual = ctk.CTkSwitch(
            body, text="Show Safe picker when saving manually",
        )
        self._picker_on_manual.pack(anchor="w", padx=8, pady=6)
        if settings.show_safe_picker_on_manual_save:
            self._picker_on_manual.select()

        self._block_sensitive = ctk.CTkSwitch(
            body, text="Do not auto-capture sensitive-looking clips (best-effort)",
        )
        self._block_sensitive.pack(anchor="w", padx=8, pady=6)
        if settings.block_sensitive_auto_capture:
            self._block_sensitive.select()

        ctk.CTkLabel(body, text="Max auto-capture size (bytes, 0 = unlimited):").pack(
            anchor="w", padx=8, pady=(6, 0))
        self._max_bytes = ctk.CTkEntry(body, width=120)
        self._max_bytes.insert(0, str(settings.max_auto_capture_bytes))
        self._max_bytes.pack(anchor="w", padx=8, pady=4)

        ctk.CTkButton(
            body, text="Manage Safes…",
            command=lambda: SafePickerDialog(
                master, settings, on_create=None, picker_mode=False,
            ),
            **theme.secondary_button(),
        ).pack(anchor="w", padx=8, pady=(4, 8))

        ctk.CTkLabel(
            body,
            text="Safes are local vault sections — not encrypted containers.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=8, pady=(0, 6))

        section("Sensitive Clips")
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

        self._auto_paste = ctk.CTkSwitch(body, text="Paste selected item immediately")
        self._auto_paste.pack(anchor="w", padx=8, pady=6)
        self._auto_paste.select() if settings.auto_paste else self._auto_paste.deselect()

        self._restore_clip = ctk.CTkSwitch(
            body, text="Restore previous clipboard after paste (text only)",
        )
        self._restore_clip.pack(anchor="w", padx=8, pady=(0, 6))
        if settings.restore_clipboard_after_paste:
            self._restore_clip.select()
        ctk.CTkLabel(
            body,
            text="When off, the chosen vault item stays on the clipboard after paste.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=8, pady=(0, 4))

        section("Vault Macros")
        ctk.CTkLabel(
            body,
            text="Live macro hotkeys, text shortcuts, and paste/type delivery.\n"
                 "No recorder or admin automation — Macro Safes are not encrypted.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=8, pady=(0, 4))
        self._vault_macros_on = ctk.CTkSwitch(body, text="Enable Vault Macros")
        self._vault_macros_on.pack(anchor="w", padx=8, pady=4)
        if settings.vault_macros_enabled:
            self._vault_macros_on.select()
        self._macro_text_sc = ctk.CTkSwitch(body, text="Enable text shortcuts")
        self._macro_text_sc.pack(anchor="w", padx=8, pady=4)
        if settings.macro_text_shortcuts_enabled:
            self._macro_text_sc.select()
        self._macro_hk_on = ctk.CTkSwitch(body, text="Enable macro hotkeys")
        self._macro_hk_on.pack(anchor="w", padx=8, pady=4)
        if settings.macro_hotkeys_enabled:
            self._macro_hk_on.select()
        self._macro_menu_hk = _hk_row("Macro menu hotkey:", settings.macro_menu_hotkey)
        self._macro_restore = ctk.CTkSwitch(
            body, text="Restore clipboard after macro paste (text only)",
        )
        self._macro_restore.pack(anchor="w", padx=8, pady=4)
        if settings.macro_restore_clipboard_after_paste:
            self._macro_restore.select()
        self._macro_sensitive = ctk.CTkSwitch(
            body, text="Require confirmation for sensitive-looking macros",
        )
        self._macro_sensitive.pack(anchor="w", padx=8, pady=4)
        if settings.macro_sensitive_confirmation:
            self._macro_sensitive.select()
        self._macro_keystroke_on = ctk.CTkSwitch(
            body, text="Allow keystroke output mode (slower, ASCII-focused)",
        )
        self._macro_keystroke_on.pack(anchor="w", padx=8, pady=4)
        if settings.macro_keystroke_enabled:
            self._macro_keystroke_on.select()
        ks_row = ctk.CTkFrame(body, fg_color="transparent")
        ks_row.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(ks_row, text="Keystroke delay (ms):").pack(side="left")
        self._macro_keystroke_delay = ctk.CTkEntry(ks_row, width=60)
        self._macro_keystroke_delay.insert(0, str(settings.macro_keystroke_delay_ms))
        self._macro_keystroke_delay.pack(side="right")

        section("Display")
        self._win_scroll = ctk.CTkSwitch(
            body, text="Use Windows scroll settings (recommended)",
        )
        self._win_scroll.pack(anchor="w", padx=8, pady=6)
        if settings.use_windows_scroll_settings:
            self._win_scroll.select()
        ctk.CTkLabel(
            body,
            text="Scroll speed follows Windows mouse wheel lines.\n"
                 "Applies to vault lists, preview, settings, and images grid.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=8, pady=(0, 4))
        mult_row = ctk.CTkFrame(body, fg_color="transparent")
        mult_row.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(mult_row, text="Scroll multiplier (1.0 = OS default):").pack(side="left")
        self._scroll_mult = ctk.CTkEntry(mult_row, width=60)
        self._scroll_mult.insert(0, str(settings.scroll_multiplier))
        self._scroll_mult.pack(side="right")

        section("Vault Lock")
        self._vault_lock_on = ctk.CTkSwitch(body, text="Enable Vault Lock")
        self._vault_lock_on.pack(anchor="w", padx=8, pady=4)
        if settings.vault_lock_enabled:
            self._vault_lock_on.select()
        self._vault_lock_mode = ctk.StringVar(
            value="PIN lock" if settings.vault_lock_mode == "pin" else "Passphrase lock",
        )
        ctk.CTkOptionMenu(
            body,
            variable=self._vault_lock_mode,
            values=["PIN lock", "Passphrase lock"],
            width=160,
        ).pack(anchor="w", padx=8, pady=4)
        self._vault_lock_secret = ctk.CTkEntry(
            body,
            show="*",
            placeholder_text="New PIN/passphrase (leave blank to keep current)",
        )
        self._vault_lock_secret.pack(fill="x", padx=8, pady=4)
        self._vault_lock_startup = ctk.CTkSwitch(body, text="Lock on startup")
        self._vault_lock_startup.pack(anchor="w", padx=8, pady=4)
        if settings.vault_lock_on_startup:
            self._vault_lock_startup.select()
        self._vault_lock_minimized = ctk.CTkSwitch(body, text="Lock when minimized")
        self._vault_lock_minimized.pack(anchor="w", padx=8, pady=4)
        if settings.vault_lock_when_minimized:
            self._vault_lock_minimized.select()
        auto_row = ctk.CTkFrame(body, fg_color="transparent")
        auto_row.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(auto_row, text="Auto-lock minutes (0 = off):").pack(side="left")
        self._vault_lock_auto = ctk.CTkEntry(auto_row, width=60)
        self._vault_lock_auto.insert(0, str(settings.vault_lock_auto_minutes))
        self._vault_lock_auto.pack(side="right")
        ctk.CTkLabel(
            body,
            text="Vault Lock hides the app surface. Safes organize your items. "
                 "They are not encryption unless encryption is added later.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11), wraplength=460,
        ).pack(anchor="w", padx=8, pady=(4, 8))

        section("Startup")
        self._startup = ctk.CTkSwitch(body, text="Start Cache Vault with Windows")
        self._startup.pack(anchor="w", padx=8, pady=6)
        self._startup.select() if startup.is_enabled() else self._startup.deselect()

        section("Help")
        if self._help.get("show_guide"):
            ctk.CTkButton(
                body,
                text=SETTINGS_SHOW_GUIDE_AGAIN,
                command=self._help["show_guide"],
                **theme.secondary_button(),
            ).pack(anchor="w", padx=8, pady=4)
        ctk.CTkLabel(
            body,
            text="Reopen the vault briefing that explains receipts, Safes, Mobile Inbox, and exports.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11), wraplength=460,
        ).pack(anchor="w", padx=8, pady=(0, 4))

        section("History")
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
        self._excluded.pack(fill="x", padx=8, pady=(4, 8))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(footer, text="Save", command=self._save,
                      **theme.primary_button()).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Cancel", command=self.destroy,
                      **theme.secondary_button()).pack(side="right")

        _bring_to_front(self, master, modal=True)

    def _build_mobile_section(self, settings: Settings) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, fg_color=brand.SURFACE_BG, corner_radius=8)
        card.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(card, text=brand.TERM_MOBILE_ACCESS,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            card,
            text=f"{brand.MOBILE_PRODUCT_NAME} · {brand.MOBILE_BYLINE}\n"
                 f"{brand.MOBILE_PROMISE}",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11), wraplength=460,
        ).pack(anchor="w", padx=12, pady=(0, 6))

        self._mobile_on = ctk.CTkSwitch(card, text="Enable Mobile Access")
        self._mobile_on.pack(anchor="w", padx=12, pady=4)
        if settings.mobile_access_enabled:
            self._mobile_on.select()

        port_row = ctk.CTkFrame(card, fg_color="transparent")
        port_row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(port_row, text="Port:").pack(side="left")
        self._mobile_port = ctk.CTkEntry(port_row, width=80)
        self._mobile_port.insert(0, str(settings.mobile_access_port))
        self._mobile_port.pack(side="left", padx=(8, 0))

        mob_btns = ctk.CTkFrame(card, fg_color="transparent")
        mob_btns.pack(fill="x", padx=12, pady=(4, 4))
        if self._mobile.get("pair"):
            ctk.CTkButton(
                mob_btns, text="Pair Android Device",
                command=lambda: self._mobile["pair"](bool(self._mobile_on.get())),
                **theme.secondary_button(),
            ).pack(fill="x", pady=3)
        if self._mobile.get("devices"):
            ctk.CTkButton(
                mob_btns, text="Paired Devices",
                command=self._mobile["devices"],
                **theme.secondary_button(),
            ).pack(fill="x", pady=3)
        if self._mobile.get("receipts"):
            ctk.CTkButton(
                mob_btns, text=brand.TERM_MOBILE_ACCESS_RECEIPTS,
                command=self._mobile["receipts"],
                **theme.secondary_button(),
            ).pack(fill="x", pady=3)

        ctk.CTkLabel(
            card,
            text="Off by default. Read-only API — no delete or edit from mobile.",
            anchor="w", text_color=brand.MUTED_FG, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=12, pady=(0, 10))
        return card

    def _save(self) -> None:
        self._settings.capture_paused = bool(self._pause.get())
        self._settings.auto_capture_enabled = bool(self._auto_capture.get())
        self._settings.default_safe_id = self._default_safe.get().strip() or "default"
        manual = self._manual_hk.get().strip()
        if manual:
            self._settings.manual_save_hotkey = manual
        arm = self._arm_hk.get().strip()
        if arm:
            self._settings.arm_next_copy_hotkey = arm
        ignore = self._ignore_hk.get().strip()
        if ignore:
            self._settings.ignore_next_copy_hotkey = ignore
        self._settings.show_safe_picker_on_manual_save = bool(self._picker_on_manual.get())
        self._settings.block_sensitive_auto_capture = bool(self._block_sensitive.get())
        try:
            self._settings.max_auto_capture_bytes = max(0, int(self._max_bytes.get()))
        except ValueError:
            pass
        self._settings.sensitive_expiry_enabled = bool(self._sens.get())
        try:
            self._settings.sensitive_expiry_minutes = max(1, int(self._minutes.get()))
        except ValueError:
            pass
        hotkey = self._hotkey.get().strip()
        if hotkey:
            self._settings.quick_paste_hotkey = hotkey
        self._settings.auto_paste = bool(self._auto_paste.get())
        self._settings.restore_clipboard_after_paste = bool(self._restore_clip.get())
        self._settings.use_windows_scroll_settings = bool(self._win_scroll.get())
        try:
            self._settings.scroll_multiplier = max(
                0.25, min(4.0, float(self._scroll_mult.get())))
        except ValueError:
            pass
        self._settings.start_with_windows = bool(self._startup.get())
        try:
            self._settings.history_max_clips = max(0, int(self._history_max.get()))
        except ValueError:
            pass
        self._settings.excluded_apps = [
            line.strip() for line in self._excluded.get("1.0", "end").splitlines()
            if line.strip()
        ]
        self._settings.vault_macros_enabled = bool(self._vault_macros_on.get())
        self._settings.macro_text_shortcuts_enabled = bool(self._macro_text_sc.get())
        self._settings.macro_hotkeys_enabled = bool(self._macro_hk_on.get())
        menu_hk = self._macro_menu_hk.get().strip()
        if menu_hk:
            self._settings.macro_menu_hotkey = menu_hk
        self._settings.macro_restore_clipboard_after_paste = bool(self._macro_restore.get())
        self._settings.macro_sensitive_confirmation = bool(self._macro_sensitive.get())
        self._settings.macro_keystroke_enabled = bool(self._macro_keystroke_on.get())
        try:
            self._settings.macro_keystroke_delay_ms = max(
                1, min(100, int(self._macro_keystroke_delay.get())),
            )
        except ValueError:
            pass
        self._settings.vault_lock_enabled = bool(self._vault_lock_on.get())
        self._settings.vault_lock_mode = (
            "passphrase" if "Passphrase" in self._vault_lock_mode.get() else "pin"
        )
        lock_secret = self._vault_lock_secret.get()
        if lock_secret:
            vault_lock.set_lock_secret(
                self._settings,
                lock_secret,
                mode=self._settings.vault_lock_mode,
            )
        elif self._settings.vault_lock_enabled and not vault_lock.has_lock_secret(self._settings):
            self._settings.vault_lock_enabled = False
        self._settings.vault_lock_on_startup = bool(self._vault_lock_startup.get())
        self._settings.vault_lock_when_minimized = bool(self._vault_lock_minimized.get())
        try:
            self._settings.vault_lock_auto_minutes = max(
                0, min(1440, int(self._vault_lock_auto.get())),
            )
        except ValueError:
            pass
        self._settings.mobile_access_enabled = bool(self._mobile_on.get())
        try:
            self._settings.mobile_access_port = max(
                1024, min(65535, int(self._mobile_port.get())))
        except ValueError:
            pass
        self._on_save(self._settings)
        self.destroy()


class SafePickerDialog(ctk.CTkToplevel):
    """Pick a Safe destination or create a new user Safe."""

    def __init__(
        self,
        master,
        settings: Settings,
        *,
        on_pick: Callable[[str, str], None] | None = None,
        on_create: Callable[[str], None] | None = None,
        picker_mode: bool = True,
        title: str = "Choose Safe",
    ):
        from ..core.safes import SafeRegistry

        super().__init__(master)
        self.title(title)
        self.geometry("380x360")
        self._settings = settings
        self._on_pick = on_pick
        self._on_create = on_create
        self._picker_mode = picker_mode
        self._registry = SafeRegistry(settings)

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))

        scroll = ctk.CTkScrollableFrame(self, height=200)
        scroll.pack(fill="both", expand=True, padx=12, pady=4)
        for safe in self._registry.list_destinations():
            ctk.CTkButton(
                scroll, text=safe.name, anchor="w",
                command=lambda s=safe: self._choose(s.id, s.name),
                **theme.secondary_button(),
            ).pack(fill="x", pady=2)

        create_row = ctk.CTkFrame(self, fg_color="transparent")
        create_row.pack(fill="x", padx=16, pady=8)
        self._new_name = ctk.CTkEntry(create_row, placeholder_text="New Safe name")
        self._new_name.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(create_row, text="Create", command=self._create_new,
                      **theme.primary_button()).pack(side="right")

        if picker_mode:
            ctk.CTkButton(self, text="Cancel", command=self.destroy,
                          **theme.secondary_button()).pack(anchor="e", padx=16, pady=(0, 12))
        else:
            ctk.CTkLabel(
                self, text="Create Safes here; pick them when saving clips.",
                anchor="w", text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=16, pady=(0, 4))
            ctk.CTkButton(self, text="Close", command=self.destroy,
                          **theme.secondary_button()).pack(anchor="e", padx=16, pady=(0, 12))

        _bring_to_front(self, master, modal=picker_mode)

    def _choose(self, safe_id: str, safe_name: str) -> None:
        if self._picker_mode and self._on_pick:
            self._on_pick(safe_id, safe_name)
        self.destroy()

    def _create_new(self) -> None:
        name = self._new_name.get().strip()
        if not name:
            return
        safe = self._registry.create(name)
        if self._on_create:
            self._on_create(name)
        if self._picker_mode and self._on_pick:
            self._on_pick(safe.id, safe.name)
            self.destroy()
        else:
            self._new_name.delete(0, "end")


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
    """Stamped Receipts — proof ledger viewer."""

    def __init__(self, master, events: list[dict], *, get_clip=None, on_refresh=None):
        from tkinter import filedialog, messagebox

        from .receipt_ledger import (
            FILTERS,
            FILTER_ALL,
            ReceiptRow,
            export_rows,
            filter_rows,
            format_detail_text,
            format_list_line,
            format_receipt_copy,
            rows_from_events,
            shorten_hash,
        )

        super().__init__(master)
        self.title(f"{brand.PRODUCT_NAME} — {brand.TERM_STAMPED_RECEIPTS}")
        self.geometry("900x560")
        self.minsize(760, 480)
        self.resizable(True, True)
        self._get_clip = get_clip
        self._on_refresh = on_refresh
        self._all_events = list(events)
        self._rows: list[ReceiptRow] = []
        self._selected: ReceiptRow | None = None
        self._row_widgets: list[tuple[ctk.CTkButton, ReceiptRow]] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(header, text=brand.TERM_STAMPED_RECEIPTS,
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(anchor="w")
        ctk.CTkLabel(
            header, text="Local proof history for Cache Vault actions.",
            anchor="w", text_color=brand.MUTED_FG,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header, text=brand.RECEIPT_NOTE, anchor="w",
            text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(2, 0))

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=16, pady=8)
        self._search = ctk.CTkEntry(tools, placeholder_text="Search receipts…")
        self._search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._search.bind("<KeyRelease>", lambda _e: self._reload_list())
        self._filter = ctk.CTkOptionMenu(tools, values=list(FILTERS),
                                         command=lambda _v: self._reload_list())
        self._filter.set(FILTER_ALL)
        self._filter.pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=4)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self._list = ctk.CTkScrollableFrame(body)
        self._list.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        detail_frame = ctk.CTkFrame(body)
        detail_frame.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(detail_frame, text="Receipt details",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 4))
        self._detail = ctk.CTkTextbox(detail_frame, wrap="word")
        self._detail.pack(fill="both", expand=True, padx=10, pady=4)
        self._detail.configure(state="disabled")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(4, 12))
        self._filedialog = filedialog
        self._messagebox = messagebox
        self._export_rows_fn = export_rows
        self._format_receipt_copy_fn = format_receipt_copy
        ctk.CTkButton(actions, text="Copy Receipt", command=self._copy_receipt,
                      **theme.secondary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Copy Full Hash", command=self._copy_hash,
                      **theme.secondary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Export Selected", command=self._export_selected,
                      **theme.secondary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Export All", command=self._export_all,
                      **theme.primary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(actions, text="Refresh", command=self._refresh,
                      **theme.secondary_button()).pack(side="right")

        try:
            self._rebuild_rows()
        except Exception:
            self._show_load_error()
        _bring_to_front(self, master, modal=False)

    def _show_load_error(self) -> None:
        self._detail.configure(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert(
            "1.0",
            "Receipts could not be loaded.\nYour vault data was not changed.",
        )
        self._detail.configure(state="disabled")

    def _rebuild_rows(self) -> None:
        from .receipt_ledger import rows_from_events
        self._rows = rows_from_events(self._all_events, get_clip=self._get_clip)
        self._reload_list()

    def _reload_list(self) -> None:
        from .receipt_ledger import filter_rows, shorten_hash

        for w, _ in self._row_widgets:
            w.destroy()
        self._row_widgets.clear()
        flt = self._filter.get()
        q = self._search.get()
        shown = filter_rows(self._rows, flt=flt, query=q)
        if not shown:
            ctk.CTkLabel(
                self._list,
                text=EMPTY_STAMPED_RECEIPTS,
                text_color=brand.MUTED_FG, justify="left", wraplength=520,
            ).pack(anchor="w", padx=8, pady=16)
            self._selected = None
            self._detail.configure(state="normal")
            self._detail.delete("1.0", "end")
            self._detail.configure(state="disabled")
            return
        for row in shown:
            frame = ctk.CTkFrame(self._list, fg_color=brand.SURFACE_BG, corner_radius=6)
            frame.pack(fill="x", pady=3, padx=2)
            ts = (row.timestamp or "")[:19].replace("T", " ")
            top = ctk.CTkFrame(frame, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(top, text=row.action_label, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=brand.PROOF_TEAL).pack(side="left")
            ctk.CTkLabel(top, text=row.result, anchor="e",
                         text_color=brand.STAMP_GOLD if row.result == "OK" else brand.WARNING_RED,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
            mid = f"{ts} · {row.item_label} · {row.content_type}"
            ctk.CTkLabel(frame, text=mid, anchor="w", text_color=brand.MUTED_FG,
                         font=theme.body_font(11)).pack(fill="x", padx=10, pady=(0, 2))
            ctk.CTkLabel(frame, text=f"Proof {shorten_hash(row.proof_hash)}", anchor="w",
                         text_color=brand.STAMP_GOLD, font=theme.mono_font(10)
                         ).pack(fill="x", padx=10, pady=(0, 6))
            btn = ctk.CTkButton(
                frame, text="", width=1, height=1, fg_color="transparent",
                hover_color=theme.nav_hover_bg(),
                command=lambda r=row: self._select(r),
            )
            btn.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._row_widgets.append((frame, row))
        self._select(shown[0])

    def _select(self, row) -> None:
        from .receipt_ledger import format_detail_text
        self._selected = row
        for frame, r in self._row_widgets:
            frame.configure(
                fg_color=brand.ROW_SELECTED_BG if r is row else brand.SURFACE_BG,
                border_width=2 if r is row else 0,
                border_color=brand.PROOF_TEAL if r is row else brand.SURFACE_BG,
            )
        self._detail.configure(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", format_detail_text(row))
        self._detail.configure(state="disabled", font=theme.mono_font(11))

    def _copy_receipt(self) -> None:
        if self._selected:
            self.clipboard_clear()
            self.clipboard_append(self._format_receipt_copy_fn(self._selected))

    def _copy_hash(self) -> None:
        if self._selected and self._selected.proof_hash:
            self.clipboard_clear()
            self.clipboard_append(self._selected.proof_hash)

    def _export_selected(self) -> None:
        if not self._selected:
            return
        self._export_dialog([self._selected])

    def _export_all(self) -> None:
        from .receipt_ledger import filter_rows
        flt = self._filter.get()
        q = self._search.get()
        rows = filter_rows(self._rows, flt=flt, query=q)
        if not rows:
            return
        self._export_dialog(rows)

    def _export_dialog(self, rows) -> None:
        path = self._filedialog.asksaveasfilename(
            parent=self,
            title="Export receipts",
            defaultextension=".txt",
            filetypes=[
                ("Text", "*.txt"),
                ("JSON", "*.json"),
                ("HTML", "*.html"),
            ],
        )
        if not path:
            return
        ext = path.rsplit(".", 1)[-1].lower()
        try:
            content = self._export_rows_fn(rows, ext)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            self._messagebox.showerror(
                "Export failed",
                "Receipts could not be exported.\nYour vault data was not changed.",
                parent=self,
            )

    def _refresh(self) -> None:
        if self._on_refresh:
            try:
                self._all_events = list(self._on_refresh())
                self._rebuild_rows()
            except Exception:
                self._show_load_error()
