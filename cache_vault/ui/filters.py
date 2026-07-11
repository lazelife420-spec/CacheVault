"""Left-hand filter navigation with grouped headings."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from .. import licensing
from ..core import storage as S
from ..core.settings import Settings
from ..core.smart_folders import SMART_FOLDER_NAV
from . import theme
from .guide_copy import EMPTY_SAFES, NAV_TOOLTIPS, TOOLTIP_SAFES
from .tooltip import bind_tooltip

# Sidebar screens and actions
NAV_QUICK_PASTE = "nav_quick_paste"
NAV_STAMPED_RECEIPTS = "nav_stamped_receipts"
NAV_EXPORTS = "nav_exports"
NAV_EDITABLE_COPIES = "nav_editable_copies"
NAV_HTML_BUNDLES = "nav_html_bundles"
NAV_MOBILE_ACCESS = "nav_mobile_access"
NAV_MOBILE_INBOX = "nav_mobile_inbox"
NAV_VAULT_MACROS = "nav_vault_macros"
NAV_HOTKEY_ACTIONS = "nav_hotkey_actions"
NAV_FOUNDER = "nav_founder"
NAV_SETTINGS = "nav_settings"
NAV_NEW_SAFE = "nav_new_safe"

NAV_DIALOG_ONLY = frozenset({NAV_QUICK_PASTE, NAV_FOUNDER, NAV_NEW_SAFE})
NAV_SCREEN_KEYS = frozenset({
    NAV_STAMPED_RECEIPTS,
    NAV_EXPORTS,
    NAV_EDITABLE_COPIES,
    NAV_HTML_BUNDLES,
    NAV_MOBILE_ACCESS,
    NAV_MOBILE_INBOX,
    NAV_VAULT_MACROS,
    NAV_HOTKEY_ACTIONS,
})

_NAV_ICONS: dict[str, str] = {
    S.FILTER_HOME: "⌂ ",
    S.FILTER_ALL: "▣ ",
    S.FILTER_FAVORITES: "★ ",
    S.FILTER_SCREENSHOTS: "▦ ",
    S.FILTER_SENSITIVE: "⚠ ",
    S.FILTER_DUPLICATES: "≡ ",
    NAV_QUICK_PASTE: "⎘ ",
    NAV_STAMPED_RECEIPTS: "⬢ ",
    NAV_EXPORTS: "↗ ",
    NAV_EDITABLE_COPIES: "⎘ ",
    NAV_HTML_BUNDLES: "🌐 ",
    NAV_MOBILE_ACCESS: "◈ ",
    NAV_MOBILE_INBOX: "↓ ",
    NAV_VAULT_MACROS: "⚡ ",
    NAV_HOTKEY_ACTIONS: "⌨ ",
    NAV_FOUNDER: "◆ ",
    NAV_SETTINGS: "⚙ ",
}

FILTER_GROUPS: list[tuple[str | None, list[tuple[str, str]]]] = [
    ("COMMAND", [
        (S.FILTER_HOME, brand.TERM_COMMAND_CENTER),
        (NAV_QUICK_PASTE, "Quick Paste"),
        (NAV_VAULT_MACROS, brand.TERM_SNIPPET_MACROS),
        (NAV_HOTKEY_ACTIONS, "Hotkey Actions"),
    ]),
    ("VAULT", [
        (S.FILTER_ALL, "All Clips"),
        (S.FILTER_FAVORITES, "Favorites"),
        (S.FILTER_SCREENSHOTS, "Screenshots / Images"),
        (S.FILTER_LINKS, "Links"),
        (S.FILTER_FILES, "Files / Paths"),
        (S.FILTER_CODE, "Code"),
        (S.FILTER_COMMANDS, "Commands"),
        (S.FILTER_EMAILS, "Emails"),
        (S.FILTER_PHONES, "Phone Numbers"),
    ]),
    ("SMART FOLDERS", list(SMART_FOLDER_NAV)),
    ("REVIEW", [
        (S.FILTER_SENSITIVE, "Sensitive"),
        (S.FILTER_DUPLICATES, "Duplicates"),
        (S.FILTER_RECENTLY_REMOVED, "Recently Removed"),
        (S.FILTER_EXPIRED, "Expired"),
    ]),
    ("PROOF", [
        (NAV_STAMPED_RECEIPTS, brand.TERM_STAMPED_RECEIPTS),
        (NAV_EXPORTS, brand.TERM_EXPORTS),
        (NAV_EDITABLE_COPIES, brand.TERM_EDITABLE_COPIES),
        (NAV_HTML_BUNDLES, brand.TERM_HTML_BUNDLES),
    ]),
    ("ACCESS", [
        (NAV_MOBILE_INBOX, brand.TERM_MOBILE_INBOX),
        (NAV_MOBILE_ACCESS, brand.TERM_MOBILE_ACCESS),
        (NAV_SETTINGS, "Settings"),
    ]),
    ("TIME", [
        (S.FILTER_TODAY, "Today"),
        (S.FILTER_WEEK, "This Week"),
        (S.FILTER_OLDER, "Older"),
    ]),
]


class HoverScrollFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._default_width = self._scrollbar.cget("width") or 8
        self._default_btn_color = self._scrollbar._button_color
        self._default_hover_color = self._scrollbar._button_hover_color
        self._default_fg_color = self._scrollbar._fg_color

        self._hovered = False
        self._focused = False
        self._scrolling = False
        self._scrolling_timer = None

        # Bind events
        self._parent_canvas.bind("<Enter>", lambda _e: self._set_hovered(True))
        self._parent_canvas.bind("<Leave>", lambda _e: self._set_hovered(False))
        self._scrollbar.bind("<Enter>", lambda _e: self._set_hovered(True))
        self._scrollbar.bind("<Leave>", lambda _e: self._set_hovered(False))

        # Bind scroll events to detect scrolling activity
        self._parent_canvas.bind("<MouseWheel>", lambda _e: self._on_scroll())

        self._update_loop()

    def _set_hovered(self, val: bool) -> None:
        self._hovered = val
        self.update_scrollbar_state()

    def set_focused(self, val: bool) -> None:
        self._focused = val
        self.update_scrollbar_state()

    def _on_scroll(self) -> None:
        self._scrolling = True
        self.update_scrollbar_state()
        if self._scrolling_timer:
            self.after_cancel(self._scrolling_timer)
        self._scrolling_timer = self.after(1000, self._stop_scrolling)

    def _stop_scrolling(self) -> None:
        self._scrolling = False
        self._scrolling_timer = None
        self.update_scrollbar_state()

    def has_overflow(self) -> bool:
        y = self._parent_canvas.yview()
        return y != (0.0, 1.0)

    def scroll_to_widget(self, widget) -> None:
        try:
            y = widget.winfo_y()
            canvas_height = self._parent_canvas.winfo_height()
            frame_height = self.winfo_height()
            if frame_height > canvas_height:
                viewport_fraction = (y - canvas_height / 2) / frame_height
                viewport_fraction = max(0.0, min(1.0, viewport_fraction))
                self._parent_canvas.yview("moveto", viewport_fraction)
        except Exception:
            pass

    def update_scrollbar_state(self) -> None:
        if not self.has_overflow():
            self._scrollbar.grid_forget()
            return

        border_spacing = self._apply_widget_scaling(self._parent_frame.cget("corner_radius") + self._parent_frame.cget("border_width"))
        self._scrollbar.grid(row=1, column=1, sticky="nsew", pady=border_spacing)

        if self._hovered or self._focused or self._scrolling:
            self._scrollbar.configure(
                width=self._default_width,
                button_color=self._default_btn_color,
                button_hover_color=self._default_hover_color,
                fg_color=self._default_fg_color
            )
        else:
            low_contrast_color = ("#D5D5D5", "#3A3A3A")
            self._scrollbar.configure(
                width=4,
                button_color=low_contrast_color,
                button_hover_color=low_contrast_color,
                fg_color="transparent"
            )

    def _update_loop(self) -> None:
        self.update_scrollbar_state()
        self._update_job = self.after(500, self._update_loop)

    def destroy(self) -> None:
        if hasattr(self, "_update_job") and self._update_job:
            try:
                self.after_cancel(self._update_job)
            except Exception:
                pass
            self._update_job = None
        if hasattr(self, "_scrolling_timer") and self._scrolling_timer:
            try:
                self.after_cancel(self._scrolling_timer)
            except Exception:
                pass
            self._scrolling_timer = None
        super().destroy()


class SidebarRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        key: str,
        display: str,
        on_select: Callable[[str], None],
        on_context: Callable[[str, int, int], None] | None = None,
        tip: str | None = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", corner_radius=6, height=36, **kwargs)
        self.pack_propagate(False)
        self._key = key
        self._on_select = on_select
        self._on_context = on_context
        self._active = False

        # Left selection rail (3px teal)
        self._rail = ctk.CTkFrame(self, width=3, fg_color="transparent")
        self._rail.pack(side="left", fill="y", padx=(2, 0), pady=4)

        # Content frame
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(side="left", fill="both", expand=True, padx=(8, 8))

        # Use grid layout inside content to prevent shifts when counts update
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_columnconfigure(1, weight=0)

        self._label = ctk.CTkLabel(
            self._content,
            text=display,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        self._label.grid(row=0, column=0, sticky="nsew", pady=4)

        self._count = ctk.CTkLabel(
            self._content,
            text="",
            anchor="e",
            width=36,
            font=ctk.CTkFont(size=11),
            text_color=brand.MUTED_FG
        )
        self._count.grid(row=0, column=1, sticky="ns", padx=(4, 0))

        # Tooltip
        if tip:
            bind_tooltip(self, tip)
            bind_tooltip(self._label, tip)
            bind_tooltip(self._count, tip)

        # Bind events
        for w in (self, self._content, self._label, self._count):
            w.bind("<Button-1>", lambda _e: self._select_clicked())
            w.configure(cursor="hand2")

        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))

        # Keyboard focus bindings
        import tkinter as tk
        tk.Frame.configure(self, takefocus=True)
        self.bind("<FocusIn>", lambda _e: self._focus_changed(True))
        self.bind("<FocusOut>", lambda _e: self._focus_changed(False))
        self.bind("<Return>", lambda _e: self._select_clicked())
        self.bind("<space>", lambda _e: self._select_clicked())

        # Keyboard arrows navigation
        self.bind("<Up>", lambda _e: self._move_focus(-1))
        self.bind("<Down>", lambda _e: self._move_focus(1))

        # Right click bindings
        self._bind_context()

    def _bind_context(self) -> None:
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Shift-F10>", self._on_right_click)
        for child in self.winfo_children():
            child.bind("<Button-3>", self._on_right_click)
            child.bind("<Shift-F10>", self._on_right_click)
            if hasattr(child, "winfo_children"):
                for subchild in child.winfo_children():
                    subchild.bind("<Button-3>", self._on_right_click)
                    subchild.bind("<Shift-F10>", self._on_right_click)

    def _on_right_click(self, event) -> None:
        # 1. Right-click selects or targets the clicked row first.
        # 2. The menu acts on that row, not the previously active row.
        if self._key not in (NAV_FOUNDER, NAV_NEW_SAFE, NAV_SETTINGS):
            self._select_clicked()
        if self._on_context:
            x = getattr(event, "x_root", self.winfo_rootx())
            y = getattr(event, "y_root", self.winfo_rooty() + 10)
            self._on_context(self._key, x, y)

    def _select_clicked(self) -> None:
        self._on_select(self._key)
        # Scroll selected row into view
        p = self.master
        while p is not None:
            if isinstance(p, HoverScrollFrame):
                p.scroll_to_widget(self)
                break
            p = getattr(p, "master", None)

    def _move_focus(self, direction: int) -> None:
        p = self.master
        while p is not None and not hasattr(p, "get_all_rows"):
            p = getattr(p, "master", None)
        if p is None:
            return
        all_rows = p.get_all_rows()
        try:
            idx = all_rows.index(self)
            next_idx = idx + direction
            if 0 <= next_idx < len(all_rows):
                all_rows[next_idx].focus_set()
        except ValueError:
            pass

    def _hover(self, inside: bool) -> None:
        if self._active:
            return
        if inside:
            self.configure(fg_color=theme.nav_hover_bg())
            p = self.master
            while p is not None:
                if isinstance(p, HoverScrollFrame):
                    p._set_hovered(True)
                    break
                p = getattr(p, "master", None)
        else:
            self.configure(fg_color="transparent")
            p = self.master
            while p is not None:
                if isinstance(p, HoverScrollFrame):
                    p._set_hovered(False)
                    break
                p = getattr(p, "master", None)

    def _focus_changed(self, focused: bool) -> None:
        if focused:
            self.configure(border_width=1, border_color=brand.PROOF_TEAL)
            p = self.master
            while p is not None:
                if isinstance(p, HoverScrollFrame):
                    p.set_focused(True)
                    p.scroll_to_widget(self)
                    break
                p = getattr(p, "master", None)
        else:
            self.configure(border_width=0)
            p = self.master
            while p is not None:
                if isinstance(p, HoverScrollFrame):
                    p.set_focused(False)
                    break
                p = getattr(p, "master", None)

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.configure(fg_color=theme.nav_active_bg())
            self._rail.configure(fg_color=brand.PROOF_TEAL)
            self._label.configure(
                text_color=(brand.FOUNDRY_BLACK, brand.PROOF_TEAL),
                font=ctk.CTkFont(size=12, weight="bold")
            )
            if self._key != NAV_FOUNDER:
                self._count.configure(
                    text_color=(brand.FOUNDRY_BLACK, brand.STAMP_GOLD)
                )
        else:
            self.configure(fg_color="transparent")
            self._rail.configure(fg_color="transparent")
            self._label.configure(
                text_color=brand.MUTED_FG,
                font=ctk.CTkFont(size=12, weight="normal")
            )
            if self._key != NAV_FOUNDER:
                self._count.configure(text_color=brand.MUTED_FG)

    def set_count(self, val: str) -> None:
        self._count.configure(text=val)


class SidebarSectionHeader(ctk.CTkFrame):
    def __init__(
        self,
        master,
        heading: str,
        collapsed: bool,
        on_toggle: Callable[[str], None],
        on_context: Callable[[str, int, int], None] | None = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", height=32, **kwargs)
        self.pack_propagate(False)
        self._heading = heading
        self._collapsed = collapsed
        self._on_toggle = on_toggle
        self._on_context = on_context

        self._btn = ctk.CTkButton(
            self,
            text=self._get_label(),
            anchor="w",
            height=32,
            command=lambda: self._on_toggle(self._heading),
            fg_color="transparent",
            hover_color=theme.nav_hover_bg(),
            text_color=brand.STAMP_GOLD,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self._btn.pack(fill="both", expand=True)

        if self._on_context:
            self._btn.bind("<Button-3>", self._on_right_click)
            self._btn.bind("<Shift-F10>", self._on_right_click)

    def _on_right_click(self, event) -> None:
        x = getattr(event, "x_root", self.winfo_rootx())
        y = getattr(event, "y_root", self.winfo_rooty() + 10)
        self._on_context(self._heading, x, y)

    def _get_label(self) -> str:
        return ("▸ " if self._collapsed else "▾ ") + self._heading

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._btn.configure(text=self._get_label())

    def bind(self, sequence=None, func=None, add=None):
        self._btn.bind(sequence, func, add)
        return super().bind(sequence, func, add)

    def configure(self, **kwargs):
        if "text" in kwargs:
            self._btn.configure(text=kwargs.pop("text"))
        super().configure(**kwargs)

    def cget(self, attribute_name: str):
        if attribute_name == "text":
            return self._btn.cget("text")
        return super().cget(attribute_name)


class FilterNav(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_select: Callable[[str], None],
        *,
        settings: Settings | None = None,
        on_safe_context: Callable[[dict, int, int], None] | None = None,
        on_collection_context: Callable[[str, int, int], None] | None = None,
        on_section_context: Callable[[str, int, int], None] | None = None,
        on_nav_context: Callable[[str, int, int], None] | None = None,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_select = on_select
        self._on_safe_context = on_safe_context
        self._on_collection_context = on_collection_context
        self._on_section_context = on_section_context
        self._on_nav_context = on_nav_context
        self._settings = settings
        self._collapsed = set(getattr(settings, "sidebar_collapsed_sections", []) or [])
        self._active = S.FILTER_HOME
        self._rows: dict[str, SidebarRow] = {}
        self._labels: dict[str, ctk.CTkLabel] = {}
        self._counts: dict[str, ctk.CTkLabel] = {}
        self._labels_text: dict[str, str] = {}
        self._collection_rows: dict[str, SidebarRow] = {}
        self._safe_rows: dict[str, SidebarRow] = {}
        self._safe_meta: dict[str, dict] = {}
        self._section_frames: dict[str, ctk.CTkFrame] = {}
        self._section_headers: dict[str, SidebarSectionHeader] = {}
        self._section_buttons: dict[str, SidebarSectionHeader] = {}

        # 1. Fixed Header (Packed directly on self so winfo_children()[0] is the title label)
        title = ctk.CTkLabel(self, text=f"◈ {brand.PRODUCT_NAME}", anchor="w",
                             text_color=brand.PROOF_TEAL,
                             font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(fill="x", padx=16, pady=(12, 0))
        byline = ctk.CTkLabel(self, text=brand.VAULT_TAGLINE, anchor="w",
                               text_color=brand.MUTED_FG,
                               font=ctk.CTkFont(size=11), wraplength=200,
                               justify="left")
        byline.pack(fill="x", padx=16, pady=(0, 2))
        seal = ctk.CTkLabel(
            self, text=f"{brand.LABEL_VAULT_SEALED} · {brand.LABEL_LOCAL_ONLY}",
            anchor="w", text_color=brand.STAMP_GOLD,
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        seal.pack(fill="x", padx=16, pady=(0, 6))

        # 2. Fixed Footer
        self._footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._footer_frame.pack(fill="x", side="bottom", padx=8, pady=(0, 8))

        divider = ctk.CTkFrame(self._footer_frame, height=1, fg_color=("#C8D0D4", "#263038"))
        divider.pack(fill="x", pady=(0, 6))

        # Compact License Status Badge
        self._status_badge = ctk.CTkLabel(
            self._footer_frame,
            text="FREE",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=brand.MUTED_FG,
            fg_color=("#E5E9EB", "#1C242C"),
            corner_radius=4,
            padx=6,
            pady=2,
            cursor="hand2"
        )
        self._status_badge.pack(side="left", padx=(4, 0))
        self._status_badge.bind("<Button-1>", lambda _e: self._select(NAV_FOUNDER))
        bind_tooltip(self._status_badge, "View license status / upgrade")

        footer_tools = ctk.CTkFrame(self._footer_frame, fg_color="transparent")
        footer_tools.pack(side="right")

        self._toggle_all_btn = ctk.CTkButton(
            footer_tools, text="↕", width=24, height=24,
            command=self._toggle_expand_collapse_all,
            **theme.secondary_button(),
        )
        self._toggle_all_btn.pack(side="left", padx=2)
        bind_tooltip(self._toggle_all_btn, "Toggle Expand/Collapse All")

        self._overflow_btn = ctk.CTkButton(
            footer_tools, text="⋮", width=24, height=24,
            command=self._show_sidebar_menu,
            **theme.secondary_button(),
        )
        self._overflow_btn.pack(side="left", padx=2)
        bind_tooltip(self._overflow_btn, "Sidebar Options")

        # Map dummy references for tests/Founder update compatibility
        self._rows[NAV_FOUNDER] = self._status_badge # type: ignore
        self._counts[NAV_FOUNDER] = self._status_badge # type: ignore
        self._labels_text[NAV_FOUNDER] = "Founder"

        # 3. Independently Scrollable Center Panel
        self._scroll_frame = HoverScrollFrame(self, fg_color="transparent", corner_radius=0)
        self._scroll_frame.pack(fill="both", expand=True, side="top", padx=2, pady=4)

        # Build items list inside scrollable center
        self._separator()

        for heading, items in FILTER_GROUPS:
            parent = self._scroll_frame
            if heading:
                parent = self._section(heading, default_open=False)
            for key, label in items:
                self._labels_text[key] = label
                display = _NAV_ICONS.get(key, "") + label
                self._rows[key] = self._nav_row(parent, key, display)
                if key in (NAV_QUICK_PASTE, NAV_VAULT_MACROS):
                    self._bind_nav_context(key)

        self._separator()
        self._collections_frame = self._section("COLLECTIONS", default_open=False)
        self._collections_empty = ctk.CTkLabel(
            self._collections_frame, text="(none yet)", anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11))
        self._collections_empty.pack(fill="x", padx=14, pady=2)

        self._separator()
        self._safes_frame = self._section("SAFES", default_open=False)
        bind_tooltip(self._section_headers["SAFES"], TOOLTIP_SAFES)
        self._new_safe_btn = ctk.CTkButton(
            self._safes_frame, text="+ New Safe", height=24, anchor="w",
            command=lambda: self._select(NAV_NEW_SAFE),
            **theme.secondary_button(),
        )
        self._new_safe_btn.pack(fill="x", padx=10, pady=(2, 4))
        self._safes_empty = ctk.CTkLabel(
            self._safes_frame, text=EMPTY_SAFES, anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
            wraplength=200, justify="left",
        )
        self._safes_empty.pack(fill="x", padx=14, pady=2)

        self._highlight()

    def pack_slaves(self) -> list:
        return self._scroll_frame.pack_slaves()

    def get_all_rows(self) -> list[SidebarRow]:
        rows = []
        for child in self._scroll_frame.winfo_children():
            if isinstance(child, SidebarRow) and child.winfo_viewable():
                rows.append(child)
            elif isinstance(child, ctk.CTkFrame) and child.winfo_viewable():
                for subchild in child.winfo_children():
                    if isinstance(subchild, SidebarRow) and subchild.winfo_viewable():
                        rows.append(subchild)
        return rows

    def destroy(self) -> None:
        if hasattr(self, "_scroll_frame") and self._scroll_frame:
            try:
                self._scroll_frame.destroy()
            except Exception:
                pass
        super().destroy()

    def _separator(self) -> None:
        ctk.CTkFrame(self._scroll_frame, height=1, fg_color=("#C8D0D4", "#263038")).pack(
            fill="x", padx=10, pady=6)

    def _section(self, heading: str, *, default_open: bool) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._scroll_frame, fg_color="transparent")
        self._section_frames[heading] = frame

        collapsed = heading in self._collapsed

        header = SidebarSectionHeader(
            self._scroll_frame,
            heading=heading,
            collapsed=collapsed,
            on_toggle=self._toggle_section,
            on_context=self._on_section_context
        )
        self._section_headers[heading] = header
        self._section_buttons[heading] = header
        header.pack(fill="x", padx=6, pady=(8 if default_open else 2, 4))

        if not collapsed:
            frame.pack(fill="x")
        return frame

    def _toggle_section(self, heading: str) -> None:
        if heading in self._collapsed:
            self.expand_section(heading)
        else:
            self.collapse_section(heading)

    @property
    def active_label(self) -> str:
        return self._labels_text.get(self._active, self._active)

    def expand_section(self, heading: str) -> None:
        if heading not in self._collapsed:
            return
        self._collapsed.remove(heading)
        header = self._section_headers[heading]
        header.set_collapsed(False)
        self._section_frames[heading].pack(fill="x", after=header)
        self._persist_collapsed()

    def collapse_section(self, heading: str) -> None:
        if heading in self._collapsed:
            return
        self._collapsed.add(heading)
        header = self._section_headers[heading]
        header.set_collapsed(True)
        self._section_frames[heading].pack_forget()
        self._persist_collapsed()

    def collapse_all(self) -> None:
        for heading in self._section_frames:
            if heading not in self._collapsed:
                self._collapsed.add(heading)
                self._section_frames[heading].pack_forget()
                self._section_headers[heading].set_collapsed(True)
        self._persist_collapsed()

    def expand_all(self) -> None:
        for heading, frame in self._section_frames.items():
            if heading in self._collapsed:
                self._collapsed.discard(heading)
                frame.pack(fill="x", after=self._section_headers[heading])
                self._section_headers[heading].set_collapsed(False)
        self._persist_collapsed()

    def _toggle_expand_collapse_all(self) -> None:
        all_collapsed = all(h in self._collapsed for h in self._section_frames)
        if all_collapsed:
            self.expand_all()
        else:
            self.collapse_all()

    def _show_sidebar_menu(self) -> None:
        from .clip_context import popup_menu
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Expand All Sections", command=self.expand_all)
        menu.add_command(label="Collapse All Sections", command=self.collapse_all)
        menu.add_separator()
        menu.add_command(label="New Safe...", command=lambda: self._select(NAV_NEW_SAFE))
        menu.add_command(label="Upgrade to Founder...", command=lambda: self._select(NAV_FOUNDER))

        x = self._overflow_btn.winfo_rootx()
        y = self._overflow_btn.winfo_rooty() - 100
        popup_menu(self, menu, x, y)

    def _persist_collapsed(self) -> None:
        if self._settings is not None:
            self._settings.sidebar_collapsed_sections = sorted(self._collapsed)
            self._settings.save()

    def _nav_row(self, parent, key: str, label: str) -> SidebarRow:
        tip = NAV_TOOLTIPS.get(key)

        on_context = None
        if self._on_nav_context:
            on_context = lambda k, x, y: self._on_nav_context(k, x, y)

        row = SidebarRow(
            parent,
            key=key,
            display=label,
            on_select=self._select,
            on_context=on_context,
            tip=tip
        )
        self._labels[key] = row._label
        self._counts[key] = row._count
        return row

    def _bind_nav_context(self, key: str) -> None:
        if self._on_nav_context is None:
            return
        row = self._rows.get(key)
        if row:
            row._on_context = lambda k, x, y: self._on_nav_context(k, x, y)
            row._bind_context()

    def _hover_row(self, row: SidebarRow, key: str, inside: bool) -> None:
        if key == self._active:
            return
        row._hover(inside)

    def _select(self, key: str) -> None:
        if key in NAV_DIALOG_ONLY:
            self._on_select(key)
            return
        self._active = key
        self._highlight()
        self._on_select(key)

    @property
    def active(self) -> str:
        return self._active

    def set_active(self, key: str) -> None:
        if key in NAV_DIALOG_ONLY:
            return
        self._active = key
        self._highlight()

    def _highlight(self) -> None:
        all_keys = {**self._rows, **self._collection_rows, **self._safe_rows}
        for key, row in all_keys.items():
            if key == NAV_FOUNDER:
                continue
            active = key == self._active
            if hasattr(row, "set_active"):
                row.set_active(active)
            else:
                row.configure(fg_color=theme.nav_active_bg() if active else "transparent")

    def update_counts(self, counts: dict[str, int]) -> None:
        for key, label in self._labels_text.items():
            if key == S.FILTER_HOME:
                self._counts[key].configure(text="")
                continue
            if key == NAV_FOUNDER:
                continue
            n = counts.get(key, 0)
            self._counts[key].configure(text=str(n) if n else "")

    def update_founder_status(self, status: licensing.LicenseStatus) -> None:
        badge = self._counts.get(NAV_FOUNDER)
        if not badge:
            return
        if status.state == licensing.LicenseState.FOUNDER_VALID:
            badge.configure(text="FOUNDER", text_color=brand.STAMP_GOLD, fg_color=("#3E2D13", "#2A1F0D"))
        elif status.state == licensing.LicenseState.MISSING_LICENSE:
            badge.configure(text="FREE", text_color=brand.MUTED_FG, fg_color=("#E5E9EB", "#1C242C"))
        elif status.state == licensing.LicenseState.EXPIRED_LICENSE:
            badge.configure(text="EXPIRED", text_color=brand.WARNING_RED, fg_color=("#FADBD8", "#2C1C1C"))
        else:
            badge.configure(text="ISSUE", text_color=brand.WARNING_RED, fg_color=("#FADBD8", "#2C1C1C"))

    def update_collections(self, collections: list[dict]) -> None:
        for row in self._collection_rows.values():
            row.destroy()
        self._collection_rows.clear()
        for key in list(self._labels):
            if key.startswith(S.COLLECTION_PREFIX):
                del self._labels[key]
                if key in self._counts:
                    del self._counts[key]
        if not collections:
            self._collections_empty.pack(fill="x", padx=14, pady=2)
        else:
            self._collections_empty.pack_forget()
            for col in collections:
                name = col["name"]
                key = S.COLLECTION_PREFIX + name

                on_context = None
                if self._on_collection_context:
                    on_context = lambda k, x, y, n=name: self._on_collection_context(n, x, y)

                row = SidebarRow(
                    self._collections_frame,
                    key=key,
                    display=f"  {name}",
                    on_select=self._select,
                    on_context=on_context
                )
                self._collection_rows[key] = row
                self._labels[key] = row._label
                self._counts[key] = row._count
                row._count.configure(text=str(col["count"]))
        self._highlight()

    def _collection_context(self, event, name: str) -> None:
        if self._on_collection_context is None:
            return
        self._on_collection_context(name, event.x_root, event.y_root)

    def update_safes(self, safes: list[dict]) -> None:
        for row in self._safe_rows.values():
            row.destroy()
        self._safe_rows.clear()
        self._safe_meta.clear()
        for key in list(self._labels):
            if key.startswith(S.SAFE_PREFIX):
                del self._labels[key]
                del self._counts[key]
        shown = [s for s in safes if s.get("count", 0) > 0 or s.get("builtin")]
        if not shown:
            self._safes_empty.pack(fill="x", padx=14, pady=2)
        else:
            self._safes_empty.pack_forget()
            for safe in shown:
                key = S.SAFE_PREFIX + safe["id"]

                on_context = None
                if self._on_safe_context:
                    on_context = lambda k, x, y, sf=safe: self._on_safe_context(sf, x, y)

                row = SidebarRow(
                    self._safes_frame,
                    key=key,
                    display=f"  {safe['name']}",
                    on_select=self._select,
                    on_context=on_context
                )
                self._safe_rows[key] = row
                self._safe_meta[key] = dict(safe)
                self._labels[key] = row._label
                self._counts[key] = row._count
                row._count.configure(text=str(safe.get("count", 0)))
        self._highlight()

    def _safe_context(self, event, key: str) -> None:
        if self._on_safe_context is None:
            return
        safe = self._safe_meta.get(key)
        if safe:
            self._on_safe_context(safe, event.x_root, event.y_root)
