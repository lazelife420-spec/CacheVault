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

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog

from .. import brand
from ..core import capture_debug, clip_accents, clip_metadata, cleanup_receipts, cleanup_suggestions, clipboard_out, copy_clean, drag_export, models, multi_link, search, selection, vault_lock
from ..core import sidebar_menu_context as smc
from .. import feature_gate
from .. import licensing
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
from ..core.storage import FILTER_ALL, FILTER_HOME, FILTER_SEARCH_ALL
from ..core.mobile.bridge import MobileBridge
from ..core.mobile.mobile_access_controller import MobileAccessController
from ..core.vault import Vault
from .clip_grid import ClipGrid
from .clip_list import ClipList
from .dialogs import (
    AboutDialog, EventLogDialog, ExportViewDialog, MoveToCollectionDialog,
    SafePickerDialog, SettingsDialog,
)
from . import batch_actions
from . import clip_context
from . import icon
from . import sidebar_context
try:
    from .settings_hub import SettingsHub
except ImportError:
    SettingsHub = None
from .clip_workflows import ClipComposerDialog, EditClipTextDialog, MultiLinkPasteDialog
from .filters import (
    FilterNav,
    NAV_EDITABLE_COPIES,
    NAV_EXPORTS,
    NAV_HOTKEY_ACTIONS,
    NAV_HTML_BUNDLES,
    NAV_CLEANUP_SUGGESTIONS,
    NAV_MOBILE_ACCESS,
    NAV_MOBILE_INBOX,
    NAV_QUICK_PASTE,
    NAV_SCREEN_KEYS,
    NAV_FOUNDER,
    NAV_NEW_SAFE,
    NAV_SETTINGS,
    NAV_STAMPED_RECEIPTS,
    NAV_VAULT_MACROS,
)
from ..core.win_mouse import install_mouse_handler
from .founder import FounderDialog, FounderPromptDialog
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
from .font_patch import install_main_thread_font_finalizer_guard
from .scroll_patch import install_windows_scroll_patch, scroll_config_from_settings
from .win_scroll import refresh_windows_scroll_cache
from .page_header import PageHeader

EXPIRY_SWEEP_MS = 15_000  # run the expiry sweep every 15s

# Each rendered clip row is a deep CustomTkinter widget tree (~45 Tk widgets,
# each a Windows USER object/HWND). Windows caps USER objects at ~10,000 per
# process, so rendering an unbounded history exhausts the quota and makes Tk
# raise "No more menus can be allocated" on the next menu/dialog. Cap the
# number of rows we materialise; older items stay reachable via search/filters.
MAX_VISIBLE_CLIPS = 120
# Home dashboard's "recent" queries only ever display their first 3-8 items
# (see home_dashboard.py's [:3]/[:4]/[:8] slices) but previously fetched every
# live/matching clip with no SQL limit, then sliced in Python -- a cost that
# scaled with total vault size instead of what's actually shown. Measured at
# ~58ms combined across 5 queries at 1500 live clips (see
# scripts/cleanup_perf_baseline.py); this bounds it regardless of vault size.
HOME_RECENT_WINDOW = 50
HK_MANUAL_SAVE = 10
HK_ARM_NEXT = 11
HK_IGNORE_NEXT = 12
HK_MACRO_MENU = 13
HK_MACRO_ID_BASE = 100
HK_COMMAND_ID_BASE = 500

_FOUNDER_NAV_GATES: dict[str, str] = {
    NAV_EXPORTS: "exports_advanced",
    NAV_EDITABLE_COPIES: "editable_copies_advanced",
    NAV_HTML_BUNDLES: "html_bundle_export",
    NAV_VAULT_MACROS: "macros_advanced",
}


