"""Home dashboard — organized entry point instead of raw clip list."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, storage as S
from ..core.models import Clip
from . import theme


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
        self._body.pack(fill="both", expand=True, padx=8, pady=8)

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
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(fill="x", pady=(0, 8))

        self._summary_cards(summary)
        self._section_title("Saved Clips Overview")
        self._recent_section(recent)
        self._favorites_section(favorites)
        self._images_section(images)
        self._needs_review(summary)
        self._mobile_section(summary)
        self._receipts_section(summary)

    def _summary_cards(self, summary: dict) -> None:
        row = ctk.CTkFrame(self._body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        cards = [
            ("All Clips", summary.get("all", 0), S.FILTER_ALL, brand.PROOF_TEAL),
            ("Favorites", summary.get("favorites", 0), S.FILTER_FAVORITES, brand.STAMP_GOLD),
            ("Screenshots", summary.get("screenshots", 0), S.FILTER_SCREENSHOTS, brand.PROOF_TEAL),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES, brand.STAMP_GOLD),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED, brand.MUTED_FG),
            ("Receipts", summary.get("receipts", 0), None, brand.STAMP_GOLD),
        ]
        for label, count, filt, color in cards:
            card = ctk.CTkFrame(row, corner_radius=8, fg_color=brand.SURFACE_BG)
            card.pack(side="left", padx=4, pady=2, fill="x", expand=True)
            ctk.CTkLabel(card, text=label, text_color=brand.MUTED_FG,
                         font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(card, text=str(count), text_color=color,
                         font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=10, pady=(0, 8))
            if filt:
                for w in (card,):
                    w.bind("<Button-1>", lambda _e, f=filt: self._on_filter(f))
            elif label == "Receipts":
                card.bind("<Button-1>", lambda _e: self._on_open_receipts())

    def _section_title(self, text: str) -> None:
        ctk.CTkLabel(self._body, text=text, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=brand.PROOF_TEAL).pack(fill="x", pady=(8, 4))

    def _recent_section(self, clips: list[Clip]) -> None:
        self._section_title("Recently Saved")
        if not clips:
            ctk.CTkLabel(self._body, text="No clips yet.", text_color=brand.MUTED_FG
                         ).pack(anchor="w", padx=4)
            return
        for clip in clips[:8]:
            self._compact_clip_card(clip)

    def _favorites_section(self, clips: list[Clip]) -> None:
        self._section_title("Favorites")
        if not clips:
            ctk.CTkLabel(
                self._body,
                text="No favorites yet.\nStar clips you want to keep close.",
                text_color=brand.MUTED_FG, justify="left",
            ).pack(anchor="w", padx=4, pady=4)
            return
        for clip in clips[:6]:
            self._compact_clip_card(clip)

    def _images_section(self, images: list[Clip]) -> None:
        self._section_title("Screenshots / Images")
        if not self._image_ready:
            ctk.CTkLabel(
                self._body,
                text="Screenshot/image support is being prepared.\n"
                     "Text, links, and code are available now.",
                text_color=brand.MUTED_FG, justify="left",
            ).pack(anchor="w", padx=4, pady=4)
            return
        if not images:
            ctk.CTkLabel(self._body, text="No screenshots saved yet.",
                         text_color=brand.MUTED_FG).pack(anchor="w", padx=4)
            return
        for clip in images[:6]:
            self._compact_clip_card(clip)

    def _needs_review(self, summary: dict) -> None:
        self._section_title("Needs Review")
        items = [
            ("Sensitive clips", summary.get("sensitive", 0), S.FILTER_SENSITIVE),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED),
            ("Expired", summary.get("expired", 0), S.FILTER_EXPIRED),
        ]
        frame = ctk.CTkFrame(self._body, fg_color="transparent")
        frame.pack(fill="x", pady=4)
        for label, count, filt in items:
            row = ctk.CTkLabel(
                frame, text=f"{label}: {count}", anchor="w",
                text_color=brand.MUTED_FG, cursor="hand2",
            )
            row.pack(anchor="w", padx=4)
            row.bind("<Button-1>", lambda _e, f=filt: self._on_filter(f))

    def _mobile_section(self, summary: dict) -> None:
        self._section_title("Mobile Access")
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8)
        frame.pack(fill="x", pady=4)
        if summary.get("mobile_enabled"):
            lines = [
                "Mobile Access: Enabled",
                f"Port: {summary.get('mobile_port', 8742)}",
                f"Paired devices: {summary.get('paired_count', 0)}",
            ]
            ctk.CTkLabel(frame, text="\n".join(lines), justify="left",
                         anchor="w").pack(fill="x", padx=12, pady=10)
        else:
            ctk.CTkLabel(
                frame, text="Off by default.", anchor="w",
                text_color=brand.MUTED_FG,
            ).pack(fill="x", padx=12, pady=(10, 4))
            ctk.CTkButton(
                frame, text="Open Mobile Access Settings",
                command=self._on_mobile_settings, **theme.secondary_button(),
            ).pack(fill="x", padx=12, pady=2)
            ctk.CTkButton(
                frame, text="Pair Android Device",
                command=self._on_pair_android, **theme.primary_button(),
            ).pack(fill="x", padx=12, pady=(2, 10))

    def _receipts_section(self, summary: dict) -> None:
        self._section_title("Proof / Receipts")
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8)
        frame.pack(fill="x", pady=(4, 12))
        text = (
            "Stamped Receipts\n"
            "Local proof history for Cache Vault actions.\n\n"
            f"Recent receipts: {summary.get('receipts', 0)}\n"
            f"Last action: {summary.get('last_receipt_action', '—')}"
        )
        ctk.CTkLabel(frame, text=text, justify="left", anchor="w").pack(
            fill="x", padx=12, pady=(10, 4))
        ctk.CTkButton(
            frame, text="Open Stamped Receipts",
            command=self._on_open_receipts, **theme.secondary_button(),
        ).pack(fill="x", padx=12, pady=(2, 10))

    def _compact_clip_card(self, clip: Clip) -> None:
        card = ctk.CTkFrame(self._body, corner_radius=8, fg_color=brand.SURFACE_BG)
        card.pack(fill="x", pady=3)

        badge = clip_metadata.format_label(clip.classification, clip.content_type)
        if clip.is_sensitive:
            badge = "SENSITIVE"
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(6, 0))
        ctk.CTkLabel(top, text=badge, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=brand.WARNING_RED if clip.is_sensitive else brand.MUTED_FG
                     ).pack(side="left")
        icons = []
        if clip.is_pinned:
            icons.append("★")
        if clip.content_hash:
            icons.append("⬢")
        if icons:
            ctk.CTkLabel(top, text=" ".join(icons), text_color=brand.STAMP_GOLD
                         ).pack(side="right")

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        ctk.CTkLabel(card, text=title, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(fill="x", padx=10)
        preview = (clip.preview or "")[:180]
        ctk.CTkLabel(card, text=preview, anchor="w", justify="left",
                     text_color=brand.MUTED_FG, wraplength=500,
                     font=ctk.CTkFont(size=10)).pack(fill="x", padx=10)
        meta = f"{clip.source_app or 'Unknown source'} · Added {_short(clip.created_at)}"
        ctk.CTkLabel(card, text=meta, anchor="w", text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=9)).pack(fill="x", padx=10, pady=(0, 4))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkButton(actions, text="Copy", width=60, height=24,
                      command=lambda c=clip: self._on_copy(c.id),
                      **theme.primary_button()).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="Open", width=60, height=24,
                      command=lambda c=clip: self._on_select_clip(c),
                      **theme.secondary_button()).pack(side="left", padx=2)

        card.bind("<Button-1>", lambda _e, c=clip: self._on_select_clip(c))


def _short(iso: str) -> str:
    return (iso or "").replace("T", " ")[:16]
