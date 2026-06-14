"""Main application shell — the one product window.

Layout::

    ┌───────────────────────────────────────────────┐
    │ top bar: search ............... [Events][⚙]    │
    ├───────────┬───────────────────────┬────────────┤
    │ filters   │ clip list             │ preview    │
    └───────────┴───────────────────────┴────────────┘
"""

from __future__ import annotations

import customtkinter as ctk

from ..core import models, search
from ..core.clipboard import ClipboardMonitor
from ..core.hotkey import HotkeyListener, focus_and_paste, foreground_window
from ..core.vault import Vault
from .clip_list import ClipList
from .dialogs import EventLogDialog, SettingsDialog
from .filters import FilterNav
from .preview import PreviewPanel
from .quick_paste import QuickPaste
from .toast import Toast
from .tray import TrayController

EXPIRY_SWEEP_MS = 15_000  # run the expiry sweep every 15s


class CacheVaultApp(ctk.CTk):
    def __init__(self, vault: Vault | None = None):
        super().__init__()
        self.vault = vault or Vault()
        self.title("Cache Vault")
        self.geometry("1040x640")
        self.minsize(820, 480)

        self._search_var = ctk.StringVar()
        self._search_job = None

        self._build_layout()

        # Clipboard monitor — callback marshalled onto the Tk thread.
        self._monitor = ClipboardMonitor(
            self._on_clip_captured,
            poll_interval_ms=self.vault.settings.poll_interval_ms,
        )
        if self.vault.settings.capture_paused:
            self._monitor.pause()
        self._monitor.start()

        # Tray (optional).
        self._tray = TrayController(
            on_open=lambda: self.after(0, self._show_window),
            on_pause=lambda: self.after(0, lambda: self._set_paused(True)),
            on_resume=lambda: self.after(0, lambda: self._set_paused(False)),
            on_clear_sensitive=lambda: self.after(0, self._clear_sensitive),
            on_quit=lambda: self.after(0, self._quit),
        )
        self._tray.start()

        # Global quick-paste hotkey (default Ctrl+Shift+V).
        self._paste_target = None
        self._hotkey = HotkeyListener(
            self.vault.settings.quick_paste_hotkey,
            on_activate=lambda: self.after(0, self._open_quick_paste),
        )
        self._hotkey.start()

        # Closing the window hides to tray (if available) rather than quitting.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.refresh()
        self.after(EXPIRY_SWEEP_MS, self._expiry_tick)

    # --- layout ------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=210)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=300)
        self.grid_rowconfigure(1, weight=1)

        # Top bar.
        top = ctk.CTkFrame(self, height=52, corner_radius=0)
        top.grid(row=0, column=0, columnspan=3, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(
            top, textvariable=self._search_var,
            placeholder_text="Search everything…  (try type:link  source:cursor  sensitive:true)",
        )
        search.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        self._search_var.trace_add("write", self._on_search_changed)
        self._status = ctk.CTkLabel(top, text="", text_color=("gray45", "gray60"),
                                    font=ctk.CTkFont(size=11))
        self._status.grid(row=0, column=1, padx=6)
        ctk.CTkButton(top, text="Events", width=70, command=self._open_events
                      ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(top, text="⚙ Settings", width=90, command=self._open_settings
                      ).grid(row=0, column=3, padx=(4, 12))

        # Panels.
        self._filters = FilterNav(self, on_select=self._on_filter_select,
                                  width=210, corner_radius=0)
        self._filters.grid(row=1, column=0, sticky="nsew")

        self._list = ClipList(self, on_select=self._on_clip_select,
                              corner_radius=0, fg_color=("gray96", "gray16"))
        self._list.grid(row=1, column=1, sticky="nsew", padx=1)

        self._preview = PreviewPanel(self, actions=self._build_actions(),
                                     corner_radius=0)
        self._preview.grid(row=1, column=2, sticky="nsew")

    def _build_actions(self) -> dict:
        return {
            "copy_again": self._copy_again,
            "reveal": self.vault.reveal_sensitive,
            "toggle_pin": self._toggle_pin,
            "mark_keep": self._mark_keep,
            "copy_metadata": self._copy_metadata,
            "expire_now": self._expire_now,
            "delete": self._delete,
        }

    # --- data refresh ------------------------------------------------------
    def refresh(self) -> None:
        query = search.parse(self._search_var.get(), self._filters.active)
        clips = self.vault.list_clips(query)
        self._list.render(clips)
        self._filters.update_counts(self.vault.counts())
        mode = "paused" if self._monitor.paused else f"capturing ({self._monitor.mode})"
        from ..core.hotkey import normalize_hotkey
        hk = normalize_hotkey(self.vault.settings.quick_paste_hotkey)
        paste = f" · paste: {hk}" if getattr(self, "_hotkey", None) and self._hotkey.available else ""
        self._status.configure(text=f"{len(clips)} shown · {mode}{paste}")

    # --- event handlers ----------------------------------------------------
    def _on_clip_captured(self, text: str, source: dict) -> None:
        # Runs on the monitor thread → hop to the UI thread before touching Tk.
        self.after(0, lambda: self._ingest(text, source))

    def _ingest(self, text: str, source: dict) -> None:
        self.vault.capture(text, source_app=source.get("source_app"),
                           source_window=source.get("source_window"))
        self.refresh()

    def _on_search_changed(self, *_):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(180, self.refresh)  # debounce

    def _on_filter_select(self, _key: str) -> None:
        self.refresh()

    def _on_clip_select(self, clip) -> None:
        self._preview.show(clip)

    # --- per-clip actions --------------------------------------------------
    def _copy_again(self, clip_id: str) -> None:
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
                f"created={clip.created_at} sensitive={clip.is_sensitive}")
        self.clipboard_clear()
        self.clipboard_append(meta)
        self._monitor.note_local_copy(meta)

    def _toggle_pin(self, clip_id: str) -> None:
        clip = self.vault.storage.get_clip(clip_id)
        if clip:
            self.vault.set_pinned(clip_id, not clip.is_pinned)
            self.refresh()
            self._preview.show(self.vault.storage.get_clip(clip_id))

    def _mark_keep(self, clip_id: str) -> None:
        self.vault.mark_keep(clip_id)
        self.refresh()

    def _expire_now(self, clip_id: str) -> None:
        self.vault.expire_now(clip_id)
        self.refresh()
        self._preview.show(None)

    def _delete(self, clip_id: str) -> None:
        self.vault.delete(clip_id)
        self.refresh()
        self._preview.show(None)

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
        SettingsDialog(self, self.vault.settings, on_save=self._apply_settings)

    def _apply_settings(self, settings) -> None:
        settings.save()
        self._monitor.pause() if settings.capture_paused else self._monitor.resume()
        self._rebind_hotkey(settings.quick_paste_hotkey)
        from ..core import startup
        startup.sync(settings.start_with_windows)
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
        EventLogDialog(self, self.vault.events.recent())

    # --- quick paste (global hotkey) ---------------------------------------
    def _open_quick_paste(self) -> None:
        # Remember the app the user was in so we can paste back into it.
        self._paste_target = foreground_window()
        self.vault.run_expiry_sweep()  # don't offer secrets that should be gone
        clips = self.vault.list_clips()[: self.vault.settings.quick_paste_count]
        QuickPaste(self, clips, on_choose=self._do_paste)

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
        n = self.vault.run_expiry_sweep()
        if n:
            self.refresh()
        self.after(EXPIRY_SWEEP_MS, self._expiry_tick)

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self) -> None:
        # Hide to tray if we have one; otherwise quit outright.
        if self._tray.available:
            self.withdraw()
        else:
            self._quit()

    def _quit(self) -> None:
        try:
            self._monitor.stop()
            self._hotkey.stop()
            self._tray.stop()
            self.vault.close()
        finally:
            self.destroy()
