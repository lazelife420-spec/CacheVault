"""Home dashboard — secure vault command center with multi-selection support."""

from __future__ import annotations

from typing import Callable
import tkinter as tk
import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models, storage as S
from ..core.models import Clip
from ..core.selection import analyze_selection
from . import theme
from .guide_copy import (
    TOOLTIP_HASH_PROOF,
    TOOLTIP_LOCAL_VAULT_ACTIVE,
    TOOLTIP_VAULT_MACROS,
)
from .tooltip import bind_tooltip

_CARD_META = {
    "All Clips": "Saved items in your vault",
    "Favorites": "Starred clips you keep close",
    "Screenshots": "Saved PNG screenshots from clipboard",
    "Duplicates": "Needs review",
    "Recently Removed": "Restorable removed clips",
    "Receipts": "Local proof history",
}

_CARD_ICONS = {
    "All Clips": "▣",
    "Favorites": "★",
    "Screenshots": "▦",
    "Duplicates": "≡",
    "Recently Removed": "↩",
    "Receipts": "⬢",
}

_CARD_HEIGHT = 108
_CARD_BORDER = brand.VAULT_CARD_BORDER
_CARD_BORDER_HOVER = (brand.PROOF_TEAL, brand.PROOF_TEAL_DIM)


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
        image_assets_ready: bool = False,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_filter = on_filter
        self._on_open_receipts = on_open_receipts
        self._on_mobile_settings = on_mobile_settings
        self._on_pair_android = on_pair_android
        self._on_export = on_export
        self._on_select_clip = on_select_clip
        self._on_copy = on_copy
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

        # --- Redesigned Premium Title & Status Header ---
        header_frame = ctk.CTkFrame(self._body, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        title_lbl = ctk.CTkLabel(
            header_frame, text="Today in CacheVault", anchor="w",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=brand.PROOF_TEAL,
        )
        title_lbl.pack(side="left")

        status_bar = ctk.CTkFrame(header_frame, fg_color="transparent")
        status_bar.pack(side="right", pady=5)

        capture_active = not summary.get("capture_paused")
        status_dot = "●"
        status_text = "Capture Active" if capture_active else "Capture Paused"
        status_color = brand.PROOF_TEAL if capture_active else brand.MUTED_FG

        lbl_cap = ctk.CTkLabel(
            status_bar, text=f"{status_dot} {status_text}",
            text_color=status_color, font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_cap.pack(side="left", padx=8)

        lbl_proof = ctk.CTkLabel(
            status_bar, text="● Receipts Active",
            text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_proof.pack(side="left", padx=8)

        lbl_status = ctk.CTkLabel(
            status_bar, text=brand.VAULT_STATUS_ACTIVE,
            text_color=brand.PROOF_TEAL, font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_status.pack(side="left", padx=8)

        mobile_on = bool(summary.get("mobile_enabled"))
        mobile_text = (
            f"Mobile Access · {summary.get('paired_count', 0)} paired"
            if mobile_on
            else "Mobile Access off"
        )
        lbl_mob = ctk.CTkLabel(
            status_bar, text=f"● {mobile_text}",
            text_color=brand.PROOF_TEAL if mobile_on else brand.MUTED_FG,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_mob.pack(side="left", padx=8)

        lbl_local = ctk.CTkLabel(
            status_bar, text=f"● {brand.LABEL_LOCAL_ONLY}",
            text_color=brand.PROOF_TEAL, font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_local.pack(side="left", padx=8)

        # --- Custody Summary Statistics ---
        stats_frame = ctk.CTkFrame(self._body, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 15))

        cards_data = [
            ("All Clips", summary.get("all", 0), S.FILTER_ALL, brand.PROOF_TEAL),
            ("Favorites", summary.get("favorites", 0), S.FILTER_FAVORITES, brand.STAMP_GOLD),
            ("Screenshots", summary.get("screenshots", 0), S.FILTER_SCREENSHOTS, brand.PROOF_TEAL),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES, brand.STAMP_GOLD),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED, brand.MUTED_FG),
            ("Receipts", summary.get("receipts", 0), None, brand.STAMP_GOLD),
        ]

        for label, count, filt, color in cards_data:
            stat_box = ctk.CTkFrame(stats_frame, fg_color=brand.SURFACE_BG, corner_radius=6, border_width=1, border_color=brand.VAULT_CARD_BORDER)
            stat_box.pack(side="left", padx=4, fill="both", expand=True)

            lbl = ctk.CTkLabel(stat_box, text=label, font=ctk.CTkFont(size=10, weight="bold"), text_color=brand.MUTED_FG)
            lbl.pack(pady=(6, 2), padx=8)

            cnt = ctk.CTkLabel(stat_box, text=str(count), font=ctk.CTkFont(size=16, weight="bold"), text_color=color)
            cnt.pack(pady=(0, 6), padx=8)

            handler = (lambda _e, f=filt: self._on_filter(f)) if filt else (lambda _e: self._on_open_receipts())
            lbl.bind("<Button-1>", handler)
            cnt.bind("<Button-1>", handler)
            stat_box.bind("<Button-1>", handler)

        # --- Primary Actions Panel ---
        actions_panel = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8, border_width=1, border_color=brand.VAULT_CARD_BORDER)
        actions_panel.pack(fill="x", pady=(0, 18))

        inner_actions = ctk.CTkFrame(actions_panel, fg_color="transparent")
        inner_actions.pack(fill="x", padx=12, pady=10)

        window = self.winfo_toplevel()

        ctk.CTkButton(
            inner_actions, text="Save Clipboard", width=110, height=28,
            command=lambda: window._manual_save_clipboard(),
            **theme.primary_button()
        ).pack(side="left", padx=4)

        if self._on_quick_paste:
            ctk.CTkButton(
                inner_actions, text="⚡ Quick Paste", width=100, height=28,
                command=self._on_quick_paste,
                **theme.secondary_button()
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            inner_actions, text="Review Links", width=100, height=28,
            command=lambda: self._on_filter(S.FILTER_LINKS),
            **theme.secondary_button()
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            inner_actions, text="View Images", width=100, height=28,
            command=lambda: self._on_filter(S.FILTER_SCREENSHOTS),
            **theme.secondary_button()
        ).pack(side="left", padx=4)

        # Combine Selected
        combine_btn = ctk.CTkButton(
            inner_actions, text="Combine Selected", width=120, height=28,
            command=lambda: window._open_clip_composer(),
            state="normal" if len(self._selected_ids) >= 2 else "disabled",
            **theme.secondary_button()
        )
        combine_btn.pack(side="left", padx=4)

        ctk.CTkButton(
            inner_actions, text="Open Receipts", width=110, height=28,
            command=self._on_open_receipts,
            **theme.secondary_button()
        ).pack(side="left", padx=4)

        # Create persistent toolbar host under the actions
        self._batch_toolbar_host = ctk.CTkFrame(self._body, fg_color="transparent")
        self._batch_toolbar_host.pack(fill="x", pady=0)
        self._update_batch_toolbar()

        # --- Recent Active Clip Section ---
        if recent:
            self._section_title("Recent Active Clip")
            self._active_clip_card(recent[0])

        # --- Today's Captured Clips ---
        if today_clips:
            self._section_title("Clips Captured Today")
            for clip in today_clips[:5]:
                self._compact_clip_card(clip)

        # --- Images ---
        if images:
            self._section_title("Images & Screenshots")
            for clip in images[:4]:
                self._compact_clip_card(clip)

        # --- Links ---
        if link_clips:
            self._section_title("Recent Links")
            for clip in link_clips[:4]:
                self._compact_clip_card(clip)

        # --- Receipts ---
        if receipts:
            self._section_title("Stamped Proof Receipts")
            for clip in receipts[:4]:
                self._compact_clip_card(clip)

        # --- Sensitive / Expiring ---
        if sensitive_items:
            self._section_title("Sensitive / Expiring Items")
            for clip in sensitive_items[:4]:
                self._compact_clip_card(clip)

    def _update_batch_toolbar(self) -> None:
        if not hasattr(self, "_batch_toolbar_host") or not self._batch_toolbar_host:
            return

        for child in self._batch_toolbar_host.winfo_children():
            child.destroy()

        if not self._selected_ids:
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
            text=f"⚡ {count} selected",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(side="left", padx=(0, 10))

        selected_clips = [self._rendered_clips[cid] for cid in self._selected_ids if cid in self._rendered_clips]
        summary = analyze_selection(selected_clips)

        # Build dynamic command center actions
        actions = []
        if summary.selection_class in ("link_only", "text_only"):
            actions = [
                ("Copy Plain", "copy"),
                ("Copy MD", "copy_md"),
                ("Move Safe", "move_safe"),
            ]
        elif summary.selection_class == "image_only":
            actions = [
                ("Save PNGs", "save_images"),
                ("Export ZIP", "export_zip"),
                ("Copy Paths", "copy_paths"),
            ]
        else:  # mixed
            actions = [
                ("Copy Text+Links", "copy_text_links"),
                ("Save PNGs", "save_images"),
                ("Move Safe", "move_safe"),
            ]

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

        # Delete Action
        if self._on_batch_action:
            ctk.CTkButton(
                inner,
                text="Delete",
                width=60,
                height=24,
                command=lambda: self._on_batch_action("delete", ordered_selected),
                **theme.destructive_button(),
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

    # Click & Multi-Select Logic
    _CTRL_MASK = 0x0004
    _SHIFT_MASK = 0x0001

    def _on_card_click(self, event, clip: Clip) -> None:
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
                    border_width=3 if selected else 1,
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

    def _compact_clip_card(self, clip: Clip) -> None:
        selected = clip.id in self._selected_ids
        card = ctk.CTkFrame(
            self._body,
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
        ctk.CTkLabel(top, text=badge, font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=brand.WARNING_RED if clip.is_sensitive else brand.MUTED_FG
                     ).pack(side="left")

        badge_lbl = ctk.CTkLabel(
            top,
            text="SELECTED",
            font=ctk.CTkFont(size=10, weight="bold"),
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
            ctk.CTkLabel(trail, text="★", font=ctk.CTkFont(size=13),
                         text_color=brand.STAMP_GOLD).pack(side="left", padx=3)
        if clip.content_hash:
            proof = ctk.CTkLabel(trail, text="⬢", font=ctk.CTkFont(size=11),
                                 text_color=brand.STAMP_GOLD, cursor="question_arrow")
            proof.pack(side="left", padx=3)
            self._bind_tooltip(proof, TOOLTIP_HASH_PROOF)

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(card, text=title, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=12)
        preview = _clip_preview_lines(clip.preview or "", max_lines=2)
        ctk.CTkLabel(card, text=preview, anchor="w", justify="left",
                     text_color=brand.MUTED_FG, wraplength=520,
                     font=theme.body_font(11)).pack(fill="x", padx=12, pady=(2, 0))

        window = self.winfo_toplevel()
        storage = getattr(getattr(window, "vault", None), "storage", None)
        meta = clip_metadata.source_summary_line(clip, storage)

        ctk.CTkLabel(card, text=meta, anchor="w", text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=10)).pack(fill="x", padx=12, pady=(0, 6))

        # Actions frame
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 8))
        self._fill_action_bar(actions, clip)

        self._bind_clip_card(card, clip)

    def _active_clip_card(self, clip: Clip) -> None:
        selected = clip.id in self._selected_ids
        card = ctk.CTkFrame(
            self._body,
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
        ctk.CTkLabel(top, text=badge, font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(side="left")

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(body, text=title, anchor="w",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(fill="x")

        preview = _clip_preview_lines(clip.preview or "", max_lines=3)
        ctk.CTkLabel(body, text=preview, anchor="w", justify="left",
                     text_color=brand.MUTED_FG, wraplength=520,
                     font=theme.body_font(12)).pack(fill="x", pady=(4, 8))

        window = self.winfo_toplevel()
        storage = getattr(getattr(window, "vault", None), "storage", None)
        meta = clip_metadata.source_summary_line(clip, storage)

        ctk.CTkLabel(body, text=meta, anchor="w", text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x", pady=(0, 8))

        # Action buttons
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(4, 0))
        self._fill_action_bar(actions, clip)

        self._bind_clip_card(card, clip)

    def _fill_action_bar(self, parent, clip: Clip) -> None:
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
        copy_label = "Copy Image" if is_image else "Copy"
        ctk.CTkButton(
            parent, text=copy_label, width=70, height=22,
            command=lambda: window._copy_again(clip.id),
            **theme.primary_button()
        ).pack(side="left", padx=2)

        # Primary Open
        if is_link:
            ctk.CTkButton(
                parent, text="Open Link", width=70, height=22,
                command=lambda: window._open_clip_link(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)
        elif is_image:
            ctk.CTkButton(
                parent, text="View Larger", width=80, height=22,
                command=lambda: window._open_photo_viewer(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)
        else:
            if cls == models.CLASS_PATH:
                ctk.CTkButton(
                    parent, text="Open Path", width=70, height=22,
                    command=lambda: window._open_clip_path(clip.id),
                    **theme.secondary_button()
                ).pack(side="left", padx=2)

        # Edit (not for image)
        if not is_image:
            ctk.CTkButton(
                parent, text="Edit", width=50, height=22,
                command=lambda: window._edit_clip_text(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)

        # Duplicate (not for image)
        if not is_image:
            ctk.CTkButton(
                parent, text="Duplicate", width=70, height=22,
                command=lambda: window._duplicate_as_editable_clip(clip.id),
                **theme.secondary_button()
            ).pack(side="left", padx=2)

        # Combine (only if text/not image)
        if not is_image:
            ctk.CTkButton(
                parent, text="Combine", width=65, height=22,
                command=lambda: window._open_clip_composer(),
                **theme.secondary_button()
            ).pack(side="left", padx=2)

        # More...
        ctk.CTkButton(
            parent, text="More…", width=50, height=22,
            command=lambda: window._open_home_clip_menu(clip, parent.winfo_rootx(), parent.winfo_rooty() + 24),
            **theme.secondary_button()
        ).pack(side="left", padx=2)

    def _bind_clip_card(self, card, clip: Clip) -> None:
        def click(e, c=clip) -> str:
            self._on_card_click(e, c)
            return "break"

        def context(e, c=clip) -> str:
            self._on_card_context_menu(e, c)
            return "break"

        card.bind("<Button-1>", click)
        card.bind("<Control-Button-1>", click)
        card.bind("<Shift-Button-1>", click)
        card.bind("<Button-3>", context)
        card.bind("<Button-2>", context)
        for child in card.winfo_children():
            self._bind_clip_child_events(child, click, context)

    def _bind_clip_child_events(self, widget, click, context) -> None:
        if isinstance(widget, ctk.CTkButton):
            return
        widget.bind("<Button-1>", click)
        widget.bind("<Control-Button-1>", click)
        widget.bind("<Shift-Button-1>", click)
        widget.bind("<Button-3>", context)
        widget.bind("<Button-2>", context)
        for child in widget.winfo_children():
            self._bind_clip_child_events(child, click, context)

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


def _short(iso: str) -> str:
    return (iso or "").replace("T", " ")[:16]


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
