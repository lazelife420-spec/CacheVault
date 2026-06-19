"""Main application shell — the one product window.

Layout::

    ┌───────────────────────────────────────────────┐
    │ top bar: search ............... [Events][⚙]    │
    ├───────────┬───────────────────────┬────────────┤
    │ filters   │ clip list             │ preview    │
    └───────────┴───────────────────────┴────────────┘
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import capture_debug, clip_accents, copy_clean, drag_export, models, search, vault_lock
from ..core.clipboard import ClipboardMonitor, read_clipboard_payload
from ..core.capture_rules import CaptureController
from ..core.capture_receipts import record_armed_receipt, record_ignored_receipt
from ..core.safes import SafeRegistry
from ..core.hotkey import HotkeyListener, MultiHotkeyListener, normalize_hotkey
from ..core.paste_delivery import (
    deliver_ctrl_v,
    foreground_window,
    hwnd_belongs_to_widget,
    restore_clipboard_text,
    snapshot_clipboard_text,
)
from ..core.storage import FILTER_HOME, FILTER_SEARCH_ALL
from ..core.mobile.bridge import MobileBridge
from ..core.vault import Vault
from .clip_grid import ClipGrid
from .clip_list import ClipList
from .dialogs import (
    AboutDialog, EventLogDialog, ExportViewDialog, MoveToCollectionDialog,
    SafePickerDialog, SettingsDialog,
)
from .filters import (
    FilterNav,
    NAV_EDITABLE_COPIES,
    NAV_EXPORTS,
    NAV_HTML_BUNDLES,
    NAV_MOBILE_ACCESS,
    NAV_MOBILE_INBOX,
    NAV_QUICK_PASTE,
    NAV_SCREEN_KEYS,
    NAV_SETTINGS,
    NAV_STAMPED_RECEIPTS,
    NAV_VAULT_MACROS,
)
from .home_dashboard import HomeDashboard
from .duplicate_dialog import DuplicateReviewDialog
from .mobile_dialogs import (
    MobileAccessReceiptsDialog, PairAndroidDialog, PairedDevicesDialog,
)
from .preview import PreviewPanel
from .quick_paste import (
    ACTION_ALTERNATE,
    ACTION_COPY_ONLY,
    ACTION_OPEN,
    ACTION_SAVE_AS,
    QuickPaste,
)
from .toast import Toast
from .tray import TrayController
from . import tooltip
from .vault_screens import VaultScreenHost
from .vault_lock import VaultControlStrip, VaultLockScreen
from . import theme
from .crashlog import write_crash
from .scroll_patch import install_windows_scroll_patch, scroll_config_from_settings
from .win_scroll import refresh_windows_scroll_cache

EXPIRY_SWEEP_MS = 15_000  # run the expiry sweep every 15s
HK_MANUAL_SAVE = 10
HK_ARM_NEXT = 11
HK_IGNORE_NEXT = 12
HK_MACRO_MENU = 13
HK_MACRO_ID_BASE = 100


class CacheVaultApp(ctk.CTk):
    def report_callback_exception(self, exc, val, tb):  # noqa: N802 - Tk API
        """Log Tk callback failures instead of failing silently."""
        err = val if isinstance(val, BaseException) else Exception(val)
        path = write_crash("Tk callback error", err)
        msg = (
            f"\nCache Vault UI error (logged to {path}):\n"
            + "".join(traceback.format_exception(exc, val, tb))
        )
        if sys.stderr is not None:
            try:
                sys.stderr.write(msg)
            except Exception:  # noqa: BLE001
                pass
        # CTk sometimes fires resize callbacks after widgets are destroyed — log only.
        if exc is not None and getattr(exc, "__name__", "") == "TclError":
            err_text = str(val or "")
            if "invalid command name" in err_text:
                return
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Cache Vault — Error",
                f"Something went wrong.\n\nDetails were saved to:\n{path}",
                parent=self if self._alive() else None,
            )
        except Exception:  # noqa: BLE001
            pass

    def __init__(self, vault: Vault | None = None):
        super().__init__()
        self.vault = vault or Vault()
        self.title(brand.WINDOW_TITLE)
        self.geometry("1200x760")
        self.minsize(1000, 650)
        self._apply_window_icon()

        self._search_var = ctk.StringVar()
        self._search_job = None
        self._capture_refresh_job = None
        self._capture_refresh_pending = False
        self._expiry_job = None
        self._shutting_down = False
        self._main_thread_calls: queue.SimpleQueue = queue.SimpleQueue()
        self._view_mode = "cards"
        self._selected_clip_id: str | None = None
        self._visible_clip_ids: list[str] = []
        self._sort_key = models.SORT_NEWEST_ADDED
        self._date_added_preset: str | None = None
        self._date_used_preset: str | None = None
        self._type_filter: str | None = None
        self._sensitive_only = False
        self._vault_locked = vault_lock.should_lock_on_startup(self.vault.settings)
        tooltip.set_tooltips_locked(self._vault_locked)
        self._idle_lock_job = None
        self._last_unlock_at = models.now_iso()
        self._nav_history: list[str] = []
        self._nav_forward_stack: list[str] = []

        self._mobile_bridge = MobileBridge(self.vault)

        from ..core.vault_macros import MacroSafeRegistry, MacroStore
        self._macro_store = MacroStore()
        self._macro_registry = MacroSafeRegistry(self.vault.settings)

        install_windows_scroll_patch(
            lambda: scroll_config_from_settings(self.vault.settings),
        )

        self._build_layout()
        if self._vault_locked:
            vault_lock.record_lock_event(
                self.vault.events,
                vault_lock.EVENT_VAULT_LOCKED,
                mode=self.vault.settings.vault_lock_mode,
                reason="startup",
            )

        # Clipboard monitor — callback marshalled onto the Tk thread.
        self._monitor = ClipboardMonitor(
            self._on_clip_captured,
            poll_interval_ms=self.vault.settings.poll_interval_ms,
        )
        if self.vault.settings.capture_paused:
            self._monitor.pause()
        self._monitor.start()

        # Global quick-paste hotkey (default Ctrl+Shift+V).
        self._paste_target = None
        self._quick_paste = None
        self._hotkey = HotkeyListener(
            self.vault.settings.quick_paste_hotkey,
            on_activate=self._schedule_quick_paste,
        )
        self._hotkey.start()

        self._capture_ctrl = CaptureController(lambda: self.vault.settings)
        self._capture_hotkeys = MultiHotkeyListener()
        self._bind_capture_hotkeys()
        self._capture_hotkeys.start()

        from ..core.macro_execute import MacroExecutor, system_reserved_hotkeys
        from ..core.macro_shortcut_listener import TextShortcutListener
        from ..core.vault_macros import TRIGGER_HOTKEY, TRIGGER_MENU_ONLY, TRIGGER_TEXT_SHORTCUT

        self._TRIGGER_HOTKEY = TRIGGER_HOTKEY
        self._TRIGGER_MENU_ONLY = TRIGGER_MENU_ONLY
        self._TRIGGER_TEXT_SHORTCUT = TRIGGER_TEXT_SHORTCUT
        self._system_reserved_hotkeys = system_reserved_hotkeys
        self._macro_picker = None
        self._macro_executor = MacroExecutor(
            self.vault.settings,
            self._macro_store,
            self._macro_registry,
            self.vault.events,
            on_notice=lambda msg: self._call_on_main(lambda m=msg: self._show_toast(m)),
            confirm_sensitive=self._confirm_sensitive_macro,
        )
        self._macro_hotkeys = MultiHotkeyListener()
        self._macro_hotkey_bindings: dict[int, tuple[str, list]] = {}
        self._bind_macro_hotkeys()
        self._macro_hotkeys.start()
        self._text_shortcut_listener = TextShortcutListener(
            on_match=self._on_text_shortcut_match,
            should_skip=lambda hwnd: hwnd_belongs_to_widget(hwnd, self),
            schedule_main=self._call_on_main,
        )
        self._sync_text_shortcut_listener()
        self._text_shortcut_listener.start()

        # Closing the window hides to tray (if available) rather than quitting.
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_window_unmap, add="+")

        self.refresh()
        self._schedule_auto_lock()
        self._expiry_job = self.after(EXPIRY_SWEEP_MS, self._expiry_tick)
        self._bind_tooltip_hide_events()
        # Start mobile bridge after the window is live (zeroconf must not block UI).
        self.after(0, lambda: self._mobile_bridge.sync(self.vault.settings))

        # Tray last — callbacks marshal through _call_on_main (pystray runs off-thread).
        self._tray = TrayController(
            on_open=lambda: self._call_on_main(self._show_window),
            on_pause=lambda: self._call_on_main(lambda: self._set_paused(True)),
            on_resume=lambda: self._call_on_main(lambda: self._set_paused(False)),
            on_clear_sensitive=lambda: self._call_on_main(self._clear_sensitive),
            on_quit=lambda: self._call_on_main(self._quit),
            on_quick_paste=lambda: self._call_on_main(self._schedule_quick_paste),
        )
        self._tray.start()

        self._center_on_screen()
        self._show_window()
        self.after(50, self._pump_main_thread)
        self.after(150, self._maybe_show_first_use_guide)
        self._bind_selection_keys()

    def _alive(self) -> bool:
        if self._shutting_down:
            return False
        try:
            return bool(self.winfo_exists())
        except Exception:  # noqa: BLE001
            return False

    def _bind_tooltip_hide_events(self) -> None:
        """Keep hover help out of active interactions and window transitions."""
        for event in (
            "<Button-1>",
            "<Button-2>",
            "<Button-3>",
            "<MouseWheel>",
            "<Configure>",
            "<FocusOut>",
            "<Unmap>",
        ):
            self.bind_all(event, lambda _e: tooltip.hide_tooltip(), add="+")

    def _bind_selection_keys(self) -> None:
        keymap = {
            "<Up>": lambda e: self._keyboard_move_selection(-1, e),
            "<Down>": lambda e: self._keyboard_move_selection(1, e),
            "<Home>": lambda e: self._keyboard_select_edge(first=True, event=e),
            "<End>": lambda e: self._keyboard_select_edge(first=False, event=e),
            "<Return>": lambda e: self._keyboard_primary_action(e),
            "<Control-c>": lambda e: self._keyboard_copy_selected(e),
            "<Control-C>": lambda e: self._keyboard_copy_selected(e),
            "<Control-Shift-C>": lambda e: self._keyboard_copy_clean_selected(e),
            "<Delete>": lambda e: self._keyboard_remove_selected(e),
            "<Shift-F10>": lambda e: self._keyboard_open_context_menu(e),
            "<Menu>": lambda e: self._keyboard_open_context_menu(e),
            "<Escape>": self._on_escape_pressed,
            "<Button-8>": lambda _e: self._navigate_back(),
            "<Button-9>": lambda _e: self._navigate_forward(),
        }
        for sequence, callback in keymap.items():
            try:
                self.bind_all(sequence, callback, add="+")
            except Exception: # Some mouse buttons might not be supported on all systems
                pass

    def destroy(self) -> None:
        """Fully clean up all background threads and listeners."""
        # 1. Stop UI timers
        if hasattr(self, "_idle_lock_job") and self._idle_lock_job:
            self.after_cancel(self._idle_lock_job)
        if hasattr(self, "_expiry_job") and self._expiry_job:
            self.after_cancel(self._expiry_job)

        # 2. Stop system listeners
        if hasattr(self, "_monitor"):
            self._monitor.stop()
        if hasattr(self, "_hotkey"):
            self._hotkey.stop()
        if hasattr(self, "_capture_hotkeys"):
            self._capture_hotkeys.stop()
        if hasattr(self, "_macro_hotkeys"):
            self._macro_hotkeys.stop()
        if hasattr(self, "_text_shortcut_listener"):
            self._text_shortcut_listener.stop()
        if hasattr(self, "_tray"):
            self._tray.stop()
        if hasattr(self, "_mobile_bridge"):
            self._mobile_bridge.stop()

        # 3. Final destroy
        super().destroy()

    def _safe_after(self, ms: int, fn):
        if not self._alive():
            return None
        return self.after(ms, fn)

    def _window_viewable(self) -> bool:
        try:
            return bool(self.winfo_viewable()) and self.state() != "withdrawn"
        except Exception:  # noqa: BLE001
            return False

    def _call_on_main(self, fn) -> None:
        """Schedule ``fn`` on the Tk main thread (safe from pystray / worker threads)."""
        self._main_thread_calls.put(fn)

    def _pump_main_thread(self) -> None:
        while True:
            try:
                fn = self._main_thread_calls.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                write_crash("main thread dispatch", exc)
        if self._alive():
            self.after(50, self._pump_main_thread)

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        w, h = 1200, 760
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # --- layout ------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=220)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=340)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        # Top bar.
        top = ctk.CTkFrame(self, height=52, corner_radius=0,
                           fg_color=brand.SURFACE_BG)
        top.grid(row=0, column=0, columnspan=3, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self._control_strip = VaultControlStrip(
            top,
            callbacks=self._control_strip_callbacks(),
        )
        self._control_strip.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(top, text=brand.TERM_EXPORT, width=130,
                      command=self._export_view, **theme.primary_button()
                      ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(top, text=brand.TERM_STAMPED_RECEIPTS, width=130,
                      command=lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
                      **theme.secondary_button()
                      ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(top, text="⚙ Settings", width=90, command=self._open_settings,
                      **theme.secondary_button()
                      ).grid(row=0, column=3, padx=(4, 12))

        # Panels.
        self._filters = FilterNav(self, on_select=self._on_filter_select,
                                  settings=self.vault.settings,
                                  on_safe_context=self._open_safe_menu,
                                  width=210, corner_radius=0)
        self._filters.grid(row=1, column=0, sticky="nsew")

        self._center = ctk.CTkFrame(self, corner_radius=0, fg_color=brand.PANEL_BG)
        self._center.grid(row=1, column=1, sticky="nsew", padx=1)
        self._center.grid_rowconfigure(1, weight=1)
        self._center.grid_columnconfigure(0, weight=1)

        self._toolbar = ctk.CTkFrame(self._center, fg_color=brand.SURFACE_BG)
        self._toolbar.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        self._toolbar_row1 = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._toolbar_row1.pack(fill="x", padx=2, pady=(4, 2))
        self._toolbar_row2 = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._toolbar_row2.pack(fill="x", padx=2, pady=(0, 2))
        self._toolbar_row3 = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._toolbar_row3.pack(fill="x", padx=2, pady=(0, 4))
        self._search_var.trace_add("write", self._on_search_changed)
        self._build_toolbar()

        self._home = HomeDashboard(
            self._center,
            on_filter=self._navigate_filter,
            on_open_receipts=lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
            on_mobile_settings=lambda: self._navigate_screen(NAV_MOBILE_ACCESS),
            on_pair_android=lambda: self._open_pair_android(),
            on_export=self._export_view,
            on_select_clip=self._on_clip_select,
            on_copy=self._copy_again,
            on_clip_context=self._open_home_clip_menu,
            on_card_context=self._open_home_card_menu,
            on_app_context=self._open_home_app_menu,
            on_status_context=self._open_home_status_menu,
            on_quick_paste=self._schedule_quick_paste,
            on_view_editable_copies=lambda: self._navigate_screen(NAV_EDITABLE_COPIES),
            on_view_html_bundles=lambda: self._navigate_screen(NAV_HTML_BUNDLES),
            on_settings=self._open_settings,
            image_assets_ready=False,
            corner_radius=0,
        )
        self._list = ClipList(
            self._center, on_select=self._on_clip_select,
            on_context=self._open_clip_menu,
            corner_radius=0, fg_color=brand.PANEL_BG,
        )
        self._grid = ClipGrid(
            self._center, on_select=self._on_clip_select,
            on_sort=self._set_sort,
            on_context=self._open_clip_menu,
            corner_radius=0, fg_color=brand.PANEL_BG,
        )
        self._home.grid(row=1, column=0, sticky="nsew")
        self._list.grid(row=1, column=0, sticky="nsew")
        self._grid.grid(row=1, column=0, sticky="nsew")
        self._grid.grid_remove()
        self._list.grid_remove()

        self._vault_screens = VaultScreenHost(
            self._center,
            callbacks={
                "vault": lambda: self.vault,
                "get_clip": self.vault.storage.get_clip,
                "open_receipts_dialog": self._open_events,
                "export_view": self._export_view,
                "open_editable_copy": self._open_editable_copy,
                "save_revision": self._save_editable_revision,
                "reveal_copy": self._reveal_editable_copy_folder,
                "select_clip": self._select_clip_by_id,
                "preview_html": self._preview_html_copy,
                "edit_html": self._edit_html_source,
                "export_html": self._export_html_bundle,
                "reveal_export": self._reveal_export_path,
                "mobile_report": self._mobile_access_report,
                "pair_android": lambda: self._open_pair_android(),
                "mobile_settings": self._open_settings,
                "macro_list": self._macro_list_rows,
                "macro_edit": self._macro_edit,
                "macro_new_template": self._macro_new_template,
                "macro_setup": self._open_macro_setup,
                "macro_run": self._macro_run,
                "copy_clip": self._copy_again,
                "open_link": self._open_clip_link,
                "export_proof": self._export_clip_proof,
                "remove_clip": self._remove_from_history,
                "open_clip_menu": self._open_clip_menu,
                "open_receipt_menu": self._open_receipt_menu,
            },
            corner_radius=0,
        )
        self._vault_screens.grid(row=1, column=0, sticky="nsew")
        self._vault_screens.grid_remove()

        self._preview = PreviewPanel(self, actions=self._build_actions(),
                                     corner_radius=0, fg_color=brand.SURFACE_BG)
        self._preview.grid(row=1, column=2, sticky="nsew")

        # Footer.
        footer = ctk.CTkFrame(self, height=28, corner_radius=0,
                              fg_color=brand.SURFACE_BG)
        footer.grid(row=2, column=0, columnspan=3, sticky="ew")
        ctk.CTkLabel(footer, text=brand.STUDIO_FOOTER, anchor="center",
                     text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=10)).pack(fill="x", pady=4)

        self._lock_screen = VaultLockScreen(
            self,
            on_unlock=self._unlock_vault,
            on_quit=self._quit,
            mode=self.vault.settings.vault_lock_mode,
            style=self.vault.settings.vault_lock_style,
            accent=self.vault.settings.vault_lock_accent,
            show_local_only=self.vault.settings.vault_lock_show_local_only,
        )
        self._lock_screen.grid(row=0, column=0, columnspan=3, rowspan=3, sticky="nsew")
        if self._vault_locked:
            self._lock_screen.lift()
            self.after(100, self._lock_screen.focus_unlock)
        else:
            self._lock_screen.grid_remove()

    def _build_toolbar(self) -> None:
        self._sort_var = ctk.StringVar(value="Newest Added")
        self._added_var = ctk.StringVar(value="Any")
        self._used_var = ctk.StringVar(value="Any")
        self._type_var = ctk.StringVar(value="All Types")

        self._clips_search = ctk.CTkEntry(
            self._toolbar_row1,
            textvariable=self._search_var,
            placeholder_text="Search saved clips…  (type:link  source:cursor)",
            height=32,
        )
        self._clips_search.pack(fill="x", padx=6, pady=4)

        ctk.CTkLabel(self._toolbar_row2, text="Sort:", text_color=brand.MUTED_FG,
                     font=theme.body_font(11)).pack(side="left", padx=(8, 4))
        ctk.CTkOptionMenu(
            self._toolbar_row2, variable=self._sort_var, width=128,
            values=[
                "Newest Added", "Oldest Added", "Recently Used", "Oldest Used",
                "Most Used", "Least Used", "Largest", "Smallest",
                "Source App", "Type", "Collection", "Favorites First", "Duplicates First",
            ],
            command=self._on_sort_menu,
        ).pack(side="left", padx=2)
        ctk.CTkLabel(self._toolbar_row2, text="First Saved:", text_color=brand.MUTED_FG,
                     font=theme.body_font(11)).pack(side="left", padx=(8, 2))
        ctk.CTkOptionMenu(
            self._toolbar_row2, variable=self._added_var, width=110,
            values=["Any", "Today", "Yesterday", "This Week", "Last 7 Days",
                    "This Month", "Last 30 Days", "Older"],
            command=self._on_added_filter,
        ).pack(side="left", padx=2)
        ctk.CTkLabel(self._toolbar_row2, text="Last Used:", text_color=brand.MUTED_FG,
                     font=theme.body_font(11)).pack(side="left", padx=(8, 2))
        ctk.CTkOptionMenu(
            self._toolbar_row2, variable=self._used_var, width=110,
            values=["Any", "Today", "Yesterday", "This Week", "Last 7 Days",
                    "This Month", "Last 30 Days", "Older"],
            command=self._on_used_filter,
        ).pack(side="left", padx=2)
        ctk.CTkLabel(self._toolbar_row2, text="Type:", text_color=brand.MUTED_FG,
                     font=theme.body_font(11)).pack(side="left", padx=(8, 2))
        ctk.CTkOptionMenu(
            self._toolbar_row2, variable=self._type_var, width=108,
            values=[
                "All Types", "Text", "Links", "Code", "Commands",
                "Emails", "Phone Numbers", "Files / Paths", "Screenshots / Images", "Sensitive",
            ],
            command=self._on_type_filter,
        ).pack(side="left", padx=2)

        ctk.CTkLabel(self._toolbar_row3, text="View:", text_color=brand.MUTED_FG,
                     font=theme.body_font(11)).pack(side="right", padx=(4, 2))
        self._grid_btn = ctk.CTkButton(
            self._toolbar_row3, text="Grid", width=58, height=28,
            command=lambda: self._set_view_mode("grid"), **theme.segmented_inactive(),
        )
        self._grid_btn.pack(side="right", padx=2)
        self._cards_btn = ctk.CTkButton(
            self._toolbar_row3, text="Cards", width=58, height=28,
            command=lambda: self._set_view_mode("cards"), **theme.segmented_active(),
        )
        self._cards_btn.pack(side="right", padx=2)
        self._dup_btn = ctk.CTkButton(
            self._toolbar_row3, text="Review Duplicates", width=140, height=28,
            command=self._open_duplicate_review, **theme.secondary_button(),
        )
        self._dup_btn.pack(side="left", padx=8)
        self._selected_action_frame = ctk.CTkFrame(self._toolbar_row3, fg_color="transparent")
        self._selected_action_frame.pack(side="left", padx=(8, 4))
        self._selected_action_label = ctk.CTkLabel(
            self._selected_action_frame,
            text="No item selected",
            text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=10),
        )
        self._selected_action_label.pack(side="left", padx=(0, 4))
        self._selected_action_buttons: list[ctk.CTkButton] = []
        self._update_selected_action_strip(None)

    def _control_strip_callbacks(self) -> dict:
        return {
            "pause_capture": lambda: self._set_paused(not self.vault.settings.capture_paused),
            "save_current_clipboard": self._manual_save_clipboard,
            "save_next_copy": self._arm_next_copy,
            "ignore_next_copy": self._ignore_next_copy,
            "capture_rules": self._open_settings,
            "mobile_access": lambda: self._navigate_screen(NAV_MOBILE_ACCESS),
            "pair_device": lambda: self._open_pair_android(),
            "mobile_inbox": lambda: self._navigate_screen(NAV_MOBILE_INBOX),
            "mobile_receipts": self._open_mobile_receipts,
            "stamped_ledger": lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
            "export_proof_zip": self._export_view,
            "open_receipts_folder": self._open_receipts_folder,
            "quick_paste": self._schedule_quick_paste,
            "vault_macros": lambda: self._navigate_screen(NAV_VAULT_MACROS),
            "export_selected": self._export_selected_or_view,
            "show_first_use_guide": self._open_first_use_guide_from_settings,
            "lock_now": self._lock_now,
        }

    def _selected_clip(self):
        if not self._selected_clip_id:
            return None
        return self.vault.storage.get_clip(self._selected_clip_id)

    def _update_selected_action_strip(self, clip) -> None:
        if not hasattr(self, "_selected_action_frame"):
            return
        for btn in getattr(self, "_selected_action_buttons", []):
            btn.destroy()
        self._selected_action_buttons = []
        if self._locked() or clip is None:
            self._selected_action_label.configure(text="No item selected")
            return
        label = (clip.title or clip.preview or "Selected item").splitlines()[0][:28]
        self._selected_action_label.configure(text=f"Selected: {label}")
        actions: list[tuple[str, Callable[[], None]]] = []
        if clip.classification == models.CLASS_LINK:
            actions = [
                ("Open", lambda c=clip: self._open_clip_link(c.id)),
                ("Copy Link", lambda c=clip: self._copy_clean(c.id, copy_clean.COPY_LINK_ONLY)),
                ("Copy Clean", lambda c=clip: self._copy_clean(c.id, copy_clean.COPY_MARKDOWN)),
                ("Export Proof", lambda c=clip: self._export_clip_proof(c.id)),
            ]
        elif clip.content_type == models.CONTENT_IMAGE:
            actions = [
                ("Copy Image", lambda c=clip: self._copy_again(c.id)),
                ("Open", lambda c=clip: self._open_asset_folder(c.id)),
                ("Export Proof", lambda c=clip: self._export_clip_proof(c.id)),
            ]
        elif clip.capture_mode == models.CAPTURE_MOBILE_SHARE:
            actions = [
                ("Copy", lambda c=clip: self._copy_again(c.id)),
                ("Move Safe", lambda c=clip: self._move_to_safe(c.id)),
                ("Export Proof", lambda c=clip: self._export_clip_proof(c.id)),
            ]
        else:
            actions = [
                ("Copy", lambda c=clip: self._copy_again(c.id)),
                ("Copy Clean", lambda c=clip: self._copy_clean(c.id, copy_clean.COPY_PLAIN_TEXT)),
                ("Move Safe", lambda c=clip: self._move_to_safe(c.id)),
                ("Export Proof", lambda c=clip: self._export_clip_proof(c.id)),
            ]
        actions.append(("More", self._keyboard_open_context_menu))
        for text, command in actions[:5]:
            btn = ctk.CTkButton(
                self._selected_action_frame,
                text=text,
                width=82,
                height=24,
                command=command,
                **theme.secondary_button(),
            )
            btn.pack(side="left", padx=2)
            self._selected_action_buttons.append(btn)

    def _keyboard_focus_is_text_input(self, event=None) -> bool:
        widget = getattr(event, "widget", None)
        if widget is None:
            return False
        cls = widget.winfo_class()
        return cls in {"Entry", "Text"} or "Entry" in cls or "Textbox" in cls

    def _keyboard_move_selection(self, delta: int, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if not self._visible_clip_ids:
            return "break"
        current = self._selected_clip_id
        idx = self._visible_clip_ids.index(current) if current in self._visible_clip_ids else 0
        idx = max(0, min(len(self._visible_clip_ids) - 1, idx + delta))
        self._select_visible_clip_by_id(self._visible_clip_ids[idx])
        return "break"

    def _keyboard_select_edge(self, *, first: bool, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if self._visible_clip_ids:
            self._select_visible_clip_by_id(self._visible_clip_ids[0 if first else -1])
        return "break"

    def _keyboard_primary_action(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        clip = self._selected_clip()
        if clip is None:
            return "break"
        if clip.classification == models.CLASS_LINK:
            self._open_clip_link(clip.id)
        else:
            self._copy_again(clip.id)
        return "break"

    def _keyboard_copy_selected(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        clip = self._selected_clip()
        if clip is not None:
            self._copy_again(clip.id)
        return "break"

    def _keyboard_copy_clean_selected(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        clip = self._selected_clip()
        if clip is not None:
            self._copy_clean(clip.id, copy_clean.COPY_PLAIN_TEXT)
        return "break"

    def _keyboard_remove_selected(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        clip = self._selected_clip()
        if clip is not None:
            from tkinter import messagebox
            ok = messagebox.askyesno(
                "Remove from History",
                "Remove the selected clip from Cache Vault history? It can be restored from Recently Removed.",
                parent=self,
            )
            if ok:
                self._remove_from_history(clip.id)
        return "break"

    def _keyboard_open_context_menu(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        clip = self._selected_clip()
        if clip is None:
            return "break"
        if self._view_mode == "grid":
            self._grid.open_context_for_selected(clip)
        else:
            self._list.open_context_for_selected(clip)
        return "break"

    def _locked(self) -> bool:
        return bool(getattr(self, "_vault_locked", False))

    def _lock_now(self, *, reason: str = "manual") -> None:
        if not vault_lock.lock_config(self.vault.settings).enabled:
            self._show_toast("Enable Vault Lock in Settings first.")
            return
        if self._locked():
            return
        tooltip.set_tooltips_locked(True)
        self._vault_locked = True
        self._selected_clip_id = None
        self._visible_clip_ids = []
        self._render_locked_surface()
        self._lock_screen.set_mode(self.vault.settings.vault_lock_mode)
        self._lock_screen.set_style(
            self.vault.settings.vault_lock_style,
            accent=self.vault.settings.vault_lock_accent,
            show_local_only=self.vault.settings.vault_lock_show_local_only,
        )
        self._lock_screen.grid()
        self._lock_screen.lift()
        self._lock_screen.focus_unlock()
        vault_lock.record_lock_event(
            self.vault.events,
            vault_lock.EVENT_VAULT_LOCKED,
            mode=self.vault.settings.vault_lock_mode,
            reason=reason,
        )

    def _unlock_vault(self, secret: str) -> bool:
        if vault_lock.verify_secret(self.vault.settings, secret):
            self._vault_locked = False
            tooltip.set_tooltips_locked(False)
            self._lock_screen.grid_remove()
            self._last_unlock_at = models.now_iso()
            vault_lock.record_lock_event(
                self.vault.events,
                vault_lock.EVENT_VAULT_UNLOCKED,
                mode=self.vault.settings.vault_lock_mode,
            )
            self._schedule_auto_lock()
            self.refresh()
            if self._capture_refresh_pending:
                self._schedule_capture_refresh()
            return True
        vault_lock.record_lock_event(
            self.vault.events,
            vault_lock.EVENT_VAULT_UNLOCK_FAILED,
            mode=self.vault.settings.vault_lock_mode,
            reason="invalid_unlock",
        )
        return False

    def _schedule_auto_lock(self) -> None:
        if self._idle_lock_job:
            try:
                self.after_cancel(self._idle_lock_job)
            except Exception:  # noqa: BLE001
                pass
            self._idle_lock_job = None
        cfg = vault_lock.lock_config(self.vault.settings)
        if not cfg.enabled or cfg.auto_lock_minutes <= 0 or self._locked():
            return
        self._idle_lock_job = self.after(
            cfg.auto_lock_minutes * 60_000,
            lambda: self._lock_now(reason="auto_lock"),
        )

    def _guard_unlocked(self) -> bool:
        if not self._locked():
            return True
        try:
            self._lock_screen.lift()
            self._lock_screen.focus_unlock()
        except Exception:  # noqa: BLE001
            pass
        return False

    def _open_receipts_folder(self) -> None:
        from ..core.settings import default_settings_path
        from ..core import pathutil
        folder = default_settings_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        pathutil.open_path(str(folder))

    def _export_selected_or_view(self) -> None:
        clip = getattr(self._preview, "_clip", None)
        if clip is not None:
            self._export_clip_proof(clip.id)
        else:
            self._export_view()

    def _sort_label_to_key(self, label: str) -> str:
        return {
            "Newest Added": models.SORT_NEWEST_ADDED,
            "Oldest Added": models.SORT_OLDEST_ADDED,
            "Recently Used": models.SORT_RECENTLY_USED,
            "Oldest Used": models.SORT_OLDEST_USED,
            "Most Used": models.SORT_MOST_USED,
            "Least Used": models.SORT_LEAST_USED,
            "Largest": models.SORT_LARGEST,
            "Smallest": models.SORT_SMALLEST,
            "Source App": models.SORT_SOURCE,
            "Type": models.SORT_TYPE,
            "Collection": models.SORT_COLLECTION,
            "Favorites First": models.SORT_FAVORITES_FIRST,
            "Duplicates First": models.SORT_DUPLICATES_FIRST,
        }.get(label, models.SORT_NEWEST_ADDED)

    def _preset_from_label(self, label: str) -> str | None:
        if label in ("Any", "First Saved: Any", "Last Used: Any"):
            return None
        mapping = {
            "Today": "today",
            "Yesterday": "yesterday",
            "This Week": "week",
            "Last 7 Days": "last7",
            "This Month": "month",
            "Last 30 Days": "last30",
            "Older": "older",
        }
        for key, val in mapping.items():
            if key in label:
                return val
        return None

    def _on_sort_menu(self, choice: str) -> None:
        self._sort_key = self._sort_label_to_key(choice)
        self.refresh()

    def _on_added_filter(self, choice: str) -> None:
        self._date_added_preset = self._preset_from_label(choice)
        self.refresh()

    def _on_used_filter(self, choice: str) -> None:
        self._date_used_preset = self._preset_from_label(choice)
        self.refresh()

    def _on_type_filter(self, choice: str) -> None:
        mapping = {
            "All Types": None,
            "Text": models.CLASS_PLAIN,
            "Links": models.CLASS_LINK,
            "Code": models.CLASS_CODE,
            "Commands": models.CLASS_COMMAND,
            "Emails": models.CLASS_EMAIL,
            "Phone Numbers": models.CLASS_PHONE,
            "Files / Paths": models.CLASS_PATH,
            "Screenshots / Images": models.CLASS_IMAGE,
            "Sensitive": "sensitive",
        }
        val = mapping.get(choice)
        if val == "sensitive":
            self._type_filter = None
            self._sensitive_only = True
        else:
            self._type_filter = val
            self._sensitive_only = False
        self.refresh()

    def _set_sort(self, key: str) -> None:
        self._sort_key = key
        self.refresh()

    def _set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        if mode == "cards":
            self._cards_btn.configure(**theme.segmented_active())
            self._grid_btn.configure(**theme.segmented_inactive())
        else:
            self._grid_btn.configure(**theme.segmented_active())
            self._cards_btn.configure(**theme.segmented_inactive())
        self.refresh()

    def _vault_panel_callbacks(self) -> dict:
        return {
            "review_duplicates": self._open_duplicate_review,
            "open_receipts": lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
            "view_editable_copies": lambda: self._navigate_screen(NAV_EDITABLE_COPIES),
            "view_html_bundles": lambda: self._navigate_screen(NAV_HTML_BUNDLES),
            "pair_android": lambda: self._open_pair_android(),
            "export": self._export_view,
            "mobile_settings": lambda: self._navigate_screen(NAV_MOBILE_ACCESS),
        }

    def _navigate_screen(self, key: str, record_history: bool = True) -> None:
        tooltip.hide_tooltip()
        prev = self._filters.active
        self._filters.set_active(key)
        self._on_filter_select(key, record_history=record_history, prev_key=prev)

    def _select_clip_by_id(self, clip_id: str) -> None:
        from ..core import storage as S
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        self._filters.set_active(S.FILTER_ALL)
        self._on_filter_select(S.FILTER_ALL)
        self._on_clip_select(clip)

    def _select_visible_clip_by_id(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip is not None:
            self._on_clip_select(clip)

    def _mobile_access_report(self) -> dict:
        import socket
        import urllib.error
        import urllib.request

        summary = self.vault.dashboard_summary()
        local_ip = "—"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except OSError:
            pass
        receipts = self._mobile_bridge.receipts.recent(5)
        last_connection = receipts[0].get("timestamp") if receipts else "—"
        pairing = (
            f"{summary.get('paired_count', 0)} device(s) paired"
            if summary.get("paired_count")
            else "No devices paired"
        )
        routes: dict[str, bool] = {}
        port = int(summary.get("mobile_port") or 8742)
        if self._mobile_bridge.is_running:
            for path in (
                "/mobile/v1/status",
                "/mobile/v1/clips",
                "/mobile/v1/recently-removed",
            ):
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{path}", timeout=1.5,
                    ) as resp:
                        routes[path] = resp.status in (200, 401)
                except urllib.error.HTTPError as exc:
                    routes[path] = exc.code in (200, 401)
                except Exception:  # noqa: BLE001
                    routes[path] = False
        else:
            for path in (
                "/mobile/v1/status",
                "/mobile/v1/clips",
                "/mobile/v1/recently-removed",
            ):
                routes[path] = False
        return {
            "summary": summary,
            "local_ip": local_ip,
            "pairing_status": pairing,
            "last_connection": last_connection,
            "routes": routes,
        }

    def _navigate_filter(self, key: str) -> None:
        prev = self._filters.active
        self._filters.set_active(key)
        if key == FILTER_HOME:
            self._preview.show_vault_control(
                self.vault.dashboard_summary(),
                self._vault_panel_callbacks(),
            )
        self._on_filter_select(key, prev_key=prev)

    def _show_home(self) -> None:
        self._toolbar.grid_remove()
        self._list.grid_remove()
        self._grid.grid_remove()
        self._vault_screens.hide()
        self._vault_screens.grid_remove()
        self._home.grid()

    def _show_clips(self) -> None:
        self._home.grid_remove()
        self._vault_screens.hide()
        self._vault_screens.grid_remove()
        self._toolbar.grid()
        if self._view_mode == "grid":
            self._list.grid_remove()
            self._grid.grid()
        else:
            self._grid.grid_remove()
            self._list.grid()

    def _show_vault_screen(self, key: str) -> None:
        self._home.grid_remove()
        self._list.grid_remove()
        self._grid.grid_remove()
        self._toolbar.grid_remove()
        self._vault_screens.grid()
        self._vault_screens.show(key)
        if self._preview._clip is None:  # noqa: SLF001
            self._preview.show_vault_control(
                self.vault.dashboard_summary(),
                self._vault_panel_callbacks(),
            )

    def _open_duplicate_review(self) -> None:
        groups = self.vault.duplicate_groups()
        if not groups:
            from tkinter import messagebox
            messagebox.showinfo("Duplicate Review", "No duplicate groups found.", parent=self)
            return
        DuplicateReviewDialog(self, groups[0], on_action=self._duplicate_action)

    def _duplicate_action(self, action: str, merge_history: bool) -> None:
        groups = self.vault.duplicate_groups()
        if not groups:
            return
        group = groups[0]
        if action == "move_extras":
            keeper = max(group.clips, key=lambda c: c.created_at)
            from ..core.duplicates import move_extras_to_recently_removed
            move_extras_to_recently_removed(self.vault.storage, self.vault.events, group, keeper.id)
        else:
            self.vault.review_duplicates(group, action, merge_history=merge_history)
        self.refresh()
        self._preview.show(None)

    def _apply_window_icon(self) -> None:
        from .icon import icon_ico_path
        try:
            path = icon_ico_path()
            if os.path.exists(path):
                self.iconbitmap(default=path)
        except Exception:  # noqa: BLE001 - icon is cosmetic
            pass

    def _build_actions(self) -> dict:
        storage = self.vault.storage

        def asset_meta(clip_id: str) -> dict | None:
            rec = storage.get_asset_record(clip_id)
            if rec is None:
                return None
            return {
                "sha256": rec.sha256,
                "size_bytes": rec.size_bytes,
                "width": rec.width,
                "height": rec.height,
            }

        def open_asset_folder(clip_id: str) -> None:
            from ..core import image_assets
            rec = storage.get_asset_record(clip_id)
            if rec is None:
                return
            path = image_assets.assets_dir() / rec.storage_name
            if path.is_file():
                subprocess.run(["explorer", "/select,", str(path)], check=False)

        return {
            "copy_again": self._copy_again,
            "reveal": self.vault.reveal_sensitive,
            "toggle_favorite": self._toggle_favorite,
            "mark_keep": self._mark_keep,
            "copy_metadata": self._copy_metadata,
            "expire_now": self._expire_now,
            "remove_from_history": self._remove_from_history,
            "restore": self._restore,
            "permanently_remove": self._permanently_remove,
            "load_asset": storage.load_clip_asset_bytes,
            "asset_meta": asset_meta,
            "save_asset_as": self._save_asset_as,
            "drag_out": self._drag_out_clip,
            "open_asset_folder": open_asset_folder,
            "latest_editable_copy": self.vault.latest_editable_copy,
            "html_bundle_summary": self.vault.html_bundle_summary,
            "create_editable_copy": self._create_editable_copy,
            "open_editable_copy": self._open_editable_copy,
            "preview_html_copy": self._preview_html_copy,
            "edit_html_source": self._edit_html_source,
            "save_editable_revision": self._save_editable_revision,
            "reveal_editable_copy_folder": self._reveal_editable_copy_folder,
            "export_html_bundle": self._export_html_bundle,
            "export_proof_zip": self._export_clip_proof,
            "export_editable_copy": lambda cid: self._export_clip_proof_mode(cid, "editable_copy"),
            "clip_inspector_context": self.vault.clip_inspector_context,
            "copy_path": self._copy_path,
        }

    # --- data refresh ------------------------------------------------------
    def refresh(self) -> None:
        if not self._alive():
            return
        tooltip.hide_tooltip()
        try:
            from ..core import storage as S

            if self._locked():
                self._render_locked_surface()
                self._lock_screen.lift()
                return

            active = self._filters.active
            counts = self.vault.counts()
            summary = self.vault.dashboard_summary()
            counts[NAV_STAMPED_RECEIPTS] = summary.get("receipts", 0)
            counts[NAV_MOBILE_ACCESS] = summary.get("paired_count", 0)
            counts[NAV_MOBILE_INBOX] = summary.get("mobile_inbox", 0)
            counts[NAV_EDITABLE_COPIES] = summary.get("editable_copies", 0)
            counts[NAV_HTML_BUNDLES] = summary.get("html_bundles", 0)
            counts[NAV_EXPORTS] = len(self.vault.list_export_events(500))
            counts[NAV_VAULT_MACROS] = len(self._macro_store.load_all())
            self._filters.update_counts(counts)
            self._filters.update_collections(self.vault.list_collections())
            self._filters.update_safes(self.vault.list_safes())

            if active in NAV_SCREEN_KEYS:
                self._show_vault_screen(active)
                clip_count = summary.get("all", 0)
            elif active == FILTER_HOME:
                self._show_home()
                q_recent = search.SearchQuery(filter_name=S.FILTER_ALL, sort=models.SORT_NEWEST_ADDED)
                q_fav = search.SearchQuery(filter_name=S.FILTER_FAVORITES, sort=models.SORT_NEWEST_ADDED)
                q_img = search.SearchQuery(filter_name=S.FILTER_SCREENSHOTS, sort=models.SORT_NEWEST_ADDED)
                image_ready = self.vault.storage.asset_storage_ready()
                self._home._image_ready = image_ready  # noqa: SLF001
                self._home.render(
                    summary,
                    self.vault.list_clips(q_recent)[:8],
                    self.vault.list_clips(q_fav)[:6],
                    self.vault.list_clips(q_img)[:6],
                )
                if self._preview._clip is None:  # noqa: SLF001
                    self._preview.show_vault_control(
                        summary,
                        self._vault_panel_callbacks(),
                    )
                clip_count = summary.get("all", 0)
            else:
                self._show_clips()
                query = self._build_query()
                clips = self.vault.list_clips(query)
                self._visible_clip_ids = [c.id for c in clips]
                if self._selected_clip_id not in self._visible_clip_ids:
                    self._selected_clip_id = self._visible_clip_ids[0] if self._visible_clip_ids else None
                empty_msg = self._empty_message(active, clips, query)
                if self._view_mode == "grid":
                    self._grid.set_selected(self._selected_clip_id)
                    self._grid.render(clips, empty_message=empty_msg)
                    self._grid.set_selected(self._selected_clip_id)
                else:
                    self._list.set_selected(self._selected_clip_id)
                    self._list.render(
                        clips,
                        empty_message=empty_msg,
                        group_by=self._group_by_for_view(active, query),
                    )
                    self._list.set_selected(self._selected_clip_id)
                self._update_selected_action_strip(
                    self.vault.storage.get_clip(self._selected_clip_id)
                    if self._selected_clip_id else None,
                )
                clip_count = len(clips)

            summary["shown"] = clip_count
            summary["default_safe"] = self.vault.settings.default_safe_id
            self._control_strip.update_state(summary)
            if self._locked():
                self._lock_screen.lift()
        except Exception as exc:  # noqa: BLE001
            write_crash("refresh", exc)
            raise

    def _render_locked_surface(self) -> None:
        self._selected_clip_id = None
        self._visible_clip_ids = []
        self._filters.update_counts({})
        self._filters.update_collections([])
        self._filters.update_safes([])
        self._show_clips()
        self._list.set_selected(None)
        self._grid.set_selected(None)
        self._list.render([], empty_message=clip_accents.LOCKED_ITEMS_MESSAGE)
        self._grid.render([], empty_message=clip_accents.LOCKED_ITEMS_MESSAGE)
        self._preview.show_locked_message()
        self._update_selected_action_strip(None)
        self._control_strip.update_state({
            "capture_paused": self.vault.settings.capture_paused,
            "mobile_enabled": False,
            "paired_count": 0,
            "default_safe": "Vault locked",
        })

    def _group_by_for_view(self, active: str, query) -> str | None:
        from ..core import storage as S

        if query.domain:
            return "domain"
        if active.startswith(S.SAFE_PREFIX):
            return "safe"
        if self._sort_key == models.SORT_SOURCE:
            return "source"
        if self._sort_key == models.SORT_TYPE:
            return "type"
        if self._sort_key in (models.SORT_NEWEST_ADDED, models.SORT_OLDEST_ADDED):
            return "date"
        return None

    # --- event handlers ----------------------------------------------------
    def _on_clip_captured(self, payload: dict) -> None:
        # Runs on the monitor thread; queue work for the Tk thread.
        capture_debug.log("queue_ingest", capture_debug.payload_summary(payload))
        self._call_on_main(lambda p=dict(payload): self._ingest(p))

    def _ingest(self, payload: dict) -> None:
        if not self._alive():
            capture_debug.log("ingest_skipped", "app_not_alive")
            return
        try:
            capture_debug.log("ingest_started", capture_debug.payload_summary(payload))
            if self._capture_ctrl.consume_ignore():
                chash = None
                item_type = models.CONTENT_TEXT
                if payload.get("text"):
                    chash = models.content_hash(payload["text"])
                elif payload.get("image_png"):
                    chash = models.bytes_hash(payload["image_png"])
                    item_type = models.CONTENT_IMAGE
                record_ignored_receipt(
                    self.vault.events,
                    source_app=payload.get("source_app"),
                    content_hash=chash,
                    item_type=item_type,
                )
                self._show_toast("Next copy was not saved.")
                capture_debug.log("ingest_skipped", "ignore_next_copy")
                return

            armed = self._capture_ctrl.consume_armed()
            if armed:
                safe_id, _safe_name = armed
                self._save_payload(
                    payload,
                    safe_id=safe_id,
                    capture_mode=models.CAPTURE_ARMED_NEXT_COPY,
                    force=True,
                )
                capture_debug.log("ingest_saved", "armed_next_copy")
                return

            if not self._capture_ctrl.should_auto_capture():
                capture_debug.log("ingest_skipped", "auto_capture_disabled_or_paused")
                return

            safe_id, _safe_name = self._capture_ctrl.resolve_safe_for_auto()
            self._save_payload(
                payload,
                safe_id=safe_id,
                capture_mode=models.CAPTURE_AUTO,
            )
        except Exception as exc:  # noqa: BLE001
            write_crash("clipboard ingest", exc)
            raise

    def _save_payload(
        self,
        payload: dict,
        *,
        safe_id: str,
        capture_mode: str,
        force: bool = False,
    ) -> None:
        clip = None
        if payload.get("image_png"):
            clip = self.vault.capture_image(
                payload["image_png"],
                width=payload.get("width") or 0,
                height=payload.get("height") or 0,
                source_app=payload.get("source_app"),
                source_window=payload.get("source_window"),
                capture_mode=capture_mode,
                safe_id=safe_id,
                force=force,
            )
        elif payload.get("text"):
            clip = self.vault.capture(
                payload["text"],
                source_app=payload.get("source_app"),
                source_window=payload.get("source_window"),
                capture_mode=capture_mode,
                safe_id=safe_id,
                force=force,
            )
            if (
                clip is None
                and capture_mode == models.CAPTURE_AUTO
                and self.vault.settings.block_sensitive_auto_capture
            ):
                from ..core import sensitive
                if sensitive.detect(payload["text"]).is_sensitive:
                    capture_debug.log("save_skipped", "sensitive_auto_block")
                    self._show_toast(
                        "Sensitive-looking clipboard item was not auto-saved."
                    )
        else:
            capture_debug.log("save_skipped", "unsupported_or_empty")
            return
        if clip is not None:
            capture_debug.log("save_created", f"clip_id={clip.id} type={clip.classification}")
            self._schedule_capture_refresh()
        else:
            capture_debug.log("save_skipped", "vault_returned_none")

    def _schedule_capture_refresh(self) -> None:
        """Batch repaint work after clipboard captures so copy feels instant."""
        self._capture_refresh_pending = True
        capture_debug.log("refresh_pending", "scheduled")
        if self._capture_refresh_job is not None:
            capture_debug.log("refresh_deferred", "existing_job")
            return
        if self._locked() or not self._window_viewable():
            capture_debug.log("refresh_deferred", "locked_or_not_viewable")
            return
        self._capture_refresh_job = self._safe_after(180, self._flush_capture_refresh)
        capture_debug.log("refresh_scheduled", "delay_ms=180")

    def _flush_capture_refresh(self) -> None:
        self._capture_refresh_job = None
        if not self._capture_refresh_pending:
            return
        self._capture_refresh_pending = False
        if self._locked() or not self._window_viewable():
            self._capture_refresh_pending = True
            capture_debug.log("refresh_deferred", "flush_locked_or_not_viewable")
            return
        self.refresh()
        capture_debug.log("refresh_flushed", "ok")

    def _show_toast(self, text: str) -> None:
        if self._alive():
            Toast(self, text)

    def _bind_capture_hotkeys(self) -> None:
        s = self.vault.settings
        self._capture_hotkeys.set_binding(
            HK_MANUAL_SAVE, s.manual_save_hotkey,
            on_activate=self._schedule_manual_save,
        )
        self._capture_hotkeys.set_binding(
            HK_ARM_NEXT, s.arm_next_copy_hotkey,
            on_activate=self._schedule_arm_next_copy,
        )
        self._capture_hotkeys.set_binding(
            HK_IGNORE_NEXT, s.ignore_next_copy_hotkey,
            on_activate=self._schedule_ignore_next_copy,
        )

    def _rebind_capture_hotkeys(self) -> None:
        if self._capture_hotkeys:
            self._capture_hotkeys.stop()
        self._capture_hotkeys = MultiHotkeyListener()
        self._bind_capture_hotkeys()
        self._capture_hotkeys.start()

    def _schedule_manual_save(self) -> None:
        self._call_on_main(self._manual_save_clipboard)

    def _schedule_arm_next_copy(self) -> None:
        self._call_on_main(self._arm_next_copy)

    def _schedule_ignore_next_copy(self) -> None:
        self._call_on_main(self._ignore_next_copy)

    def _manual_save_clipboard(self) -> None:
        if not self._guard_unlocked():
            return
        payload = read_clipboard_payload()
        if payload is None:
            self._show_toast("Clipboard is empty — nothing to save.")
            return
        picked = self._capture_ctrl.pick_safe_for_manual()
        if picked is None:
            SafePickerDialog(
                self, self.vault.settings,
                on_pick=lambda sid, _name: self._manual_save_to_safe(payload, sid),
                on_create=lambda name: self.vault.create_safe(name),
            )
            return
        self._manual_save_to_safe(payload, picked[0])

    def _manual_save_to_safe(self, payload: dict, safe_id: str) -> None:
        self._save_payload(
            payload,
            safe_id=safe_id,
            capture_mode=models.CAPTURE_MANUAL_SAVE_HOTKEY,
            force=True,
        )
        self._show_toast("Clipboard saved to Safe.")

    def _arm_next_copy(self) -> None:
        if not self._guard_unlocked():
            return
        def _apply(safe_id: str, safe_name: str) -> None:
            self._capture_ctrl.arm_next_copy(safe_id, safe_name)
            record_armed_receipt(
                self.vault.events, safe_id=safe_id, safe_name=safe_name,
            )
            self._show_toast(f"Save next copy to: {safe_name}")

        SafePickerDialog(
            self, self.vault.settings,
            title="Save next copy to",
            on_pick=_apply,
            on_create=lambda name: self.vault.create_safe(name),
        )

    def _ignore_next_copy(self) -> None:
        if not self._guard_unlocked():
            return
        self._capture_ctrl.arm_ignore_next()
        self._show_toast("Next copy will not be saved.")

    def _on_search_changed(self, *_):
        if not self._alive():
            return
        if self._search_job:
            try:
                self.after_cancel(self._search_job)
            except Exception:  # noqa: BLE001
                pass
        self._search_job = self._safe_after(180, self._debounced_refresh)

    def _debounced_refresh(self) -> None:
        self._search_job = None
        self.refresh()

    def _empty_message(self, active: str, clips: list, query) -> str | None:
        from ..core import storage as S
        if clips:
            return None
        if active != S.FILTER_ALL or query.text or query.type_filter or query.date_added_preset:
            return "No clips match this filter.\nTry All Clips or clear filters."
        return None

    def _on_filter_select(self, key: str, record_history: bool = True, prev_key: str | None = None) -> None:
        tooltip.hide_tooltip()
        if not self._guard_unlocked():
            return

        if record_history:
            current = prev_key if prev_key is not None else self._filters.active
            if current and current != key:
                # Only track actual sections, not transient actions.
                # Use a small history limit to avoid memory bloat.
                if not self._nav_history or self._nav_history[-1] != current:
                    self._nav_history.append(current)
                    if len(self._nav_history) > 50:
                        self._nav_history.pop(0)
                self._nav_forward_stack.clear()

        if key == NAV_QUICK_PASTE:
            self._schedule_quick_paste()
            return
        if key == NAV_SETTINGS:
            self._open_settings()
            return
        if key == NAV_VAULT_MACROS:
            if (
                self.vault.settings.vault_macros_enabled
                and not self.vault.settings.vault_macros_setup_completed
            ):
                self._open_macro_setup()
        if key == FILTER_HOME and self._preview._clip is None:  # noqa: SLF001
            self._preview.show_vault_control(
                self.vault.dashboard_summary(),
                self._vault_panel_callbacks(),
            )
        self.refresh()

    def _navigate_back(self) -> None:
        if self._locked():
            # Locked back returns to safe home if not already there,
            # or does nothing if history is empty.
            return
        if not self._nav_history:
            return
        
        current = self._filters.active
        prev = self._nav_history.pop()
        self._nav_forward_stack.append(current)
        self._navigate_screen(prev, record_history=False)

    def _navigate_forward(self) -> None:
        if self._locked() or not self._nav_forward_stack:
            return
        
        current = self._filters.active
        nxt = self._nav_forward_stack.pop()
        self._nav_history.append(current)
        self._navigate_screen(nxt, record_history=False)

    def _on_escape_pressed(self, event=None) -> None:
        tooltip.hide_tooltip()
        
        # 1. Close context menus (if we can find them)
        # 2. Close transient overlays
        if self._quick_paste and self._quick_paste.winfo_exists():
            self._quick_paste.destroy()
            self._quick_paste = None
            return

        # 3. Clear search if it has focus or text
        if self._search_var.get():
            self._search_var.set("")
            self.focus_set()
            return

        # 4. Clear selection if in list
        if self._selected_clip_id:
            self._selected_clip_id = None
            self.refresh()
            return

    def _on_clip_select(self, clip) -> None:
        if not self._guard_unlocked():
            return
        self._selected_clip_id = getattr(clip, "id", None)
        self._list.set_selected(self._selected_clip_id)
        self._grid.set_selected(self._selected_clip_id)
        self._home.set_selected(self._selected_clip_id)
        self._update_selected_action_strip(clip)
        if clip is not None:
            self._preview.set_usage_events(self.vault.clip_usage_events(clip.id))
        self._preview.show(clip)

    def _copy_again(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if clip.content_type == models.CONTENT_IMAGE:
            png = self.vault.copied_again_image(clip_id)
            if not png:
                return
            from ..core import image_assets
            if image_assets.write_clipboard_png(png):
                # Verify clipboard contains image data when possible and give a
                # precise message advising where to paste.
                ok = image_assets.clipboard_has_image()
                self._monitor.note_local_copy_image(png)
                if ok:
                    Toast(self, "Image copied to clipboard — paste into an image-capable app like Paint")
                else:
                    Toast(self, "Image copied to clipboard (target apps may not accept images)")
            return
        content = self.vault.copied_again(clip_id)
        if content is None:
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self._monitor.note_local_copy(content)

    def _open_clip_link(self, clip_id: str) -> None:
        import webbrowser
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        url = (clip.source_url or clip.content or "").strip()
        if url.startswith(("http://", "https://")):
            webbrowser.open(url)

    def _copy_metadata(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        clip = self.vault.storage.get_clip(clip_id)
        if not clip:
            return
        meta = (f"type={clip.classification} source={clip.source_app} "
                f"created={clip.created_at} last_used={clip.date_used} "
                f"use_count={clip.use_count} sensitive={clip.is_sensitive} "
                f"hash={clip.content_hash[:12]}")
        self.clipboard_clear()
        self.clipboard_append(meta)
        self._monitor.note_local_copy(meta)

    def _copy_path(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        self._copy_text(clip.content, "Copied path.")

    def _copy_clean(self, clip_id: str, action: str) -> None:
        if not self._guard_unlocked():
            return
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        text = copy_clean.format_clip(clip, action)
        if text is None:
            self._show_toast("That Copy Clean format is not available for this item.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._monitor.note_local_copy(text)
        self.vault.events.record(
            copy_clean.EVENT_ITEM_COPIED_CLEAN,
            clip_id,
            {
                "format": action,
                "classification": clip.classification,
                "content_type": clip.content_type,
                "capture_mode": clip.capture_mode,
                "safe_id": clip.safe_id,
                "safe_name": clip.safe_name,
            },
        )
        self._show_toast("Copied clean format.")

    def _copy_receipt_summary(self, row) -> None:
        if not self._guard_unlocked():
            return
        text = copy_clean.receipt_summary(row)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._monitor.note_local_copy(text)
        self.vault.events.record(
            copy_clean.EVENT_RECEIPT_SUMMARY_COPIED,
            getattr(row, "clip_id", None),
            {
                "receipt_id": getattr(row, "receipt_id", ""),
                "action": getattr(row, "action_raw", ""),
                "has_hash": bool(getattr(row, "proof_hash", "")),
            },
        )
        self._show_toast("Copied receipt summary.")

    def _toggle_favorite(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip:
            self.vault.set_favorite(clip_id, not clip.is_pinned)
            self.refresh()  # moves the row between Favorites / normal sections
            self._preview.show(self.vault.storage.get_clip(clip_id))

    def _mark_keep(self, clip_id: str) -> None:
        self.vault.mark_keep(clip_id)
        self.refresh()

    def _expire_now(self, clip_id: str) -> None:
        self.vault.expire_now(clip_id)
        self.refresh()
        self._preview.show(None)

    def _remove_from_history(self, clip_id: str) -> None:
        """Remove a clip from history. Confirms first if it's a favorite.

        Never deletes any real file/folder — only the Cache Vault entry.
        """
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if clip.is_pinned:  # favorite — confirm before losing it
            from tkinter import messagebox
            ok = messagebox.askyesno(
                "Remove from History",
                "This removes the clip from Cache Vault history. It does not "
                "delete files from your computer.\n\nRemove this favorite?",
                parent=self,
            )
            if not ok:
                return
        self.vault.remove_from_history(clip_id)
        self.refresh()
        self._preview.show(None)

    # --- clip-row context menu ---------------------------------------------
    def _open_clip_menu(self, clip, x_root: int, y_root: int) -> None:
        import tkinter as tk

        from ..core.contextmenu import clip_menu_items

        tooltip.before_menu_open()
        if self._locked():
            try:
                self._open_locked_menu(x_root, y_root)
            finally:
                tooltip.after_menu_close()
            return
        menu = tk.Menu(self, tearoff=0)
        dispatch = {
            "copy_again": lambda: self._copy_again(clip.id),
            "open_link": lambda: self._open_clip_link(clip.id),
            "open_asset_folder": lambda: self._open_asset_folder(clip.id),
            "drag_out": lambda: self._drag_out_clip(clip.id),
            "toggle_favorite": lambda: self._toggle_favorite(clip.id),
            "move_safe": lambda: self._move_to_safe(clip.id),
            "create_editable_copy": lambda: self._create_editable_copy(clip.id),
            "export_proof_zip": lambda: self._export_clip_proof(clip.id),
            "view_receipts": self._open_events,
            "view_mobile_receipt": self._open_events,
            "copy_metadata": lambda: self._copy_metadata(clip.id),
            "copy_item_id": lambda: self._copy_text(clip.id, "Copied item ID."),
            "copy_source_summary": lambda: self._copy_clean(clip.id, copy_clean.COPY_SOURCE_SUMMARY),
            "open": lambda: self._open_clip_path(clip.id),
            "reveal": lambda: self._reveal_clip_path(clip.id),
            "remove": lambda: self._remove_from_history(clip.id),
            "restore": lambda: self._restore(clip.id),
            "permanently_remove": lambda: self._permanently_remove(clip.id),
        }
        self._add_menu_items(menu, clip_menu_items(clip), dispatch, clip.id)
        self.vault.events.record(
            copy_clean.EVENT_ITEM_CONTEXT_ACTION_USED,
            clip.id,
            {"surface": "clip", "classification": clip.classification},
        )
        try:
            menu.tk_popup(x_root, y_root)  # native: dismisses on click-away/Esc
        finally:
            menu.grab_release()
            tooltip.after_menu_close()

    def _add_menu_items(self, menu, items, dispatch: dict, clip_id: str) -> None:
        import tkinter as tk

        for item in items:
            if item.separator_before:
                menu.add_separator()
            if item.children:
                sub = tk.Menu(menu, tearoff=0)
                self._add_menu_items(sub, item.children, dispatch, clip_id)
                menu.add_cascade(label=item.label, menu=sub, state="normal")
                continue
            if item.key.startswith("copy_clean:"):
                action = item.key.split(":", 1)[1]
                command = lambda a=action, cid=clip_id: self._copy_clean(cid, a)
            else:
                command = dispatch[item.key]
            menu.add_command(
                label=item.label,
                state=("normal" if item.enabled else "disabled"),
                command=command,
            )

    def _open_locked_menu(self, x_root: int, y_root: int) -> None:
        import tkinter as tk

        tooltip.before_menu_open()
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Unlock Vault", command=self._lock_screen.focus_unlock)
        menu.add_command(label="Quit", command=self._quit)
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()
            tooltip.after_menu_close()

    def _popup_menu(self, menu, x_root: int, y_root: int) -> None:
        tooltip.before_menu_open()
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()
            tooltip.after_menu_close()

    def _add_nav_command(self, menu, label: str, command) -> None:
        menu.add_command(label=label, command=command)

    def _open_home_clip_menu(self, clip, x_root: int, y_root: int) -> None:
        self._on_clip_select(clip)
        self._open_clip_menu(clip, x_root, y_root)

    def _open_home_card_menu(
        self,
        label: str,
        filter_key: str | None,
        x_root: int,
        y_root: int,
    ) -> None:
        import tkinter as tk

        from ..core import storage as S

        if self._locked():
            self._open_locked_menu(x_root, y_root)
            return
        menu = tk.Menu(self, tearoff=0)
        nav_items = [
            ("All Clips", lambda: self._navigate_filter(S.FILTER_ALL)),
            ("Favorites", lambda: self._navigate_filter(S.FILTER_FAVORITES)),
            ("Screenshots", lambda: self._navigate_filter(S.FILTER_SCREENSHOTS)),
            ("Links", lambda: self._navigate_filter(S.FILTER_LINKS)),
            ("Code", lambda: self._navigate_filter(S.FILTER_CODE)),
            ("Mobile Inbox", lambda: self._navigate_screen(NAV_MOBILE_INBOX)),
            ("Stamped Receipts", lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS)),
            ("Exports", lambda: self._navigate_screen(NAV_EXPORTS)),
        ]
        if filter_key:
            self._add_nav_command(menu, f"Open {label}", lambda f=filter_key: self._navigate_filter(f))
            menu.add_separator()
        elif label == "Receipts":
            self._add_nav_command(menu, "Open Stamped Receipts", lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS))
            menu.add_separator()
        for item_label, command in nav_items:
            self._add_nav_command(menu, item_label, command)
        self._popup_menu(menu, x_root, y_root)

    def _open_home_app_menu(self, x_root: int, y_root: int) -> None:
        import tkinter as tk

        from ..core import storage as S

        if self._locked():
            self._open_locked_menu(x_root, y_root)
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Quick Paste", command=self._schedule_quick_paste)
        menu.add_command(label="Save Current Clipboard", command=self._manual_save_clipboard)
        menu.add_separator()
        menu.add_command(label="Open All Clips", command=lambda: self._navigate_filter(S.FILTER_ALL))
        menu.add_command(label="Mobile Inbox", command=lambda: self._navigate_screen(NAV_MOBILE_INBOX))
        menu.add_command(label="Stamped Receipts", command=lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS))
        menu.add_command(label="Settings", command=self._open_settings)
        self._popup_menu(menu, x_root, y_root)

    def _open_home_status_menu(self, surface: str, x_root: int, y_root: int) -> None:
        import tkinter as tk

        from ..core import storage as S

        if self._locked():
            self._open_locked_menu(x_root, y_root)
            return
        summary = self.vault.dashboard_summary()
        menu = tk.Menu(self, tearoff=0)
        if surface == "vault_status":
            menu.add_command(label="Open Safe", command=lambda: self._navigate_filter(f"{S.SAFE_PREFIX}{summary.get('default_safe', 'default')}"))
            menu.add_command(label="Set as Default Safe", state="disabled")
            menu.add_command(label="Copy Safe Summary", command=self._copy_default_safe_summary)
            menu.add_command(label="Export Safe Proof Zip", state="disabled")
            menu.add_separator()
        menu.add_command(label="Open Receipts", command=lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS))
        menu.add_command(label="Open Mobile Inbox", command=lambda: self._navigate_screen(NAV_MOBILE_INBOX))
        menu.add_command(label="Mobile Access", command=lambda: self._navigate_screen(NAV_MOBILE_ACCESS))
        self._popup_menu(menu, x_root, y_root)

    def _copy_default_safe_summary(self) -> None:
        safe_id = self.vault.settings.default_safe_id or "default"
        safe = next((s for s in self.vault.list_safes() if s.get("id") == safe_id), None)
        if safe is None:
            return
        self._copy_safe_summary(safe)

    def _open_receipt_menu(self, row, x_root: int, y_root: int) -> None:
        import tkinter as tk

        tooltip.before_menu_open()
        if self._locked():
            try:
                self._open_locked_menu(x_root, y_root)
            finally:
                tooltip.after_menu_close()
            return
        clip_id = getattr(row, "clip_id", None)
        proof_hash = getattr(row, "proof_hash", "") or ""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Copy Receipt Summary",
            command=lambda: self._copy_receipt_summary(row),
        )
        menu.add_command(
            label="Copy Receipt Path",
            state="disabled",
        )
        menu.add_command(
            label="Copy Item ID",
            state=("normal" if clip_id else "disabled"),
            command=lambda: self._copy_text(str(clip_id), "Copied item ID."),
        )
        menu.add_command(
            label="Copy Hash",
            state=("normal" if proof_hash else "disabled"),
            command=lambda: self._copy_text(proof_hash, "Copied hash."),
        )
        menu.add_separator()
        menu.add_command(
            label="Open Receipt File / Folder",
            state="disabled",
        )
        menu.add_command(
            label="Export Proof Zip",
            state=("normal" if clip_id else "disabled"),
            command=lambda: self._export_clip_proof(str(clip_id)),
        )
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()
            tooltip.after_menu_close()

    def _open_safe_menu(self, safe: dict, x_root: int, y_root: int) -> None:
        import tkinter as tk

        tooltip.before_menu_open()
        if self._locked():
            try:
                self._open_locked_menu(x_root, y_root)
            finally:
                tooltip.after_menu_close()
            return
        safe_id = str(safe.get("id") or "")
        builtin = bool(safe.get("builtin"))
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Set as Default Safe",
            command=lambda: self._set_default_safe(safe_id),
        )
        menu.add_command(
            label="Copy Safe Summary",
            command=lambda: self._copy_safe_summary(safe),
        )
        menu.add_separator()
        menu.add_command(
            label="Rename Safe",
            state=("disabled" if builtin else "normal"),
            command=lambda: self._rename_safe(safe),
        )
        menu.add_command(
            label="Change Icon",
            state=("disabled" if builtin else "normal"),
            command=lambda: self._customize_safe_text(safe, "icon", "Safe icon"),
        )
        menu.add_command(
            label="Change Color",
            state=("disabled" if builtin else "normal"),
            command=lambda: self._customize_safe_text(safe, "accent", "Safe accent color"),
        )
        menu.add_command(label="Export Safe Proof Zip", state="disabled")
        menu.add_command(
            label="Collapse/Expand Safes",
            command=lambda: self._filters._toggle_section("SAFES"),  # noqa: SLF001
        )
        menu.add_command(
            label="Delete Safe",
            state="disabled",
        )
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()
            tooltip.after_menu_close()

    def _set_default_safe(self, safe_id: str) -> None:
        if not safe_id:
            return
        self.vault.settings.default_safe_id = safe_id
        self.vault.settings.save()
        self.refresh()
        self._show_toast("Default Safe updated.")

    def _copy_safe_summary(self, safe: dict) -> None:
        text = (
            f"Safe: {safe.get('name', 'Safe')}\n"
            f"Safe ID: {safe.get('id', 'unknown')}\n"
            f"Icon: {safe.get('icon', 'unavailable')}\n"
            f"Accent: {safe.get('accent', 'unavailable')}\n"
            f"Style: {safe.get('visual_style', 'default')}\n"
            f"Items: {safe.get('count', 0)}\n"
            "Safes organize items. They are not encryption unless encryption is added later."
        )
        self._copy_text(text, "Copied Safe summary.")

    def _rename_safe(self, safe: dict) -> None:
        from tkinter import simpledialog

        safe_id = str(safe.get("id") or "")
        name = simpledialog.askstring(
            "Rename Safe",
            "Safe name:",
            initialvalue=str(safe.get("name") or ""),
            parent=self,
        )
        if name:
            updated = self.vault.safes.rename(safe_id, name)
            if updated:
                self.vault.settings.save()
                self.refresh()

    def _customize_safe_text(self, safe: dict, field: str, label: str) -> None:
        from tkinter import simpledialog

        safe_id = str(safe.get("id") or "")
        value = simpledialog.askstring(
            label,
            f"{label}:",
            initialvalue=str(safe.get(field) or ""),
            parent=self,
        )
        if value:
            updated = self.vault.safes.update_customization(safe_id, **{field: value})
            if updated:
                self.vault.settings.save()
                self.refresh()

    def _copy_text(self, text: str, notice: str = "Copied.") -> None:
        if not self._guard_unlocked():
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._monitor.note_local_copy(text)
        self._show_toast(notice)

    def _open_clip_path(self, clip_id: str) -> None:
        from ..core import pathutil
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if pathutil.is_local_file(clip.content):
            self._open_editable_copy(clip_id)
        else:
            pathutil.open_path(clip.content)

    def _open_asset_folder(self, clip_id: str) -> None:
        from ..core import image_assets, pathutil
        rec = self.vault.storage.get_asset_record(clip_id)
        if rec is None:
            return
        path = image_assets.assets_dir() / rec.storage_name
        pathutil.reveal_in_explorer(str(path))

    def _drag_out_clip(self, clip_id: str) -> None:
        from ..core import pathutil

        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if self._locked():
            self.vault.events.record(models.EVENT_ASSET_DRAG_BLOCKED_LOCKED, clip_id, {})
            self._guard_unlocked()
            return
        prepared = drag_export.prepare_drag_export(clip, self.vault.storage)
        if prepared is None:
            details = {
                "classification": clip.classification,
                "content_type": clip.content_type,
                "reason": (
                    "missing_file"
                    if clip.classification == models.CLASS_PATH
                    else "unsupported_item"
                ),
            }
            event_type = (
                models.EVENT_ASSET_DRAG_MISSING_FILE
                if clip.classification == models.CLASS_PATH
                else models.EVENT_ASSET_DRAG_FALLBACK_USED
            )
            self.vault.events.record(event_type, clip_id, details)
            if clip.classification == models.CLASS_PATH:
                if clip.content and pathutil.parent_exists(clip.content):
                    self._show_toast("File not found. You can still Copy Path or Open Folder.")
                else:
                    self._show_toast("File not found. You can still Copy Path.")
            else:
                self._show_toast("Drag file export is not available for this item.")
            return
        self.vault.events.record(
            models.EVENT_ASSET_DRAG_STARTED,
            clip_id,
            {"kind": prepared.drag_kind, "source": prepared.source},
        )
        self.vault.events.record(
            models.EVENT_ASSET_DRAG_EXPORT_PREPARED,
            clip_id,
            {
                "kind": prepared.drag_kind,
                "file_name": prepared.display_name,
                "source": prepared.source,
                "reused_existing": prepared.reused_existing,
            },
        )
        drag_export.start_file_drag(prepared.file_path)
        self._show_toast(
            "Drag PNG ready." if prepared.drag_kind == "image" else "Drag file out ready."
        )

    def _create_editable_copy(self, clip_id: str) -> None:
        self.vault.create_editable_copy(clip_id)
        self._refresh_editable_preview(clip_id)

    def _open_editable_copy(self, clip_id: str) -> None:
        self.vault.open_editable_copy(clip_id)
        self._refresh_editable_preview(clip_id)

    def _save_editable_revision(self, clip_id: str) -> None:
        self.vault.save_editable_revision(clip_id)
        self._refresh_editable_preview(clip_id)

    def _reveal_editable_copy_folder(self, clip_id: str) -> None:
        from ..core import pathutil
        rec = self.vault.latest_editable_copy(clip_id)
        if rec is not None:
            target = rec.bundle_dir or rec.copy_path
            pathutil.reveal_in_explorer(target)

    def _preview_html_copy(self, clip_id: str) -> None:
        self.vault.preview_html_copy(clip_id)
        self._refresh_editable_preview(clip_id)

    def _edit_html_source(self, clip_id: str) -> None:
        self.vault.edit_html_source(clip_id)
        self._refresh_editable_preview(clip_id)

    def _export_html_bundle(self, clip_id: str) -> None:
        from tkinter import filedialog

        from ..core.exports import export_zip_basename

        rec = self.vault.latest_editable_copy(clip_id)
        if rec is None:
            self.vault.create_editable_copy(clip_id)
        dest = filedialog.asksaveasfilename(
            parent=self,
            title="Export HTML Bundle",
            defaultextension=".zip",
            initialfile=export_zip_basename(),
            filetypes=[("Zip archive", "*.zip")],
        )
        if dest:
            self.vault.export_proof_zip([clip_id], dest, mode="html_bundle")
            self.refresh()

    def _export_clip_proof(self, clip_id: str) -> None:
        self._export_clip_proof_mode(clip_id, "auto")

    def _export_clip_proof_mode(self, clip_id: str, mode: str) -> None:
        from tkinter import filedialog

        from ..core.exports import export_zip_basename

        dest = filedialog.asksaveasfilename(
            parent=self,
            title="Export proof zip",
            defaultextension=".zip",
            initialfile=export_zip_basename(),
            filetypes=[("Zip archive", "*.zip")],
        )
        if dest:
            self.vault.export_proof_zip([clip_id], dest, mode=mode)
            self.refresh()

    def _reveal_export_path(self, path: str) -> None:
        from ..core import pathutil
        pathutil.reveal_in_explorer(path)

    def _refresh_editable_preview(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip is not None:
            self._preview.show(clip)

    def _reveal_clip_path(self, clip_id: str) -> None:
        from ..core import pathutil
        clip = self.vault.storage.get_clip(clip_id)
        if clip:
            pathutil.reveal_in_explorer(clip.content)

    def _move_to_collection(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        existing = [c["name"] for c in self.vault.list_collections()]

        def save(name):
            self.vault.set_collection(clip_id, name)
            self.refresh()
            self._preview.show(self.vault.storage.get_clip(clip_id))

        MoveToCollectionDialog(self, clip.collection, existing, on_save=save)

    def _move_to_safe(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return

        def pick(safe_id: str, safe_name: str) -> None:
            updated = self.vault.move_to_safe(clip_id, safe_id)
            if updated:
                self.refresh()
                self._preview.show(updated)
                self._show_toast(f"Moved to {safe_name}.")

        SafePickerDialog(
            self, self.vault.settings,
            title="Move to Safe",
            on_pick=pick,
            on_create=lambda name: self.vault.create_safe(name),
        )

    def _restore(self, clip_id: str) -> None:
        self.vault.restore(clip_id)
        self.refresh()
        self._preview.show(self.vault.storage.get_clip(clip_id))

    def _permanently_remove(self, clip_id: str) -> None:
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Permanently Remove",
            "Permanently remove this clip from Cache Vault? This cannot be "
            "undone. It does not delete any files from your computer.",
            parent=self,
        )
        if not ok:
            return
        self.vault.permanently_remove(clip_id)
        self.refresh()
        self._preview.show(None)

    # --- export ------------------------------------------------------------
    def _save_asset_as(self, clip_id: str) -> None:
        from tkinter import filedialog

        loaded = self.vault.storage.load_clip_asset_bytes(clip_id)
        if not loaded:
            return
        png_bytes, _mime = loaded
        clip = self.vault.storage.get_clip(clip_id)
        # Block when locked to avoid leaking metadata
        if not self._guard_unlocked():
            return
        from ..core import image_assets as _ia

        initial = _ia.make_smart_filename(clip)[:80]
        path = filedialog.asksaveasfilename(
            parent=self, title="Save Screenshot As",
            defaultextension=".png",
            initialfile=initial,
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return
        p = Path(path)
        p = _ia.next_available_path(p)
        p.write_bytes(png_bytes)
        self.vault.events.record(models.EVENT_EXPORTED, clip_id, {"target": "asset_png"})

    def _export_clip(self, clip_id: str) -> None:
        """Export / Save As for a single clip (txt / md / html / json)."""
        from tkinter import filedialog

        from ..core import export, models
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if clip.content_type == models.CONTENT_IMAGE:
            loaded = self.vault.storage.load_clip_asset_bytes(clip_id)
            if loaded:
                png_bytes, _mime = loaded
                from ..core import image_assets as _ia
                initial = _ia.make_smart_filename(clip)[:80]
                path = filedialog.asksaveasfilename(
                    parent=self, title="Export / Save As",
                    defaultextension=".png",
                    initialfile=initial,
                    filetypes=[("PNG image", "*.png")],
                )
                if path:
                    p = Path(path)
                    p = _ia.next_available_path(p)
                    p.write_bytes(png_bytes)
                    self.vault.events.record(
                        models.EVENT_EXPORTED, clip_id, {"target": "single_png"})
                return
        path = filedialog.asksaveasfilename(
            parent=self, title="Export / Save As",
            defaultextension=".txt",
            initialfile=f"{(clip.preview or 'clip')[:40].strip()}.txt",
            filetypes=[("Plain text", "*.txt"), ("Markdown", "*.md"),
                       ("HTML", "*.html"), ("JSON (Proof Manifest)", "*.json")],
        )
        if not path:
            return
        export.export_single(clip, path)
        self.vault.events.record(models.EVENT_EXPORTED, clip_id, {"target": "single"})

    def _export_view(self) -> None:
        """Export the clips currently shown (active filter / collection)."""
        clips = self._current_clips()
        if not clips:
            return
        name = self._collection_name_for(self._filters.active)
        ExportViewDialog(self, len(clips),
                         on_export=lambda kind, incl: self._do_export_view(
                             clips, name, kind, incl))

    def _do_export_view(self, clips, collection_name, kind, include_files) -> None:
        from tkinter import filedialog

        from ..core import export, models
        from ..core.exports import export_zip_basename

        if kind == "zip":
            dest = filedialog.asksaveasfilename(
                parent=self, title=f"{brand.TERM_EXPORT} — zip",
                defaultextension=".zip",
                initialfile=export_zip_basename(),
                filetypes=[("Zip archive", "*.zip")])
            if not dest:
                return
            self.vault.export_proof_zip(
                [c.id for c in clips],
                dest,
                include_original_files=include_files,
                collection_name=collection_name,
            )
        else:
            dest = filedialog.askdirectory(
                parent=self, title=f"{brand.TERM_EXPORT} — folder")
            if not dest:
                return

            def load_asset_bytes(clip_id: str) -> bytes | None:
                loaded = self.vault.storage.load_clip_asset_bytes(clip_id)
                return loaded[0] if loaded else None

            export.export_collection(clips, dest, include_files=include_files,
                                     collection_name=collection_name,
                                     load_asset_bytes=load_asset_bytes)
            self.vault.events.record(models.EVENT_EXPORTED, None,
                                     {"target": kind, "count": len(clips),
                                      "include_files": include_files})
        self.refresh()

    def _build_query(self):
        raw = self._search_var.get()
        active = self._filters.active
        if raw.strip():
            q = search.parse(raw, FILTER_SEARCH_ALL)
        else:
            q = search.parse(raw, active)
        q.sort = self._sort_key
        q.date_added_preset = self._date_added_preset
        q.date_used_preset = self._date_used_preset
        if self._type_filter:
            q.type_filter = self._type_filter
        if getattr(self, "_sensitive_only", False):
            q.sensitive = True
        return q

    def _current_clips(self):
        return self.vault.list_clips(self._build_query())

    @staticmethod
    def _collection_name_for(active: str):
        from ..core.storage import COLLECTION_PREFIX
        if active.startswith(COLLECTION_PREFIX):
            return active[len(COLLECTION_PREFIX):]
        return None

    # --- capture state -----------------------------------------------------
    def _set_paused(self, paused: bool) -> None:
        self.vault.settings.capture_paused = paused
        self.vault.settings.save()
        self._monitor.pause() if paused else self._monitor.resume()
        self.refresh()

    def _clear_sensitive(self) -> None:
        self.vault.clear_sensitive()
        self.refresh()
        self._preview.show(None)

    # --- dialogs -----------------------------------------------------------
    def _open_settings(self) -> None:
        SettingsDialog(
            self, self.vault.settings, on_save=self._apply_settings,
            mobile={
                "pair": self._open_pair_android,
                "devices": self._open_paired_devices,
                "receipts": self._open_mobile_receipts,
            },
            help={"show_guide": self._open_first_use_guide_from_settings},
        )

    def _maybe_show_first_use_guide(self) -> None:
        if self._shutting_down or self.vault.settings.first_use_guide_dismissed:
            return
        try:
            self._open_first_use_guide(from_settings=False)
        except Exception:  # noqa: BLE001 — guide must not block startup
            pass

    def _open_first_use_guide_from_settings(self) -> None:
        self._open_first_use_guide(from_settings=True)

    def _open_first_use_guide(self, *, from_settings: bool) -> None:
        from .first_use_guide import FirstUseGuideDialog, GuideAction

        def on_action(action: GuideAction) -> None:
            if action == "dismiss" or not from_settings:
                self.vault.settings.first_use_guide_dismissed = True
                self.vault.settings.save()
            if action == "receipts":
                self._navigate_screen(NAV_STAMPED_RECEIPTS)

        FirstUseGuideDialog(
            self,
            from_settings=from_settings,
            on_action=on_action,
        )

    def _open_pair_android(self, pending_mobile: bool | None = None) -> None:
        from tkinter import messagebox

        from .pairing_help import MOBILE_ACCESS_OFF_HINT, MOBILE_ACCESS_SAVE_HINT

        saved_on = self.vault.settings.mobile_access_enabled
        want_on = pending_mobile if pending_mobile is not None else saved_on
        if not want_on:
            messagebox.showinfo(
                "Mobile Access",
                MOBILE_ACCESS_OFF_HINT,
                parent=self,
            )
            return
        if pending_mobile is not None and not saved_on:
            messagebox.showinfo(
                "Mobile Access",
                MOBILE_ACCESS_SAVE_HINT,
                parent=self,
            )
            return
        if not self._mobile_bridge.is_running:
            self._mobile_bridge.sync(self.vault.settings)
        if not self._mobile_bridge.is_running:
            messagebox.showwarning(
                "Mobile Access",
                "Mobile Access bridge is not running.\n"
                "Save settings, then try pairing again.",
                parent=self,
            )
            return
        PairAndroidDialog(
            self,
            on_pair=self._complete_mobile_pair,
            on_revoke_all_and_pair=self._revoke_all_and_pair,
            port=self.vault.settings.mobile_access_port,
            bridge_running=self._mobile_bridge.is_running,
            get_doctor_report=self._mobile_doctor_report,
            has_active_devices=bool(self._mobile_bridge.active_devices()),
        )

    def _mobile_doctor_report(self) -> dict:
        from ..core.mobile.connection_doctor import connection_doctor_report
        from ..core.mobile.models import DEFAULT_BIND_HOST
        s = self.vault.settings
        return connection_doctor_report(
            mobile_access_enabled=s.mobile_access_enabled,
            bridge_listening=self._mobile_bridge.is_running,
            port=int(s.mobile_access_port or 8742),
            bind_host=(s.mobile_access_bind_host or DEFAULT_BIND_HOST),
            receipts=self._mobile_bridge.receipts.recent(20),
        )

    def _revoke_all_and_pair(self, device_id: str, name: str) -> tuple[str, str]:
        self._mobile_bridge.revoke_all_active()
        return self._complete_mobile_pair(device_id, name)

    def _complete_mobile_pair(self, device_id: str, name: str) -> tuple[str, str]:
        _, token = self._mobile_bridge.pair_device(device_id, name)
        return device_id, token

    def _open_paired_devices(self) -> None:
        devices = [d.to_dict() for d in self._mobile_bridge.active_devices()]
        PairedDevicesDialog(self, devices, on_revoke=self._revoke_mobile_device)

    def _revoke_mobile_device(self, device_id: str) -> None:
        self._mobile_bridge.revoke_device(device_id)

    def _open_mobile_receipts(self) -> None:
        MobileAccessReceiptsDialog(
            self, self._mobile_bridge.receipts.recent())

    def _apply_settings(self, settings) -> None:
        settings.save()
        vault_lock.record_lock_event(
            self.vault.events,
            vault_lock.EVENT_VAULT_LOCK_SETTINGS_CHANGED,
            mode=settings.vault_lock_mode,
            reason="settings_saved",
        )
        self._lock_screen.set_mode(settings.vault_lock_mode)
        if not vault_lock.lock_config(settings).enabled and self._locked():
            self._vault_locked = False
            self._lock_screen.grid_remove()
        self._schedule_auto_lock()
        refresh_windows_scroll_cache()
        self._monitor.pause() if settings.capture_paused else self._monitor.resume()
        self._rebind_hotkey(settings.quick_paste_hotkey)
        self._rebind_capture_hotkeys()
        self._rebind_macro_hotkeys()
        self._sync_text_shortcut_listener()
        self.vault.safes = SafeRegistry(settings)
        from ..core import startup
        startup.sync(settings.start_with_windows)
        self.refresh()
        if not self._mobile_bridge.needs_sync(settings):
            return

        def _sync_bridge() -> None:
            try:
                self._mobile_bridge.sync(settings)
            except Exception as exc:  # noqa: BLE001
                write_crash("mobile bridge sync", exc)
            finally:
                if self._alive():
                    self.after(0, self.refresh)

        threading.Thread(
            target=_sync_bridge, name="mobile-bridge-sync", daemon=True,
        ).start()

    def _rebind_hotkey(self, spec: str) -> None:
        """Re-register the global hotkey if the user changed it."""
        if self._hotkey and self._hotkey._spec == spec:
            return
        if self._hotkey:
            self._hotkey.stop()
        self._hotkey = HotkeyListener(
            spec, on_activate=self._schedule_quick_paste)
        self._hotkey.start()

    def _open_events(self) -> None:
        EventLogDialog(
            self,
            self.vault.events.recent(),
            get_clip=self.vault.storage.get_clip,
            on_refresh=self.vault.events.recent,
        )

    def _open_about(self) -> None:
        AboutDialog(self)

    # --- quick paste (global hotkey) ---------------------------------------
    def _schedule_quick_paste(self) -> None:
        """Capture foreground hwnd on the hotkey thread before UI steals focus."""
        target = foreground_window()
        self._call_on_main(lambda t=target: self._open_quick_paste(paste_target=t))

    def _open_quick_paste(self, paste_target=None) -> None:
        if not self._alive():
            return
        if self._locked():
            self.vault.events.record("quick_paste_blocked_locked", None, {})
            self._guard_unlocked()
            return
        try:
            # If a popup is already up (hotkey pressed twice), just refocus it.
            existing = getattr(self, "_quick_paste", None)
            if existing is not None:
                try:
                    if existing.winfo_exists():
                        existing.focus_popup()
                        return
                except Exception:  # noqa: BLE001
                    self._quick_paste = None
            if paste_target is None:
                paste_target = foreground_window()
            if hwnd_belongs_to_widget(paste_target, self):
                paste_target = None
            self._paste_target = paste_target
            self._paste_clipboard_snapshot = None
            self.vault.run_expiry_sweep()
            clips = sorted(self.vault.list_clips(), key=lambda c: c.created_at,
                           reverse=True)[: self.vault.settings.quick_paste_count]
            self.vault.events.record("quick_paste_opened", None, {"count": len(clips)})
            self._quick_paste = QuickPaste(self, clips, on_choose=self._do_paste)
        except Exception as exc:  # noqa: BLE001
            write_crash("quick paste", exc)
            raise

    def _do_paste(self, clip, action: str = "primary") -> None:
        if clip is None:
            return
        if self._locked():
            self.vault.events.record("quick_paste_blocked_locked", None, {})
            self._guard_unlocked()
            return
        if clip.content_type == models.CONTENT_IMAGE:
            self._quick_paste_image_action(clip, action)
            return
        if clip.classification == models.CLASS_PATH:
            self._quick_paste_copy_path(clip)
            return
        settings = self.vault.settings
        prior_clipboard = None
        if settings.restore_clipboard_after_paste:
            prior_clipboard = snapshot_clipboard_text()

        pasted_text = False
        if action == ACTION_COPY_ONLY:
            content = self._quick_paste_text_for_action(clip, ACTION_COPY_ONLY)
            if content is None:
                Toast(self, "Nothing available to copy.")
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            self._monitor.note_local_copy(content)
            self.vault.events.record(
                "quick_paste_copy_only",
                clip.id,
                self._quick_paste_receipt_details(clip, "copy_only"),
            )
            Toast(self, "Copied to clipboard")
            return
        else:
            content = self._quick_paste_text_for_action(clip, action)
            if content is None:
                Toast(self, "Nothing available to paste.")
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            self._monitor.note_local_copy(content)
            pasted_text = True
            item_type = clip.content_type or clip.classification or "text"

        target = self._paste_target
        skip_delivery = (
            not settings.auto_paste
            or not target
            or hwnd_belongs_to_widget(target, self)
        )
        delivery_ok = False
        reason = ""
        target_title = ""
        if skip_delivery:
            if settings.auto_paste and not target:
                reason = "no_target_window"
            elif settings.auto_paste and hwnd_belongs_to_widget(target, self):
                reason = "target_is_cache_vault"
            delivery_ok = not settings.auto_paste
        else:

            def _deliver() -> None:
                nonlocal delivery_ok, reason, target_title
                result = deliver_ctrl_v(target)
                delivery_ok = result.ok
                reason = result.reason
                target_title = result.target_title
                if settings.restore_clipboard_after_paste and pasted_text:
                    restore_clipboard_text(prior_clipboard)
                self._finish_paste(
                    clip, delivery_ok, item_type, target_title, reason,
                    clipboard_restored=settings.restore_clipboard_after_paste and delivery_ok,
                )

            self.after(80, _deliver)
            return

        if settings.restore_clipboard_after_paste and pasted_text and delivery_ok:
            restore_clipboard_text(prior_clipboard)
        self._finish_paste(
            clip, delivery_ok, item_type, target_title, reason,
            clipboard_restored=settings.restore_clipboard_after_paste and delivery_ok,
        )

    def _quick_paste_text_for_action(self, clip, action: str) -> str | None:
        if clip.classification == models.CLASS_LINK:
            if action == ACTION_ALTERNATE:
                formatted = copy_clean.format_clip(clip, copy_clean.COPY_MARKDOWN)
                return formatted or clip.content
            if action == ACTION_COPY_ONLY:
                return copy_clean.format_clip(clip, copy_clean.COPY_LINK_ONLY) or clip.content
            return copy_clean.format_clip(clip, copy_clean.COPY_LINK_ONLY) or clip.content
        if clip.classification == models.CLASS_PATH:
            return clip.content
        if action == ACTION_ALTERNATE:
            return copy_clean.format_clip(clip, copy_clean.COPY_PLAIN_TEXT) or clip.content
        return clip.content

    def _quick_paste_image_action(self, clip, action: str) -> None:
        if action == ACTION_OPEN:
            self._open_image_asset(clip.id)
            return
        if action == ACTION_SAVE_AS:
            self.vault.events.record(
                "quick_paste_opened_asset",
                clip.id,
                self._quick_paste_receipt_details(clip, "save_as_png"),
            )
            self._save_asset_as(clip.id)
            return
        loaded = self.vault.storage.load_clip_asset_bytes(clip.id)
        png = loaded[0] if loaded else None
        if not png:
            self.vault.events.record(
                "quick_paste_image_copied",
                clip.id,
                self._quick_paste_receipt_details(clip, "image_copy_failed", reason="no_asset"),
            )
            Toast(self, "Image not available.")
            return
        from ..core import image_assets
        if not image_assets.write_clipboard_png(png):
            self.vault.events.record(
                "quick_paste_image_copied",
                clip.id,
                self._quick_paste_receipt_details(clip, "image_copy_failed", reason="clipboard_image_failed"),
            )
            Toast(self, "Could not copy image to clipboard.")
            return
        # Confirm the clipboard contains image data and provide a helpful toast.
        ok = image_assets.clipboard_has_image()
        self._monitor.note_local_copy_image(png)
        self.vault.storage.touch_clip(clip.id)
        self.vault.events.record(
            "quick_paste_image_copied",
            clip.id,
            self._quick_paste_receipt_details(clip, "copy_image"),
        )
        if ok:
            Toast(self, "Image copied to clipboard — paste into an image-capable app like Paint")
        else:
            Toast(self, "Image copied to clipboard (target apps may not accept images)")

    def _open_image_asset(self, clip_id: str) -> None:
        from ..core import image_assets, pathutil
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None or clip.content_type != models.CONTENT_IMAGE:
            return
        rec = self.vault.storage.get_asset_record(clip_id)
        if rec is None:
            Toast(self, "Image not available.")
            return
        path = image_assets.assets_dir() / rec.storage_name
        opened = pathutil.open_file(str(path))
        self.vault.events.record(
            "quick_paste_opened_asset",
            clip.id,
            self._quick_paste_receipt_details(
                clip,
                "open_image",
                reason="" if opened else "open_failed",
            ),
        )
        Toast(self, "Opened image." if opened else "Could not open image.")

    def _quick_paste_copy_path(self, clip) -> None:
        path_text = clip.content or ""
        if not path_text:
            Toast(self, "No path available to copy.")
            return
        self.clipboard_clear()
        self.clipboard_append(path_text)
        self._monitor.note_local_copy(path_text)
        self.vault.events.record(
            "quick_paste_copy_only",
            clip.id,
            self._quick_paste_receipt_details(clip, "copy_path"),
        )
        Toast(self, "Copied path to clipboard.")

    def _quick_paste_receipt_details(
        self,
        clip,
        action_type: str,
        *,
        target_title: str = "",
        reason: str = "",
    ) -> dict:
        return {
            "item_type": clip.content_type or clip.classification or "unknown",
            "safe_id": clip.safe_id or "",
            "safe_name": clip.safe_name or "",
            "target_title": target_title[:120] if target_title else "",
            "action_type": action_type,
            "reason": reason[:80] if reason else "",
        }

    def _finish_paste(
        self, clip, delivery_ok: bool, item_type: str, target_title: str, reason: str,
        *, clipboard_restored: bool,
    ) -> None:
        self.vault.log_item_pasted(
            clip.id,
            success=delivery_ok,
            item_type=item_type,
            target_title=target_title,
            clipboard_restored=clipboard_restored,
            reason=reason,
        )
        action_type = "paste_attempted" if self.vault.settings.auto_paste else "copy_only"
        if delivery_ok and self.vault.settings.auto_paste:
            event_type = (
                "quick_paste_link_pasted"
                if clip.classification == models.CLASS_LINK
                else "quick_paste_text_pasted"
            )
        elif self.vault.settings.auto_paste:
            event_type = "quick_paste_paste_attempted"
        else:
            event_type = "quick_paste_copy_only"
        self.vault.events.record(
            event_type,
            clip.id,
            self._quick_paste_receipt_details(
                clip,
                action_type,
                target_title=target_title,
                reason=reason,
            ),
        )
        if clip.is_sensitive:
            Toast(self, "Paste attempted for sensitive clip." if delivery_ok else "Paste failed.")
        elif not delivery_ok and self.vault.settings.auto_paste and reason:
            Toast(self, "Target app unavailable - copied instead")
        elif delivery_ok and self.vault.settings.auto_paste:
            snippet = clip.preview if len(clip.preview) <= 60 else clip.preview[:59] + "…"
            Toast(self, f"Paste attempted   {snippet}")
        else:
            snippet = clip.preview if len(clip.preview) <= 60 else clip.preview[:59] + "…"
            Toast(self, f"Copied to clipboard   {snippet}")

    # --- maintenance / lifecycle -------------------------------------------
    def _expiry_tick(self) -> None:
        if not self._alive():
            return
        try:
            n = self.vault.run_expiry_sweep()
            if n:
                self.refresh()
        except Exception as exc:  # noqa: BLE001
            write_crash("expiry tick", exc)
        finally:
            if self._alive():
                self._expiry_job = self._safe_after(EXPIRY_SWEEP_MS, self._expiry_tick)

    # --- Vault Macros -------------------------------------------------------
    def _macro_record_receipt(self, action: str, payload: dict) -> None:
        from ..core import models
        from ..core.macro_receipts import record_macro_receipt
        event_map = {
            "vault_macros_setup_completed": models.EVENT_VAULT_MACROS_SETUP,
            "macro_safe_created": models.EVENT_MACRO_SAFE_CREATED,
            "macro_template_created": models.EVENT_MACRO_TEMPLATE_CREATED,
            "macro_smart_type_assigned": models.EVENT_MACRO_SMART_TYPE_ASSIGNED,
            "macro_moved_by_user": models.EVENT_MACRO_MOVED_BY_USER,
            "macro_conflict_detected": models.EVENT_MACRO_CONFLICT_DETECTED,
        }
        record_macro_receipt(
            self.vault.events,
            action=action,
            event_type=event_map.get(action, action),
            success=bool(payload.get("success", True)),
            macro_id=payload.get("macro_id"),
            safe_id=payload.get("safe_id"),
            safe_name=payload.get("safe_name"),
            smart_type=payload.get("smart_type"),
            template_id=payload.get("template_id"),
        )

    def _open_macro_setup(self) -> None:
        from .macro_dialogs import VaultMacrosSetupDialog

        def _done() -> None:
            self.refresh()
            self._sync_macro_triggers()

        VaultMacrosSetupDialog(
            self,
            self.vault.settings,
            on_complete=_done,
            record_receipt=self._macro_record_receipt,
        )

    def _macro_list_rows(self, filter_key: str, query: str) -> list[dict]:
        from ..core.vault_macros import (
            MacroSafeRegistry,
            SMART_TYPE_LABELS,
            apply_macro_filter,
            inspector_warnings,
            search_macros,
        )
        settings = self.vault.settings
        registry = MacroSafeRegistry(settings)
        macros = self._macro_store.load_all()
        ctx = {"registry": registry, "all_macros": macros, "settings": settings}
        filtered = apply_macro_filter(macros, filter_key, registry=registry, settings=settings)
        if query:
            filtered = search_macros(
                filtered, query, registry=registry,
                search_content=settings.macro_search_content,
            )
        rows: list[dict] = []
        for m in filtered:
            safe = registry.resolve(m.safe_id)
            warns = inspector_warnings(m, **ctx)
            rows.append({
                "macro": m,
                "warnings": warns,
                "subtitle": (
                    f"{safe.name if safe else 'Missing Safe'} · "
                    f"{m.trigger_type} · {m.output_mode} · "
                    f"runs {m.run_count} · "
                    f"{'enabled' if m.enabled else 'disabled'}"
                    + (" · last run failed" if m.last_run_failed else "")
                ),
                "inspector": self._macro_inspector_text(m, warns, safe),
            })
        return rows

    def _macro_inspector_text(self, macro, warnings, safe) -> str:
        from ..core.vault_macros import SMART_TYPE_LABELS
        lines = [
            f"Name: {macro.name}",
            f"Safe: {safe.name if safe else '—'}",
            f"Smart type: {SMART_TYPE_LABELS.get(macro.smart_type, macro.smart_type)}",
            f"Trigger: {macro.trigger_type} {macro.trigger_value or '(none)'}",
            f"Output: {macro.output_mode}",
            f"Enabled: {'yes' if macro.enabled else 'no'} · Favorite: {'yes' if macro.favorite else 'no'}",
            f"Runs: {macro.run_count} · Receipts: {macro.receipt_count}",
            f"Last used: {macro.last_used_at or 'never'}",
        ]
        if warnings:
            lines.append("Warnings: " + "; ".join(warnings))
        if macro.last_run_failed:
            lines.append("Last run: FAILED")
        return "\n".join(lines)

    def _macro_edit(self, macro_id: str) -> None:
        from .macro_dialogs import MacroEditDialog
        from ..core import models
        from ..core.vault_macros import MacroSafeRegistry
        macro = self._macro_store.get(macro_id)
        if macro is None:
            return
        old_type = macro.smart_type

        def on_save(updated) -> None:
            self._macro_store.upsert(updated)
            if updated.smart_type != old_type:
                self._macro_record_receipt("macro_smart_type_assigned", {
                    "macro_id": updated.id,
                    "smart_type": updated.smart_type,
                    "success": True,
                })
            self._sync_macro_triggers()
            self.refresh()

        MacroEditDialog(
            self, macro=macro, registry=MacroSafeRegistry(self.vault.settings), on_save=on_save,
        )

    def _macro_new_template(self) -> None:
        from .macro_dialogs import MacroEditDialog, MacroTemplatePicker
        from ..core.vault_macros import MacroSafeRegistry, create_from_template

        def on_pick(template_id: str) -> None:
            registry = MacroSafeRegistry(self.vault.settings)
            macro = create_from_template(template_id, registry=registry)
            self._macro_store.upsert(macro)
            self._macro_record_receipt("macro_template_created", {
                "macro_id": macro.id,
                "template_id": template_id,
                "safe_id": macro.safe_id,
                "smart_type": macro.smart_type,
                "success": True,
            })

            def on_save(updated) -> None:
                self._macro_store.upsert(updated)
                self._sync_macro_triggers()
                self.refresh()

            MacroEditDialog(self, macro=macro, registry=registry, on_save=on_save)

        MacroTemplatePicker(self, on_pick=on_pick)

    # --- vault macro execution ---------------------------------------------
    def _confirm_sensitive_macro(self, label: str) -> bool:
        result = [False]
        done = threading.Event()

        def _ask() -> None:
            from tkinter import messagebox
            try:
                result[0] = messagebox.askyesno(
                    "Sensitive macro",
                    f"'{label}' looks sensitive.\nRun anyway?",
                    parent=self,
                )
            except Exception:  # noqa: BLE001
                result[0] = False
            done.set()

        self._call_on_main(_ask)
        done.wait(timeout=30)
        return result[0]

    def _sync_text_shortcut_listener(self) -> None:
        s = self.vault.settings
        enabled = bool(
            s.vault_macros_enabled
            and s.vault_macros_setup_completed
            and s.macro_text_shortcuts_enabled
        )
        self._text_shortcut_listener.update(
            self._macro_store.load_all(), enabled=enabled,
        )

    def _bind_macro_hotkeys(self) -> None:
        s = self.vault.settings
        reserved = self._system_reserved_hotkeys(s)
        self._macro_hotkeys.set_binding(
            HK_MACRO_MENU,
            s.macro_menu_hotkey or "ctrl+shift+m",
            self._schedule_macro_menu,
        )
        hotkey_map: dict[str, list] = {}
        if s.vault_macros_enabled and s.macro_hotkeys_enabled and s.vault_macros_setup_completed:
            for m in self._macro_store.load_all():
                if not m.enabled or m.trigger_type != self._TRIGGER_HOTKEY:
                    continue
                raw = (m.trigger_value or "").strip()
                if not raw:
                    continue
                spec = normalize_hotkey(raw).lower()
                if spec in {normalize_hotkey(r).lower() for r in reserved}:
                    continue
                hotkey_map.setdefault(spec, []).append(m)
        self._macro_hotkey_bindings.clear()
        hid = HK_MACRO_ID_BASE
        for _spec, macros in hotkey_map.items():
            raw = macros[0].trigger_value.strip()

            def _activate(ms=macros, hk=raw) -> None:
                self._schedule_macro_hotkey(ms, hk)

            self._macro_hotkeys.set_binding(hid, raw, _activate)
            self._macro_hotkey_bindings[hid] = (raw, macros)
            hid += 1

    def _rebind_macro_hotkeys(self) -> None:
        if getattr(self, "_macro_hotkeys", None):
            self._macro_hotkeys.stop()
        self._macro_hotkeys = MultiHotkeyListener()
        self._bind_macro_hotkeys()
        self._macro_hotkeys.start()

    def _sync_macro_triggers(self) -> None:
        self._rebind_macro_hotkeys()
        self._sync_text_shortcut_listener()

    def _schedule_macro_menu(self) -> None:
        target = foreground_window()
        self._call_on_main(lambda t=target: self._open_macro_picker(paste_target=t))

    def _schedule_macro_hotkey(self, macros: list, hotkey_spec: str) -> None:
        target = foreground_window()
        self._call_on_main(
            lambda t=target, ms=macros, hk=hotkey_spec: self._handle_macro_hotkey(ms, hk, t),
        )

    def _handle_macro_hotkey(self, macros: list, hotkey_spec: str, target) -> None:
        ok, _reason = self._macro_executor.execution_allowed()
        if not ok or not self.vault.settings.macro_hotkeys_enabled:
            return
        enabled = [m for m in macros if m.enabled]
        if not enabled:
            return
        if len(enabled) == 1:
            self._run_macro(enabled[0], self._TRIGGER_HOTKEY, hotkey_spec, target)
        else:
            self._open_macro_picker(
                paste_target=target,
                filter_macros=enabled,
                title="Vault Macros — choose hotkey match",
            )

    def _on_text_shortcut_match(self, macro, shortcut: str, backspace_count: int, hwnd) -> None:
        ok, _reason = self._macro_executor.execution_allowed()
        if not ok or not self.vault.settings.macro_text_shortcuts_enabled:
            return
        self._text_shortcut_listener.update([], enabled=False)

        def _run() -> None:
            try:
                self._run_macro(
                    macro,
                    self._TRIGGER_TEXT_SHORTCUT,
                    shortcut,
                    hwnd,
                    shortcut_backspaces=backspace_count,
                )
            finally:
                self._sync_text_shortcut_listener()

        self._call_on_main(_run)

    def _open_macro_picker(
        self,
        *,
        paste_target=None,
        filter_macros=None,
        title: str = "Vault Macros",
    ) -> None:
        if not self._alive():
            return
        ok, _reason = self._macro_executor.execution_allowed()
        if not ok:
            self._show_toast("Vault Macros are disabled or setup is incomplete.")
            return
        try:
            existing = getattr(self, "_macro_picker", None)
            if existing is not None:
                try:
                    if existing.winfo_exists():
                        existing.focus_popup()
                        return
                except Exception:  # noqa: BLE001
                    self._macro_picker = None
            if paste_target is None:
                paste_target = foreground_window()
            if hwnd_belongs_to_widget(paste_target, self):
                paste_target = None
            macros = filter_macros or [
                m for m in self._macro_store.load_all() if m.enabled
            ]
            from .macro_picker import MacroPicker

            def _choose(chosen) -> None:
                self._run_macro(
                    chosen, self._TRIGGER_MENU_ONLY, "", paste_target,
                )

            self._macro_picker = MacroPicker(
                self, macros, on_choose=_choose, title=title,
            )
        except Exception as exc:  # noqa: BLE001
            write_crash("macro picker", exc)

    def _resolve_macro_target(self, target_hwnd):
        if target_hwnd and hwnd_belongs_to_widget(target_hwnd, self):
            target_hwnd = None
        if not target_hwnd:
            target_hwnd = foreground_window()
            if hwnd_belongs_to_widget(target_hwnd, self):
                target_hwnd = None
        return target_hwnd

    def _run_macro(
        self,
        macro,
        trigger_type: str,
        trigger_value: str = "",
        target_hwnd=None,
        *,
        shortcut_backspaces: int = 0,
    ):
        if not self._guard_unlocked():
            return None
        target_hwnd = self._resolve_macro_target(target_hwnd)
        if not target_hwnd:
            self._show_toast("No target window — focus an app and try again.")
            result = self._macro_executor.execute(
                macro,
                trigger_type=trigger_type,
                trigger_value=trigger_value,
                target_hwnd=None,
                shortcut_backspaces=shortcut_backspaces,
            )
        else:
            result = self._macro_executor.execute(
                macro,
                trigger_type=trigger_type,
                trigger_value=trigger_value,
                target_hwnd=target_hwnd,
                shortcut_backspaces=shortcut_backspaces,
            )
        if self._alive():
            self._refresh_after_macro()
        return result

    def _refresh_after_macro(self) -> None:
        """Refresh macro list/counts without a full shell rebuild (avoids CTk races)."""
        if not self._alive():
            return
        try:
            counts = self.vault.counts()
            counts[NAV_VAULT_MACROS] = len(self._macro_store.load_all())
            self._filters.update_counts(counts)
            if self._filters.active == NAV_VAULT_MACROS:
                frame = self._vault_screens._screens.get(NAV_VAULT_MACROS)  # noqa: SLF001
                refresh = getattr(frame, "_refresh", None)
                if callable(refresh):
                    refresh()
        except Exception as exc:  # noqa: BLE001
            write_crash("macro refresh", exc)

    def _macro_run(self, macro_id: str) -> None:
        macro = self._macro_store.get(macro_id)
        if macro is None:
            return
        target = foreground_window()
        if hwnd_belongs_to_widget(target, self):
            target = None
        self._run_macro(macro, self._TRIGGER_MENU_ONLY, "run_button", target)

    def _show_window(self) -> None:
        if not self._alive():
            return
        try:
            if self.state() == "iconic":
                self.state("normal")
        except Exception:  # noqa: BLE001
            pass
        self.deiconify()
        self.update_idletasks()
        self.lift()
        self.focus_force()
        if self._capture_refresh_pending:
            self._schedule_capture_refresh()

    def _on_close(self) -> None:
        # Hide to tray if we have one; otherwise quit outright.
        if (
            self.vault.settings.vault_lock_when_minimized
            and vault_lock.lock_config(self.vault.settings).enabled
        ):
            self._lock_now(reason="minimized")
        if self._tray.available:
            self.withdraw()
        else:
            self._quit()

    def _on_window_unmap(self, _event=None) -> None:
        if self._shutting_down or self._locked():
            return
        if not (
            self.vault.settings.vault_lock_when_minimized
            and vault_lock.lock_config(self.vault.settings).enabled
        ):
            return
        try:
            is_minimized = self.state() == "iconic"
        except Exception:  # noqa: BLE001
            is_minimized = False
        if is_minimized:
            self._lock_now(reason="minimized")

    def _quit(self) -> None:
        self._shutting_down = True
        for job in (self._search_job, self._capture_refresh_job, self._expiry_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass
        try:
            self._monitor.stop()
            self._hotkey.stop()
            if getattr(self, "_capture_hotkeys", None):
                self._capture_hotkeys.stop()
            if getattr(self, "_macro_hotkeys", None):
                self._macro_hotkeys.stop()
            if getattr(self, "_text_shortcut_listener", None):
                self._text_shortcut_listener.stop()
            self._tray.stop()
            self._mobile_bridge.stop()
            self.vault.close()
        finally:
            try:
                self.destroy()
            except Exception:  # noqa: BLE001
                pass
