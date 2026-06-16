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
import traceback
from pathlib import Path

import customtkinter as ctk

from .. import brand
from ..core import models, search
from ..core.clipboard import ClipboardMonitor
from ..core.hotkey import HotkeyListener, focus_and_paste, foreground_window
from ..core.storage import FILTER_HOME, FILTER_SEARCH_ALL
from ..core.mobile.bridge import MobileBridge
from ..core.vault import Vault
from .clip_grid import ClipGrid
from .clip_list import ClipList
from .dialogs import (
    AboutDialog, EventLogDialog, ExportViewDialog, MoveToCollectionDialog,
    SettingsDialog,
)
from .filters import FilterNav, NAV_MOBILE_ACCESS, NAV_STAMPED_RECEIPTS
from .home_dashboard import HomeDashboard
from .duplicate_dialog import DuplicateReviewDialog
from .mobile_dialogs import (
    MobileAccessReceiptsDialog, PairAndroidDialog, PairedDevicesDialog,
)
from .preview import PreviewPanel
from .quick_paste import QuickPaste
from .toast import Toast
from .tray import TrayController
from . import theme
from .crashlog import write_crash

EXPIRY_SWEEP_MS = 15_000  # run the expiry sweep every 15s


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
        self._expiry_job = None
        self._shutting_down = False
        self._main_thread_calls: queue.SimpleQueue = queue.SimpleQueue()
        self._view_mode = "cards"
        self._sort_key = models.SORT_NEWEST_ADDED
        self._date_added_preset: str | None = None
        self._date_used_preset: str | None = None
        self._type_filter: str | None = None
        self._sensitive_only = False

        self._mobile_bridge = MobileBridge(self.vault)

        self._build_layout()

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
            on_activate=lambda: self.after(0, self._open_quick_paste),
        )
        self._hotkey.start()

        # Closing the window hides to tray (if available) rather than quitting.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.refresh()
        self._expiry_job = self.after(EXPIRY_SWEEP_MS, self._expiry_tick)
        # Start mobile bridge after the window is live (zeroconf must not block UI).
        self.after(0, lambda: self._mobile_bridge.sync(self.vault.settings))

        # Tray last — callbacks marshal through _call_on_main (pystray runs off-thread).
        self._tray = TrayController(
            on_open=lambda: self._call_on_main(self._show_window),
            on_pause=lambda: self._call_on_main(lambda: self._set_paused(True)),
            on_resume=lambda: self._call_on_main(lambda: self._set_paused(False)),
            on_clear_sensitive=lambda: self._call_on_main(self._clear_sensitive),
            on_quit=lambda: self._call_on_main(self._quit),
            on_quick_paste=lambda: self._call_on_main(self._open_quick_paste),
        )
        self._tray.start()

        self._center_on_screen()
        self._show_window()
        self.after(50, self._pump_main_thread)

    def _alive(self) -> bool:
        if self._shutting_down:
            return False
        try:
            return bool(self.winfo_exists())
        except Exception:  # noqa: BLE001
            return False

    def _safe_after(self, ms: int, fn):
        if not self._alive():
            return None
        return self.after(ms, fn)

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
        top.grid_columnconfigure(0, weight=0)
        self._status = ctk.CTkLabel(top, text="", text_color=brand.MUTED_FG,
                                    font=ctk.CTkFont(size=11))
        self._status.grid(row=0, column=0, sticky="w", padx=12)
        ctk.CTkButton(top, text=brand.TERM_EXPORT, width=130,
                      command=self._export_view, **theme.primary_button()
                      ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(top, text=brand.TERM_STAMPED_RECEIPTS, width=130,
                      command=self._open_events, **theme.secondary_button()
                      ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(top, text="About", width=70, command=self._open_about,
                      **theme.secondary_button()
                      ).grid(row=0, column=3, padx=4)
        ctk.CTkButton(top, text="⚙ Settings", width=90, command=self._open_settings,
                      **theme.secondary_button()
                      ).grid(row=0, column=4, padx=(4, 12))

        # Panels.
        self._filters = FilterNav(self, on_select=self._on_filter_select,
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
            on_open_receipts=self._open_events,
            on_mobile_settings=self._open_settings,
            on_pair_android=lambda: self._open_pair_android(),
            on_export=self._export_view,
            on_select_clip=self._on_clip_select,
            on_copy=self._copy_again,
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
            corner_radius=0, fg_color=brand.PANEL_BG,
        )
        self._home.grid(row=1, column=0, sticky="nsew")
        self._list.grid(row=1, column=0, sticky="nsew")
        self._grid.grid(row=1, column=0, sticky="nsew")
        self._grid.grid_remove()
        self._list.grid_remove()

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
        ctk.CTkLabel(
            self._toolbar_row3,
            text="Extras go to Recently Removed — nothing is permanently deleted.",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=4)

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
            "open_receipts": self._open_events,
            "pair_android": lambda: self._open_pair_android(),
            "export": self._export_view,
            "mobile_settings": self._open_settings,
        }

    def _navigate_filter(self, key: str) -> None:
        self._filters.set_active(key)
        if key == FILTER_HOME:
            self._preview.show_vault_control(
                self.vault.dashboard_summary(),
                self._vault_panel_callbacks(),
            )
        self._on_filter_select(key)

    def _show_home(self) -> None:
        self._toolbar.grid_remove()
        self._list.grid_remove()
        self._grid.grid_remove()
        self._home.grid()

    def _show_clips(self) -> None:
        self._home.grid_remove()
        self._toolbar.grid()
        if self._view_mode == "grid":
            self._list.grid_remove()
            self._grid.grid()
        else:
            self._grid.grid_remove()
            self._list.grid()

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
            "open_asset_folder": open_asset_folder,
        }

    # --- data refresh ------------------------------------------------------
    def refresh(self) -> None:
        if not self._alive():
            return
        try:
            from ..core import storage as S

            active = self._filters.active
            counts = self.vault.counts()
            summary = self.vault.dashboard_summary()
            counts[NAV_STAMPED_RECEIPTS] = summary.get("receipts", 0)
            counts[NAV_MOBILE_ACCESS] = summary.get("paired_count", 0)
            self._filters.update_counts(counts)
            self._filters.update_collections(self.vault.list_collections())

            if active == FILTER_HOME:
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
                empty_msg = self._empty_message(active, clips, query)
                if self._view_mode == "grid":
                    self._grid.render(clips, empty_message=empty_msg)
                else:
                    self._list.render(clips, empty_message=empty_msg)
                clip_count = len(clips)

            mode = "paused" if self._monitor.paused else f"capturing ({self._monitor.mode})"
            from ..core.hotkey import normalize_hotkey
            hk = normalize_hotkey(self.vault.settings.quick_paste_hotkey)
            paste = f" · paste: {hk}" if getattr(self, "_hotkey", None) and self._hotkey.available else ""
            self._status.configure(text=f"{clip_count} shown · {mode}{paste}")
        except Exception as exc:  # noqa: BLE001
            write_crash("refresh", exc)
            raise

    # --- event handlers ----------------------------------------------------
    def _on_clip_captured(self, payload: dict) -> None:
        # Runs on the monitor thread → hop to the UI thread before touching Tk.
        if self._alive():
            self.after(0, lambda p=dict(payload): self._ingest(p))

    def _ingest(self, payload: dict) -> None:
        if not self._alive():
            return
        try:
            if payload.get("image_png"):
                self.vault.capture_image(
                    payload["image_png"],
                    width=payload.get("width") or 0,
                    height=payload.get("height") or 0,
                    source_app=payload.get("source_app"),
                    source_window=payload.get("source_window"),
                )
            elif payload.get("text"):
                self.vault.capture(
                    payload["text"],
                    source_app=payload.get("source_app"),
                    source_window=payload.get("source_window"),
                )
            else:
                return
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            write_crash("clipboard ingest", exc)
            raise

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

    def _on_filter_select(self, key: str) -> None:
        if key == NAV_STAMPED_RECEIPTS:
            self._open_events()
            return
        if key == NAV_MOBILE_ACCESS:
            self._open_settings()
            return
        if key == FILTER_HOME and self._preview._clip is None:  # noqa: SLF001
            self._preview.show_vault_control(
                self.vault.dashboard_summary(),
                self._vault_panel_callbacks(),
            )
        self.refresh()

    def _on_clip_select(self, clip) -> None:
        if clip is not None:
            self._preview.set_usage_events(self.vault.clip_usage_events(clip.id))
        self._preview.show(clip)

    # --- per-clip actions --------------------------------------------------
    def _copy_again(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip is None:
            return
        if clip.content_type == models.CONTENT_IMAGE:
            png = self.vault.copied_again_image(clip_id)
            if not png:
                return
            from ..core import image_assets
            if image_assets.write_clipboard_png(png):
                self._monitor.note_local_copy_image(png)
            return
        content = self.vault.copied_again(clip_id)
        if content is None:
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self._monitor.note_local_copy(content)

    def _copy_metadata(self, clip_id: str) -> None:
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

        menu = tk.Menu(self, tearoff=0)
        dispatch = {
            "copy_again": lambda: self._copy_again(clip.id),
            "toggle_favorite": lambda: self._toggle_favorite(clip.id),
            "move_collection": lambda: self._move_to_collection(clip.id),
            "export": lambda: self._export_clip(clip.id),
            "open": lambda: self._open_clip_path(clip.id),
            "reveal": lambda: self._reveal_clip_path(clip.id),
            "remove": lambda: self._remove_from_history(clip.id),
            "restore": lambda: self._restore(clip.id),
            "permanently_remove": lambda: self._permanently_remove(clip.id),
        }
        for item in clip_menu_items(clip):
            if item.separator_before:
                menu.add_separator()
            menu.add_command(
                label=item.label,
                state=("normal" if item.enabled else "disabled"),
                command=dispatch[item.key],
            )
        try:
            menu.tk_popup(x_root, y_root)  # native: dismisses on click-away/Esc
        finally:
            menu.grab_release()

    def _open_clip_path(self, clip_id: str) -> None:
        from ..core import pathutil
        clip = self.vault.storage.get_clip(clip_id)
        if clip:
            pathutil.open_path(clip.content)

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
        initial = f"{(clip.title if clip else 'screenshot') or 'screenshot'}.png"
        path = filedialog.asksaveasfilename(
            parent=self, title="Save Screenshot As",
            defaultextension=".png",
            initialfile=initial[:80],
            filetypes=[("PNG image", "*.png")],
        )
        if not path:
            return
        Path(path).write_bytes(png_bytes)
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
                path = filedialog.asksaveasfilename(
                    parent=self, title="Export / Save As",
                    defaultextension=".png",
                    initialfile=f"{(clip.title or 'screenshot')[:40].strip()}.png",
                    filetypes=[("PNG image", "*.png")],
                )
                if path:
                    Path(path).write_bytes(png_bytes)
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

        def load_asset_bytes(clip_id: str) -> bytes | None:
            loaded = self.vault.storage.load_clip_asset_bytes(clip_id)
            return loaded[0] if loaded else None

        if kind == "zip":
            dest = filedialog.asksaveasfilename(
                parent=self, title=f"{brand.TERM_EXPORT} — zip",
                defaultextension=".zip",
                initialfile=f"{(collection_name or 'cache-vault-export')}.zip",
                filetypes=[("Zip archive", "*.zip")])
            if not dest:
                return
            export.export_zip(clips, dest, include_files=include_files,
                              collection_name=collection_name,
                              load_asset_bytes=load_asset_bytes)
        else:
            dest = filedialog.askdirectory(
                parent=self, title=f"{brand.TERM_EXPORT} — folder")
            if not dest:
                return
            export.export_collection(clips, dest, include_files=include_files,
                                     collection_name=collection_name,
                                     load_asset_bytes=load_asset_bytes)
        self.vault.events.record(models.EVENT_EXPORTED, None,
                                 {"target": kind, "count": len(clips),
                                  "include_files": include_files})

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
            port=self.vault.settings.mobile_access_port,
        )

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
        self._monitor.pause() if settings.capture_paused else self._monitor.resume()
        self._rebind_hotkey(settings.quick_paste_hotkey)
        from ..core import startup
        startup.sync(settings.start_with_windows)
        self._mobile_bridge.sync(settings)
        self.refresh()

    def _rebind_hotkey(self, spec: str) -> None:
        """Re-register the global hotkey if the user changed it."""
        if self._hotkey and self._hotkey._spec == spec:
            return
        if self._hotkey:
            self._hotkey.stop()
        self._hotkey = HotkeyListener(
            spec, on_activate=lambda: self.after(0, self._open_quick_paste))
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
    def _open_quick_paste(self) -> None:
        if not self._alive():
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
            self._paste_target = foreground_window()
            self.vault.run_expiry_sweep()
            clips = sorted(self.vault.list_clips(), key=lambda c: c.created_at,
                           reverse=True)[: self.vault.settings.quick_paste_count]
            self._quick_paste = QuickPaste(self, clips, on_choose=self._do_paste)
        except Exception as exc:  # noqa: BLE001
            write_crash("quick paste", exc)
            raise

    def _do_paste(self, clip) -> None:
        content = self.vault.copied_again(clip.id)  # logs copied_again
        if content is None:
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self._monitor.note_local_copy(content)
        if self.vault.settings.auto_paste:
            target = self._paste_target
            self.after(60, lambda: focus_and_paste(target))
        # Confirm without revealing secrets.
        if clip.is_sensitive:
            Toast(self, "Pasted sensitive clip 🔒")
        else:
            snippet = clip.preview if len(clip.preview) <= 60 else clip.preview[:59] + "…"
            verb = "Pasted" if self.vault.settings.auto_paste else "Copied"
            Toast(self, f"{verb} ✓   {snippet}")

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

    def _on_close(self) -> None:
        # Hide to tray if we have one; otherwise quit outright.
        if self._tray.available:
            self.withdraw()
        else:
            self._quit()

    def _quit(self) -> None:
        self._shutting_down = True
        for job in (self._search_job, self._expiry_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass
        try:
            self._monitor.stop()
            self._hotkey.stop()
            self._tray.stop()
            self._mobile_bridge.stop()
            self.vault.close()
        finally:
            try:
                self.destroy()
            except Exception:  # noqa: BLE001
                pass