class CacheVaultApp(ctk.CTk):
    # Label for the page-level All Clips Refresh affordance. The ⟳ glyph is the
    # visible refresh icon (same monochrome-symbol language as the ◈/⟳ marks
    # already used in the chrome); the word keeps it accessible and testable.
    _REFRESH_LABEL = "⟳ Refresh"
    _REFRESH_BUSY_LABEL = "⟳ Refreshing…"

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
            self._show_crash_dialog(exc, val, tb, path)
        except Exception:  # noqa: BLE001
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Cache Vault — Error",
                    f"Something went wrong.\n\nDetails were saved to:\n{path}",
                    parent=self if self._alive() else None,
                )
            except Exception:  # noqa: BLE001
                pass

    def _show_crash_dialog(self, exc, val, tb, path) -> None:
        try:
            if not self._alive():
                return
            from tkinter import messagebox
            dialog = ctk.CTkToplevel(self)
            dialog.title("Cache Vault — Application Error")
            dialog.geometry("500x220")
            dialog.resizable(False, False)
            dialog.attributes("-topmost", True)
            dialog.grab_set()

            dialog.columnconfigure(0, weight=1)
            dialog.columnconfigure(1, weight=1)
            dialog.columnconfigure(2, weight=1)

            ctk.CTkLabel(
                dialog,
                text="⚠️ Application Error",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=brand.WARNING_RED,
            ).grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(15, 5))

            err_summary = str(val)[:120] + ("..." if len(str(val)) > 120 else "")
            ctk.CTkLabel(
                dialog,
                text=f"An unexpected error occurred: {err_summary}\n\n"
                     f"Details have been saved to:\n{path}",
                font=ctk.CTkFont(size=11),
                justify="left",
                wraplength=460,
            ).grid(row=1, column=0, columnspan=3, sticky="w", padx=20, pady=5)

            tb_str = "".join(traceback.format_exception(exc, val, tb))

            def _copy():
                clipboard_out.write_via_tk(self, tb_str)
                messagebox.showinfo("Copied", "Error traceback copied to clipboard.", parent=dialog)

            def _open_log():
                import os
                try:
                    os.startfile(path)
                except Exception:
                    pass

            ctk.CTkButton(
                dialog,
                text="Copy Error",
                command=_copy,
                **theme.secondary_button(),
            ).grid(row=2, column=0, padx=(20, 5), pady=(15, 10), sticky="ew")

            ctk.CTkButton(
                dialog,
                text="Open Crash Log",
                command=_open_log,
                **theme.secondary_button(),
            ).grid(row=2, column=1, padx=5, pady=(15, 10), sticky="ew")

            ctk.CTkButton(
                dialog,
                text="Continue",
                command=dialog.destroy,
                **theme.primary_button(),
            ).grid(row=2, column=2, padx=(5, 20), pady=(15, 10), sticky="ew")
        except Exception:
            pass

    def __init__(self, vault: Vault | None = None):
        # CTk.__init__ (invoked by super().__init__() below) schedules its
        # own Windows titlebar-icon workaround via
        # self.after(200, self._windows_set_titlebar_icon) before any of
        # this constructor's own body runs -- before _init_jobs even exists
        # (see below) -- so nothing else in this class ever gets a chance to
        # record that job's id, and destroy() never cancelled it: a
        # construct-then-destroy within 200ms left it pending against an
        # already-destroyed interpreter (issue #80). Overriding self.after
        # only for the duration of super().__init__() captures that one
        # call without affecting anything else CTk.__init__ schedules --
        # e.g. the 1ms focus-restore inside its titlebar-color workaround --
        # and without touching self.after for the rest of this window's
        # life; the override is removed immediately after super().__init__()
        # returns.
        self._titlebar_icon_job: str | None = None
        self.after = self._capture_titlebar_icon_job
        try:
            super().__init__()
        finally:
            del self.after
        self.vault = vault or Vault()
        self.title(brand.WINDOW_TITLE)
        self.geometry("1100x700")
        self.minsize(900, 600)
        self._apply_window_icon()

        self._search_var = ctk.StringVar()
        self._search_job = None
        self._capture_refresh_job = None
        self._capture_refresh_pending = False
        self._expiry_job = None
        self._shutting_down = False
        self._main_thread_calls: queue.SimpleQueue = queue.SimpleQueue()
        # Count of refresh requests queued/running but not yet applied (or
        # failed). Tests poll this to know when an async refresh has
        # settled; production code uses it only via _alive()-guarded apply
        # callbacks, never read directly for control flow.
        self._refresh_workers_in_flight = 0
        # True from the moment a refresh actually commits to doing work
        # (worker query queued) until its result has fully finished
        # rendering -- including, for the general-clips case, the last
        # after(10, ...) batch of a chunked list/grid render. While True,
        # refresh() does not cancel and restart the active render; see
        # refresh()/_finish_active_refresh().
        self._render_active = False
        # Latest requested state recorded while a refresh is active, or
        # None. Applied (as exactly one trailing refresh) only if it turns
        # out to differ from what the active render actually showed.
        self._pending_refresh_signature = None
        # A single persistent worker thread processes refresh-snapshot
        # requests one at a time, in arrival order -- not a new OS thread
        # per refresh() call. Under a test suite building hundreds of app
        # instances (each refreshing many times), spawn-per-call thread
        # creation churn was heavy enough to destabilize the Tk/Tcl runtime
        # (observed as sporadic "couldn't read ttk/combobox.tcl" errors
        # constructing later Tk windows). One long-lived thread per app
        # avoids that, and serializing refreshes is also just correct: it
        # avoids N concurrent reader connections hitting the vault at once.
        self._refresh_request_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._refresh_worker_thread = threading.Thread(
            target=self._refresh_worker_loop, name="refresh-worker", daemon=True,
        )
        self._refresh_worker_thread.start()
        self._view_mode = "cards"
        self._selected_clip_id: str | None = None
        self._selected_clip_ids: list[str] = []
        self._visible_clip_ids: list[str] = []
        # "Select all matching" scope (Ctrl+Shift+A) -- an immutable query
        # descriptor, never a materialized id list. Kept separate from the
        # existing visible-selection tracking above (_selected_clip_ids /
        # ClipList._selected_ids), which is unchanged. See core/selection.py.
        # Exactly one of {visible, matching} is authoritative at a time --
        # see _exit_matching_selection_if_manual, called from every real
        # selection-changing callback so a manual click/ctrl-click/
        # shift-click/right-click-collapse always makes visible selection
        # authoritative again rather than leaving a stale "All N matching"
        # banner showing while _selected_clip_ids has silently diverged.
        self._selection_scope = selection.SelectionScope(self.vault.storage)
        # Suppresses that exit-on-change logic for exactly the one
        # deliberate view.select_all() call _keyboard_select_all_matching
        # makes to cosmetically paint the rendered subset of a *new*
        # matching selection -- without this, that call would immediately
        # cancel the very selection it's painting.
        self._suppress_matching_exit_on_selection_change = False
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
        self._resize_job = None
        self._last_width = 0
        self._last_height = 0
        self._mouse_handler = None
        self._is_compact_width = False
        self._settings_window = None
        self._photo_viewer_window = None
        self._init_jobs = []
        # Dedicated tracking for the current live _pump_main_thread schedule
        # -- unlike the one-shot jobs in _init_jobs, this one reschedules
        # itself every 50ms, so its id changes on every firing and must be
        # kept current rather than recorded once.
        self._pump_job = None

        self._mobile_bridge = MobileBridge(self.vault)
        self._mobile_controller = MobileAccessController(self.vault, self._mobile_bridge)
        self._mobile_controller.subscribe(lambda _state: self.after(0, self.refresh))

        from ..core.vault_macros import MacroSafeRegistry, MacroStore
        self._macro_store = MacroStore()
        self._macro_registry = MacroSafeRegistry(self.vault.settings)

        # Must be installed before any font is discarded: a font finalized on
        # a background thread calls Tk off-thread and hangs the refresh.
        install_main_thread_font_finalizer_guard()
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

        # Command Center — Hotkey Actions (Phase 1).
        from ..core import command_center as cc
        from .. import __version__ as _app_version
        self._cc = cc
        self._command_store = cc.HotkeyActionStore()
        self._command_runlog = cc.CommandRunLog()
        self._command_dispatcher = cc.CommandActionDispatcher(
            self._command_store,
            self._command_runlog,
            self._command_action_handlers(),
            is_locked=self._locked,
            confirm=self._confirm_command_action,
            app_version=_app_version,
            on_event=self._on_command_run_event,
        )
        self._command_hotkeys = MultiHotkeyListener()
        self._command_hotkey_ids: dict[int, str] = {}
        # Defer binding so CTk init is fully complete before hotkey registration
        # accesses widget internals.
        self._init_jobs.append(self.after(100, self._bind_command_hotkeys))
        self._init_jobs.append(self.after(150, self._command_hotkeys.start))
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
        self._init_jobs.append(self.after(0, lambda: self._mobile_controller.sync(self.vault.settings)))

        # Tray last — callbacks marshal through _call_on_main (pystray runs off-thread).
        self._tray = TrayController(
            on_open=lambda: self._call_on_main(self._show_window),
            on_toggle_pause=lambda: self._call_on_main(
                lambda: self._set_paused(not self.vault.settings.capture_paused)
            ),
            is_paused=lambda: bool(self.vault.settings.capture_paused),
            on_clear_sensitive=lambda: self._call_on_main(self._clear_sensitive),
            on_quit=lambda: self._call_on_main(self._quit),
            on_quick_paste=lambda: self._call_on_main(self._schedule_quick_paste),
            on_macro_menu=lambda: self._call_on_main(self._schedule_macro_menu),
        )
        self._tray.start()

        self._center_on_screen()
        self._show_window()
        self._pump_job = self.after(50, self._pump_main_thread)
        self._init_jobs.append(self.after(150, self._maybe_show_first_use_guide))
        self._bind_selection_keys()
        self.bind("<Configure>", self._on_window_configure)
        self._init_jobs.append(self.after(200, self._install_native_mouse_handler))

    def _capture_titlebar_icon_job(self, ms, fn=None, *args):
        """Instance-only override of self.after, installed immediately
        before -- and removed immediately after -- super().__init__() (see
        __init__). CTk.__init__ schedules its Windows titlebar-icon
        workaround via self.after(200, self._windows_set_titlebar_icon)
        before this class's own __init__ body runs, so this is the only
        window in which that specific job's id can be captured at all.

        Every other self.after(...) call made during super().__init__() --
        e.g. the 1ms focus-restore CTk's titlebar-color workaround schedules
        -- passes straight through to the real after() untouched via the
        `fn == self._windows_set_titlebar_icon` guard below; only the exact
        titlebar-icon callback gets recorded, so destroy() can cancel that
        one job without touching any other live callback.
        """
        job_id = super().after(ms) if fn is None else super().after(ms, fn, *args)
        if fn is not None and fn == self._windows_set_titlebar_icon:
            self._titlebar_icon_job = job_id
        return job_id

    def _install_native_mouse_handler(self) -> None:
        self._mouse_handler = install_mouse_handler(
            self,
            on_back=lambda: self._call_on_main(self._navigate_back),
            on_forward=lambda: self._call_on_main(self._navigate_forward),
        )

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
            "<Control-d>": lambda e: self._keyboard_duplicate_selected(e),
            "<Control-D>": lambda e: self._keyboard_duplicate_selected(e),
            "<Control-c>": lambda e: self._keyboard_copy_selected(e),
            "<Control-C>": lambda e: self._keyboard_copy_selected(e),
            "<Control-Shift-C>": lambda e: self._keyboard_copy_clean_selected(e),
            "<Control-a>": lambda e: self._keyboard_select_all(e),
            "<Control-A>": lambda e: self._keyboard_select_all(e),
            "<Control-Shift-A>": lambda e: self._keyboard_select_all_matching(e),
            "<Control-l>": lambda e: self._focus_clips_search(e),
            "<Control-L>": lambda e: self._focus_clips_search(e),
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
        self._shutting_down = True
        # 1. Stop UI timers
        # CTk.__init__'s own titlebar-icon workaround (see __init__ and
        # _capture_titlebar_icon_job) -- cancel before any other teardown
        # step in case it's already due to fire.
        if hasattr(self, "_titlebar_icon_job") and self._titlebar_icon_job:
            try:
                self.after_cancel(self._titlebar_icon_job)
            except Exception:
                pass
            self._titlebar_icon_job = None
        # _pump_job reschedules itself every 50ms (see _pump_main_thread),
        # so unlike _init_jobs' one-shot entries, cancelling it here means
        # cancelling whichever id is CURRENTLY live, not just the original.
        if hasattr(self, "_pump_job") and self._pump_job:
            try:
                self.after_cancel(self._pump_job)
            except Exception:
                pass
            self._pump_job = None
        if hasattr(self, "_idle_lock_job") and self._idle_lock_job:
            self.after_cancel(self._idle_lock_job)
            self._idle_lock_job = None
        if hasattr(self, "_expiry_job") and self._expiry_job:
            self.after_cancel(self._expiry_job)
            self._expiry_job = None
        if hasattr(self, "_search_job") and self._search_job:
            self.after_cancel(self._search_job)
            self._search_job = None
        if hasattr(self, "_capture_refresh_job") and self._capture_refresh_job:
            self.after_cancel(self._capture_refresh_job)
            self._capture_refresh_job = None
        if hasattr(self, "_refresh_job") and self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        if hasattr(self, "_refresh_request_queue"):
            self._refresh_request_queue.put(None)  # wake and stop the worker

        # 2. Stop system listeners
        for attr in ("_monitor", "_hotkey", "_capture_hotkeys", "_macro_hotkeys", "_command_hotkeys", "_text_shortcut_listener", "_tray", "_mobile_bridge"):
            if hasattr(self, attr):
                obj = getattr(self, attr)
                if obj and hasattr(obj, "stop"):
                    try:
                        obj.stop()
                    except Exception:
                        pass

        if hasattr(self, "_resize_job") and self._resize_job:
            self.after_cancel(self._resize_job)
            self._resize_job = None
        if hasattr(self, "_mouse_handler") and self._mouse_handler:
            self._mouse_handler.stop()
            self._mouse_handler = None

        if hasattr(self, "_init_jobs"):
            for job in self._init_jobs:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
            self._init_jobs.clear()

        # Release any grabs
        try:
            self.grab_release()
        except Exception:
            pass

        # 3. Final destroy
        try:
            super().destroy()
        except Exception:
            pass

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
        # _shutting_down is set at the very start of destroy(), before any
        # widget teardown -- checking it here (rather than relying solely on
        # _alive()'s visibility-based check) stops this from doing any work,
        # including rescheduling, once destruction has begun.
        if self._shutting_down:
            self._pump_job = None
            return
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
            self._pump_job = self.after(50, self._pump_main_thread)
        else:
            self._pump_job = None

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
        self.grid_columnconfigure(0, weight=0, minsize=200)
        self.grid_columnconfigure(1, weight=1, minsize=560)
        self.grid_columnconfigure(2, weight=0, minsize=320)
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
        self._top_receipts_btn = ctk.CTkButton(
            top, text=brand.TERM_STAMPED_RECEIPTS, width=130,
            command=lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
            **theme.secondary_button())
        self._top_receipts_btn.grid(row=0, column=2, padx=4)
        self._top_capture_rules_btn = ctk.CTkButton(
            top, text="⚡ Capture Rules", width=120, command=self._open_regex_macros,
            **theme.secondary_button())
        self._top_capture_rules_btn.grid(row=0, column=3, padx=4)
        # Compact-width overflow for the two buttons above -- see
        # _set_toolbar_compact. Occupies their combined grid slot but stays
        # ungridded (not merely invisible) until compact mode needs it, so
        # it never steals layout space at standard/wide widths.
        self._top_more_btn = ctk.CTkButton(
            top, text="More ▾", width=90, command=self._open_top_overflow_menu,
            **theme.secondary_button())
        ctk.CTkButton(top, text="⚙ Settings", width=90, command=self._open_settings,
                      **theme.secondary_button()
                      ).grid(row=0, column=4, padx=(4, 12))

        # Panels.
        self._filters = FilterNav(self, on_select=self._on_filter_select,
                                  settings=self.vault.settings,
                                  on_safe_context=self._open_safe_menu,
                                  on_collection_context=self._open_collection_sidebar_menu,
                                  on_section_context=self._open_sidebar_section_menu,
                                  on_nav_context=self._open_sidebar_nav_menu,
                                  width=210, corner_radius=0)

        self._filters.grid(row=1, column=0, sticky="nsew")

        self._center = ctk.CTkFrame(self, corner_radius=0, fg_color=brand.PANEL_BG)
        self._center.grid(row=1, column=1, sticky="nsew", padx=1)
        self._center.grid_rowconfigure(2, weight=1)
        self._center.grid_columnconfigure(0, weight=1)

        self._page_header = PageHeader(self._center)
        self._page_header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        self._toolbar = ctk.CTkFrame(self._center, fg_color=brand.SURFACE_BG)
        self._toolbar.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 0))
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
            on_double_click=self._on_clip_double_click,
            on_clip_context=self._open_home_clip_menu,
            on_card_context=self._open_home_card_menu,
            on_app_context=self._open_home_app_menu,
            on_status_context=self._open_home_status_menu,
            on_quick_paste=self._schedule_quick_paste,
            on_view_editable_copies=lambda: self._navigate_screen(NAV_EDITABLE_COPIES),
            on_view_html_bundles=lambda: self._navigate_screen(NAV_HTML_BUNDLES),
            on_settings=self._open_settings,
            on_selection_change=self._on_clip_selection_change,
            on_batch_action=self._on_home_batch_action,
            on_open_cleanup=lambda: self._navigate_screen(NAV_CLEANUP_SUGGESTIONS),
            on_scan_cleanup=self._scan_cleanup_suggestions,
            image_assets_ready=False,
            corner_radius=0,
        )
        self._list = ClipList(
            self._center, on_select=self._on_clip_select,
            on_context=self._open_clip_menu,
            on_selection_change=self._on_clip_selection_change,
            on_double_click=self._on_clip_double_click,
            corner_radius=0, fg_color=brand.PANEL_BG,
        )
        self._grid = ClipGrid(
            self._center, on_select=self._on_clip_select,
            on_sort=self._set_sort,
            on_context=self._open_clip_menu,
            on_selection_change=self._on_clip_selection_change,
            on_double_click=self._on_clip_double_click,
            corner_radius=0, fg_color=brand.PANEL_BG,
        )
        self._home.grid(row=2, column=0, sticky="nsew")
        self._list.grid(row=2, column=0, sticky="nsew")
        self._grid.grid(row=2, column=0, sticky="nsew")
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
                "select_clip_in_place": self._select_visible_clip_by_id,
                "preview_html": self._preview_html_copy,
                "edit_html": self._edit_html_source,
                "export_html": self._export_html_bundle,
                "reveal_export": self._reveal_export_path,
                "mobile_report": self._mobile_access_report,
                "pair_android": lambda: self._open_pair_android(),
                "paired_devices": self._open_paired_devices,
                "mobile_settings": self._open_settings,
                "revoke_all_mobile": self._revoke_all_mobile_and_refresh,
                "macro_list": self._macro_list_rows,
                "macro_edit": self._macro_edit,
                "macro_new_template": self._macro_new_template,
                "macro_setup": self._open_macro_setup,
                "macro_run": self._macro_run,
                "hotkey_action_list": self._command_action_rows,
                "hotkey_action_new": self._command_action_new,
                "hotkey_action_edit": self._command_action_edit,
                "hotkey_action_run": self._command_action_run_button,
                "hotkey_action_toggle": self._command_action_toggle,
                "hotkey_action_delete": self._command_action_delete,
                "copy_clip": self._copy_again,
                "open_link": self._open_clip_link,
                "export_proof": self._export_clip_proof,
                "remove_clip": self._remove_from_history,
                "open_clip_menu": self._open_clip_menu,
                "open_receipt_menu": self._open_receipt_menu,
                "set_header_actions": self._page_header.set_actions,
                "set_header_subtitle": lambda sub: self._page_header.set_content(self._page_header._title_label.cget("text"), sub),
                "set_header_chips": self._page_header.set_status_chips,
                "navigate_filter": self._navigate_filter,
                "storage": lambda: self.vault.storage,
                "events": lambda: self.vault.events,
                "scan_cleanup_suggestions": self._scan_cleanup_suggestions,
                "rescan_after_decision": self._rescan_cleanup_suggestions_quiet,
                "open_receipts": lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
            },
            corner_radius=0,
        )
        self._vault_screens.grid(row=2, column=0, sticky="nsew")
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
            self._init_jobs.append(self.after(100, self._lock_screen.focus_unlock))
        else:
            self._lock_screen.grid_remove()

    def _build_toolbar(self) -> None:
        self._sort_var = ctk.StringVar(value="Newest Added")
        self._added_var = ctk.StringVar(value="Any")
        self._used_var = ctk.StringVar(value="Any")
        self._type_var = ctk.StringVar(value="All Types")

        # --- Search field -----------------------------------------------------
        # The default CTkEntry surface matches the IRON_GRAY toolbar panel
        # (#1A1F26), so an unstyled entry reads as an empty divider rather
        # than an interactive control (UX finding: All Clips search control
        # difficult to discover). Wrap it in a differentiated, outlined well
        # with a visible magnifier icon and a clear focus state. Search
        # semantics, the bound StringVar/callback, and the toolbar layout are
        # unchanged.
        self._search_field_wrap = ctk.CTkFrame(
            self._toolbar_row1,
            fg_color=brand.BLACK_METAL,
            border_width=1,
            border_color=brand.VAULT_BORDER,
            corner_radius=6,
            height=32,
        )
        self._search_field_wrap.pack(fill="x", padx=6, pady=4)

        # Visible magnifier icon. The PhotoImage is bound to this app's own
        # Tk root (master=self) and retained on the instance so it lives
        # exactly as long as this window. A CTkImage is deliberately NOT used
        # here: CTkImage binds its internal photo to Tk._default_root, which
        # triggers "pyimageN doesn't exist" across the many app
        # construction/teardown cycles in the test suite (and any other
        # multi-root process). The glyph matches the app's monochrome-symbol
        # language (cf. the ⟳/◈ marks used elsewhere).
        self._search_icon_photo = None
        self._search_icon_label = None
        _icon_pil = icon.search_icon_pil(18)
        if _icon_pil is not None:
            from PIL import ImageTk
            self._search_icon_photo = ImageTk.PhotoImage(_icon_pil, master=self)
            self._search_icon_label = tk.Label(
                self._search_field_wrap,
                image=self._search_icon_photo,
                text="",
                bg=brand.BLACK_METAL,
                highlightthickness=0,
                borderwidth=0,
            )
            self._search_icon_label.pack(side="left", padx=(8, 4))

        self._clips_search = ctk.CTkEntry(
            self._search_field_wrap,
            textvariable=self._search_var,
            placeholder_text="Search clips…  (type:link  source:cursor)",
            height=32,
            fg_color="transparent",
            border_width=0,
        )
        self._clips_search.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # Visible placeholder cue. CTkEntry's own placeholder_text never renders
        # here because CTk only activates it when no textvariable is bound
        # (see CTkEntry._activate_placeholder) and this field binds
        # ``_search_var``. That silent gap was part of the discoverability
        # defect, so drive an explicit overlay label that reads "Search clips…"
        # while the field is empty and unfocused. Clicking it focuses the entry.
        self._search_placeholder = tk.Label(
            self._search_field_wrap,
            text="Search clips…",
            bg=brand.BLACK_METAL,
            fg=brand.MUTED_TEXT,
            highlightthickness=0,
            borderwidth=0,
        )
        self._search_placeholder.bind("<Button-1>", lambda _e: self._clips_search.focus_set())

        # Clear focus affordance: lift the well outline to Proof Teal while the
        # search input has focus, restore the restrained border on blur, and
        # keep the placeholder cue in sync with focus/text state.
        self._clips_search.bind("<FocusIn>", self._on_search_focus_in)
        self._clips_search.bind("<FocusOut>", self._on_search_focus_out)
        self._search_var.trace_add("write", lambda *_: self._update_search_placeholder())
        self._search_placeholder_focused = False
        self._update_search_placeholder()
        # Cross-view search banner — visible when search is active.
        # Matches FEATURE_DIRECTION: "search runs across all clips — live history AND Recently Removed"
        self._search_scope_banner = ctk.CTkLabel(
            self._toolbar_row1,
            text="⟳  Searching all clips including Recently Removed",
            anchor="w",
            text_color=brand.PROOF_TEAL,
            font=ctk.CTkFont(size=10),
        )
        # Initially hidden — shown when search box has text.


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
        # Removed First Saved and Last Used filters to simplify toolbar
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

        # Page-level Refresh control. Exposes the EXISTING refresh() path
        # (debounced; single persistent background worker; overlap-guarded by
        # _render_active/_refresh_generation) as a visible, supported
        # affordance — the packaged UI previously had no way to invoke it.
        # Deliberately lives on row2 with Sort/Type (page-level controls) and
        # is visually distinct from the Cards/Grid view toggle on row3, so the
        # refresh action is never confused with switching views. It calls
        # refresh(); it does not add a second refresh implementation. Its
        # busy/disabled state is driven in lockstep with the refresh indicator
        # by _set_refreshing().
        self._refresh_btn = ctk.CTkButton(
            self._toolbar_row2, text=self._REFRESH_LABEL, width=112, height=28,
            command=self._on_refresh_clicked, **theme.secondary_button(),
        )
        self._refresh_btn.pack(side="right", padx=(2, 8))
        tooltip.bind_tooltip(self._refresh_btn, "Refresh")

        # Narrow-width containment guard: packed first (side="right") so it
        # stays the true rightmost element of the row regardless of whether
        # _view_label is later hidden/shown, guaranteeing Grid/Cards always
        # keep a minimum inset from the toolbar's right edge -- headroom,
        # not a fix for any observed clipping (none was found at any
        # supported window size; see the Slice 2 measurement record).
        ctk.CTkFrame(self._toolbar_row3, width=12, height=1, fg_color="transparent").pack(
            side="right")
        self._view_label = ctk.CTkLabel(self._toolbar_row3, text="View:", text_color=brand.MUTED_FG,
                     font=theme.body_font(11))
        self._view_label.pack(side="right", padx=(4, 2))
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
        # Removed Review Duplicates button from global toolbar
        self._selected_action_frame = ctk.CTkFrame(self._toolbar_row3, fg_color="transparent")
        self._selected_action_label = ctk.CTkLabel(
            self._selected_action_frame,
            text="No item selected",
            text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=10),
        )
        self._selected_action_label.pack(side="left", padx=(0, 4))
        self._selected_action_buttons: list[ctk.CTkButton] = []
        # Persistent discoverability hint (lives outside the button list so it
        # survives strip rebuilds). Shows the multi-select shortcut when 0/1 is
        # selected; the action label shows "N selected" once a set is active.
        self._selection_hint_label = ctk.CTkLabel(
            self._toolbar_row3,
            text=brand.SELECTION_HINT,
            text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=10),
        )
        self._selection_hint_label.pack(side="left", padx=(6, 0))
        self._update_selected_action_strip(None)

    def _focus_clips_search(self, _event=None):
        """Make the primary All Clips search surface reachable by keyboard."""
        if self._filters.active != FILTER_ALL:
            self._navigate_filter(FILTER_ALL)
        self.after_idle(self._clips_search.focus_set)
        return "break"

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
            self._selected_action_frame.pack_forget()
            self._set_selection_hint(brand.SELECTION_HINT)
            self._selected_action_label.configure(text="")
            return

        if getattr(self, "_current_layout_mode", None) == "compact":
            self._selected_action_frame.pack(side="left", padx=(8, 4))
            self._set_selection_hint("")
            self._selected_action_label.configure(text="1 clip selected")

            def show_details():
                self._preview.configure(width=360)
                self._preview.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
                self._preview.lift()

            btn = ctk.CTkButton(
                self._selected_action_frame,
                text="Details",
                width=92,
                height=24,
                command=show_details,
                **theme.secondary_button(),
            )
            btn.pack(side="left", padx=2)
            self._selected_action_buttons.append(btn)
        else:
            self._selected_action_frame.pack_forget()
            self._set_selection_hint(brand.SELECTION_HINT)
            self._selected_action_label.configure(text="")

    def _clear_selection(self) -> None:
        # Use clear_selection (not set_selected(None)) so a multi-row selection
        # is fully repainted, not just the single anchor row.
        self._list.clear_selection()
        self._grid.clear_selection()
        self._selected_clip_ids = []
        self._selected_clip_id = None
        self._selection_scope.clear()
        self._set_selection_notice(None)
        self._home.set_selected(None)
        self._update_selected_action_strip(None)
        # Clear the inspector so navigation cannot leave a stale clip from the
        # previous page visible in the preview panel.
        self._preview.show(None)
        self._update_inspector_visibility()

    def _keyboard_select_all(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if not self._visible_clip_ids:
            return "break"
        view = self._grid if self._view_mode == "grid" else self._list
        # Only act when the clip view is actually on screen (not the dashboard).
        try:
            if not view.winfo_ismapped():
                return "break"
        except Exception:  # noqa: BLE001
            return "break"
        view.select_all()
        return "break"

    def _keyboard_select_all_matching(self, event=None):
        """Ctrl+Shift+A: select every clip matching the current nav/search/
        filter/sort context -- not just the up-to-120 rendered rows. Stores
        an immutable query descriptor (see core/selection.py) and shows the
        resolved count; does not materialize a widget or an id per match.
        Rendered rows are given the existing visual "selected" treatment
        via view.select_all() (they're a subset of the matching set, so
        this is honest, not a fake full-set render) -- unloaded matches
        never become widgets.
        """
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        active = self._filters.active
        general_clips = active not in NAV_SCREEN_KEYS and active != FILTER_HOME
        if not general_clips:
            return "break"
        view = self._grid if self._view_mode == "grid" else self._list
        try:
            if not view.winfo_ismapped():
                return "break"
        except Exception:  # noqa: BLE001
            return "break"
        query = self._build_query()
        matching = self._selection_scope.activate_matching(active, query)
        self._paint_matching_selection_visuals(view)
        self._set_selection_notice(f"All {matching.resolved_count} matching items selected")
        return "break"

    def _paint_matching_selection_visuals(self, view) -> None:
        """Gives every currently-rendered row the existing visual
        "selected" treatment for the active matching selection (a true
        subset, never a fake full-set render -- unloaded matches never
        become widgets). Used both right after Ctrl+Shift+A activates a
        matching selection, and after a same-context refresh re-renders
        rows while matching mode is still active (see
        _apply_refresh_snapshot) -- a refresh that didn't change the
        matching context must keep showing every rendered row as
        selected, not silently drop back to a single highlighted row.
        Suppressed via _suppress_matching_exit_on_selection_change so
        this call doesn't trip _exit_matching_selection_if_manual and
        cancel the very selection it's painting. When invoked as a
        render_batched on_complete callback, a newer refresh may have
        cleared matching mode (or completed and replaced this render) by
        the time the callback actually fires -- guarded so a stale
        callback can't resurrect a selection that's genuinely gone.
        """
        if self._selection_scope.mode != "matching" or not self._visible_clip_ids:
            return
        self._suppress_matching_exit_on_selection_change = True
        try:
            view.select_all()
        finally:
            self._suppress_matching_exit_on_selection_change = False

    def _set_selection_notice(self, text: str | None) -> None:
        """Surfaces (or clears) the "All N matching items selected"
        banner. Non-destructive to the rest of the header (same .place()
        pattern as the existing refreshing indicator)."""
        header = getattr(self, "_page_header", None)
        if header is not None and hasattr(header, "set_selection_notice"):
            header.set_selection_notice(text)

    def _selected_text_clips(self) -> list[models.Clip]:
        clips: list[models.Clip] = []
        for clip_id in self._selected_clip_ids:
            clip = self.vault.storage.get_clip(clip_id)
            if clip is None or clip.content_type == models.CONTENT_IMAGE:
                continue
            clips.append(clip)
        return clips

    def _open_clip_composer(self) -> None:
        if not self._guard_unlocked():
            return
        clips = self._selected_text_clips()
        if len(clips) < 2:
            self._show_toast("Select at least two text clips to combine them.")
            return
        parts = [clip.content for clip in clips if clip.content]
        if len(parts) < 2:
            self._show_toast("Not enough text in the selection to combine.")
            return
        ClipComposerDialog(
            self,
            parts=parts,
            on_copy=lambda text: self._copy_generated_text(text, "Copied combined clip."),
            on_save_clip=lambda text, base=clips[-1]: self._save_generated_clip(text, base.safe_id),
            on_save_macro=self._save_generated_macro,
        )

    def _block_if_matching_active(self, action_label: str) -> bool:
        """Guards every legacy action that reads ``_selected_clip_ids``
        directly (copy/export/move-to-safe/remove and their keyboard
        shortcuts) against silently acting on only the up-to-120 visible
        ids while a "select all matching" selection is active and its
        banner is still showing "All N matching items selected". None of
        these actions are matching-aware yet (that's later commits'
        scope) -- for now they refuse to run against a matching
        selection rather than quietly mutate/export a mismatched subset.
        Returns True (and shows an explanatory toast) if the caller must
        abort; False if it's safe to proceed normally.
        """
        if self._selection_scope.mode == "none":
            return False
        self._show_toast(
            f"{action_label} isn't available yet for \"select all matching\" -- "
            "click an item first to select a specific set."
        )
        return True

    def _bulk_copy(self) -> None:
        if self._block_if_matching_active("Copy"):
            return
        batch_actions.bulk_copy(self)

    def _copy_generated_text(self, text: str, toast: str) -> bool:
        # note_local_copy is told the string the clipboard actually holds, not
        # the source text: they differ whenever line breaks are involved, and
        # the mismatch made the monitor re-capture our own copy as a new clip.
        copied = clipboard_out.write_via_tk(self, text)
        self._monitor.note_local_copy(copied)
        self._show_toast(toast)
        return True

    def _save_generated_clip(self, text: str, safe_id: str | None = None) -> bool:
        """Returns whether the clip was actually stored.

        The composer/edit dialogs close only on a truthy result, so a capture the
        vault declined leaves the dialog open with the user's text instead of
        silently discarding it.
        """
        clip = self.vault.capture(
            text,
            source_app=brand.PRODUCT_NAME,
            capture_mode=models.CAPTURE_EXTERNAL_APP,
            safe_id=safe_id,
            force=True,
        )
        if clip is None:
            self._show_toast("That clip could not be saved.")
            return False
        self.refresh()
        self._on_clip_select(clip)
        self._show_toast("Saved as a new clip.")
        return True

    def _save_generated_macro(self, text: str) -> bool:
        clip = self.vault.capture(
            text,
            source_app=brand.PRODUCT_NAME,
            capture_mode=models.CAPTURE_EXTERNAL_APP,
            safe_id=self.vault.settings.default_safe_id,
            force=True,
        )
        if clip is None:
            self._show_toast("That snippet macro could not be saved.")
            return False
        self._send_to_macro_safe(clip.id)
        return True

    def _bulk_export_proof(self) -> None:
        if self._block_if_matching_active("Export"):
            return
        batch_actions.bulk_export_proof(self)

    def _bulk_move_to_safe(self) -> None:
        if self._block_if_matching_active("Move to Safe"):
            return
        batch_actions.bulk_move_to_safe(self)

    def _bulk_remove(self) -> None:
        if self._block_if_matching_active("Remove"):
            return
        batch_actions.bulk_remove(self)

    def _confirm_and_permanently_delete(self, ids: list[str], *, on_done=None) -> None:
        """The one shared entry point behind every single-confirmation
        permanent-deletion trigger -- single-item menu, preview-pane
        danger-zone button, and bulk item/context menu all call this,
        so there is exactly one permanent-deletion safety architecture
        (one dialog, one plan builder, one pipeline) regardless of how
        many ids are involved. The sidebar's "selected" command also
        calls this; only Delete All needs its own two-step dialog and
        stays separate (see ``_sidebar_permanently_delete_all``), though
        it still ends at the same ``Vault.permanently_delete_many``.
        """
        from ..core import permanent_delete as pd
        from .dialogs import PermanentDeleteSelectedDialog

        plan = pd.build_deletion_plan(self.vault.storage, ids)

        def _run() -> None:
            result = self.vault.permanently_delete_many(ids, confirmation_mode="selected")
            self._report_permanent_delete_result(result)
            if on_done is not None:
                on_done()

        PermanentDeleteSelectedDialog(
            self,
            eligible_count=len(plan.eligible_ids),
            skipped_count=len(plan.skipped),
            asset_count=plan.asset_count,
            bytes_scheduled=plan.planned_bytes,
            on_confirm=_run,
        )

    def _bulk_permanently_delete(self, ids: list[str]) -> None:
        """Recently Removed item/bulk menu only -- ``clip_menu_items``
        only offers this command when every targeted clip was already
        soft-deleted at menu-build time. The deletion plan re-validates
        ``deleted_at`` for each id again right here at execution time
        regardless, so a clip restored in the meantime is skipped, not
        deleted (same staleness contract as the sidebar's equivalent
        commands).
        """
        if not self._guard_unlocked():
            return
        from ..core.selection import dedupe_preserve_order

        ids = dedupe_preserve_order(ids)
        if not ids:
            return
        self._confirm_and_permanently_delete(ids)

    # --- Commit 2: additional visible-mode bulk selection commands ---------
    # (Copy/Export/Move-to-Recently-Removed already existed above; these
    # fill in the rest of core/menu_context.py's command_matrix.)

    def _bulk_toggle_favorite(self, favorite: bool) -> None:
        label = "Favorite" if favorite else "Remove Favorite"
        if self._block_if_matching_active(label):
            return
        if not self._guard_unlocked():
            return
        from ..core.selection import dedupe_preserve_order

        ids = dedupe_preserve_order(self._selected_clip_ids)
        if not ids:
            return
        for cid in ids:
            self.vault.set_favorite(cid, favorite)
        self.refresh()
        verb = "Favorited" if favorite else "Removed favorite mark from"
        self._show_toast(f"{verb} {len(ids)} clip(s).")

    def _run_atomic_bulk_mutation(self, fn, ids, *, action_label: str):
        """Calls an atomic bulk-mutation primitive (vault.restore_many /
        vault.remove_from_history_many) and turns a raised exception into
        a visible error toast instead of letting a caller compute a
        success count from a call that never actually committed. Because
        those primitives are atomic (storage.restore_many/
        soft_delete_many: one transaction, full rollback on any
        exception), there is no partial-success state to report here --
        either this returns the committed BulkMutationResult, or it
        returns None and nothing in the database changed.
        """
        try:
            return fn(ids)
        except Exception as exc:  # noqa: BLE001
            write_crash(f"bulk_{action_label.lower().replace(' ', '_')}", exc)
            self._show_toast(f"{action_label} failed -- no clips were changed.")
            return None

    def _bulk_restore(self) -> None:
        if self._block_if_matching_active("Restore"):
            return
        if not self._guard_unlocked():
            return
        from ..core.selection import dedupe_preserve_order

        ids = dedupe_preserve_order(self._selected_clip_ids)
        if not ids:
            return
        result = self._run_atomic_bulk_mutation(self.vault.restore_many, ids, action_label="Restore")
        if result is None:
            return
        self._clear_selection()
        self.refresh()
        self._show_toast(f"Restored {result.succeeded_count} clip(s).")

    def _bulk_add_to_collection(self) -> None:
        if self._block_if_matching_active("Add to Collection"):
            return
        if not self._guard_unlocked():
            return
        from ..core.selection import dedupe_preserve_order

        ids = dedupe_preserve_order(self._selected_clip_ids)
        if not ids:
            return
        existing = [c["name"] for c in self.vault.list_collections()]

        def save(name: str) -> None:
            for cid in ids:
                self.vault.set_collection(cid, name)
            self.refresh()
            self._show_toast(f"Added {len(ids)} clip(s) to '{name}'.")

        MoveToCollectionDialog(self, None, existing, on_save=save)

    def _current_collection_name(self) -> str | None:
        from ..core.storage import COLLECTION_PREFIX

        active = self._filters.active
        if isinstance(active, str) and active.startswith(COLLECTION_PREFIX):
            return active[len(COLLECTION_PREFIX):]
        return None

    def _bulk_remove_from_collection(self) -> None:
        """Clears only the current single-assignment collection label
        (clips.collection) from selected clips that actually belong to
        it -- never removes the clip itself, never touches favorites or
        any other metadata. See clear_collection() in clip_context.py
        for the sidebar/whole-collection equivalent."""
        name = self._current_collection_name()
        if name is None:
            return
        if self._block_if_matching_active("Remove from Collection"):
            return
        if not self._guard_unlocked():
            return
        from ..core.selection import dedupe_preserve_order

        ids = dedupe_preserve_order(self._selected_clip_ids)
        if not ids:
            return
        count = 0
        for cid in ids:
            clip = self.vault.storage.get_clip(cid)
            if clip is not None and clip.collection == name:
                self.vault.set_collection(cid, None)
                count += 1
        self.refresh()
        self._show_toast(f"Removed {count} clip(s) from '{name}'. Clips remain in the vault.")

    def _invert_visible_selection(self) -> None:
        """Selects every currently-rendered (visible) row that is NOT
        currently selected, and deselects the ones that are. Exits
        matching mode first via the normal manual-selection path (this
        is an explicit visible-only command, not a matching one)."""
        if not self._guard_unlocked():
            return
        view = self._grid if self._view_mode == "grid" else self._list
        inverted = set(self._visible_clip_ids) - set(self._selected_clip_ids)
        view.set_selected_ids(inverted)

    # --- Commit 2: matching-wide selection commands -------------------------
    # Every one of these re-validates the matching context (signature +
    # fresh count) immediately before doing anything, and resolves ids
    # through a single read snapshot (core/selection.py's
    # clip_id_snapshot via SelectionResolution.iter_ids) rather than ever
    # touching _selected_clip_ids -- see this commit's core invariant: a
    # matching-selection command must never look like it targets every
    # matching record while actually acting on only the rendered subset.

    def _resolve_matching_or_abort(self, *, confirm_title: str | None = None, confirm_detail: str = ""):
        """Shared preamble for every matching-wide command: resolve
        (validating the signature and re-counting fresh), abort visibly
        if stale, and optionally confirm with the caller showing the
        exact resolved count. Returns the SelectionResolution to consume
        via .iter_ids()/.resolve_all_ids(), or None if the caller should
        stop (stale, empty, or the user declined the confirmation).
        """
        active = self._filters.active
        query = self._build_query()
        resolution = self._selection_scope.resolve(active, query)
        if resolution.mode != "matching":
            self._show_toast("No matching selection is active.")
            return None
        if resolution.stale:
            self._show_toast(
                "The matching selection is out of date (search, filter, or "
                "view changed) -- select all matching again to continue."
            )
            return None
        if resolution.count == 0:
            self._show_toast("No matching items to act on.")
            return None
        if confirm_title is not None:
            from tkinter import messagebox

            ok = messagebox.askyesno(
                confirm_title,
                f"{confirm_title} {resolution.count} matching item(s)?{confirm_detail}",
                parent=self,
            )
            if not ok:
                return None
        return resolution

    def _matching_export(self) -> None:
        if not self._guard_unlocked():
            return
        if not self._require_founder("proof_pack_export"):
            return
        resolution = self._resolve_matching_or_abort()
        if resolution is None:
            return
        ids = resolution.resolve_all_ids()
        if not ids:
            self._show_toast("No matching items to export.")
            return
        from ..core.exports import export_zip_basename
        from tkinter import filedialog

        dest = filedialog.asksaveasfilename(
            parent=self,
            title="Export proof zip",
            defaultextension=".zip",
            initialfile=export_zip_basename(),
            filetypes=[("Zip archive", "*.zip")],
        )
        if not dest:
            return
        # Re-derive protection/existence is handled by export_proof_zip
        # itself per-id (missing/invalid ids are simply skipped there,
        # same as the existing visible-mode bulk export path).
        self.vault.export_proof_zip(ids, dest, mode="auto")
        self.refresh()
        self._show_toast(f"Exported proof for {len(ids)} matching clips.")

    def _matching_move_to_recently_removed(self) -> None:
        if not self._guard_unlocked():
            return
        resolution = self._resolve_matching_or_abort(
            confirm_title="Move to Recently Removed",
            confirm_detail=" They can be restored from Recently Removed. "
                            "This does not delete any files from your computer.",
        )
        if resolution is None:
            return
        ids = resolution.resolve_all_ids()
        result = self._run_atomic_bulk_mutation(
            self.vault.remove_from_history_many, ids, action_label="Move to Recently Removed",
        )
        if result is None:
            return
        self._clear_selection()
        self.refresh()
        self._show_toast(f"Moved {result.succeeded_count} matching clip(s) to Recently Removed.")

    def _matching_restore(self) -> None:
        if not self._guard_unlocked():
            return
        resolution = self._resolve_matching_or_abort(confirm_title="Restore")
        if resolution is None:
            return
        ids = resolution.resolve_all_ids()
        result = self._run_atomic_bulk_mutation(self.vault.restore_many, ids, action_label="Restore")
        if result is None:
            return
        self._clear_selection()
        self.refresh()
        self._show_toast(f"Restored {result.succeeded_count} matching clip(s).")

    def _matching_toggle_favorite(self, favorite: bool) -> None:
        if not self._guard_unlocked():
            return
        resolution = self._resolve_matching_or_abort()
        if resolution is None:
            return
        changed = 0
        for cid in resolution.resolve_all_ids():
            self.vault.set_favorite(cid, favorite)
            changed += 1
        self.refresh()
        verb = "Favorited" if favorite else "Removed favorite mark from"
        self._show_toast(f"{verb} {changed} matching clip(s).")

    # --- Commit 2: single dispatch point for context-menu selection commands

    def _dispatch_selection_command(self, key: str, ctx) -> None:
        """The one place every selection-wide context-menu command (see
        core/menu_context.py's command_matrix) is dispatched from --
        commands never independently guess selection state or mode.
        """
        if key == "select_all_visible":
            self._keyboard_select_all()
            return
        if key == "select_all_matching":
            self._keyboard_select_all_matching()
            return
        if key == "deselect_all":
            self._clear_selection()
            return
        if key == "invert_visible":
            self._invert_visible_selection()
            return

        if ctx.selection_mode == "matching":
            matching_dispatch = {
                "export_selected": self._matching_export,
                "favorite_selected": lambda: self._matching_toggle_favorite(True),
                "unfavorite_selected": lambda: self._matching_toggle_favorite(False),
                "remove_favorite_marks": lambda: self._matching_toggle_favorite(False),
                "move_to_recently_removed": self._matching_move_to_recently_removed,
                "restore": self._matching_restore,
            }
            handler = matching_dispatch.get(key)
            if handler is not None:
                handler()
            return

        if ctx:
            target_ids = list(ctx.visible_selected_ids) if ctx.visible_selected_ids else ([ctx.clicked_clip_id] if ctx.clicked_clip_id else [])
            if target_ids:
                self._selected_clip_ids = target_ids
                self._selected_clip_id = target_ids[0]

        visible_dispatch = {
            "copy_selected": self._bulk_copy,
            "export_selected": self._bulk_export_proof,
            "favorite_selected": lambda: self._bulk_toggle_favorite(True),
            "unfavorite_selected": lambda: self._bulk_toggle_favorite(False),
            "remove_favorite_marks": lambda: self._bulk_toggle_favorite(False),
            "add_to_collection": self._bulk_add_to_collection,
            "remove_from_collection": self._bulk_remove_from_collection,
            "move_to_recently_removed": self._bulk_remove,
            "restore": self._bulk_restore,
        }
        handler = visible_dispatch.get(key)
        if handler is not None:
            handler()

    def _keyboard_focus_is_text_input(self, event=None) -> bool:
        widget = getattr(event, "widget", None)
        if widget is None:
            return False
        if isinstance(widget, str):
            try:
                widget = self.nametowidget(widget)
            except Exception:
                return False
        try:
            cls = widget.winfo_class()
            return cls in {"Entry", "Text"} or "Entry" in cls or "Textbox" in cls
        except Exception:
            return False

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

    def _open_item(self, clip_id: str) -> None:
        """Item-target "Open": the same type-based primary action as
        Enter-on-selected (_keyboard_primary_action), but for an
        explicit clip_id -- used by the matching-mode context menu's
        "Open", which must always act on the clicked clip, never the
        whole matching selection."""
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if clip.classification == models.CLASS_LINK:
            self._open_clip_link(clip.id)
        elif clip.content_type != models.CONTENT_IMAGE:
            self._edit_clip_text(clip.id)
        else:
            self._copy_again(clip.id)

    def _preview_item(self, clip_id: str) -> None:
        """Item-target "Preview": shows the clicked clip in the inspector
        panel without changing _selected_clip_ids/_selected_clip_id --
        previewing must not itself act as a selection command."""
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        self._preview.set_usage_events(self.vault.clip_usage_events(clip.id))
        self._preview.show(clip)

    def _keyboard_primary_action(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        clip = self._selected_clip()
        if clip is None:
            return "break"
        if clip.classification == models.CLASS_LINK:
            self._open_clip_link(clip.id)
        elif clip.content_type != models.CONTENT_IMAGE:
            # Enter on selected text clip = Edit Clip Text
            self._edit_clip_text(clip.id)
        else:
            self._copy_again(clip.id)
        return "break"

    def _keyboard_duplicate_selected(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if self._block_if_matching_active("Duplicate"):
            return "break"
        clip = self._selected_clip()
        if clip is not None:
            self._duplicate_as_editable_clip(clip.id)
        return "break"

    def _on_clip_double_click(self, clip: Clip) -> None:
        if not self._guard_unlocked():
            return
        if clip.content_type == models.CONTENT_IMAGE:
            self._open_photo_viewer(clip.id)
        elif clip.classification == models.CLASS_LINK:
            self._open_clip_link(clip.id)
        else:
            self._edit_clip_text(clip.id)

    def _add_to_link_batch(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        if not hasattr(self, "_link_batch_ids"):
            self._link_batch_ids = []
        if clip_id not in self._link_batch_ids:
            self._link_batch_ids.append(clip_id)
        self._show_toast(f"Link added to batch. ({len(self._link_batch_ids)} link(s) in batch)")

    def _keyboard_copy_selected(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if self._block_if_matching_active("Copy"):
            return "break"
        if len(self._selected_clip_ids) > 1:
            self._bulk_copy()
            return "break"
        clip = self._selected_clip()
        if clip is not None:
            self._copy_again(clip.id)
        return "break"

    def _keyboard_copy_clean_selected(self, event=None):
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if self._block_if_matching_active("Copy"):
            return "break"
        clip = self._selected_clip()
        if clip is not None:
            self._copy_clean(clip.id, copy_clean.COPY_PLAIN_TEXT)
        return "break"

    def _keyboard_remove_selected(self, event=None):
        """Delete: routes only to the existing safe soft-remove path
        (Recently Removed), never to permanent deletion. While a
        matching selection is active this refuses to run rather than
        silently soft-removing only the up-to-120 rendered/visible ids
        while the "All N matching" banner is still showing a larger
        claimed set -- see _block_if_matching_active.
        """
        if self._keyboard_focus_is_text_input(event) or not self._guard_unlocked():
            return None
        if self._block_if_matching_active("Remove"):
            return "break"
        if len(self._selected_clip_ids) > 1:
            self._bulk_remove()
            return "break"
        clip = self._selected_clip()
        if clip is not None:
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
        self._selected_clip_ids = []
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

    def _require_founder(self, feature_key: str) -> bool:
        if feature_gate.requires_feature(feature_key):
            return True
        FounderPromptDialog(
            self,
            feature_key,
            on_enter_license=self._open_founder,
            on_learn_more=self._open_founder,
        )
        return False

    def _open_founder(self) -> None:
        FounderDialog(self, on_license_changed=self.refresh)

    def _open_receipts_folder(self) -> None:
        from ..core.settings import default_settings_path
        from ..core import pathutil
        folder = default_settings_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        pathutil.open_path(str(folder))

    def _export_selected_or_view(self) -> None:
        if not self._require_founder("exports_advanced"):
            return
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
        from ..core.mobile.mobile_access_controller import relative_timestamp

        summary = self.vault.dashboard_summary()
        # Use controller for canonical state
        ctrl = self._mobile_controller
        local_ip = "—"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except OSError:
            pass
        receipts = self._mobile_bridge.receipts.recent(5)
        raw_ts = receipts[0].get("timestamp") if receipts else None
        last_connection = relative_timestamp(raw_ts) if raw_ts else "—"
        last_connection_raw = raw_ts or "—"
        pairing = (
            f"{summary.get('paired_count', 0)} device(s) paired"
            if summary.get("paired_count")
            else "No devices paired"
        )
        routes: dict[str, bool] = {}
        port = int(summary.get("mobile_port") or 8742)
        if ctrl.listening:
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
        # Build device list for the page
        from ..core.mobile.compatibility import evaluate_compatibility

        devices = []
        for d in self._mobile_bridge.all_devices():
            entry = {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "app_version": d.app_version or "Unknown",
                "platform": d.platform or "Android",
                "last_seen": relative_timestamp(d.last_seen_at),
                "last_seen_raw": d.last_seen_at or "",
                "is_active": d.is_active,
                "revoked": d.revoked_at is not None,
            }
            # Compatibility only applies to devices that declared a mobile
            # platform at pairing time — the desktop CLI pairs itself as a
            # device too but never participates in this handshake.
            if d.platform:
                compat = evaluate_compatibility(d.protocol, d.app_version)
                entry["protocol"] = d.protocol
                entry["compatibility_state"] = compat.state
                entry["compatible"] = compat.compatible
                entry["update_required"] = compat.update_required
            devices.append(entry)
        return {
            "summary": summary,
            "local_ip": local_ip,
            "pairing_status": pairing,
            "last_connection": last_connection,
            "last_connection_raw": last_connection_raw,
            "routes": routes,
            "mdns_advertising": ctrl.advertising,
            "controller_enabled": ctrl.enabled,
            "controller_listening": ctrl.listening,
            "controller_status": ctrl.status_text,
            "controller_error": ctrl.last_error,
            "devices": devices,
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
        self._page_header.set_content("Command Center")
        self._page_header.set_actions()
        self._home.grid()
        self._update_inspector_visibility()

    def _show_clips(self) -> None:
        self._home.grid_remove()
        self._vault_screens.hide()
        self._vault_screens.grid_remove()
        self._toolbar.grid()
        self._page_header.set_content(self._filters.active_label)
        self._page_header.set_actions()
        self._page_header.set_status_chips([])
        if self._view_mode == "grid":
            self._list.grid_remove()
            self._grid.grid()
        else:
            self._grid.grid_remove()
            self._list.grid()
        self._update_inspector_visibility()

    def _update_clip_surface_chrome(
        self, active: str, total_clips: int, query,
    ) -> None:
        """Keep All Clips title, status, and actions in one coherent hierarchy."""
        if active != FILTER_ALL:
            return

        noun = "clip" if total_clips == 1 else "clips"
        subtitle = (
            f"{total_clips} matching {noun}"
            if query is not None and query.text.strip()
            else f"{total_clips} {noun}"
        )
        chips = [
            "Active clips",
            f"View: {'Grid' if self._view_mode == 'grid' else 'Cards'}",
        ]
        if self._type_filter:
            chips.append(f"Type: {self._type_var.get()}")
        if self._sort_var.get() != "Newest Added":
            chips.append(f"Sort: {self._sort_var.get()}")
        if query is not None and query.text.strip():
            chips.insert(0, "Search active")
        self._page_header.set_content(self._filters.active_label, subtitle)
        self._page_header.set_status_chips(chips)
        if total_clips:
            self._page_header.set_actions(
                secondary_text="Clear all…",
                secondary_cmd=self._clear_all_from_header,
            )
        else:
            self._page_header.set_actions()

    def _clear_all_from_header(self) -> None:
        """Expose the recoverable clear action without changing its safety path."""
        if not self._guard_unlocked():
            return
        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            self, FILTER_ALL,
        )
        self._sidebar_clear_all_clips(ctx)

    def _show_vault_screen(self, key: str) -> None:
        self._home.grid_remove()
        self._list.grid_remove()
        self._grid.grid_remove()
        self._toolbar.grid_remove()
        self._page_header.set_content(self._filters.active_label)
        self._page_header.set_actions()
        self._page_header.set_status_chips([])
        self._vault_screens.grid()
        self._vault_screens.show(key)
        self._update_inspector_visibility()

    def _open_duplicate_review(self) -> None:
        if not self._require_founder("smart_filters_advanced"):
            return
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
            "view_larger": self._open_photo_viewer,
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
            "send_to_macro": self._send_to_macro_safe,
            "create_paste_macro": self._create_macro_from_clip,
            "get_storage": lambda: self.vault.storage,
            "close_inspector": self._close_inspector,
        }

    # --- data refresh ------------------------------------------------------
    def _cancel_all_refreshes(self) -> None:
        """Kill any pending background render jobs before starting a new one."""
        if self._search_job:
            try:
                self.after_cancel(self._search_job)
            except Exception:  # noqa: BLE001
                pass
            self._search_job = None

        if self._capture_refresh_job:
            try:
                self.after_cancel(self._capture_refresh_job)
            except Exception: # noqa: BLE001
                pass
            self._capture_refresh_job = None

        self._list.cancel_render()
        self._grid.cancel_render()

    def _recent_cleanup_cutoff_iso(self) -> str:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=cleanup_suggestions.RECENT_PROTECTION_MINUTES,
        )
        return cutoff.isoformat()

    def _cleanup_summary_dict(self) -> dict:
        """What the Home dashboard's Cleanup Suggestions card renders.
        Empty until the user has run at least one scan -- this app never
        scans automatically.
        """
        state = getattr(self, "_cleanup_scan_state", None)
        if not state or (state.get("result") is None and not state.get("failed")):
            return {}
        if state.get("failed") and not state.get("scanning"):
            return {
                "status": "Scan failed",
                "error_message": state.get("error_message") or "The scan could not complete.",
                "last_scan_label": state.get("finished_at_label", ""),
                "failed": True,
            }
        result = state["result"]
        return {
            "total_groups": result.total_groups,
            "total_reviewable_items": result.total_reviewable_items,
            "redundant_bytes_identified": result.redundant_bytes_identified,
            "last_scan_label": state.get("finished_at_label", ""),
            "status": "Scanning…" if state.get("scanning") else (
                "Cancelled" if result.cancelled else "Idle"
            ),
        }

    def _scan_cleanup_suggestions(self, *, reuse_generation: bool = False) -> None:
        """Background, cancellable scan for Vault Cleanup Suggestions --
        only ever runs when the user explicitly asks (Scan vault / Scan
        again), never automatically and never as part of the normal
        dashboard refresh. Uses a dedicated read-only connection (like the
        existing list-refresh worker) since this runs off the Tk thread
        while the main thread may be writing on the shared connection.

        [reuse_generation], when True, reuses the previous scan's
        scan_generation instead of minting a fresh one -- used only by the
        quiet rescan immediately after a Keep/Keep forever/Ignore decision,
        so a "keep" recorded against the scan currently on screen still
        suppresses on that immediate refresh. A real user-initiated scan
        (the Scan vault / Scan again button) always mints a fresh
        generation, which is what makes "keep" (unlike "keep forever")
        stop suppressing on the next real scan.
        """
        if not hasattr(self, "_cleanup_scan_state"):
            self._cleanup_scan_state = {"result": None, "scanning": False, "finished_at_label": ""}
        prior_cancel = getattr(self, "_cleanup_scan_cancel_event", None)
        if prior_cancel is not None:
            prior_cancel.set()  # cancel any still-running previous scan first

        # A monotonic request id, independent of cleanup_suggestions'
        # decision-suppression scan_generation: guards against a stale
        # (cancelled or merely slow) worker's completion callback landing
        # after a newer scan has already applied its result.
        self._cleanup_scan_request_id = getattr(self, "_cleanup_scan_request_id", 0) + 1
        my_request_id = self._cleanup_scan_request_id

        cancel_event = threading.Event()
        self._cleanup_scan_cancel_event = cancel_event
        self._cleanup_scan_state["scanning"] = True
        self._cleanup_scan_state["failed"] = False
        self._refresh_cleanup_ui()

        vault = self.vault
        cutoff = self._recent_cleanup_cutoff_iso()
        prior_result = self._cleanup_scan_state.get("result")
        reuse_scan_generation = (
            prior_result.scan_generation if (reuse_generation and prior_result is not None) else None
        )

        def worker() -> None:
            try:
                from ..core.vault_macros import MacroStore
                macro_store = MacroStore()
            except Exception:  # noqa: BLE001 -- macros are optional context, never fatal
                macro_store = None
            try:
                with vault.storage.reader_connection() as reader:
                    result = cleanup_suggestions.run_scan(
                        vault.storage,
                        conn=reader,
                        macro_store=macro_store,
                        recent_cutoff_iso=cutoff,
                        cancel_check=cancel_event.is_set,
                        scan_generation=reuse_scan_generation,
                    )
            except Exception as exc:  # noqa: BLE001
                message = f"{type(exc).__name__}: {exc}"
                self._call_on_main(
                    lambda: self._apply_cleanup_scan_failure(my_request_id, message),
                )
                return
            try:
                cleanup_receipts.record_scan_receipt(
                    vault.events,
                    rule_version=cleanup_suggestions.RULE_VERSION,
                    duplicate_group_count=len(result.duplicate_screenshot_groups),
                    repeated_text_group_count=len(result.repeated_text_groups),
                    tiny_image_count=len(result.tiny_images),
                    missing_or_damaged_count=len(result.missing_or_damaged),
                    largest_asset_count=len(result.largest_assets),
                    redundant_bytes_identified=result.redundant_bytes_identified,
                    cancelled=result.cancelled,
                )
            except Exception:  # noqa: BLE001 -- a receipt failure must never hide the scan result
                pass
            self._call_on_main(lambda: self._apply_cleanup_scan_result(my_request_id, result))

        threading.Thread(target=worker, name="cleanup-scan", daemon=True).start()

    def _rescan_cleanup_suggestions_quiet(self) -> None:
        """Re-run the scan after a Keep/Ignore/Move decision so the review
        screen reflects the new state, without any extra navigation. Reuses
        the on-screen scan's generation -- see _scan_cleanup_suggestions.
        """
        self._scan_cleanup_suggestions(reuse_generation=True)

    def _apply_cleanup_scan_result(self, request_id: int, result) -> None:
        if not self._alive():
            return
        if request_id != getattr(self, "_cleanup_scan_request_id", None):
            return  # a newer scan has since started; this result is stale
        self._cleanup_scan_state["result"] = result
        self._cleanup_scan_state["scanning"] = False
        self._cleanup_scan_state["failed"] = False
        self._cleanup_scan_state["finished_at_label"] = clip_metadata.format_captured_at(models.now_iso())
        self._refresh_cleanup_ui()

    def _apply_cleanup_scan_failure(self, request_id: int, error_message: str = "") -> None:
        if not self._alive():
            return
        if request_id != getattr(self, "_cleanup_scan_request_id", None):
            return  # a newer scan has since started; this failure is stale
        self._cleanup_scan_state["scanning"] = False
        self._cleanup_scan_state["failed"] = True
        self._cleanup_scan_state["error_message"] = error_message
        self._cleanup_scan_state["finished_at_label"] = clip_metadata.format_captured_at(models.now_iso())
        self._refresh_cleanup_ui()

    def _refresh_cleanup_ui(self) -> None:
        """Update whatever's currently showing that depends on the last
        scan: the cleanup screen itself (if built/open), and the Home
        dashboard card (via the normal debounced refresh, which threads
        _cleanup_summary_dict() into the existing home render call).
        """
        screen_host = getattr(self, "_vault_screens", None)
        if screen_host is not None:
            frame = screen_host._screens.get(NAV_CLEANUP_SUGGESTIONS)
            if frame is not None and hasattr(frame, "_cleanup_state"):
                frame._cleanup_state["result"] = self._cleanup_scan_state.get("result")
                frame._cleanup_state["scanning"] = self._cleanup_scan_state.get("scanning", False)
                if screen_host._active == NAV_CLEANUP_SUGGESTIONS:
                    frame._refresh()
        self.refresh()

    def _on_refresh_clicked(self) -> None:
        """Handler for the page-level Refresh control.

        Invokes the existing supported refresh path only. Overlap protection is
        the engine's job (refresh() coalesces a call made while a render is
        active into a single pending request and never spins up a second
        worker), so this deliberately adds no locking of its own -- it must not
        become a second refresh implementation.
        """
        if not self._alive():
            return
        self.refresh()

    def _set_refreshing(self, active: bool, *, error: bool = False) -> None:
        """Single choke point for refresh busy/idle presentation.

        Drives the existing non-blocking PageHeader indicator AND the page-level
        Refresh control together so the two can never drift: while a refresh is
        in flight the control shows a busy label and is disabled (which also
        makes an overlapping click impossible), and it returns to normal once
        the refresh settles -- on success or on the honest failure path, where
        the header keeps showing "Refresh failed — showing previous results".
        """
        self._page_header.set_refreshing(active, error=error)
        # Read via __dict__ rather than getattr(): CTk/tkinter override
        # __getattr__ to delegate unknown names to self.tk, so a plain
        # getattr(self, "_refresh_btn", None) does NOT return the default when
        # the attribute is absent (e.g. an early call, or the bare
        # object.__new__ stubs in tests/test_refresh_generation.py) -- it
        # recurses into self.tk and raises RecursionError. __dict__.get stays
        # a simple instance-attribute lookup.
        btn = self.__dict__.get("_refresh_btn")
        if btn is None:
            return
        try:
            if active:
                btn.configure(state="disabled", text=self._REFRESH_BUSY_LABEL)
            else:
                btn.configure(state="normal", text=self._REFRESH_LABEL)
        except Exception:  # noqa: BLE001 - widget may be mid-teardown
            pass

    def refresh(self, *, immediate: bool = False) -> None:
        """Debounced refresh — collapses rapid-fire calls into one actual render.

        While a refresh is actively rendering (worker query in flight, or
        its resulting widget batch still being built across after() ticks),
        a new call does not cancel and restart it.  Cancelling here would
        discard already-built rows and force a second full DB query + widget
        rebuild for what is often the exact same visible content.  Instead
        the latest requested state is recorded as one pending trailing
        request; when the active render finishes (_finish_active_refresh),
        exactly one more refresh runs, and only if that pending state is
        materially different from what was just rendered.
        """
        if not self._alive():
            return
        if self._render_active:
            self._pending_refresh_signature = self._current_refresh_signature()
            return

        if hasattr(self, "_refresh_job") and self._refresh_job:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:  # noqa: BLE001
                pass
            self._refresh_job = None

        if not hasattr(self, "_refresh_generation"):
            self._refresh_generation = 0
        self._refresh_generation += 1

        self._set_refreshing(True)

        if immediate:
            self._do_refresh_sync()
        else:
            self._refresh_job = self.after(50, self._do_refresh_sync)

    def _do_refresh_sync(self) -> None:
        """Kicks off a refresh: DB reads happen on the background refresh
        worker thread (see _refresh_worker_loop/_collect_refresh_snapshot),
        Tk widget work happens afterward on the main thread (see
        _apply_refresh_snapshot). Never do DB/network work directly in this
        method or its continuation -- that's the whole point of the split.
        """
        # Cancel our own pending after() job if this is being invoked
        # directly (e.g. by a test skipping the debounce) rather than by
        # that job firing -- otherwise the still-scheduled timer fires 50ms
        # later and enqueues a second, redundant refresh for the same
        # generation.
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:  # noqa: BLE001 - job may already be gone
                pass
        self._refresh_job = None
        if not self._alive():
            return
        tooltip.hide_tooltip()
        self._cancel_all_refreshes()
        if self._locked():
            self._render_locked_surface()
            self._lock_screen.lift()
            return

        active, query, _view_mode = self._current_refresh_signature()
        # Single choke point for matching-selection invalidation: every
        # context change that matters (search text, type/date filter,
        # sort, collection, nav tab, active-vs-Recently-Removed state)
        # flows through _build_query()+refresh() to get here, so checking
        # once, right here, covers all of them without hooking each
        # individual setter separately. Never silently reinterprets an old
        # matching selection against a new view.
        if self._selection_scope.invalidate_if_stale(active, query):
            self._set_selection_notice(None)
        gen = self._refresh_generation
        self._render_active = True
        self._refresh_workers_in_flight += 1
        self._refresh_request_queue.put((gen, active, query))

    def _current_refresh_signature(self):
        """Minimal state that determines rendered clip content and which
        widget renders it: active page/filter, the built search query
        (search text, type/date filters, sort, collection, matching-vs-
        visible mode -- everything _build_query() folds in), and grid-vs-
        list view mode.

        Layout mode (compact/standard/wide) is deliberately excluded: it
        only changes toolbar/column chrome, never which clips are queried
        or how a row's own content is built, so a layout-only refresh()
        call must not be treated as materially different from what is
        already on screen.
        """
        active = self._filters.active
        general_clips = active not in NAV_SCREEN_KEYS and active != FILTER_HOME
        query = self._build_query() if general_clips else None
        return (active, query, self._view_mode)

    def _finish_active_refresh(self, rendered_signature=None) -> None:
        """Called once the active refresh has fully finished -- either a
        synchronous render (home/nav-screen) or the last batch of a
        chunked clip-list/grid render. Runs at most one trailing refresh,
        and only if a request arrived during the active render whose state
        genuinely differs from what was just shown.
        """
        self._render_active = False
        pending = self._pending_refresh_signature
        self._pending_refresh_signature = None
        if pending is None:
            return
        if rendered_signature is not None and pending == rendered_signature:
            return
        self.refresh()

    def _abandon_active_refresh(self) -> None:
        """Called when a batched render is superseded before its last batch.

        That render's on_complete can never fire, so render ownership is
        released here instead. Without it _render_active stays True forever and
        refresh() only records _pending_refresh_signature -- whose sole consumer
        is _finish_active_refresh() -- so Search during a large-vault render
        would freeze the view part-way through the previous query, keeping its
        stale header counts and busy state.

        The pending signature is deliberately kept rather than consumed here:
        when the supersede came from a newer refresh, that refresh claims
        ownership on this same tick and consumes it normally.
        _resume_abandoned_refresh only steps in when nothing claimed ownership
        -- which is reachable without any refresh at all, e.g. clicking a
        date-group header (ClipList._toggle_group -> render -> clear ->
        cancel_render) or the lock surface, both of which cancel the chain
        without going through refresh(). It defers to idle so an abandon
        raised from inside a render can't re-enter render_batched underneath
        its own caller.
        """
        if not self._render_active:
            return
        self._render_active = False
        if self._pending_refresh_signature is not None:
            self.after_idle(self._resume_abandoned_refresh)

    def _resume_abandoned_refresh(self) -> None:
        if not self._alive() or self._render_active:
            return
        pending = self._pending_refresh_signature
        if pending is None:
            return
        self._pending_refresh_signature = None
        if pending != self._current_refresh_signature():
            self.refresh(immediate=True)

    def _refresh_worker_loop(self) -> None:
        """The one persistent background thread for this app instance.
        Processes refresh-snapshot requests one at a time, in the order
        refresh() calls arrived, for as long as the app is alive.
        """
        while True:
            item = self._refresh_request_queue.get()
            if item is None:
                return  # shutdown sentinel, see destroy()
            gen, active, query = item
            self._collect_refresh_snapshot(gen, active, query)

    def _collect_refresh_snapshot(self, gen: int, active: str, query) -> None:
        """Runs on the refresh worker thread: DB reads only, never touches
        Tk.

        Uses a dedicated read-only connection (VaultStorage.reader_connection)
        instead of the shared self.conn, which the main thread may be using
        concurrently for writes/event recording. Results are handed back to
        the Tk thread via _call_on_main -- nothing here may construct,
        configure, or destroy a widget.
        """
        if gen != self._refresh_generation:
            self._refresh_workers_in_flight = max(0, self._refresh_workers_in_flight - 1)
            return
        try:
            with self.vault.storage.reader_connection() as reader:
                counts = self.vault.counts(conn=reader)
                if gen != self._refresh_generation:
                    self._refresh_workers_in_flight = max(0, self._refresh_workers_in_flight - 1)
                    return
                clips = None
                total_clips = None
                if query is not None:
                    dedicated_reader = reader is not self.vault.storage.conn
                    if dedicated_reader:
                        reader.execute("BEGIN")
                    try:
                        clips = self.vault.list_clips(
                            query, limit=MAX_VISIBLE_CLIPS, conn=reader,
                        )
                        total_clips = self.vault.count_clips(query, conn=reader)
                    finally:
                        if dedicated_reader:
                            reader.execute("ROLLBACK")
        except Exception as exc:  # noqa: BLE001
            failure = exc
            self._call_on_main(lambda: self._apply_refresh_failure(gen, failure))
            return
        self._call_on_main(
            lambda: self._apply_refresh_snapshot(gen, active, query, counts, clips, total_clips)
        )

    def _apply_refresh_failure(self, gen: int, exc: Exception) -> None:
        self._refresh_workers_in_flight = max(0, self._refresh_workers_in_flight - 1)
        if gen != self._refresh_generation or not self._alive():
            return  # superseded by a newer refresh, or the window is gone
        write_crash("refresh", exc)
        self._set_refreshing(False, error=True)
        self._finish_active_refresh()

    def _apply_refresh_snapshot(
        self, gen: int, active: str, query, counts: dict, clips, total_clips,
    ) -> None:
        """Main-thread apply phase for a refresh started by _do_refresh_sync.

        Discards stale results: if a newer refresh() call has already
        bumped _refresh_generation since this worker started, or the window
        no longer exists, this is a no-op rather than overwriting newer
        state with an older snapshot.
        """
        self._refresh_workers_in_flight = max(0, self._refresh_workers_in_flight - 1)
        if gen != self._refresh_generation or not self._alive():
            return
        rendered_signature = (active, query, self._view_mode)
        try:
            from ..core import storage as S

            def _apply_dashboard_updates(counts):
                """Populate counts, filters, collections, safes — toolbar/sidebar
                chrome.  Only called once per snapshot, and may be deferred
                until after first content appears in the clip-content path."""
                summary = self.vault.dashboard_summary(counts=counts)
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
                self._filters.update_founder_status(licensing.load_license())
                return summary

            if active in NAV_SCREEN_KEYS:
                summary = _apply_dashboard_updates(counts)
                self._list.clear()
                self._grid.clear()
                self._show_vault_screen(active)
                clip_count = summary.get("all", 0)
                self._finish_active_refresh(rendered_signature)
            elif active == FILTER_HOME:
                summary = _apply_dashboard_updates(counts)
                self._list.clear()
                self._grid.clear()
                self._show_home()
                capture_active = not summary.get("capture_paused")
                status_text = "● Capture Active" if capture_active else "● Capture Paused"
                mobile_on = bool(summary.get("mobile_enabled"))
                mobile_text = f"● Mobile Access ({summary.get('paired_count', 0)} paired)" if mobile_on else "● Mobile Access Off"
                self._page_header.set_status_chips([
                    status_text,
                    "● Receipts Active",
                    f"● {brand.VAULT_STATUS_ACTIVE}",
                    mobile_text,
                    f"● {brand.LABEL_LOCAL_ONLY}"
                ])
                q_recent = search.SearchQuery(filter_name=S.FILTER_ALL, sort=models.SORT_NEWEST_ADDED)
                q_fav = search.SearchQuery(filter_name=S.FILTER_FAVORITES, sort=models.SORT_NEWEST_ADDED)
                q_img = search.SearchQuery(filter_name=S.FILTER_SCREENSHOTS, sort=models.SORT_NEWEST_ADDED)
                q_today = search.SearchQuery(date_added_preset="today")
                q_links = search.SearchQuery(type_filter=models.CLASS_LINK)
                image_ready = self.vault.storage.asset_storage_ready()
                self._home._image_ready = image_ready  # noqa: SLF001

                all_recent = self.vault.list_clips(q_recent, limit=HOME_RECENT_WINDOW)
                today_clips = self.vault.list_clips(q_today, limit=HOME_RECENT_WINDOW)
                link_clips = self.vault.list_clips(q_links, limit=6)
                receipts = [c for c in all_recent if c.content_hash][:6]
                sensitive_items = [c for c in all_recent if c.is_sensitive][:6]

                self._home.render(
                    summary,
                    all_recent[:8],
                    self.vault.list_clips(q_fav, limit=6),
                    self.vault.list_clips(q_img, limit=6),
                    today_clips=today_clips,
                    link_clips=link_clips,
                    receipts=receipts,
                    sensitive_items=sensitive_items,
                    cleanup_summary=self._cleanup_summary_dict(),
                )
                if self._preview._clip is None:  # noqa: SLF001
                    self._preview.show_vault_control(
                        summary,
                        self._vault_panel_callbacks(),
                    )
                clip_count = summary.get("all", 0)
                self._finish_active_refresh(rendered_signature)
            else:
                # Build the first row immediately so content is visible ASAP.
                # Toolbar/chrome updates happen after — they update the
                # header/sidebar but don't affect which clip rows appear.
                self._visible_clip_ids = [c.id for c in clips]
                empty_msg = self._empty_message(active, clips, query)
                view = self._grid if self._view_mode == "grid" else self._list
                other = self._list if self._view_mode == "grid" else self._grid
                more_count = total_clips - len(clips)
                other.clear()

                if self._selection_scope.mode == "matching":
                    def on_complete(v=view, sig=rendered_signature):  # noqa: E731
                        self._paint_matching_selection_visuals(v)
                        self._finish_active_refresh(sig)
                    if self._view_mode == "grid":
                        self._grid.render_batched(
                            clips, empty_message=empty_msg, more_count=more_count,
                            on_complete=on_complete, generation=gen,
                            on_superseded=self._abandon_active_refresh,
                        )
                    else:
                        self._list.render_batched(
                            clips,
                            empty_message=empty_msg,
                            group_by=self._group_by_for_view(active, query),
                            more_count=more_count,
                            on_complete=on_complete, generation=gen,
                            on_superseded=self._abandon_active_refresh,
                        )
                else:
                    self._selected_clip_ids = [
                        cid for cid in self._selected_clip_ids if cid in self._visible_clip_ids
                    ]
                    if self._selected_clip_id not in self._visible_clip_ids:
                        self._selected_clip_id = self._visible_clip_ids[0] if self._visible_clip_ids else None
                    def _finish(sig=rendered_signature):
                        self._finish_active_refresh(sig)
                    if self._view_mode == "grid":
                        self._grid.set_selected(self._selected_clip_id)
                        self._grid.render_batched(
                            clips, empty_message=empty_msg, more_count=more_count,
                            on_complete=_finish, generation=gen,
                            on_superseded=self._abandon_active_refresh,
                        )
                        self._grid.set_selected(self._selected_clip_id)
                    else:
                        self._list.set_selected(self._selected_clip_id)
                        self._list.render_batched(
                            clips,
                            empty_message=empty_msg,
                            group_by=self._group_by_for_view(active, query),
                            more_count=more_count,
                            on_complete=_finish, generation=gen,
                            on_superseded=self._abandon_active_refresh,
                        )
                        self._list.set_selected(self._selected_clip_id)
                    clip = self.vault.storage.get_clip(self._selected_clip_id) if self._selected_clip_id else None
                    self._update_selected_action_strip(clip)
                    self._preview.show(clip)

                # Now make the view visible and update toolbar/chrome.
                # The first row is already built; _show_clips maps the parent
                # so the row becomes visible immediately.
                self._show_clips()
                clip_noun = "clip" if total_clips == 1 else "clips"
                self._page_header.set_content(self._filters.active_label, f"{total_clips} {clip_noun}")
                self._update_clip_surface_chrome(active, total_clips, query)
                clip_count = total_clips

                # Dashboard/filter updates are deferred until after the first
                # clip row is already on screen — they update navbar/sidebar
                # chrome, not clip content.
                summary = _apply_dashboard_updates(counts)

            summary["shown"] = clip_count
            summary["default_safe"] = self.vault.settings.default_safe_id
            summary["mobile_status_text"] = self._mobile_controller.status_text
            self._control_strip.update_state(summary)
            if self._locked():
                self._lock_screen.lift()
            self._set_refreshing(False)
        except Exception as exc:  # noqa: BLE001
            write_crash("refresh", exc)
            self._set_refreshing(False, error=True)
            # Safety net: if the exception happened before any of the
            # branch-specific _finish_active_refresh() calls above ran (or
            # before an async render_batched's on_complete could ever
            # fire), _render_active would otherwise stay stuck True and
            # every future refresh() call would silently just record a
            # pending signature forever. If a batch was already scheduled
            # and its own on_complete later fires too, this is a harmless
            # no-op the second time (pending is already consumed).
            self._finish_active_refresh()

    def _render_locked_surface(self) -> None:
        self._selected_clip_id = None
        self._visible_clip_ids = []
        self._filters.update_counts({})
        self._filters.update_collections([])
        self._filters.update_safes([])
        self._home.grid_remove()
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
            "mobile_status_text": "Off",
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
                on_create=self._create_safe_if_allowed,
            )
            return
        self._manual_save_to_safe(payload, picked[0])

    def _manual_save_to_safe(self, payload: dict, safe_id: str) -> None:
        detected = multi_link.detect_multi_link_payload(payload.get("text", ""))
        if detected is not None:
            self._open_multi_link_dialog(payload, safe_id, detected)
            return
        self._save_payload(
            payload,
            safe_id=safe_id,
            capture_mode=models.CAPTURE_MANUAL_SAVE_HOTKEY,
            force=True,
        )
        self._show_toast("Clipboard saved to Safe.")

    def _open_multi_link_dialog(
        self,
        payload: dict,
        safe_id: str,
        detected: multi_link.MultiLinkPayload,
    ) -> None:
        def save_text_clip() -> None:
            self._save_payload(
                payload,
                safe_id=safe_id,
                capture_mode=models.CAPTURE_MANUAL_SAVE_HOTKEY,
                force=True,
            )
            self._show_toast("Saved raw link paste as one text clip.")

        def save_separate() -> None:
            self._save_multi_link_batch(
                detected,
                safe_id=safe_id,
                source_app=payload.get("source_app"),
                source_window=payload.get("source_window"),
                batch_label="Saved links as separate clips.",
            )

        def copy_list() -> None:
            self._copy_generated_text(
                multi_link.one_per_line(detected),
                "Copied clean download list.",
            )

        def create_batch() -> None:
            self._save_multi_link_batch(
                detected,
                safe_id=safe_id,
                source_app=payload.get("source_app"),
                source_window=payload.get("source_window"),
                batch_label="Saved link batch with raw receipt.",
            )

        MultiLinkPasteDialog(
            self,
            payload=detected,
            on_separate=save_separate,
            on_text_clip=save_text_clip,
            on_copy_list=copy_list,
            on_batch=create_batch,
        )

    def _save_multi_link_batch(
        self,
        detected: multi_link.MultiLinkPayload,
        *,
        safe_id: str,
        source_app: str | None,
        source_window: str | None,
        batch_label: str,
    ) -> None:
        # Keep the original raw paste as a receipt clip before saving each URL.
        self.vault.capture(
            detected.raw_text,
            source_app=f"{brand.PRODUCT_NAME} Multi-Link Receipt",
            source_window=source_window,
            capture_mode=models.CAPTURE_EXTERNAL_APP,
            safe_id=safe_id,
            force=True,
        )
        saved = 0
        for url in detected.urls:
            clip = self.vault.capture(
                url,
                source_app=source_app,
                source_window=source_window,
                capture_mode=models.CAPTURE_MANUAL_SAVE_HOTKEY,
                safe_id=safe_id,
                force=True,
            )
            if clip is not None:
                saved += 1
        self.refresh()
        self._show_toast(f"{batch_label} {saved} link{'s' if saved != 1 else ''} saved.")

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
            on_create=self._create_safe_if_allowed,
        )

    def _ignore_next_copy(self) -> None:
        if not self._guard_unlocked():
            return
        self._capture_ctrl.arm_ignore_next()
        self._show_toast("Next copy will not be saved.")

    def _on_search_focus_in(self, _event=None) -> None:
        self._search_placeholder_focused = True
        try:
            self._search_field_wrap.configure(border_color=brand.PROOF_TEAL)
        except Exception:  # noqa: BLE001 — cosmetic only, must not break focus
            pass
        self._update_search_placeholder()

    def _on_search_focus_out(self, _event=None) -> None:
        self._search_placeholder_focused = False
        try:
            self._search_field_wrap.configure(border_color=brand.VAULT_BORDER)
        except Exception:  # noqa: BLE001 — cosmetic only, must not break focus
            pass
        self._update_search_placeholder()

    def _update_search_placeholder(self) -> None:
        """Show the "Search clips…" overlay only while the field is empty and
        unfocused (standard placeholder behavior). Driven manually because
        CTkEntry suppresses its own placeholder when a textvariable is bound."""
        label = getattr(self, "_search_placeholder", None)
        if label is None:
            return
        try:
            empty = self._search_var.get() == ""
            show = empty and not getattr(self, "_search_placeholder_focused", False)
            if show:
                # Sit just right of the magnifier icon, vertically centered.
                label.place(relx=0, rely=0.5, x=34, anchor="w")
            else:
                label.place_forget()
        except Exception:  # noqa: BLE001 — cosmetic only
            pass

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
        # Show/hide the cross-view search scope banner.
        try:
            if self._search_var.get().strip():
                self._search_scope_banner.pack(fill="x", padx=8, pady=(0, 4))
            else:
                self._search_scope_banner.pack_forget()
        except Exception:  # noqa: BLE001
            pass
        self.refresh()


    def _on_window_configure(self, event) -> None:
        """Throttle layout-heavy work during window resizing."""
        if event.widget != self:
            return
        w, h = event.width, event.height
        if w == self._last_width and h == self._last_height:
            return
        self._last_width, self._last_height = w, h

        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(150, self._handle_resize_debounced)

    def _handle_resize_debounced(self) -> None:
        self._resize_job = None
        if not self._alive() or self._locked():
            return

        # Responsive check
        w = self.winfo_width()

        if w >= 1500:
            layout_mode = "wide"
        elif w >= 1150:
            layout_mode = "standard"
        else:
            layout_mode = "compact"

        current_mode = getattr(self, "_current_layout_mode", None)
        if current_mode != layout_mode:
            self._current_layout_mode = layout_mode
            self._apply_layout_mode(layout_mode)

    def _apply_layout_mode(self, mode: str) -> None:
        # Column sizing is applied here immediately so the layout doesn't
        # visibly jump; actual preview grid/place/hidden state is decided
        # solely by _update_inspector_visibility (called synchronously below)
        # so there is exactly one authority for whether the panel is showing.
        if mode == "compact":
            self.grid_columnconfigure(2, minsize=0, weight=0)
        else:
            self.grid_columnconfigure(2, weight=0, minsize=400 if mode == "wide" else 320)

        self._set_toolbar_compact(mode)
        self._update_inspector_visibility()

        if hasattr(self._home, "set_layout_mode"):
            self._home.set_layout_mode(mode)

        # During a resize, we don't want to rebuild the entire clip list if possible.
        # But we might need to tell elements to wrap or adjust.
        # For now, we'll just refresh, but Phase A batched render will make this cheap.
        self.refresh()

    def _set_toolbar_compact(self, mode: str) -> None:
        """Drop the least-essential toolbar chrome at narrow widths instead of
        letting the global toolbar clip or extend past the window edge.

        Every action stays reachable either way: at non-wide widths,
        Stamped Receipts, Capture Rules, and Quick Actions move into the
        "More" overflow menu (_open_top_overflow_menu) rather than being
        removed outright.

        VaultControlStrip's own content (Capture/Mobile/Receipts dropdowns
        + Default Safe label + Lock + Quick Actions) is wide enough that,
        combined with the outer top bar's fixed-width buttons, "standard"
        mode (not just "compact") is too narrow to fit everything without
        clipping. winfo_ismapped() alone doesn't catch this -- a widget
        Tk still "manages" can be positioned past its own parent frame's
        boundary and get silently clipped there, at any of the four
        breakpoint-adjacent widths measured (900x600 / 1000x650 / 1100x700
        against the 1150-1499 "standard" floor). So Default Safe, Stamped
        Receipts, Capture Rules, and Quick Actions are all dropped in
        "standard" as well as "compact" -- only "wide" keeps the complete,
        uncollapsed toolbar. Lock stays a direct, always-visible button at
        every width (never moved into the overflow menu); it fits once the
        wider dropdowns/buttons above stop competing with it for
        VaultControlStrip's own allotted column width.
        """
        if not hasattr(self, "_view_label"):
            return
        compact = mode == "compact"
        not_wide = mode != "wide"
        if compact:
            self._view_label.pack_forget()
            self._selection_hint_label.pack_forget()
        else:
            if not self._view_label.winfo_ismapped():
                self._view_label.pack(side="right", padx=(4, 2), before=self._grid_btn)
            if not self._selection_hint_label.winfo_ismapped():
                self._selection_hint_label.pack(side="left", padx=(6, 0))
        if not_wide:
            self._top_receipts_btn.grid_remove()
            self._top_capture_rules_btn.grid_remove()
            self._top_more_btn.grid(row=0, column=2, columnspan=2, padx=4)
        else:
            self._top_more_btn.grid_remove()
            self._top_receipts_btn.grid(row=0, column=2, padx=4)
            self._top_capture_rules_btn.grid(row=0, column=3, padx=4)
        self._control_strip.set_compact(not_wide)
        self._control_strip.set_lock_label_compact(compact)
        self._control_strip.set_quick_actions_compact(not_wide)

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
        if key == NAV_FOUNDER:
            self._open_founder()
            return
        if key == NAV_NEW_SAFE:
            self._open_new_safe()
            return
        gate = _FOUNDER_NAV_GATES.get(key)
        if gate and not self._require_founder(gate):
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

        self._clear_selection()
        if getattr(self, "_current_layout_mode", None) == "compact":
            self._close_inspector()

        self.refresh()

    def _navigate_back(self, event=None) -> None:
        if self._keyboard_focus_is_text_input(event) or self._locked():
            # Locked back returns to safe home if not already there,
            # or does nothing if history is empty.
            return
        if not self._nav_history:
            return

        current = self._filters.active
        prev = self._nav_history.pop()
        self._nav_forward_stack.append(current)
        self._navigate_screen(prev, record_history=False)

    def _navigate_forward(self, event=None) -> None:
        if self._keyboard_focus_is_text_input(event) or self._locked() or not self._nav_forward_stack:
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
            # Search text is part of the matching-selection signature; the
            # next refresh() this triggers would invalidate it anyway, but
            # clear it (and its banner) immediately rather than leaving a
            # stale "All N matching" notice on screen until that refresh
            # actually lands.
            self._selection_scope.clear()
            self._set_selection_notice(None)
            return

        # 4. Clear selection (single, multi, or matching) without
        # re-rendering the list.
        if self._selected_clip_ids or self._selected_clip_id or self._selection_scope.mode != "none":
            self._clear_selection()
            self._preview.show(None)
            return

    def _exit_matching_selection_if_manual(self) -> None:
        """Enforces "exactly one active selection mode": any real manual
        selection action (plain click, Ctrl-click, Shift-click, a
        right-click that collapses to a single item, Ctrl+A) must make
        visible selection authoritative again, clearing a stale matching
        selection and its banner rather than leaving both "active" at
        once. The one deliberate exception -- painting the rendered
        subset of a brand-new matching selection -- brackets its own
        view.select_all() call with _suppress_matching_exit_on_selection_change
        so it doesn't immediately cancel itself; merely re-rendering
        existing rows (e.g. after a same-context refresh) never calls
        this at all, since that path doesn't go through the view's
        on_select/on_selection_change callbacks.
        """
        if self._suppress_matching_exit_on_selection_change:
            return
        if self._selection_scope.mode != "none":
            self._selection_scope.clear()
            self._set_selection_notice(None)

    def _on_clip_select(self, clip) -> None:
        if not self._guard_unlocked():
            return
        self._exit_matching_selection_if_manual()
        self._selected_clip_id = getattr(clip, "id", None)
        self._selected_clip_ids = [self._selected_clip_id] if self._selected_clip_id else []
        self._list.set_selected(self._selected_clip_id)
        self._grid.set_selected(self._selected_clip_id)
        self._home.set_selected(self._selected_clip_id)
        self._update_selected_action_strip(clip)
        if clip is not None:
            self._preview.set_usage_events(self.vault.clip_usage_events(clip.id))
        self._preview.show(clip)
        self._update_inspector_visibility()

    def _on_clip_selection_change(self, ids: list[str]) -> None:
        """Multi-selection (Ctrl/Shift click) reported from the list/grid.

        Unlike ``_on_clip_select`` this does NOT call ``set_selected`` on the
        originating view — that would collapse the painted multi-selection back
        to a single row. The view has already painted itself; here we only sync
        shell state, the preview (showing the primary/most-recent row), and the
        action strip (bulk when more than one is selected).
        """
        if not self._guard_unlocked():
            return
        self._exit_matching_selection_if_manual()
        self._selected_clip_ids = list(ids)
        primary_id = ids[-1] if ids else None
        self._selected_clip_id = primary_id
        from ..core.storage import FILTER_HOME
        if self._filters.active != FILTER_HOME:
            self._home.set_selected(primary_id)
        primary = self.vault.storage.get_clip(primary_id) if primary_id else None
        if len(ids) > 1:
            self._update_bulk_action_strip(self._selected_clip_ids)
        else:
            self._update_selected_action_strip(primary)
        if primary is not None:
            self._preview.set_usage_events(self.vault.clip_usage_events(primary.id))
        self._preview.show(primary)
        self._update_inspector_visibility()

    def _on_home_batch_action(self, action: str, ids: list[str]) -> None:
        if not ids:
            return
        self._selected_clip_ids = list(ids)
        if action == "copy":
            self._bulk_copy_format("plain")
        elif action == "copy_md":
            self._bulk_copy_format("markdown")
        elif action == "move_safe":
            self._bulk_move_to_safe()
        elif action == "save_images":
            self._bulk_save_images()
        elif action == "export_zip":
            self._bulk_export_zip()
        elif action == "copy_paths":
            self._bulk_copy_paths()
        elif action == "copy_text_links":
            self._bulk_copy_text_links()
        elif action == "combine":
            self._open_clip_composer()
        elif action == "receipt":
            from ..core.selection import analyze_selection
            clips = [self.vault.storage.get_clip(cid) for cid in ids]
            self._bulk_create_receipt(analyze_selection([clip for clip in clips if clip]))
        elif action == "export_selection":
            self._bulk_export_bundle()
        elif action == "delete":
            self._bulk_remove()
        self._home.clear_selection()
        self.refresh()

    def _close_inspector(self) -> None:
        self._selected_clip_id = None
        self._selected_clip_ids = []
        if self._view_mode == "grid":
            self._grid.set_selected(None)
        else:
            self._list.set_selected(None)
        self._home.set_selected(None)
        self._update_selected_action_strip(None)
        self._preview.show(None)
        if getattr(self, "_current_layout_mode", None) == "compact":
            self._preview.place_forget()
        self._update_inspector_visibility()
        self.refresh()

    def _update_inspector_visibility(self) -> None:
        """Single source of truth for inspector visibility (docked/slide-over/hidden).

        Rules: non-clip vault screens (Hotkey Actions, Mobile Access, etc.) never
        show the inspector. Editable Copies is the one exception — it shows the
        inspector once a revision's original clip has been explicitly selected
        in place. Every other page (Command Center, All Clips, Today/Week/Older)
        shows the inspector only when a clip is selected, docked at
        standard/wide width or as a compact slide-over.
        """
        active = self._filters.active
        always_hidden_screens = NAV_SCREEN_KEYS - {NAV_EDITABLE_COPIES}
        if active in always_hidden_screens:
            has_selection = False
        else:
            has_selection = self._selected_clip_id is not None

        self._preview.place_forget()
        if not has_selection:
            self._preview.grid_remove()
            self.grid_columnconfigure(2, minsize=0)
            return

        compact = getattr(self, "_current_layout_mode", None) == "compact"
        if compact:
            self._preview.grid_remove()
            self.grid_columnconfigure(2, minsize=0)
            self._preview.configure(width=360)
            self._preview.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
            self._preview.lift()
        else:
            wide = getattr(self, "_current_layout_mode", None) == "wide"
            self._preview.grid(row=1, column=2, sticky="nsew")
            self.grid_columnconfigure(2, minsize=400 if wide else 320)

    def _clear_filters(self) -> None:
        self._search_var.set("")
        self._type_var.set("All Types")
        self._sort_var.set("Newest Added")
        self._date_added_preset = None
        self._date_used_preset = None
        self.refresh()

    def _set_selection_hint(self, text: str) -> None:
        label = getattr(self, "_selection_hint_label", None)
        if label is not None:
            label.configure(text=text)

    def _update_bulk_action_strip(self, ids: list[str]) -> None:
        """Render the action strip for a multi-clip selection."""
        if not hasattr(self, "_selected_action_frame"):
            return
        for btn in getattr(self, "_selected_action_buttons", []):
            btn.destroy()
        self._selected_action_buttons = []
        if self._locked() or len(ids) < 2:
            self._selected_action_frame.pack_forget()
            self._set_selection_hint(brand.SELECTION_HINT)
            self._selected_action_label.configure(text="")
            return
        self._selected_action_frame.pack(side="left", padx=(8, 4))
        # Count is carried by the label; drop the hint to keep the strip compact.
        self._set_selection_hint("")

        clips = []
        for cid in ids:
            clip = self.vault.storage.get_clip(cid)
            if clip is not None:
                clips.append(clip)

        from ..core.selection import analyze_selection
        summary = analyze_selection(clips)
        # Keep static check happy: text=f"{len(ids)} selected"
        self._selected_action_label.configure(text=f"{len(ids)} clips selected")

        actions = []
        if summary.text_count or summary.link_count:
            copy_command = (
                self._open_clip_composer
                if summary.selection_class in ("link_only", "text_only")
                else self._bulk_copy_text_links
            )
            actions.append(("Copy Combined Text", copy_command))
        actions.extend([
            ("Create Proof Receipt", lambda: self._bulk_create_receipt(summary)),
            ("Export Selection", self._bulk_export_bundle),
        ])
        if summary.image_count:
            actions.append(("Save Images", self._bulk_save_images))
        actions.append((
            "More…",
            lambda: self._open_bulk_clip_menu(
                ids,
                self._selected_action_frame.winfo_rootx(),
                self._selected_action_frame.winfo_rooty() + self._selected_action_frame.winfo_height(),
            ),
        ))
        for text, command in actions:
            btn = ctk.CTkButton(
                self._selected_action_frame,
                text=text,
                width=92,
                height=24,
                command=command,
                **theme.secondary_button(),
            )
            btn.pack(side="left", padx=2)
            self._selected_action_buttons.append(btn)

    def _bulk_copy_format(self, format_name: str) -> None:
        batch_actions.bulk_copy_format(self, format_name)

    def _bulk_create_receipt(self, summary) -> None:
        batch_actions.bulk_create_receipt(self, summary)

    def _bulk_copy_images(self) -> None:
        batch_actions.bulk_copy_images(self)

    def _bulk_save_images(self) -> None:
        batch_actions.bulk_save_images(self)

    def _bulk_export_zip(self) -> None:
        batch_actions.bulk_export_zip(self)

    def _bulk_copy_paths(self) -> None:
        batch_actions.bulk_copy_paths(self)

    def _bulk_view_proof(self) -> None:
        batch_actions.bulk_view_proof(self)

    def _bulk_export_bundle(self) -> None:
        batch_actions.bulk_export_bundle(self)

    def _bulk_copy_text_links(self) -> None:
        batch_actions.bulk_copy_text_links(self)

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
                    Toast(self, brand.TOAST_VAULT_IMAGE_COPIED)
                else:
                    Toast(self, "◈ Image copied to clipboard — paste in an image-capable app")
            return
        content = self.vault.copied_again(clip_id)
        if content is None:
            return
        copied = clipboard_out.write_via_tk(self, content)
        self._monitor.note_local_copy(copied)

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
        self._monitor.note_local_copy(clipboard_out.write_via_tk(self, meta))

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
        self._monitor.note_local_copy(clipboard_out.write_via_tk(self, text))
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

    def _edit_clip_text(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None or clip.content_type == models.CONTENT_IMAGE:
            return
        EditClipTextDialog(
            self,
            title="Edit Clip Text",
            initial_text=clip.content or "",
            on_save=lambda text, c=clip: self._save_generated_clip(text, c.safe_id),
        )

    def _duplicate_as_editable_clip(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None or clip.content_type == models.CONTENT_IMAGE:
            return
        EditClipTextDialog(
            self,
            title="Duplicate as Editable Clip",
            initial_text=clip.content or "",
            on_save=lambda text, c=clip: self._save_generated_clip(text, c.safe_id),
        )

    def _copy_receipt_summary(self, row) -> None:
        if not self._guard_unlocked():
            return
        text = copy_clean.receipt_summary(row)
        self._monitor.note_local_copy(clipboard_out.write_via_tk(self, text))
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
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Expire Now",
            "Immediately expire this clip? It will be treated as expired "
            "and may be auto-removed on the next expiry sweep.",
            parent=self,
        )
        if not ok:
            return
        self.vault.expire_now(clip_id)
        self.refresh()
        self._preview.show(None)

    def _remove_from_history(self, clip_id: str) -> None:
        """Remove a clip from history. Confirms for any removal.

        Never deletes any real file/folder — only the Cache Vault entry.
        """
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        from tkinter import messagebox
        suffix = "\n\nIt is a favorite." if clip.is_pinned else ""
        ok = messagebox.askyesno(
            "Remove from History",
            "Remove this clip from Cache Vault history? It can be "
            f"restored from Recently Removed.{suffix}",
            parent=self,
        )
        if not ok:
            return
        self.vault.remove_from_history(clip_id)
        self.refresh()
        self._preview.show(None)

    # --- clip-row context menu ---------------------------------------------
    # --- clip-row context menu ---------------------------------------------
    def _open_clip_menu(self, clip, x_root: int, y_root: int) -> None:
        clip_context.open_clip_menu(self, clip, x_root, y_root)

    def _open_bulk_clip_menu(self, ids: list[str], x_root: int, y_root: int) -> None:
        clip_context.open_bulk_clip_menu(self, ids, x_root, y_root)

    def _open_locked_menu(self, x_root: int, y_root: int) -> None:
        clip_context.open_locked_menu(self, x_root, y_root)

    def _open_home_clip_menu(self, clip, x_root: int, y_root: int) -> None:
        if len(self._selected_clip_ids) > 1 and clip.id in self._selected_clip_ids:
            self._open_bulk_clip_menu(self._selected_clip_ids, x_root, y_root)
        else:
            self._on_clip_select(clip)
            self._open_clip_menu(clip, x_root, y_root)

    def _open_home_card_menu(self, label: str, filter_key: str | None, x_root: int, y_root: int) -> None:
        clip_context.open_home_card_menu(self, label, filter_key, x_root, y_root)

    def _open_home_app_menu(self, x_root: int, y_root: int) -> None:
        clip_context.open_home_app_menu(self, x_root, y_root)

    def _open_home_status_menu(self, surface: str, x_root: int, y_root: int) -> None:
        clip_context.open_home_status_menu(self, surface, x_root, y_root)

    def _open_collection_sidebar_menu(self, name: str, x_root: int, y_root: int) -> None:
        clip_context.open_collection_sidebar_menu(self, name, x_root, y_root)

    def _open_safe_menu(self, safe: dict, x_root: int, y_root: int) -> None:
        sidebar_context.open_safe_menu(self, safe, x_root, y_root)

    def _open_sidebar_section_menu(self, heading: str, x_root: int, y_root: int) -> None:
        if heading == "SAFES":
            sidebar_context.open_safes_heading_menu(self, x_root, y_root)
        else:
            sidebar_context.open_section_heading_menu(self, heading, x_root, y_root)

    def _open_sidebar_nav_menu(self, nav_key: str, x_root: int, y_root: int) -> None:
        sidebar_context.open_nav_row_menu(self, nav_key, x_root, y_root)

    # --- Sidebar context-menu dispatch -----------------------------------
    def _dispatch_sidebar_command(self, key: str, ctx: Any) -> None:
        """Execute a sidebar context-menu command, re-validating live state first."""
        if not self._guard_unlocked():
            return
        # Rebuild context from current app state for every command so stale
        # captured contexts cannot silently act on the wrong view.
        current_ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            self, ctx.target_key, getattr(ctx, "collection_name", None),
        )
        if not current_ctx.is_target_active and key not in (
            smc.CMD_OPEN,
            smc.CMD_SCAN_CLEANUP_SUGGESTIONS,
            smc.CMD_SCAN_AGAIN,
            smc.CMD_REVIEW_SUGGESTIONS,
            smc.CMD_SHOW_IGNORED,
            smc.CMD_RESTORE_ALL,
            smc.CMD_RENAME_COLLECTION,
            smc.CMD_EMPTY_COLLECTION,
            smc.CMD_PERMANENTLY_DELETE_ALL,
            smc.CMD_CLEAR_ALL_CLIPS,
        ):
            self._show_toast("Sidebar context changed; command aborted.")
            return
        handler = getattr(self, f"_sidebar_{key}", None)
        if handler is None:
            return
        handler(current_ctx)

    def _sidebar_open(self, ctx: Any) -> None:
        from ..core import storage as S
        target = ctx.target_key
        if target == NAV_CLEANUP_SUGGESTIONS:
            self._navigate_screen(NAV_CLEANUP_SUGGESTIONS)
        elif getattr(ctx, "collection_name", None) is not None:
            self._navigate_filter(f"{S.COLLECTION_PREFIX}{ctx.collection_name}")
        elif target.startswith("nav_"):
            self._navigate_screen(target)
        else:
            self._navigate_filter(target)

    def _sidebar_refresh(self, ctx: Any) -> None:
        if not ctx.is_target_active:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        self.refresh()

    def _sidebar_scan_cleanup_suggestions(self, ctx: Any) -> None:
        self._scan_cleanup_suggestions()

    def _sidebar_select_all_visible(self, ctx: Any) -> None:
        if not ctx.is_target_active:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        if not self._visible_clip_ids:
            return
        view = self._grid if self._view_mode == "grid" else self._list
        try:
            if not view.winfo_ismapped():
                return
        except Exception:  # noqa: BLE001
            return
        self._selection_scope.clear()
        view.select_all()

    def _sidebar_select_all_matching(self, ctx: Any) -> None:
        if not ctx.is_target_active or ctx.target_query is None:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        query = ctx.target_query
        view = self._grid if self._view_mode == "grid" else self._list
        try:
            if not view.winfo_ismapped():
                return
        except Exception:  # noqa: BLE001
            return
        matching = self._selection_scope.activate_matching(ctx.target_key, query)
        self._paint_matching_selection_visuals(view)
        self._set_selection_notice(f"All {matching.resolved_count} matching items selected")

    def _sidebar_deselect_all(self, ctx: Any) -> None:
        self._clear_selection()

    def _sidebar_export_current_view(self, ctx: Any) -> None:
        if not ctx.is_target_active or ctx.target_query is None:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        collection = self._collection_name_for(ctx.target_key)
        self._export_for_query(ctx.target_query, collection_name=collection)

    def _sidebar_export_selected(self, ctx: Any) -> None:
        if not ctx.is_target_active or not ctx.visible_selected_ids:
            self._show_toast("No selection to export.")
            return
        self._export_clip_ids(list(ctx.visible_selected_ids))

    def _sidebar_scan_image_duplicates(self, ctx: Any) -> None:
        if not ctx.is_target_active:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        self._scan_cleanup_suggestions()
        self._navigate_screen(NAV_CLEANUP_SUGGESTIONS)

    def _sidebar_review_tiny_images(self, ctx: Any) -> None:
        if not ctx.is_target_active:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        self._scan_cleanup_suggestions()
        self._navigate_screen(NAV_CLEANUP_SUGGESTIONS)

    def _sidebar_review_largest_images(self, ctx: Any) -> None:
        if not ctx.is_target_active:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        self._scan_cleanup_suggestions()
        self._navigate_screen(NAV_CLEANUP_SUGGESTIONS)

    def _sidebar_remove_favorite_marks(self, ctx: Any) -> None:
        if not ctx.is_target_active or ctx.target_query is None:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        ids = self._resolve_sidebar_target_ids(ctx, prefer_selection=True)
        if not ids:
            self._show_toast("No favorite marks to remove.")
            return
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Remove Favorite Marks",
            f"Remove favorite marks from {len(ids)} clip{'s' if len(ids) != 1 else ''}?\n\n"
            "Clips and collections are not affected.",
            parent=self,
        )
        if not ok:
            return
        succeeded = 0
        skipped = 0
        for cid in ids:
            clip = self.vault.storage.get_clip(cid)
            if clip is None:
                skipped += 1
                continue
            if clip.is_pinned:
                self.vault.set_favorite(cid, False)
                succeeded += 1
            else:
                skipped += 1
        if skipped:
            self._show_toast(f"Removed favorite marks from {succeeded} clips ({skipped} already removed).")
        else:
            self._show_toast(f"Removed favorite marks from {succeeded} clip{'s' if succeeded != 1 else ''}.")
        self.refresh()

    def _sidebar_rename_collection(self, ctx: Any) -> None:
        from tkinter import simpledialog
        name = getattr(ctx, "collection_name", None)
        if not name:
            return
        # Re-resolve the collection at execution time. If the target collection
        # no longer exists (renamed or deleted before invocation), abort
        # rather than silently updating zero rows on the wrong set.
        if ctx.target_query is None or self.vault.count_clips(ctx.target_query) == 0:
            self._show_toast("Collection no longer exists or is empty; rename aborted.")
            return
        new_name = simpledialog.askstring("Rename Collection", "New name:", initialvalue=name, parent=self)
        if not new_name or new_name.strip() == name:
            return
        new_name = new_name.strip()
        try:
            self.vault.storage.conn.execute(
                "UPDATE clips SET collection = ? WHERE collection = ?",
                (new_name, name),
            )
            self.vault.storage.conn.commit()
        except Exception as exc:  # noqa: BLE001
            self.vault.storage.conn.rollback()
            raise exc
        self.refresh()
        self._show_toast(f"Renamed collection to '{new_name}'.")

    def _sidebar_empty_collection(self, ctx: Any) -> None:
        from tkinter import messagebox
        from ..core import storage as S

        name = getattr(ctx, "collection_name", None)
        if not name:
            return

        # Re-resolve current membership at execution time, not the count
        # frozen in the menu label. The command is collection-wide and must
        # not depend on any visible/matching selection.
        ids = self._resolve_sidebar_target_ids(ctx, prefer_selection=False)
        if not ids:
            self._show_toast(f"Collection '{name}' is already empty. No clips were changed.")
            return

        count = len(ids)
        plural = "s" if count != 1 else ""
        msg = (
            f"Empty collection '{name}'?\n\n"
            f"This will remove the collection label from {count} clip{plural}.\n\n"
            "Clips will remain in your vault.\n"
            "Only the collection label will be removed.\n\n"
            "No clips, files, or favorites will be deleted."
        )
        ok = messagebox.askyesno(
            "Empty collection",
            msg,
            parent=self,
        )
        if not ok:
            return

        result = self.vault.empty_collection(name, ids)
        removed = result.succeeded_count
        skipped = result.skipped_count

        if removed == 0:
            self._show_toast(f"Collection '{name}' is already empty. No clips were changed.")
        elif skipped:
            self._show_toast(
                f"Emptied collection '{name}': removed labels from {removed} clip"
                f"{'s' if removed != 1 else ''} ({skipped} already removed). "
                "Clips remain in your vault."
            )
        else:
            self._show_toast(
                f"Emptied collection '{name}': removed labels from {removed} clip"
                f"{'s' if removed != 1 else ''}. Clips remain in your vault."
            )

        if ctx.is_target_active:
            self._selection_scope.clear()
            self._navigate_filter(S.FILTER_ALL)
        else:
            self.refresh()

    def _sidebar_export_collection(self, ctx: Any) -> None:
        if not ctx.is_target_active or ctx.target_query is None:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        collection = ctx.collection_name
        self._export_for_query(ctx.target_query, collection_name=collection)

    def _sidebar_restore_selected(self, ctx: Any) -> None:
        if not ctx.is_target_active or not ctx.visible_selected_ids:
            self._show_toast("No selection to restore.")
            return
        ids = list(dict.fromkeys(ctx.visible_selected_ids))
        result = self.vault.storage.restore_many(ids)
        for cid in result.succeeded:
            self.vault.events.record(models.EVENT_RESTORED, cid)
        total = len(result.succeeded)
        skipped = len(result.skipped)
        if skipped:
            self._show_toast(f"Restored {total} clip{'s' if total != 1 else ''} ({skipped} already active or missing).")
        else:
            self._show_toast(f"Restored {total} clip{'s' if total != 1 else ''}.")
        self._selection_scope.clear()
        self.refresh()

    def _sidebar_restore_all(self, ctx: Any) -> None:
        if ctx.target_query is None:
            return
        ids = []
        with self.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (count, batches):
            for batch in batches:
                ids.extend(batch)
        if not ids:
            self._show_toast("No removed items to restore.")
            return
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Restore All",
            f"Restore all {len(ids)} removed item{'s' if len(ids) != 1 else ''}?",
            parent=self,
        )
        if not ok:
            return
        result = self.vault.storage.restore_many(ids)
        for cid in result.succeeded:
            self.vault.events.record(models.EVENT_RESTORED, cid)
        total = len(result.succeeded)
        skipped = len(result.skipped)
        if skipped:
            self._show_toast(f"Restored {total} clip{'s' if total != 1 else ''} ({skipped} skipped).")
        else:
            self._show_toast(f"Restored {total} clip{'s' if total != 1 else ''}.")
        self._selection_scope.clear()
        self.refresh()

    def _sidebar_clear_all_clips(self, ctx: Any) -> None:
        """Move every currently-active clip to Recently Removed.

        Re-resolves the ids from the database at execution time rather
        than trusting the count frozen into the menu label, and never
        consults the visible/matching selection -- this command is
        view-wide by definition.
        """
        if ctx.target_query is None:
            return
        ids: list[str] = []
        with self.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (
            count, batches,
        ):
            for batch in batches:
                ids.extend(batch)
        if not ids:
            self._show_toast("There are no clips to clear.")
            return

        def _run() -> None:
            try:
                result = self.vault.clear_all_clips(ids)
            except Exception:  # noqa: BLE001
                # soft_delete_many rolls the whole batch back, so the vault
                # is genuinely unchanged; say so instead of implying a
                # partial clear the user would then go hunting for.
                self._show_toast(
                    "Clear all clips failed. No clips were moved and your vault is unchanged."
                )
                self.refresh()
                return
            self._report_clear_all_clips_result(result)

        from .dialogs import ClearAllClipsDialog
        ClearAllClipsDialog(self, total_count=len(ids), on_confirm=_run)

    def _report_clear_all_clips_result(self, result: Any) -> None:
        moved = result.succeeded_count
        skipped = result.skipped_count
        if moved == 0:
            self._show_toast("No clips were moved.")
        elif skipped:
            self._show_toast(
                f"Moved {moved} clip{'s' if moved != 1 else ''} to Recently Removed "
                f"({skipped} already removed). They can be restored from Recently Removed."
            )
        else:
            self._show_toast(
                f"Moved {moved} clip{'s' if moved != 1 else ''} to Recently Removed. "
                "They can be restored from Recently Removed."
            )
        self._selection_scope.clear()
        self.refresh()

    def _sidebar_permanently_delete_selected(self, ctx: Any) -> None:
        """Recently Removed only -- guarded by the dispatch allowlist not
        exempting this key, so a stale/inactive context aborts before we
        even get here (mirrors ``_sidebar_restore_selected``).
        """
        if not ctx.is_target_active:
            self._show_toast("Sidebar context changed; command aborted.")
            return
        ids = self._resolve_sidebar_target_ids(ctx, prefer_selection=True)
        if not ids:
            self._show_toast("No selection to permanently delete.")
            return
        self._confirm_and_permanently_delete(ids)

    def _sidebar_permanently_delete_all(self, ctx: Any) -> None:
        from ..core import permanent_delete as pd

        if ctx.target_query is None:
            return
        ids = []
        with self.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (count, batches):
            for batch in batches:
                ids.extend(batch)
        if not ids:
            self._show_toast("No removed items to permanently delete.")
            return

        plan = pd.build_deletion_plan(self.vault.storage, ids)

        def _run() -> None:
            result = self.vault.permanently_delete_many(ids, confirmation_mode="delete_all")
            self._report_permanent_delete_result(result)

        from .dialogs import PermanentDeleteAllDialog
        PermanentDeleteAllDialog(
            self,
            total_count=len(ids),
            eligible_count=len(plan.eligible_ids),
            skipped_count=len(plan.skipped),
            asset_count=plan.asset_count,
            bytes_scheduled=plan.planned_bytes,
            on_confirm=_run,
        )

    def _report_permanent_delete_result(self, result: Any) -> None:
        deleted = len(result.deleted_ids)
        skipped = len(result.skipped)
        deferred = result.managed_files_deferred
        if deleted == 0:
            self._show_toast("Nothing was eligible to permanently delete.")
        elif deferred:
            self._show_toast(
                f"Permanently deleted {deleted} item{'s' if deleted != 1 else ''} "
                f"({skipped} skipped); {deferred} asset file(s) could not be purged "
                "and are queued for retry."
            )
        elif skipped:
            self._show_toast(
                f"Permanently deleted {deleted} item{'s' if deleted != 1 else ''} "
                f"({skipped} skipped)."
            )
        else:
            self._show_toast(f"Permanently deleted {deleted} item{'s' if deleted != 1 else ''}.")
        self._selection_scope.clear()
        self.refresh()

    def _sidebar_review_suggestions(self, ctx: Any) -> None:
        self._navigate_screen(NAV_CLEANUP_SUGGESTIONS)

    def _sidebar_show_ignored(self, ctx: Any) -> None:
        self._navigate_screen(NAV_CLEANUP_SUGGESTIONS)

    def _sidebar_scan_again(self, ctx: Any) -> None:
        self._scan_cleanup_suggestions()

    def _sidebar_properties(self, ctx: Any) -> None:
        label = self._filters.active_label if ctx.is_target_active else ctx.target_key
        self._show_toast(f"{label}: {ctx.item_count} items")

    # --- Helpers for sidebar commands ------------------------------------
    def _resolve_sidebar_target_ids(self, ctx: Any, *, prefer_selection: bool = False) -> list[str]:
        """Resolve the unique IDs a sidebar command should act on.

        If ``prefer_selection`` is True and a visible/matching selection
        exists, use it. Otherwise use all IDs matching the target query.
        """
        if prefer_selection and ctx.has_selection:
            if ctx.matching_descriptor is not None:
                resolution = self._selection_scope.resolve(
                    ctx.target_key,
                    ctx.target_query,
                    visible_ids=list(ctx.visible_selected_ids),
                )
                if resolution.stale:
                    return []
                ids = []
                for batch in resolution.iter_ids():
                    ids.extend(batch)
                return list(dict.fromkeys(ids))
            return list(dict.fromkeys(ctx.visible_selected_ids))
        if ctx.target_query is None:
            return []
        ids = []
        with self.vault.storage.clip_id_snapshot(ctx.target_query, batch_size=500) as (count, batches):
            for batch in batches:
                ids.extend(batch)
        return list(dict.fromkeys(ids))

    def _export_for_query(self, query, *, collection_name: str | None = None) -> None:
        """Export every clip matching ``query`` via the same dialog used
        by the active-view export command.
        """
        if not self._require_founder("exports_advanced"):
            return
        clips = self.vault.list_clips(query)
        if not clips:
            return
        from ..ui.dialogs import ExportViewDialog
        ExportViewDialog(self, len(clips),
                         on_export=lambda kind, incl: self._do_export_view(
                             clips, collection_name, kind, incl))

    def _export_clip_ids(self, clip_ids: list[str]) -> None:
        """Export the provided clip ids via the existing export dialog."""
        if not self._require_founder("exports_advanced"):
            return
        clips = [self.vault.storage.get_clip(cid) for cid in clip_ids]
        clips = [c for c in clips if c is not None]
        if not clips:
            return
        from ..ui.dialogs import ExportViewDialog
        collection = self._collection_name_for(self._filters.active)
        ExportViewDialog(self, len(clips),
                         on_export=lambda kind, incl: self._do_export_view(
                             clips, collection, kind, incl))

    def _open_receipt_menu(self, row, x_root: int, y_root: int) -> None:
        clip_context.open_receipt_menu(self, row, x_root, y_root)

    def _copy_default_safe_summary(self) -> None:
        safe_id = self.vault.settings.default_safe_id or "default"
        safe = next((s for s in self.vault.list_safes() if s.get("id") == safe_id), None)
        if safe is None:
            return
        self._copy_safe_summary(safe)

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
        self._monitor.note_local_copy(clipboard_out.write_via_tk(self, text))
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
        if not self._require_founder("editable_copies_advanced"):
            return
        self.vault.create_editable_copy(clip_id)
        self._refresh_editable_preview(clip_id)

    def _open_editable_copy(self, clip_id: str) -> None:
        if not self._require_founder("editable_copies_advanced"):
            return
        self.vault.open_editable_copy(clip_id)
        self._refresh_editable_preview(clip_id)

    def _save_editable_revision(self, clip_id: str) -> None:
        if not self._require_founder("editable_copies_advanced"):
            return
        self.vault.save_editable_revision(clip_id)
        self._refresh_editable_preview(clip_id)

    def _reveal_editable_copy_folder(self, clip_id: str) -> None:
        if not self._require_founder("editable_copies_advanced"):
            return
        from ..core import pathutil
        rec = self.vault.latest_editable_copy(clip_id)
        if rec is not None:
            target = rec.bundle_dir or rec.copy_path
            pathutil.reveal_in_explorer(target)

    def _preview_html_copy(self, clip_id: str) -> None:
        if not self._require_founder("html_bundle_export"):
            return
        self.vault.preview_html_copy(clip_id)
        self._refresh_editable_preview(clip_id)

    def _edit_html_source(self, clip_id: str) -> None:
        if not self._require_founder("html_bundle_export"):
            return
        self.vault.edit_html_source(clip_id)
        self._refresh_editable_preview(clip_id)

    def _export_html_bundle(self, clip_id: str) -> None:
        if not self._require_founder("html_bundle_export"):
            return
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
        if not self._require_founder("proof_pack_export"):
            return
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
            on_create=self._create_safe_if_allowed,
        )

    def _restore(self, clip_id: str) -> None:
        self.vault.restore(clip_id)
        self.refresh()
        self._preview.show(self.vault.storage.get_clip(clip_id))

    def _permanently_remove(self, clip_id: str) -> None:
        """Recently Removed only -- routes through the exact same staged
        pipeline as bulk/Delete All (``_confirm_and_permanently_delete``
        -> ``Vault.permanently_delete_many``), never a direct
        ``hard_delete`` call. See cache_vault/core/permanent_delete.py
        for the full managed-root containment, quarantine-staging, and
        rollback contract this now inherits -- there is exactly one
        permanent-deletion safety architecture, not a separate one for
        single items.
        """
        if not self._guard_unlocked():
            return
        self._confirm_and_permanently_delete([clip_id], on_done=lambda: self._preview.show(None))

    def _send_to_macro_safe(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        if not self._require_founder("macros_advanced"):
            return
        if not self.vault.settings.vault_macros_setup_completed:
            from ..core.vault_macros import complete_macro_setup
            complete_macro_setup(
                self.vault.settings,
                record_receipt=self._macro_record_receipt,
            )
            self._sync_macro_triggers()
        if self.vault.send_to_macro_safe(clip_id):
            self._show_toast("Saved to Snippet Macros.")
            self.refresh()
        else:
            from tkinter import messagebox
            messagebox.showinfo(
                "Snippet Macros",
                "This clip has no text body to save as a macro.\n"
                "Text clips and links work best.",
                parent=self,
            )

    def _create_macro_from_clip(self, clip_id: str) -> None:
        if not self._guard_unlocked():
            return
        if not self._require_founder("macros_advanced"):
            return
        if not self.vault.settings.vault_macros_setup_completed:
            from ..core.vault_macros import complete_macro_setup
            complete_macro_setup(
                self.vault.settings,
                record_receipt=self._macro_record_receipt,
            )
            self._sync_macro_triggers()

        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return

        if clip.content_type == models.CONTENT_IMAGE:
            body = (clip.title or clip.preview or "").strip()
        else:
            body = (clip.content or "").strip()
        if not body:
            from tkinter import messagebox
            messagebox.showinfo(
                "Snippet Macros",
                "This clip has no text body to save as a macro.\n"
                "Text clips and links work best.",
                parent=self,
            )
            return

        from .macro_dialogs import MacroEditDialog
        from ..core.vault_macros import MacroSafeRegistry, Macro, suggest_smart_type
        registry = MacroSafeRegistry(self.vault.settings)
        sid = registry.default_safe().id

        macro = Macro(
            id=models.new_id(),
            name=(clip.title or clip.preview or "New Macro")[:64],
            body=body,
            safe_id=sid,
            smart_type=suggest_smart_type(body, clip.title or ""),
        )

        def on_save(updated) -> None:
            self._macro_store.upsert(updated)
            self._macro_record_receipt("sent_to_macros", {
                "macro_id": updated.id,
                "clip_id": clip_id,
                "safe_id": updated.safe_id,
                "success": True,
            })
            self._sync_macro_triggers()
            self.refresh()
            self._show_toast("Saved to Snippet Macros.")

        other, reserved = self._macro_editor_context(macro.id)
        MacroEditDialog(
            self, macro=macro, registry=registry, on_save=on_save,
            other_macros=other, reserved_specs=reserved,
        )

    def _create_safe_if_allowed(self, name: str):
        if not self._require_founder("safes_advanced"):
            return None
        return self.vault.create_safe(name)

    def _open_new_safe(self) -> None:
        SafePickerDialog(
            self, self.vault.settings,
            title="New Safe",
            picker_mode=False,
            on_create=lambda _name: self.refresh(),
        )

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
        if not self._require_founder("exports_advanced"):
            return
        clips = self._current_clips()
        if not clips:
            return
        name = self._collection_name_for(self._filters.active)
        ExportViewDialog(self, len(clips),
                         on_export=lambda kind, incl: self._do_export_view(
                             clips, name, kind, incl))

    def _do_export_view(self, clips, collection_name, kind, include_files) -> None:
        if kind == "zip" and not self._require_founder("zip_export"):
            return
        if kind != "zip" and not self._require_founder("exports_advanced"):
            return
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
        from ..core.smart_folders import folder_id_from_key, folder_receipt, is_smart_filter

        if is_smart_filter(self._filters.active):
            fid = folder_id_from_key(self._filters.active)
            if fid:
                self.vault.events.record(
                    models.EVENT_EXPORTED,
                    None,
                    {
                        "target": "smart_folder_export",
                        "smart_folder": folder_receipt(fid, len(clips)),
                    },
                )
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
        from ..core.smart_folders import export_collection_name
        from ..core.storage import COLLECTION_PREFIX

        name = export_collection_name(active)
        if name:
            return name
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
    def _settings_external_hotkeys(self) -> dict[str, str]:
        """Macro/Hotkey-Action combos so Settings can flag capture-key clashes."""
        external: dict[str, str] = {}
        for m in self._macro_store.load_all():
            if m.trigger_type == self._TRIGGER_HOTKEY and (m.trigger_value or "").strip():
                external[m.trigger_value] = f"macro “{m.name}”"
        for a in self._command_store.load_all():
            if getattr(a, "enabled", True) and getattr(a, "hotkey", "").strip():
                external[a.hotkey] = f"hotkey action “{a.name}”"
        return external

    def _open_top_overflow_menu(self) -> None:
        """Non-wide-width overflow for the top toolbar's secondary actions
        and Quick Actions.

        Invokes the exact same handlers as the full-width controls -- this
        is purely a narrow-width access path, not a different feature.
        """
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label=brand.TERM_STAMPED_RECEIPTS,
            command=lambda: self._navigate_screen(NAV_STAMPED_RECEIPTS),
        )
        menu.add_command(label="⚡ Capture Rules", command=self._open_regex_macros)
        menu.add_separator()
        for choice in self._control_strip.QUICK_ACTION_CHOICES:
            menu.add_command(
                label=choice,
                command=lambda c=choice: self._control_strip.invoke_quick_action(c),
            )
        x = self._top_more_btn.winfo_rootx()
        y = self._top_more_btn.winfo_rooty() + self._top_more_btn.winfo_height()
        clip_context.popup_menu(self, menu, x, y)

    def _open_regex_macros(self) -> None:
        from .regex_macro_dialog import RegexMacroDialog
        def _view():
            self._vault_screens.set_receipts_filter_hint("Capture Rules")
            self._navigate_screen(NAV_STAMPED_RECEIPTS)
        RegexMacroDialog(self, on_view_receipts=_view)

    def _clear_settings_window_reference(self, window=None) -> None:
        if window is not None and self._settings_window is not window:
            return
        self._settings_window = None

    def _open_settings(self, category_id: str | None = None) -> None:
        if self._settings_window is not None:
            try:
                if self._settings_window.winfo_exists():
                    self._settings_window.present()
                    if category_id:
                        self._settings_window._select_category(category_id)  # noqa: SLF001
                    return
            except Exception:
                pass
            self._settings_window = None

        # Prefer the new registry-backed Settings Hub (Chunk C2).
        if SettingsHub is not None:
            try:
                from ..modules.registry import build_default_registry
                registry = build_default_registry(
                    mobile_bridge=self._mobile_bridge,
                    mobile_controller=self._mobile_controller,
                    mobile_pair_action=lambda: self._open_pair_android(),
                    mobile_devices_action=self._open_paired_devices,
                    mobile_receipts_action=self._open_mobile_receipts,
                    show_guide_action=self._open_first_use_guide_from_settings,
                    db_path_getter=lambda: str(self.vault.storage.db_path),
                )
                self._settings_window = SettingsHub(
                    self,
                    self.vault.settings,
                    registry,
                    on_save=self._apply_settings,
                    on_close=self._clear_settings_window_reference,
                    category_id=category_id,
                )
                self._settings_window.present()
                return
            except Exception:
                self._settings_window = None
                # Fallback to old dialog if hub construction fails.
                pass

        SettingsDialog(
            self, self.vault.settings, on_save=self._apply_settings,
            mobile={
                "pair": self._open_pair_android,
                "devices": self._open_paired_devices,
                "receipts": self._open_mobile_receipts,
            },
            help={
                "show_guide": self._open_first_use_guide_from_settings,
                "founder": self._open_founder,
                "about": self._open_about,
            },
            external_hotkeys=self._settings_external_hotkeys(),
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
            mdns_advertising=self._mobile_bridge.discovery.is_advertising,
        )

    def _revoke_all_and_pair(self, device_id: str, name: str) -> tuple[str, str]:
        self._mobile_bridge.revoke_all_active()
        return self._complete_mobile_pair(device_id, name)

    def _complete_mobile_pair(self, device_id: str, name: str) -> tuple[str, str]:
        _, token = self._mobile_bridge.pair_device(device_id, name)
        return device_id, token

    def _open_paired_devices(self) -> None:
        devices = [d.to_dict() for d in self._mobile_bridge.all_devices()]
        PairedDevicesDialog(self, devices, on_revoke=self._revoke_mobile_device)

    def _revoke_mobile_device(self, device_id: str) -> None:
        self._mobile_bridge.revoke_device(device_id)

    def _revoke_all_mobile_and_refresh(self) -> None:
        self._mobile_bridge.revoke_all_active()
        self._navigate_screen(NAV_MOBILE_ACCESS)

    def _open_mobile_receipts(self) -> None:
        MobileAccessReceiptsDialog(
            self, self._mobile_bridge.receipts.recent())

    def _apply_settings(self, settings) -> None:
        settings.save()
        self.vault.settings = settings
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
        if not self._mobile_controller.needs_change(settings):
            return

        def _sync_mobile() -> None:
            try:
                if settings.mobile_access_enabled:
                    result = self._mobile_controller.enable(settings)
                    if not result.success:
                        if self._alive():
                            self.after(0, lambda: self._show_toast(
                                f"Could not start Mobile Access: {result.error}"))
                else:
                    self._mobile_controller.disable(settings)
            except Exception as exc:  # noqa: BLE001
                write_crash("mobile controller sync", exc)
            finally:
                if self._alive():
                    self.after(0, self.refresh)

        threading.Thread(
            target=_sync_mobile, name="mobile-sync", daemon=True,
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
            self._quick_paste = QuickPaste(
                self, clips, on_choose=self._do_paste,
                persist=self._quick_paste_should_persist,
            )
        except Exception as exc:  # noqa: BLE001
            write_crash("quick paste", exc)
            raise

    def _quick_paste_should_persist(self, clip, action: str = "primary") -> bool:
        """Keep the Quick Paste popup open after copy-style choices.

        Copy-only actions never move focus, so the popup can stay up and let the
        user grab several clips in a row. Actions that deliver into another app
        (auto-paste) or open a file/folder dialog must still close so focus and
        the keyboard grab are released first.
        """
        if action == ACTION_COPY_ONLY:
            return True
        if action in (ACTION_OPEN, ACTION_SAVE_AS, ACTION_ALTERNATE):
            return False
        # ACTION_PRIMARY from here on.
        if getattr(clip, "content_type", None) == models.CONTENT_IMAGE:
            return False
        if getattr(clip, "classification", None) == models.CLASS_PATH:
            return True  # _quick_paste_copy_path only copies, never delivers
        settings = self.vault.settings
        target = getattr(self, "_paste_target", None)
        will_deliver = bool(
            settings.auto_paste and target and not hwnd_belongs_to_widget(target, self)
        )
        return not will_deliver

    def _do_paste(self, clip, action: str = "primary") -> None:
        if clip is None:
            return
        if self._locked():
            self.vault.events.record("quick_paste_blocked_locked", None, {})
            self._guard_unlocked()
            return
        if clip.content_type == models.CONTENT_IMAGE:
            # Defer until Quick Paste releases keyboard grab / closes cleanly.
            self.after(80, lambda c=clip, a=action: self._quick_paste_image_action(c, a))
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
            self._monitor.note_local_copy(clipboard_out.write_via_tk(self, content))
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
            self._monitor.note_local_copy(clipboard_out.write_via_tk(self, content))
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
            Toast(self, brand.TOAST_VAULT_IMAGE_COPIED)
        else:
            Toast(self, "◈ Image copied to clipboard — paste in an image-capable app")

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

    def _open_photo_viewer(self, clip_id: str) -> None:
        if self._photo_viewer_window is not None:
            try:
                if self._photo_viewer_window.winfo_exists():
                    self._photo_viewer_window.destroy()
            except Exception:
                pass
            self._photo_viewer_window = None

        from .photo_viewer import PhotoViewer

        # Get visible clip ids from active view
        all_clip_ids = getattr(self, "_visible_clip_ids", [clip_id])
        if not all_clip_ids:
            all_clip_ids = [clip_id]

        def get_clip_fn(cid: str) -> Any:
            return self.vault.storage.get_clip(cid)

        def load_asset_fn(cid: str) -> tuple[bytes, str] | None:
            return self.vault.storage.load_clip_asset_bytes(cid)

        def asset_meta_fn(cid: str) -> dict | None:
            rec = self.vault.storage.get_asset_record(cid)
            if rec is None:
                return None
            return {
                "sha256": rec.sha256,
                "size_bytes": rec.size_bytes,
                "width": rec.width,
                "height": rec.height,
            }

        def open_asset_folder(cid: str) -> None:
            from ..core import image_assets
            rec = self.vault.storage.get_asset_record(cid)
            if rec is None:
                return
            path = image_assets.assets_dir() / rec.storage_name
            if path.is_file():
                subprocess.run(["explorer", "/select,", str(path)], check=False)

        self._photo_viewer_window = PhotoViewer(
            self,
            initial_clip_id=clip_id,
            all_clip_ids=all_clip_ids,
            get_clip_fn=get_clip_fn,
            load_asset_fn=load_asset_fn,
            asset_meta_fn=asset_meta_fn,
            copy_image_fn=self._copy_again,
            save_image_as_fn=self._save_asset_as,
            open_asset_folder_fn=open_asset_folder,
        )
        self._photo_viewer_window.present()

    def _quick_paste_copy_path(self, clip) -> None:
        path_text = clip.content or ""
        if not path_text:
            Toast(self, "No path available to copy.")
            return
        self._monitor.note_local_copy(clipboard_out.write_via_tk(self, path_text))
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

    def _macro_editor_context(self, macro_id: str | None) -> tuple[list, set]:
        macros = self._macro_store.load_all()
        other = [m for m in macros if m.id != macro_id]
        reserved = set(self._system_reserved_hotkeys(self.vault.settings))
        for a in self._command_store.load_all():
            if getattr(a, "enabled", True) and getattr(a, "hotkey", ""):
                reserved.add(normalize_hotkey(a.hotkey))
        return other, reserved

    def _macro_edit(self, macro_id: str) -> None:
        from .macro_dialogs import MacroEditDialog
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

        other, reserved = self._macro_editor_context(macro_id)
        MacroEditDialog(
            self, macro=macro, registry=MacroSafeRegistry(self.vault.settings),
            on_save=on_save, other_macros=other, reserved_specs=reserved,
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

            other, reserved = self._macro_editor_context(macro.id)
            MacroEditDialog(
                self, macro=macro, registry=registry, on_save=on_save,
                other_macros=other, reserved_specs=reserved,
            )

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
                title="Snippet Macros — choose hotkey match",
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
        title: str = "Snippet Macros",
    ) -> None:
        if not self._alive():
            return
        ok, _reason = self._macro_executor.execution_allowed()
        if not ok:
            self._show_toast("Snippet Macros are disabled or setup is incomplete.")
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
            self._show_toast("Macro copied — switch to your app and paste (Ctrl+V).")
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
        if hwnd_belongs_to_widget(foreground_window(), self):
            self._pending_macro_run_id = macro_id
            self.withdraw()
            self.after(220, self._complete_macro_run_from_button)
            return
        target = self._resolve_macro_target(None)
        self._run_macro(macro, self._TRIGGER_MENU_ONLY, "run_button", target)

    def _complete_macro_run_from_button(self) -> None:
        macro_id = getattr(self, "_pending_macro_run_id", None)
        self._pending_macro_run_id = None
        if not macro_id:
            return
        macro = self._macro_store.get(macro_id)
        if macro is None:
            if self._tray.available:
                return
            self.deiconify()
            return
        target = foreground_window()
        if hwnd_belongs_to_widget(target, self):
            target = None
        self._run_macro(macro, self._TRIGGER_MENU_ONLY, "run_button", target)
        if not self._tray.available:
            self.after(400, self._show_window)

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

    def _command_action_handlers(self) -> dict:
        import pyperclip
        from ..core.command_center import (
            ACTION_LOCK_VAULT,
            ACTION_OPEN_QUICK_PASTE,
            ACTION_OPEN_VAULT,
            ACTION_RUN_MACRO,
            ACTION_SAVE_CLIPBOARD_TO_SAFE,
            ACTION_TOGGLE_CAPTURE,
        )

        def open_vault(*_args):
            self._show_window()

        def open_quick_paste(*_args):
            self._schedule_quick_paste()

        def toggle_capture(*_args):
            self._set_paused(not self.vault.settings.capture_paused)

        def save_clipboard_to_safe(action):
            try:
                text = pyperclip.paste()
            except Exception:
                text = ""
            if not text or not text.strip():
                return {"ok": False, "error": "empty clipboard"}
            clip = self.vault.capture(text)
            if clip is None:
                return {"ok": False, "error": "capture failed"}
            self.vault.move_to_safe(clip.id, action.target or self.vault.settings.default_safe_id)
            self.vault.events.record("clip_move", clip.id, {
                "safe_id": action.target,
                "source": "command_center",
            })
            self.refresh()
            return None

        def run_macro(action):
            macros = self._macro_store.load_all()
            target = next((m for m in macros if m.id == action.target), None)
            if target is None:
                return {"ok": False, "error": "macro not found"}
            self._run_macro(target, self._TRIGGER_MENU_ONLY, "command_center", None)
            return None

        def lock_vault(*_args):
            self._lock_now(reason="command_center")
            return None

        return {
            ACTION_OPEN_VAULT: open_vault,
            ACTION_OPEN_QUICK_PASTE: open_quick_paste,
            ACTION_TOGGLE_CAPTURE: toggle_capture,
            ACTION_SAVE_CLIPBOARD_TO_SAFE: save_clipboard_to_safe,
            ACTION_RUN_MACRO: run_macro,
            ACTION_LOCK_VAULT: lock_vault,
        }

    def _confirm_command_action(self, action) -> bool:
        from tkinter import messagebox
        return messagebox.askyesno(
            "Confirm command",
            f"Run \u201c{action.name}\u201d?\n"
            "This action is marked as requiring confirmation.",
            parent=self,
        )

    def _on_command_run_event(self, entry) -> None:
        try:
            self.vault.events.record("command_run", None, {
                "action": "command_run",
                "command_name": entry.command_name,
                "action_type": entry.action_type,
                "trigger_type": entry.trigger_type,
                "trigger_value": entry.trigger_value,
                "result": entry.result,
                "safe_target": entry.safe_target or None,
                "dry_run": entry.dry_run,
                "error": entry.error or None,
            })
        except Exception as exc:
            write_crash("command run event", exc)

    def _command_reserved_specs(self) -> set:
        reserved = set(self._system_reserved_hotkeys(self.vault.settings))
        for m in self._macro_store.load_all():
            if m.trigger_type == self._TRIGGER_HOTKEY and m.trigger_value:
                reserved.add(normalize_hotkey(m.trigger_value))
        return reserved

    def _command_safe_options(self) -> list:
        return [(s["id"], s["name"]) for s in self.vault.list_safes()]

    def _command_macro_options(self) -> list:
        return [(m.id, m.name) for m in self._macro_store.load_all()]

    def _bind_command_hotkeys(self) -> None:
        cc = self._cc
        self._command_hotkeys.clear_bindings()
        self._command_hotkey_ids.clear()
        reserved = self._command_reserved_specs()
        actions = self._command_store.load_all()
        hid = HK_COMMAND_ID_BASE
        for action in actions:
            if not action.enabled or not action.hotkey:
                continue
            kind, _msg = cc.diagnose_action_hotkey(
                action.hotkey, self_id=action.id, other_actions=actions,
                reserved_specs=reserved,
                win32_available=self._command_hotkeys.available,
            )
            if kind != "ok":
                continue
            self._command_hotkeys.set_binding(
                hid, action.hotkey,
                on_activate=(lambda aid=action.id: self._schedule_command_action(aid)),
            )
            self._command_hotkey_ids[hid] = action.id
            hid += 1

    def _rebind_command_hotkeys(self) -> None:
        if getattr(self, "_command_hotkeys", None):
            self._command_hotkeys.stop()
        self._command_hotkeys = MultiHotkeyListener()
        self._command_hotkey_ids = {}
        self._bind_command_hotkeys()
        self._command_hotkeys.start()
        self.after(600, self._refresh_command_registration)

    def _refresh_command_registration(self) -> None:
        if not self._alive():
            return
        if self._filters.active == NAV_HOTKEY_ACTIONS:
            self._refresh_command_screen()

    def _refresh_command_screen(self) -> None:
        frame = self._vault_screens._screens.get(NAV_HOTKEY_ACTIONS)
        refresh = getattr(frame, "_refresh", None)
        if callable(refresh):
            refresh()

    def _command_action_rows(self) -> dict:
        status_rows = self._cc.compute_status_rows(
            self._command_store.load_all(),
            reserved_specs=self._command_reserved_specs(),
            win32_available=self._command_hotkeys.available,
            registered_ids=self._command_hotkeys.registered_ids(),
            hotkey_id_by_action={
                aid: hid for hid, aid in self._command_hotkey_ids.items()
            },
        )
        quiet = (self._cc.REG_ACTIVE, self._cc.REG_DISABLED)
        rows = [
            {
                "action": r.action,
                "status": r.status,
                "status_message": "" if r.status in quiet else r.message,
            }
            for r in status_rows
        ]
        return {"rows": rows, "win32_available": self._command_hotkeys.available}

    def _command_action_new(self) -> None:
        self._open_command_dialog(None)

    def _command_action_edit(self, action_id: str) -> None:
        action = self._command_store.get(action_id)
        if action is not None:
            self._open_command_dialog(action)

    def _open_command_dialog(self, action) -> None:
        from .command_center import HotkeyActionDialog
        HotkeyActionDialog(
            self, action,
            safes=self._command_safe_options(),
            macros=self._command_macro_options(),
            other_actions=self._command_store.load_all(),
            reserved_specs=self._command_reserved_specs(),
            win32_available=self._command_hotkeys.available,
            on_save=self._command_action_save,
            on_delete=self._command_action_delete,
        )

    def _command_action_save(self, action) -> None:
        self._command_store.upsert(action)
        self._rebind_command_hotkeys()
        self.refresh()
        self._refresh_command_screen()

    def _command_action_delete(self, action_id: str) -> None:
        from tkinter import messagebox
        action = self._command_store.get(action_id)
        name = action.name if action else "this hotkey"
        if not messagebox.askyesno(
            "Delete hotkey action", f"Delete \u201c{name}\u201d?", parent=self,
        ):
            return
        self._command_store.delete(action_id)
        self._rebind_command_hotkeys()
        self.refresh()
        self._refresh_command_screen()

    def _command_action_toggle(self, action_id: str) -> None:
        action = self._command_store.get(action_id)
        if action is None:
            return
        action.enabled = not action.enabled
        self._command_store.upsert(action)
        self._rebind_command_hotkeys()
        self.refresh()
        self._refresh_command_screen()

    def _command_action_run_button(self, action_id: str) -> None:
        action = self._command_store.get(action_id)
        if action is None:
            return
        result = self._command_dispatcher.run(
            action, trigger_type="run_button", trigger_value=action.hotkey,
        )
        if result.result == self._cc.RESULT_FAILED:
            self._show_toast(f"Command failed safely: {result.error}")
        self._refresh_command_screen()

    def _schedule_command_action(self, action_id: str) -> None:
        self._call_on_main(lambda: self._run_command_action(action_id))

    def _run_command_action(self, action_id: str) -> None:
        action = self._command_store.get(action_id)
        if action is None:
            return
        self._command_dispatcher.run(
            action, trigger_type="hotkey", trigger_value=action.hotkey,
        )
        self._refresh_command_screen()

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
