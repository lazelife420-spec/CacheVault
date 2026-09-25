"""Home dashboard — secure vault command center with multi-selection support."""

from __future__ import annotations

import os
from typing import Callable
import tkinter as tk
import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models, storage as S
from ..core.cleanup_suggestions import format_bytes as _format_bytes_summary
from ..core.models import Clip
from ..core.selection import analyze_selection
from . import theme
from .guide_copy import (
    TOOLTIP_HASH_PROOF,
    TOOLTIP_LOCAL_VAULT_ACTIVE,
    TOOLTIP_VAULT_MACROS,
)
from .tooltip import bind_tooltip

class HomeDashboard(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        *,
        on_filter: Callable[[str], None],
        on_open_receipts: Callable[[], None],
        on_mobile_settings: Callable[[], None],
        on_pair_android: Callable[[], None],
        on_export: Callable[[], None],
        on_select_clip: Callable[[Clip], None],
        on_copy: Callable[[str], None],
        on_double_click: Callable[[Clip], None] | None = None,
        on_clip_context: Callable[[Clip, int, int], None] | None = None,
        on_card_context: Callable[[str, str | None, int, int], None] | None = None,
        on_app_context: Callable[[int, int], None] | None = None,
        on_status_context: Callable[[str, int, int], None] | None = None,
        on_quick_paste: Callable[[], None] | None = None,
        on_view_editable_copies: Callable[[], None] | None = None,
        on_view_html_bundles: Callable[[], None] | None = None,
        on_settings: Callable[[], None] | None = None,
        on_selection_change: Callable[[list[str]], None] | None = None,
        on_batch_action: Callable[[str, list[str]], None] | None = None,
        on_open_cleanup: Callable[[], None] | None = None,
        on_scan_cleanup: Callable[[], None] | None = None,
        image_assets_ready: bool = False,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_filter = on_filter
        self._on_open_receipts = on_open_receipts
        self._on_open_cleanup = on_open_cleanup
        self._on_scan_cleanup = on_scan_cleanup
        self._on_mobile_settings = on_mobile_settings
        self._on_pair_android = on_pair_android
        self._on_export = on_export
        self._on_select_clip = on_select_clip
        self._on_copy = on_copy
        self._on_double_click = on_double_click
        self._on_clip_context = on_clip_context
        self._on_card_context = on_card_context
        self._on_app_context = on_app_context
        self._on_status_context = on_status_context
        self._on_quick_paste = on_quick_paste
        self._on_view_editable_copies = on_view_editable_copies
        self._on_view_html_bundles = on_view_html_bundles
        self._on_settings = on_settings
        self._on_selection_change = on_selection_change
        self._on_batch_action = on_batch_action
        self._image_ready = image_assets_ready

        # Multi-select state
        self._selected_ids: set[str] = set()
        self._anchor_id: str | None = None
        self._render_order: list[str] = []
        self._rendered_clips: dict[str, Clip] = {}
        self._cards: dict[str, ctk.CTkFrame] = {}
        self._batch_frame: ctk.CTkFrame | None = None
        self._selected_clip_id: str | None = None
        self._guard_selection: bool = False

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=14, pady=14)
        self._bind_context(self, lambda e: self._open_app_context(e))
        self._bind_context(self._body, lambda e: self._open_app_context(e))

    def set_layout_mode(self, mode: str) -> None:
        """Adjust responsiveness based on dashboard width."""
        if not hasattr(self, "_split_pane"):
            return
        if mode == "compact":
            self._split_pane.grid_columnconfigure(0, weight=1)
            self._split_pane.grid_columnconfigure(1, weight=0)
            self._split_pane.grid_rowconfigure(0, weight=0)
            self._split_pane.grid_rowconfigure(1, weight=0)
            self._left_pane.grid(row=0, column=0, sticky="nsew")
            self._right_pane.grid(row=1, column=0, sticky="nsew")
        else:
            self._split_pane.grid_columnconfigure(0, weight=6)
            self._split_pane.grid_columnconfigure(1, weight=4)
            self._split_pane.grid_rowconfigure(0, weight=1)
            self._left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            self._right_pane.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def set_selected(self, clip_id: str | None) -> None:
        if getattr(self, "_guard_selection", False):
            return
        self._selected_clip_id = clip_id
        self._guard_selection = True
        try:
            if clip_id is None:
                self._selected_ids.clear()
                self._anchor_id = None
            else:
                self._selected_ids = {clip_id}
                self._anchor_id = clip_id
            self._repaint_selection()
            self._update_batch_toolbar()
        finally:
            self._guard_selection = False

    def render(
        self,
        summary: dict,
        recent: list[Clip],
        favorites: list[Clip],
        images: list[Clip],
        today_clips: list[Clip] = None,
        link_clips: list[Clip] = None,
        receipts: list[Clip] = None,
        sensitive_items: list[Clip] = None,
        cleanup_summary: dict | None = None,
    ) -> None:
        del favorites
        self._cards = {}
        self._rendered_clips = {}
        self._render_order = []

        all_rendered_lists = [recent, today_clips, images, link_clips, receipts, sensitive_items]
        for lst in all_rendered_lists:
            if lst:
                for c in lst:
                    self._rendered_clips[c.id] = c
                    if c.id not in self._render_order:
                        self._render_order.append(c.id)

        # Cleanup selection list for removed clips
        self._selected_ids = {cid for cid in self._selected_ids if cid in self._render_order}

        for w in self._body.winfo_children():
            w.destroy()
        self._batch_frame = None

        # Product-first hero: identity, live vault/capture state, and the
        # single obvious next action -- the real, visible status surface.
        # No hidden test-compat widgets: tests assert against this surface.
        self._build_hero(summary, recent)

        # Create persistent toolbar host under the actions
        # A CTkFrame defaults to 200px high even when it has no children. Keep
        # the empty batch-action host collapsed so it cannot push vault content
        # below the first viewport.
        self._batch_toolbar_host = ctk.CTkFrame(
            self._body, fg_color="transparent", height=0,
        )
        self._batch_toolbar_host.pack(fill="x", pady=0)
        self._update_batch_toolbar()

        # --- Split Grid Layout for Command Center ---
        self._split_pane = ctk.CTkFrame(self._body, fg_color="transparent")
        self._split_pane.pack(fill="both", expand=True, pady=(5, 0))

        # Left Column (Active Clip & Queue, width ~ 55%)
        self._left_pane = ctk.CTkFrame(self._split_pane, fg_color="transparent")

        # Right Column (Quick Actions & Today's Clips, width ~ 45%)
        self._right_pane = ctk.CTkFrame(self._split_pane, fg_color="transparent")
        
        mode = getattr(self.master, "_current_layout_mode", "standard")
        self.set_layout_mode(mode)

        # --- Left Pane Contents ---
        left_pane = self._left_pane
        right_pane = self._right_pane
        
        # 1. Recent Active Clip (Center of attention)
        if recent:
            self._pane_section_title(left_pane, "Recent Active Clip")
            self._active_clip_card(left_pane, recent[0])

        # 1b. More retained content right behind the lead card — real clips
        # fill the first viewport instead of dead canvas. (CV-ULTIMATE-B:
        # the owner called out the mostly-empty Command Center.)
        more_recent = [c for c in recent[1:5]]
        if more_recent:
            self._pane_section_title(left_pane, "More Recent")
            for clip in more_recent:
                self._compact_clip_card(left_pane, clip)

        # 2. What Needs Review -- progressive disclosure: only surfaces when
        # at least one queue actually holds items. A healthy vault stays calm;
        # zero-count rows are never rendered just because the card exists.
        attention_items = [
            ("Sensitive Items", summary.get("sensitive", 0), S.FILTER_SENSITIVE),
            ("Duplicate Clips", summary.get("duplicates", 0), S.FILTER_DUPLICATES),
            ("Expired Clips", summary.get("expired", 0), S.FILTER_EXPIRED),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED),
        ]
        attention_items = [item for item in attention_items if item[1] > 0]
        if attention_items:
            self._pane_section_title(left_pane, "What Needs Review")
            self._render_needs_review(left_pane, attention_items)
        self._render_cleanup_suggestions(left_pane, cleanup_summary or {})

        # 3. Sensitive / Expiring Items
        if sensitive_items:
            self._pane_section_title(left_pane, "Sensitive / Expiring Items")
            for clip in sensitive_items[:3]:
                self._compact_clip_card(left_pane, clip)

        # 4. Receipts ready for review
        if receipts:
            self._pane_section_title(left_pane, "Receipts Ready")
            for clip in receipts[:3]:
                self._compact_clip_card(left_pane, clip)

        # --- Right Pane Contents ---
        # The former "Quick Actions" button grid was removed in CV-ULTIMATE-B:
        # every one of its actions duplicated a surface that already exists
        # (hero Quick Paste / Save Clipboard, sidebar filters, receipts pill,
        # batch Combine). The right pane now leads with retained content.

        # 1. Captured today
        if today_clips:
            self._pane_section_title(right_pane, "Captured Today")
            for clip in today_clips[:4]:
                self._compact_clip_card(right_pane, clip)

        # 3. Recent Links
        if link_clips:
            self._pane_section_title(right_pane, "Recent Links")
            for clip in link_clips[:3]:
                self._compact_clip_card(right_pane, clip)

        # 4. Images captured
        if images:
            self._pane_section_title(right_pane, "Images Captured")
            for clip in images[:3]:
                self._compact_clip_card(right_pane, clip)

    def _build_hero(self, summary: dict, recent: list[Clip]) -> None:
        """Hero band: product identity, real vault/capture state, and the one
        dominant next action.

        Hierarchy contract: Cache Vault -> capture/vault state -> latest
        item -> Quick Paste (or Resume Capture when paused). Everything else
        lives below the fold."""
        paused = bool(summary.get("capture_paused"))
        hero = ctk.CTkFrame(self._body, **theme.vault_card(border_width=1))
        hero.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(hero, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        inner.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        mark = self._product_mark(left)
        if mark is not None:
            mark.pack(side="left", padx=(0, 12))

        text_col = ctk.CTkFrame(left, fg_color="transparent")
        text_col.pack(side="left")

        ctk.CTkLabel(
            text_col, text=brand.PRODUCT_NAME, anchor="w",
            font=theme.font(size=20, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col,
            text="Capture paused" if paused else brand.VAULT_STATUS_ACTIVE,
            anchor="w",
            text_color=brand.STAMP_GOLD if paused else brand.PROOF_TEAL,
            font=theme.font(size=12, weight="bold"),
        ).pack(anchor="w")

        chips = ctk.CTkFrame(text_col, fg_color="transparent")
        chips.pack(anchor="w", pady=(5, 0))
        for chip in (
            brand.LABEL_LOCAL_ONLY,
            "Capture paused" if paused else "Capture active",
            "Mobile Access on" if summary.get("mobile_enabled") else "Mobile Access off",
            f"Safe: {summary.get('default_safe') or 'default'}",
        ):
            ctk.CTkLabel(
                chips, text=chip, text_color=brand.MUTED_FG,
                font=theme.meta_font(10),
            ).pack(side="left", padx=(0, 10))

        if recent:
            latest = recent[0]
            latest_title = latest.title or clip_metadata.clip_title(latest.content, latest.preview)
            ctk.CTkLabel(
                text_col,
                text=f"Latest · {latest_title} · {clip_metadata.human_timestamp(latest.created_at)}",
                anchor="w", text_color=brand.MUTED_FG,
                font=theme.body_font(11),
            ).pack(anchor="w", pady=(3, 0))

        actions = ctk.CTkFrame(inner, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(14, 0))
        window = self.winfo_toplevel()
        if paused:
            ctk.CTkButton(
                actions, text="Resume Capture", width=150, height=34,
                command=lambda: window._set_paused(False),  # noqa: SLF001
                **theme.primary_button(),
            ).pack(anchor="e")
        elif self._on_quick_paste:
            ctk.CTkButton(
                actions, text="Quick Paste", width=150, height=34,
                command=self._on_quick_paste,
                **theme.primary_button(),
            ).pack(anchor="e")
        ctk.CTkButton(
            actions, text="Save Clipboard", width=150, height=28,
            command=lambda: window._manual_save_clipboard(),  # noqa: SLF001
            **theme.secondary_button(),
        ).pack(anchor="e", pady=(6, 0))

        # Filter pills live inside the hero band — truthful counts attached to
        # the product identity instead of a separate chrome strip below it.
        pills = ctk.CTkFrame(hero, fg_color="transparent")
        pills.pack(fill="x", padx=16, pady=(0, 12))
        cards_data = [
            ("All Clips", summary.get("all", 0), S.FILTER_ALL),
            ("Favorites", summary.get("favorites", 0), S.FILTER_FAVORITES),
            ("Screenshots", summary.get("screenshots", 0), S.FILTER_SCREENSHOTS),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES),
            ("Receipts", summary.get("receipts", 0), None),
        ]
        for label, count, filt in cards_data:
            pill = ctk.CTkFrame(
                pills, fg_color=brand.ROW_BG, corner_radius=999,
            )
            pill.pack(side="left", padx=(0, 6))
            label_widget = ctk.CTkLabel(
                pill, text=label, cursor="hand2", text_color=brand.MUTED_FG,
                font=theme.meta_font(9),
            )
            label_widget.pack(side="left", padx=(9, 3), pady=3)
            count_widget = ctk.CTkLabel(
                pill, text=str(count), cursor="hand2", text_color=brand.MUTED_FG,
                font=theme.font(size=9, weight="bold"),
            )
            count_widget.pack(side="left", padx=(0, 9), pady=3)
            handler = (lambda _e, f=filt: self._on_filter(f)) if filt else (lambda _e: self._on_open_receipts())
            for widget in (pill, label_widget, count_widget):
                widget.bind("<Button-1>", handler)
                widget.configure(cursor="hand2")

    def _product_mark(self, parent):
        """Load the product icon bound to this dashboard's own Tk root.

        PIL + ImageTk (not CTkImage): CTkImage binds its photo to
        ``Tk._default_root``, which breaks across the suite's many app
        create/destroy cycles -- the same reason the toolbar search icon uses
        this pattern (see shell.py). Returns ``None`` when Pillow or the
        asset is unavailable so the hero degrades to a text-only lockup."""
        try:
            from PIL import Image, ImageTk
            from . import icon as _icon
            path = _icon.asset_path("cache-vault-icon-48.png")
            if not os.path.exists(path):
                return None
            img = Image.open(path).convert("RGBA").resize((44, 44), Image.LANCZOS)
            self._hero_icon = ImageTk.PhotoImage(img, master=self)
            # Native tk.Label, matching the search-icon pattern in shell.py:
            # CTkLabel warns about non-CTkImage scaling, and CTkImage binds to
            # Tk._default_root (which breaks the suite's many-root cycles).
            return tk.Label(
                parent, image=self._hero_icon,
                bg=brand.SURFACE_BG[1] if isinstance(brand.SURFACE_BG, tuple) else brand.SURFACE_BG,
                highlightthickness=0, borderwidth=0,
            )
        except Exception:  # noqa: BLE001 - product mark is decorative
            return None

    def _update_batch_toolbar(self) -> None:
        if not hasattr(self, "_batch_toolbar_host") or not self._batch_toolbar_host:
            return

        for child in self._batch_toolbar_host.winfo_children():
            child.destroy()

        if len(self._selected_ids) < 2:
            self._batch_toolbar_host.pack_configure(pady=0)
            self._batch_frame = None
            return

        self._batch_toolbar_host.pack_configure(pady=(0, 12))

        self._batch_frame = ctk.CTkFrame(
            self._batch_toolbar_host,
            fg_color=brand.PANEL_BG,
            border_width=2,
            border_color=brand.PROOF_TEAL,
            corner_radius=8,
        )
        self._batch_frame.pack(fill="x")

        inner = ctk.CTkFrame(self._batch_frame, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        count = len(self._selected_ids)
        ctk.CTkLabel(
            inner,
            text=f"{count} clips selected",
            font=theme.heading_font(13),
            text_color=brand.PROOF_TEAL,
        ).pack(side="left", padx=(0, 10))

        selected_clips = [self._rendered_clips[cid] for cid in self._selected_ids if cid in self._rendered_clips]
        summary = analyze_selection(selected_clips)

        actions = []
        if summary.text_count or summary.link_count:
            action = "copy_text_links" if summary.selection_class == "mixed" else "combine"
            actions.append(("Copy Combined Text", action))
        actions.extend([
            ("Create Proof Receipt", "receipt"),
            ("Export Selection", "export_selection"),
        ])
        if summary.image_count:
            actions.append(("Save Images", "save_images"))

        ordered_selected = [cid for cid in self._render_order if cid in self._selected_ids]

        # Standard action buttons
        for text, act in actions:
            if self._on_batch_action:
                ctk.CTkButton(
                    inner,
                    text=text,
                    width=80,
                    height=24,
                    command=lambda a=act: self._on_batch_action(a, ordered_selected),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)

        ctk.CTkButton(
            inner, text="More…", width=60, height=24,
            command=lambda: self.winfo_toplevel()._open_bulk_clip_menu(
                ordered_selected, inner.winfo_rootx(), inner.winfo_rooty() + inner.winfo_height()
            ),
            **theme.secondary_button(),
        ).pack(side="left", padx=2)

        # Clear Selection
        ctk.CTkButton(
            inner,
            text="Clear",
            width=60,
            height=24,
            command=self.clear_selection,
            **theme.secondary_button(),
        ).pack(side="right", padx=2)

        # Select All Visible
        ctk.CTkButton(
            inner,
            text="Select All",
            width=80,
            height=24,
            command=self.select_all_visible,
            **theme.secondary_button(),
        ).pack(side="right", padx=2)

    def _pane_section_title(self, parent, text: str) -> None:
        ctk.CTkLabel(parent, text=text, anchor="w", **theme.section_heading()
                     ).pack(fill="x", pady=(4, 6))

    def _render_needs_review(self, parent, items: list) -> None:
        frame = ctk.CTkFrame(parent, fg_color=brand.SURFACE_BG, corner_radius=8,
                             border_width=1, border_color=brand.VAULT_CARD_BORDER)
        frame.pack(fill="x", pady=4)
        for label, count, filt in items:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=5)
            row.grid_columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(12))
            lbl.grid(row=0, column=0, sticky="w")

            cnt = ctk.CTkLabel(row, text=str(count), anchor="e",
                               text_color=brand.STAMP_GOLD if count else brand.MUTED_FG,
                               font=theme.font(size=12, weight="bold"))
            cnt.grid(row=0, column=1, sticky="e")

            handler = lambda _e, f=filt: self._on_filter(f)
            row.bind("<Button-1>", handler)
            lbl.bind("<Button-1>", handler)
            cnt.bind("<Button-1>", handler)
            row.configure(cursor="hand2")
            lbl.configure(cursor="hand2")
            cnt.configure(cursor="hand2")

    def _render_cleanup_suggestions(self, parent, cleanup_summary: dict) -> None:
        """Home card for Vault Cleanup Suggestions. Never scans automatically
        -- this only ever shows the result of the LAST scan the user ran
        (cleanup_summary is empty until then), plus explicit Scan/Review
        actions. Byte counts here are always "identified", never
        "recoverable" -- moving to Recently Removed does not free disk space.
        """
        frame = ctk.CTkFrame(parent, fg_color=brand.SURFACE_BG, corner_radius=8,
                             border_width=1, border_color=brand.VAULT_CARD_BORDER)
        frame.pack(fill="x", pady=4)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header, text="Cleanup Suggestions", anchor="w",
                     font=theme.heading_font(13)).pack(side="left")

        failed = bool(cleanup_summary.get("failed"))
        scanned = bool(cleanup_summary) and not failed and "total_groups" in cleanup_summary
        if failed:
            # A failed scan must be visible, not silently indistinguishable
            # from "no scan yet" -- the prior successful result (if any) is
            # untouched in state and still shown in the review screen; this
            # card only reports that the LAST attempt didn't complete.
            ctk.CTkLabel(
                frame, text="Scan failed", anchor="w", text_color=brand.WARNING_RED,
                font=theme.font(size=12, weight="bold"),
            ).pack(fill="x", padx=12, pady=(0, 2))
            error_text = cleanup_summary.get("error_message") or "The scan could not complete."
            # Bounded so an unexpected exception message can't blow up the
            # card layout or leak an unbounded traceback/path into the UI.
            if len(error_text) > 160:
                error_text = error_text[:157] + "..."
            ctk.CTkLabel(
                frame, text=error_text, anchor="w", text_color=brand.MUTED_FG,
                font=theme.body_font(11), wraplength=340, justify="left",
            ).pack(fill="x", padx=12, pady=(0, 2))
            last_scan = cleanup_summary.get("last_scan_label", "")
            if last_scan:
                ctk.CTkLabel(
                    frame, text=f"Attempted {last_scan}", anchor="w", text_color=brand.MUTED_FG,
                    font=theme.body_font(10),
                ).pack(fill="x", padx=12, pady=(0, 4))
        elif scanned:
            group_count = cleanup_summary.get("total_groups", 0)
            item_count = cleanup_summary.get("total_reviewable_items", 0)
            bytes_identified = cleanup_summary.get("redundant_bytes_identified", 0)
            last_scan = cleanup_summary.get("last_scan_label", "")
            status = cleanup_summary.get("status", "Idle")

            for label, value in (
                ("Suggestion groups", str(group_count)),
                ("Reviewable items", str(item_count)),
                ("Redundant bytes identified", _format_bytes_summary(bytes_identified)),
                ("Last scan", last_scan or "—"),
                ("Status", status),
            ):
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=1)
                row.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(11),
                             text_color=brand.MUTED_FG).grid(row=0, column=0, sticky="w")
                ctk.CTkLabel(row, text=value, anchor="e", font=theme.body_font(11)).grid(
                    row=0, column=1, sticky="e",
                )
        else:
            ctk.CTkLabel(
                frame, text="No scan yet.", anchor="w", text_color=brand.MUTED_FG,
                font=theme.body_font(11),
            ).pack(fill="x", padx=12, pady=(0, 4))

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(6, 10))
        if self._on_scan_cleanup:
            scan_label = "Retry scan" if failed else "Scan vault"
            ctk.CTkButton(actions, text=scan_label, height=26, command=self._on_scan_cleanup,
                          **theme.secondary_button()).pack(side="left", padx=(0, 6))
        if self._on_open_cleanup:
            ctk.CTkButton(actions, text="Review suggestions", height=26,
                          state="normal" if scanned else "disabled",
                          command=self._on_open_cleanup, **theme.secondary_button()).pack(side="left")

    # Click & Multi-Select Logic
    _CTRL_MASK = 0x0004
    _SHIFT_MASK = 0x0001

    def _on_card_click(self, event, clip: Clip) -> None:
        try:
            self.winfo_toplevel().focus_set()
        except Exception:
            pass
        state = getattr(event, "state", 0) or 0
        if state & self._CTRL_MASK:
            self._toggle_select(clip)
        elif state & self._SHIFT_MASK:
            self._range_select(clip)
        else:
            self._select(clip)

    def _on_card_context_menu(self, event, clip: Clip) -> None:
        if clip.id not in self._selected_ids or len(self._selected_ids) <= 1:
            self._select(clip)
        if self._on_clip_context:
            self._on_clip_context(clip, event.x_root, event.y_root)

    def _select(self, clip: Clip) -> None:
        self._guard_selection = True
        try:
            self._selected_ids = {clip.id}
            self._anchor_id = clip.id
            self._repaint_selection()
            self._notify_selection_change()
            self._on_select_clip(clip)
        finally:
            self._guard_selection = False

    def _toggle_select(self, clip: Clip) -> None:
        self._guard_selection = True
        try:
            if clip.id in self._selected_ids:
                self._selected_ids.discard(clip.id)
                if self._anchor_id == clip.id:
                    self._anchor_id = next(iter(self._selected_ids), None)
            else:
                self._selected_ids.add(clip.id)
                self._anchor_id = clip.id
            self._repaint_selection()
            self._notify_selection_change()
        finally:
            self._guard_selection = False

    def _range_select(self, clip: Clip) -> None:
        self._guard_selection = True
        try:
            anchor = self._anchor_id if self._anchor_id in self._render_order else None
            if anchor is None or clip.id not in self._render_order:
                self._selected_ids = {clip.id}
                self._anchor_id = clip.id
                self._repaint_selection()
                self._notify_selection_change()
                self._on_select_clip(clip)
                return
            start = self._render_order.index(anchor)
            end = self._render_order.index(clip.id)
            lo, hi = (start, end) if start <= end else (end, start)
            self._selected_ids = set(self._render_order[lo:hi + 1])
            self._repaint_selection()
            self._notify_selection_change()
        finally:
            self._guard_selection = False

    def select_all_visible(self) -> None:
        if not self._render_order:
            return
        self._guard_selection = True
        try:
            self._selected_ids = set(self._render_order)
            self._anchor_id = self._render_order[0]
            self._repaint_selection()
            self._notify_selection_change()
        finally:
            self._guard_selection = False

    def clear_selection(self) -> None:
        self._guard_selection = True
        try:
            self._selected_ids.clear()
            self._anchor_id = None
            self._repaint_selection()
            self._notify_selection_change()
        finally:
            self._guard_selection = False

    def _repaint_selection(self) -> None:
        for cid, card in self._cards.items():
            if card.winfo_exists():
                selected = cid in self._selected_ids
                card.configure(
                    border_width=2 if selected else 1,
                    border_color=brand.PROOF_TEAL if selected else brand.VAULT_CARD_BORDER,
                )

    def _notify_selection_change(self) -> None:
        ordered = [cid for cid in self._render_order if cid in self._selected_ids]
        if self._on_selection_change:
            self._on_selection_change(ordered)
        self._update_batch_toolbar()

    def _section_title(self, text: str) -> None:
        ctk.CTkLabel(self._body, text=text, anchor="w", **theme.section_heading()
                     ).pack(fill="x", pady=(4, 8))

    def _compact_clip_card(self, parent, clip: Clip) -> None:
        selected = clip.id in self._selected_ids
        card = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=brand.SURFACE_BG,
            border_width=3 if selected else 1,
            border_color=brand.PROOF_TEAL if selected else brand.VAULT_CARD_BORDER,
        )
        card.pack(fill="x", pady=4)
        self._cards[clip.id] = card

        badge = clip_metadata.format_label(clip.classification, clip.content_type).upper()
        if clip.is_sensitive:
            badge = "SENSITIVE"

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(top, text=badge, font=theme.font(size=10, weight="bold"),
                     text_color=brand.WARNING_RED if clip.is_sensitive else brand.MUTED_FG
                     ).pack(side="left")

        badge_lbl = ctk.CTkLabel(
            top,
            text="SELECTED",
            font=theme.font(size=10, weight="bold"),
            text_color=brand.FOUNDRY_BLACK,
            fg_color=brand.PROOF_TEAL,
            corner_radius=999,
            padx=10,
            pady=2,
        )
        if selected:
            badge_lbl.pack(side="left", padx=(8, 0))

        trail = ctk.CTkFrame(top, fg_color="transparent")
        trail.pack(side="right")
        if clip.is_pinned:
            ctk.CTkLabel(trail, text="★", font=theme.font(size=13),
                         text_color=brand.STAMP_GOLD).pack(side="left", padx=3)
        if clip.content_hash:
            proof = ctk.CTkLabel(trail, text="⬢", font=theme.font(size=11),
                                 text_color=brand.STAMP_GOLD, cursor="question_arrow")
            proof.pack(side="left", padx=3)
            self._bind_tooltip(proof, TOOLTIP_HASH_PROOF)

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(card, text=title, anchor="w",
                     font=theme.heading_font(13)).pack(fill="x", padx=12)
        preview = _clip_preview_lines(clip.preview or "", max_lines=2)
        ctk.CTkLabel(card, text=preview, anchor="w", justify="left",
                     text_color=brand.MUTED_FG, wraplength=520,
                     font=theme.body_font(11)).pack(fill="x", padx=12, pady=(2, 0))

        window = self.winfo_toplevel()
        storage = getattr(getattr(window, "vault", None), "storage", None)
        meta = clip_metadata.source_summary_line(clip, storage)

        ctk.CTkLabel(card, text=meta, anchor="w", text_color=brand.MUTED_FG,
                     font=theme.meta_font(10)).pack(fill="x", padx=12, pady=(0, 6))

        # Actions frame
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 8))
        self._fill_action_bar(actions, clip, compact=True)

        self._bind_clip_card(card, clip)

    def _active_clip_card(self, parent, clip: Clip) -> None:
        selected = clip.id in self._selected_ids
        card = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=brand.ROW_SELECTED_BG if selected else brand.ROW_BG,
            border_width=3 if selected else 1,
            border_color=brand.PROOF_TEAL if selected else brand.VAULT_CARD_BORDER,
        )
        card.pack(fill="x", pady=6)
        self._cards[clip.id] = card

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=12)

        badge = clip_metadata.format_label(clip.classification, clip.content_type).upper()
        if clip.is_sensitive:
            badge = "SENSITIVE"

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(top, text=badge, font=theme.font(size=10, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(side="left")

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(body, text=title, anchor="w",
                     font=theme.heading_font(15)).pack(fill="x")

        preview = _clip_preview_lines(clip.preview or "", max_lines=3)
        ctk.CTkLabel(body, text=preview, anchor="w", justify="left",
                     text_color=brand.MUTED_FG, wraplength=520,
                     font=theme.body_font(12)).pack(fill="x", pady=(4, 8))

        window = self.winfo_toplevel()
        storage = getattr(getattr(window, "vault", None), "storage", None)
        meta = clip_metadata.source_summary_line(clip, storage)

        ctk.CTkLabel(body, text=meta, anchor="w", text_color=brand.MUTED_FG,
                     font=theme.font(size=11, weight="bold")).pack(fill="x", pady=(0, 8))

        # Action buttons
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(4, 0))
        self._fill_action_bar(actions, clip, compact=False)

        self._bind_clip_card(card, clip)

    def _fill_action_bar(self, parent, clip: Clip, *, compact: bool) -> None:
        for child in parent.winfo_children():
            child.destroy()

        window = self.winfo_toplevel()

        # Detect type
        is_image = False
        cls = getattr(clip, "classification", None)
        ct = getattr(clip, "content_type", None)
        if (isinstance(ct, str) and ct.startswith("image")) or (isinstance(cls, str) and ("screen" in cls.lower() or "screenshot" in cls.lower())) or cls == models.CLASS_IMAGE:
            is_image = True
        is_link = (cls == models.CLASS_LINK)

        # Primary Copy
        copy_label = "Copy" if not is_image else "Copy Image"
        ctk.CTkButton(
            parent, text=copy_label, width=70, height=22,
            command=lambda: window._copy_again(clip.id),
            **theme.primary_button()
        ).pack(side="left", padx=2)

        # Narrow cards intentionally expose only Copy, one contextual action,
        # and More. Wide cards may expose the common editing actions.
        if is_link:
            ctk.CTkButton(
                parent, text="Open Link", width=70, height=22,
                command=lambda: window._open_clip_link(clip.id),
                **theme.quiet_button()
            ).pack(side="left", padx=2)
        elif is_image:
            ctk.CTkButton(
                parent, text="View Larger", width=80, height=22,
                command=lambda: window._open_photo_viewer(clip.id),
                **theme.quiet_button()
            ).pack(side="left", padx=2)
        else:
            if cls == models.CLASS_PATH:
                ctk.CTkButton(
                    parent, text="Open Path", width=70, height=22,
                    command=lambda: window._open_clip_path(clip.id),
                    **theme.quiet_button()
                ).pack(side="left", padx=2)

        # Edit (not for image)
        if not is_image and (not compact or not is_link):
            ctk.CTkButton(
                parent, text="Edit", width=50, height=22,
                command=lambda: window._edit_clip_text(clip.id),
                **theme.quiet_button()
            ).pack(side="left", padx=2)

        # Duplicate (not for image)
        if not compact and not is_image:
            ctk.CTkButton(
                parent, text="Duplicate", width=70, height=22,
                command=lambda: window._duplicate_as_editable_clip(clip.id),
                **theme.quiet_button()
            ).pack(side="left", padx=2)

        # Combine (only if text/not image)
        if not compact and not is_image and not is_link:
            ctk.CTkButton(
                parent, text="Combine", width=65, height=22,
                command=lambda: window._open_clip_composer(),
                **theme.quiet_button()
            ).pack(side="left", padx=2)

        # More...
        ctk.CTkButton(
            parent, text="More…", width=50, height=22,
            command=lambda: window._open_home_clip_menu(clip, parent.winfo_rootx(), parent.winfo_rooty() + 24),
            **theme.quiet_button()
        ).pack(side="left", padx=2)

    def _bind_clip_card(self, card, clip: Clip) -> None:
        def click(e, c=clip) -> str:
            self._on_card_click(e, c)
            return "break"

        def context(e, c=clip) -> str:
            self._on_card_context_menu(e, c)
            return "break"

        def double_click(e, c=clip) -> str:
            if self._on_double_click:
                self._on_double_click(c)
            return "break"

        card.bind("<Button-1>", click)
        card.bind("<Control-Button-1>", click)
        card.bind("<Shift-Button-1>", click)
        card.bind("<Double-Button-1>", double_click)
        card.bind("<Button-3>", context)
        card.bind("<Button-2>", context)
        for child in card.winfo_children():
            self._bind_clip_child_events(child, click, context, double_click)

    def _bind_clip_child_events(self, widget, click, context, double_click) -> None:
        if isinstance(widget, ctk.CTkButton):
            return
        widget.bind("<Button-1>", click)
        widget.bind("<Control-Button-1>", click)
        widget.bind("<Shift-Button-1>", click)
        widget.bind("<Double-Button-1>", double_click)
        widget.bind("<Button-3>", context)
        widget.bind("<Button-2>", context)
        for child in widget.winfo_children():
            self._bind_clip_child_events(child, click, context, double_click)

    def _open_card_context(self, label: str, filt: str | None, event) -> str:
        if self._on_card_context:
            self._on_card_context(label, filt, event.x_root, event.y_root)
        return "break"

    def _open_status_context(self, surface: str, event) -> str:
        if self._on_status_context:
            self._on_status_context(surface, event.x_root, event.y_root)
        return "break"

    def _open_app_context(self, event) -> str:
        if self._on_app_context:
            self._on_app_context(event.x_root, event.y_root)
        return "break"

    @staticmethod
    def _bind_context(widget, handler) -> None:
        widget.bind("<Button-3>", handler)
        widget.bind("<Button-2>", handler)
        for child in widget.winfo_children():
            HomeDashboard._bind_context(child, handler)

    @staticmethod
    def _bind_tooltip(widget, text: str) -> None:
        bind_tooltip(widget, text)


def _clip_preview_lines(text: str, *, max_lines: int = 2) -> str:
    lines = text.splitlines()[:max_lines]
    out = "\n".join(lines)
    if len(text.splitlines()) > max_lines:
        out += "…"
    return out or "(empty)"


def vault_status_text(summary: dict) -> str:
    """Build the compact vault status line for tests."""
    capture = "Capture paused" if summary.get("capture_paused") else "Capture active"
    mobile = "Mobile Access on" if summary.get("mobile_enabled") else "Mobile Access off"
    return (
        f"Local-first · {capture} · Receipts on · {mobile} · "
        f"{summary.get('all', 0)} saved clips · {summary.get('receipts', 0)} receipts"
    )
