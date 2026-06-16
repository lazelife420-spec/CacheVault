"""Home dashboard — secure vault command center."""

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
_CARD_BORDER = ("#C8D0D4", "#263038")
_CARD_BORDER_HOVER = (brand.PROOF_TEAL, brand.PROOF_TEAL)


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
        self._image_ready = image_assets_ready
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=14, pady=14)

    def render(
        self,
        summary: dict,
        recent: list[Clip],
        favorites: list[Clip],
        images: list[Clip],
    ) -> None:
        del favorites, images  # overview cards cover these; keep signature for shell
        for w in self._body.winfo_children():
            w.destroy()

        ctk.CTkLabel(
            self._body, text="Home", anchor="w",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(
            self._body, text="Your local saved-clips command center.",
            anchor="w", text_color=brand.MUTED_FG,
            font=theme.body_font(12),
        ).pack(fill="x", pady=(0, 14))

        self._vault_status_strip(summary)
        self._section_title("Saved Clips Overview")
        self._summary_cards(summary)
        self._section_title("Recently Saved")
        self._recent_section(recent)
        self._section_title("Needs Review")
        self._needs_review(summary)
        self._section_title("Proof & Access")
        self._proof_access_section(summary)

    def _vault_status_strip(self, summary: dict) -> None:
        strip = ctk.CTkFrame(
            self._body, fg_color=brand.SURFACE_BG, corner_radius=8,
            border_width=1, border_color=("#C8D0D4", "#263038"),
        )
        strip.pack(fill="x", pady=(0, 18))

        top = ctk.CTkFrame(strip, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            top, text="⬢", font=ctk.CTkFont(size=14),
            text_color=brand.STAMP_GOLD,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            top, text=brand.VAULT_STATUS_ACTIVE,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(side="left")

        capture = "Capture paused" if summary.get("capture_paused") else "Capture active"
        mobile = (
            "Mobile Access on" if summary.get("mobile_enabled") else "Mobile Access off"
        )
        detail = (
            f"Local-only · {capture} · Receipts on · {mobile}"
        )
        ctk.CTkLabel(
            strip, text=detail, anchor="w",
            font=theme.body_font(11), text_color=brand.MUTED_FG,
        ).pack(fill="x", padx=14, pady=(0, 4))

        counts = (
            f"{summary.get('all', 0)} saved clips · "
            f"{summary.get('receipts', 0)} receipts"
        )
        ctk.CTkLabel(
            strip, text=counts, anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=brand.STAMP_GOLD,
        ).pack(fill="x", padx=14, pady=(0, 4))

        ctk.CTkLabel(
            strip, text=brand.VAULT_STATUS_NOTE,
            anchor="w", wraplength=560, justify="left",
            text_color=brand.MUTED_FG, font=theme.body_font(10),
        ).pack(fill="x", padx=14, pady=(0, 12))

    def _summary_cards(self, summary: dict) -> None:
        wrap = ctk.CTkFrame(self._body, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, 20))
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
                row.pack(fill="x", pady=(8, 0))
            self._make_summary_card(row, label, count, filt, color)

    def _make_summary_card(
        self, parent, label: str, count: int, filt: str | None, color: str,
    ) -> None:
        card = ctk.CTkFrame(
            parent, corner_radius=10, fg_color=brand.SURFACE_BG,
            border_width=1, border_color=_CARD_BORDER, height=_CARD_HEIGHT,
        )
        card.pack(side="left", padx=4, pady=2, fill="x", expand=True)
        card.pack_propagate(False)

        icon = _CARD_ICONS.get(label, "▣")
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 0))
        ctk.CTkLabel(header, text=icon, font=ctk.CTkFont(size=13),
                     text_color=brand.STAMP_GOLD).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(header, text=label, text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

        ctk.CTkLabel(card, text=str(count), text_color=color,
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", padx=12, pady=(4, 0))
        ctk.CTkLabel(card, text=_CARD_META.get(label, ""), text_color=brand.MUTED_FG,
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=12, pady=(0, 10))

        handler = (lambda _e, f=filt: self._on_filter(f)) if filt else (lambda _e: self._on_open_receipts())
        self._bind_clickable(card, handler)

        def on_enter(_e, c=card) -> None:
            c.configure(border_color=_CARD_BORDER_HOVER)

        def on_leave(_e, c=card) -> None:
            c.configure(border_color=_CARD_BORDER)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

    @staticmethod
    def _bind_clickable(widget, handler) -> None:
        widget.bind("<Button-1>", handler)
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            HomeDashboard._bind_clickable(child, handler)

    def _section_title(self, text: str) -> None:
        ctk.CTkLabel(self._body, text=text, anchor="w", **theme.section_heading()
                     ).pack(fill="x", pady=(4, 8))

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

    def _needs_review(self, summary: dict) -> None:
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8,
                             border_width=1, border_color=("#C8D0D4", "#263038"))
        frame.pack(fill="x", pady=(0, 16))
        items = [
            ("Sensitive", summary.get("sensitive", 0), S.FILTER_SENSITIVE),
            ("Duplicates", summary.get("duplicates", 0), S.FILTER_DUPLICATES),
            ("Expired", summary.get("expired", 0), S.FILTER_EXPIRED),
            ("Recently Removed", summary.get("recently_removed", 0), S.FILTER_RECENTLY_REMOVED),
        ]
        for label, count, filt in items:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=label, anchor="w",
                         font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=str(count), anchor="e",
                         text_color=brand.STAMP_GOLD if count else brand.MUTED_FG,
                         font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=0, column=1, sticky="e")
            for w in (row,):
                w.bind("<Button-1>", lambda _e, f=filt: self._on_filter(f))
                w.configure(cursor="hand2")

    def _proof_access_section(self, summary: dict) -> None:
        frame = ctk.CTkFrame(self._body, fg_color=brand.SURFACE_BG, corner_radius=8,
                             border_width=1, border_color=("#C8D0D4", "#263038"))
        frame.pack(fill="x", pady=(0, 16))

        receipts_row = ctk.CTkFrame(frame, fg_color="transparent")
        receipts_row.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(receipts_row, text="⬢", text_color=brand.STAMP_GOLD,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            receipts_row,
            text=f"{brand.TERM_STAMPED_RECEIPTS} — {summary.get('receipts', 0)} local receipts",
            anchor="w", font=theme.body_font(11),
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            frame, text=f"Open {brand.TERM_STAMPED_RECEIPTS}",
            command=self._on_open_receipts, **theme.secondary_button(),
        ).pack(fill="x", padx=12, pady=(0, 8))

        if summary.get("mobile_enabled"):
            mobile_text = (
                f"{brand.TERM_MOBILE_ACCESS}: Enabled · "
                f"Port {summary.get('mobile_port', 8742)} · "
                f"{summary.get('paired_count', 0)} paired"
            )
        else:
            mobile_text = brand.MOBILE_ACCESS_HONEST
        mob_row = ctk.CTkFrame(frame, fg_color="transparent")
        mob_row.pack(fill="x", padx=12, pady=(4, 4))
        ctk.CTkLabel(mob_row, text="◉", text_color=brand.PROOF_TEAL,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(mob_row, text=mobile_text, anchor="w", justify="left",
                     wraplength=480, font=theme.body_font(11)).pack(side="left", fill="x", expand=True)

        mob_btns = ctk.CTkFrame(frame, fg_color="transparent")
        mob_btns.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkButton(
            mob_btns, text=brand.TERM_MOBILE_ACCESS,
            command=self._on_mobile_settings, **theme.secondary_button(),
        ).pack(side="left", padx=(0, 6), expand=True, fill="x")
        ctk.CTkButton(
            mob_btns, text="Pair Android Device",
            command=self._on_pair_android, **theme.primary_button(),
        ).pack(side="left", expand=True, fill="x")

        ctk.CTkButton(
            frame, text=brand.TERM_EXPORT,
            command=self._on_export, **theme.secondary_button(),
        ).pack(fill="x", padx=12, pady=(4, 12))

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


def vault_status_text(summary: dict) -> str:
    """Build the compact vault status line for tests."""
    capture = "Capture paused" if summary.get("capture_paused") else "Capture active"
    mobile = "Mobile Access on" if summary.get("mobile_enabled") else "Mobile Access off"
    return (
        f"Local-only · {capture} · Receipts on · {mobile} · "
        f"{summary.get('all', 0)} saved clips · {summary.get('receipts', 0)} receipts"
    )
