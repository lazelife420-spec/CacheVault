"""Home dashboard — organized entry point instead of raw clip list."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, storage as S
from ..core.models import Clip
from . import theme

_CARD_META = {
    "All Clips": "Saved items in your vault",
    "Favorites": "Starred clips you keep close",
    "Screenshots": "Image clips from clipboard",
    "Duplicates": "Groups needing review",
    "Recently Removed": "Restorable removed clips",
    "Receipts": "Local proof history",
}


class HomeDashboard(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        *,
        on_filter: Callable[[str], None],
        on_open_receipts: Callable[[], None],
        on_mobile_settings: Callable[[], None],
        on_pair_android: Callable[[], None],
        on_select_clip: Callable[[Clip], None],
        on_copy: Callable[[str], None],
        image_assets_ready: bool = False,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_filter = on_filter
        self._on_open_receipts = on_open_receipts
        self._on_mobile_settings = on_mobile_settings
        self._on_pair_android = on_pair_android
        self._on_select_clip = on_select_clip
        self._on_copy = on_copy
        self._image_ready = image_assets_ready
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=12, pady=12)

    def render(
        self,
        summary: dict,
        recent: list[Clip],
        favorites: list[Clip],
        images: list[Clip],
    ) -> None:
        for w in self._body.winfo_children():
            w.destroy()

        ctk.CTkLabel(
            self._body, text="Home", anchor="w",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            self._body, text="Your saved-clips command center.",
            anchor="w", text_color=brand.MUTED_FG,
            font=theme.body_font(12),
        ).pack(fill="x", pady=(0, 12))

        self._summary_cards(summary)
        self._section_title("Recently Saved")
        self._recent_section(recent)
        self._section_title("Favorites")
        self._favorites_section(favorites)
        self._section_title("Screenshots / Images")
        self._images_section(images)
        self._section_title("Needs Review")
        self._needs_review(summary)
        self._section_title("Mobile Access")
        self._mobile_section(summary)
        self._section_title("Proof / Receipts")
        self._receipts_section(summary)

    def _summary_cards(self, summary: dict) -> None:
        wrap = ctk.CTkFrame(self._body, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, 16))
        cards = [
            ("All Clips", summary.get("all", 0), S.FILTER_ALL, brand.PROOF_TEAL),
            ("Favorites", summary.get("favorites", 0), S.FILTER_FAVORITES, brand.STAMP_GOLD),
            ("Screenshots", summary.get("screenshots", 0), S.FILTER_SCREENSHOTS, brand.PROOF_TEAL),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES, brand.STAMP_GOLD),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED, brand.MUTED_FG),
            ("Receipts", summary.get("receipts", 0), None, brand.STAMP_GOLD),
        ]
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        for i, (label, count, filt, color) in enumerate(cards):
            if i and i % 3 == 0:
                row = ctk.CTkFrame(wrap, fg_color="transparent")
                row.pack(fill="x", pady=(6, 0))
            card = ctk.CTkFrame(row, corner_radius=10, fg_color=brand.SURFACE_BG,
                                border_width=1, border_color=("#C8D0D4", "#263038"))
            card.pack(side="left", padx=4, pady=2, fill="x", expand=True)
            ctk.CTkLabel(card, text=label, text_color=brand.MUTED_FG,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=str(count), text_color=color,
                         font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=12, pady=(2, 0))
            ctk.CTkLabel(card, text=_CARD_META.get(label, ""), text_color=brand.MUTED_FG,
                         font=ctk.CTkFont(size=10)).pack(anchor="w", padx=12, pady=(0, 10))
            handler = (lambda _e, f=filt: self._on_filter(f)) if filt else (lambda _e: self._on_open_receipts())
            for w in (card,):
                w.bind("<Button-1>", handler)
                w.configure(cursor="hand2")

    def _section_title(self, text: str) -> None:
        ctk.CTkLabel(self._body, text=text, anchor="w", **theme.section_heading()
                     ).pack(fill="x", pady=(10, 6))

    def _recent_section(self, clips: list[Clip]) -> None:
        if not clips:
            ctk.CTkLabel(
                self._body,
                text="No saved clips yet.\nCopy something and Cache Vault will save it here.",
                text_color=brand.MUTED_FG, justify="left", font=theme.body_font(11),
            ).pack(anchor="w", padx=4, pady=4)
            return
        for clip in clips[:8]:
            self._compact_clip_card(clip)

    def _favorites_section(self, clips: list[Clip]) -> None:
        if not clips:
            ctk.CTkLabel(
                self._body,
                text="No favorites yet.\nStar clips you want to keep close.",
                text_color=brand.MUTED_FG, justify="left", font=theme.body_font(11),
            ).pack(anchor="w", padx=4, pady=4)
            return
        for clip in clips[:6]:
            self._compact_clip_card(clip)

    def _images_section(self, images: list[Clip]) -> None:
        if not self._image_ready:
            ctk.CTkLabel(
                self._body,
                text="Screenshot/image support is being prepared.\n"
                     "Text, links, and code are available now.",
                text_color=brand.MUTED_FG, justify="left", font=theme.body_font(11),
            ).pack(anchor="w", padx=4, pady=4)
            return
        if not images:
            ctk.CTkLabel(self._body, text="No screenshots saved yet.",
                         text_color=brand.MUTED_FG, font=theme.body_font(11)).pack(anchor="w", padx=4)
            return
        for clip in images[:6]:
            self._compact_clip_card(clip)

    def _needs_review(self, summary: dict) -> None:
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8)
        frame.pack(fill="x", pady=4)
        items = [
            ("Sensitive clips", summary.get("sensitive", 0), S.FILTER_SENSITIVE),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED),
            ("Expired", summary.get("expired", 0), S.FILTER_EXPIRED),
        ]
        for label, count, filt in items:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(11)).grid(
                row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=str(count), anchor="e",
                         text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=12, weight="bold")
                         ).grid(row=0, column=1, sticky="e")
            for w in (row,):
                w.bind("<Button-1>", lambda _e, f=filt: self._on_filter(f))
                w.configure(cursor="hand2")

    def _mobile_section(self, summary: dict) -> None:
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8)
        frame.pack(fill="x", pady=4)
        if summary.get("mobile_enabled"):
            lines = (
                f"Mobile Access: Enabled\n"
                f"Port: {summary.get('mobile_port', 8742)}\n"
                f"Paired devices: {summary.get('paired_count', 0)}"
            )
            ctk.CTkLabel(frame, text=lines, justify="left", anchor="w",
                         font=theme.body_font(11)).pack(fill="x", padx=14, pady=12)
        else:
            ctk.CTkLabel(frame, text="Off by default.", anchor="w",
                         text_color=brand.MUTED_FG, font=theme.body_font(11)
                         ).pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkButton(frame, text="Open Mobile Access Settings",
                          command=self._on_mobile_settings, **theme.secondary_button()
                          ).pack(fill="x", padx=14, pady=2)
            ctk.CTkButton(frame, text="Pair Android Device",
                          command=self._on_pair_android, **theme.primary_button()
                          ).pack(fill="x", padx=14, pady=(2, 12))

    def _receipts_section(self, summary: dict) -> None:
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8)
        frame.pack(fill="x", pady=(4, 16))
        text = (
            f"Stamped Receipts — local proof history.\n"
            f"Recent receipts: {summary.get('receipts', 0)}\n"
            f"Last action: {summary.get('last_receipt_action', '—')}"
        )
        ctk.CTkLabel(frame, text=text, justify="left", anchor="w",
                     font=theme.body_font(11)).pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkButton(frame, text="Open Stamped Receipts",
                      command=self._on_open_receipts, **theme.secondary_button()
                      ).pack(fill="x", padx=14, pady=(2, 12))

    def _compact_clip_card(self, clip: Clip) -> None:
        card = ctk.CTkFrame(self._body, corner_radius=8, fg_color=brand.SURFACE_BG,
                             border_width=1, border_color=("#C8D0D4", "#263038"))
        card.pack(fill="x", pady=4)

        badge = clip_metadata.format_label(clip.classification, clip.content_type).upper()
        if clip.is_sensitive:
            badge = "SENSITIVE"
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(top, text=badge, font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=brand.WARNING_RED if clip.is_sensitive else brand.MUTED_FG
                     ).pack(side="left")
        trail = ctk.CTkFrame(top, fg_color="transparent")
        trail.pack(side="right")
        if clip.is_pinned:
            ctk.CTkLabel(trail, text="★", font=ctk.CTkFont(size=13),
                         text_color=brand.STAMP_GOLD).pack(side="left", padx=3)
        if clip.content_hash:
            proof = ctk.CTkLabel(trail, text="⬢", font=ctk.CTkFont(size=11),
                                 text_color=brand.STAMP_GOLD, cursor="question_arrow")
            proof.pack(side="left", padx=3)
            self._bind_tooltip(proof, "Proof receipt available")

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(card, text=title, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=12)
        preview = _clip_preview_lines(clip.preview or "", max_lines=2)
        ctk.CTkLabel(card, text=preview, anchor="w", justify="left",
                     text_color=brand.MUTED_FG, wraplength=520,
                     font=theme.body_font(11)).pack(fill="x", padx=12, pady=(2, 0))
        meta = (
            f"{clip_metadata.display(clip.source_app)} · "
            f"First saved {_short(clip.created_at)} · "
            f"Last used {_short(clip.date_used or clip.updated_at)}"
        )
        ctk.CTkLabel(card, text=meta, anchor="w", text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=10)).pack(fill="x", padx=12, pady=(0, 6))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(actions, text="Copy", width=64, height=26,
                      command=lambda c=clip: self._on_copy(c.id),
                      **theme.primary_button()).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="Open", width=64, height=26,
                      command=lambda c=clip: self._on_select_clip(c),
                      **theme.secondary_button()).pack(side="left", padx=2)
        card.bind("<Button-1>", lambda _e, c=clip: self._on_select_clip(c))

    @staticmethod
    def _bind_tooltip(widget, text: str) -> None:
        tip: ctk.CTkToplevel | None = None

        def show(_e=None) -> None:
            nonlocal tip
            tip = ctk.CTkToplevel(widget)
            tip.wm_overrideredirect(True)
            tip.attributes("-topmost", True)
            ctk.CTkLabel(tip, text=text, fg_color=brand.IRON_GRAY,
                         text_color=brand.RECEIPT_WHITE,
                         corner_radius=4, padx=8, pady=4).pack()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tip.geometry(f"+{x}+{y}")

        def hide(_e=None) -> None:
            nonlocal tip
            if tip:
                tip.destroy()
                tip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)


def _short(iso: str) -> str:
    return (iso or "").replace("T", " ")[:16]


def _clip_preview_lines(text: str, *, max_lines: int = 2) -> str:
    lines = text.splitlines()[:max_lines]
    out = "\n".join(lines)
    if len(text.splitlines()) > max_lines:
        out += "…"
    return out or "(empty)"
