"""Vault Cleanup Suggestions v1 -- desktop UI (Stage D).

A VaultScreenHost-registered grouped review screen (reached from the Home
dashboard's "Cleanup Suggestions" card), plus a generic per-category review
dialog with EXPLICIT checkbox selection (not just click/Ctrl/Shift -- the
design review was explicit that a destructive-adjacent review workflow
needs visible, discoverable selection state) and a confirmation dialog
before any mutation.

Terminology is deliberately exact throughout: "redundant bytes identified"
/ "bytes represented by selected items", never "recoverable" or "free up
N MB" -- moving to Recently Removed does not reclaim disk space.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import cleanup_suggestions as cs
from ..core.cleanup_actions import CleanupSelection, apply_cleanup_selection
from ..core.cleanup_store import (
    DECISION_IGNORED, DECISION_KEEP, DECISION_KEEP_FOREVER, SCOPE_GROUP, SCOPE_ITEM, record_decision,
)
from . import theme
from .dialogs import _bring_to_front

_CATEGORY_LABELS = {
    cs.CATEGORY_DUPLICATE_SCREENSHOT: "Exact duplicate screenshots",
    cs.CATEGORY_REPEATED_TEXT: "Repeated text clips",
    cs.CATEGORY_TINY_IMAGE: "Unusually small images",
    cs.CATEGORY_MISSING_ASSET: "Missing or damaged assets",
    cs.CATEGORY_LARGEST_ASSET: "Largest assets",
}

_CATEGORY_WHY = {
    cs.CATEGORY_DUPLICATE_SCREENSHOT: "Byte-identical copies of the same screenshot.",
    cs.CATEGORY_REPEATED_TEXT: "Exact repeated text captures (line-ending differences only).",
    cs.CATEGORY_TINY_IMAGE: "Unusually small image -- may be a test capture, icon, or failed screenshot.",
    cs.CATEGORY_MISSING_ASSET: "The vault record exists but its file is missing, empty, or unreadable.",
    cs.CATEGORY_LARGEST_ASSET: "Visibility only -- not a claim that these are clutter.",
}

_CONFIDENCE_LABELS = {
    cs.CONFIDENCE_SAFE: "Safe",
    cs.CONFIDENCE_REVIEW: "Review",
    cs.CONFIDENCE_CAUTION: "Caution",
}


def build_cleanup_suggestions_screen(frame: ctk.CTkScrollableFrame, callbacks: dict) -> None:
    """VaultScreenHost builder -- called once at app startup. Does NOT scan
    the vault; only renders whatever's already cached (nothing, at first)
    plus a "Scan vault" action. Scanning only happens when the user asks.
    """
    frame._cleanup_state = {"result": None, "scanning": False, "scan_generation": None}
    frame._cleanup_callbacks = callbacks
    frame._refresh = lambda: render_cleanup_screen(frame)
    render_cleanup_screen(frame)


def render_cleanup_screen(frame: ctk.CTkScrollableFrame) -> None:
    for w in frame.winfo_children():
        w.destroy()

    ctk.CTkLabel(frame, text="Cleanup Suggestions", anchor="w", **theme.section_heading()).pack(
        fill="x", padx=12, pady=(12, 4),
    )
    ctk.CTkLabel(
        frame,
        text="CacheVault finds the clutter and shows the evidence. You decide what gets cleaned.",
        anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(12), wraplength=560, justify="left",
    ).pack(fill="x", padx=12, pady=(0, 10))

    callbacks = frame._cleanup_callbacks
    state = frame._cleanup_state
    result: cs.CleanupScanResult | None = state["result"]

    top_row = ctk.CTkFrame(frame, fg_color="transparent")
    top_row.pack(fill="x", padx=12, pady=(0, 10))
    scan_label = "Scanning…" if state["scanning"] else ("Scan again" if result else "Scan vault")
    scan_btn = ctk.CTkButton(
        top_row, text=scan_label, height=30, state="disabled" if state["scanning"] else "normal",
        command=lambda: callbacks["scan_cleanup_suggestions"](frame),
        **theme.primary_button(),
    )
    scan_btn.pack(side="left")

    if result is None:
        ctk.CTkLabel(
            frame, text="No scan yet. Run a scan to see suggestions.",
            text_color=brand.MUTED_FG, font=theme.body_font(12),
        ).pack(padx=12, pady=20)
        return

    if result.cancelled:
        ctk.CTkLabel(
            frame, text="Last scan was cancelled before finishing.",
            text_color=brand.MUTED_FG, font=theme.body_font(12),
        ).pack(fill="x", padx=12, pady=(0, 10))

    categories = [
        (cs.CATEGORY_DUPLICATE_SCREENSHOT, result.duplicate_screenshot_groups, cs.CONFIDENCE_SAFE),
        (cs.CATEGORY_REPEATED_TEXT, result.repeated_text_groups, cs.CONFIDENCE_REVIEW),
        (cs.CATEGORY_TINY_IMAGE, result.tiny_images, cs.CONFIDENCE_REVIEW),
        (cs.CATEGORY_MISSING_ASSET, result.missing_or_damaged, cs.CONFIDENCE_REVIEW),
        (cs.CATEGORY_LARGEST_ASSET, result.largest_assets, cs.CONFIDENCE_CAUTION),
    ]
    for category, items_or_groups, confidence in categories:
        _category_card(frame, callbacks, category, items_or_groups, confidence)


def _category_card(frame, callbacks, category, items_or_groups, confidence) -> None:
    card = ctk.CTkFrame(frame, fg_color=brand.SURFACE_BG, corner_radius=8,
                         border_width=1, border_color=brand.VAULT_CARD_BORDER)
    card.pack(fill="x", padx=12, pady=6)

    header = ctk.CTkFrame(card, fg_color="transparent")
    header.pack(fill="x", padx=12, pady=(10, 2))
    ctk.CTkLabel(header, text=_CATEGORY_LABELS[category], anchor="w",
                 font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
    ctk.CTkLabel(header, text=_CONFIDENCE_LABELS[confidence], anchor="e",
                 text_color=brand.STAMP_GOLD, font=theme.body_font(11)).pack(side="right")

    ctk.CTkLabel(card, text=_CATEGORY_WHY[category], anchor="w", text_color=brand.MUTED_FG,
                 font=theme.body_font(11), wraplength=520, justify="left").pack(
        fill="x", padx=12, pady=(0, 4),
    )

    is_grouped = category in (cs.CATEGORY_DUPLICATE_SCREENSHOT, cs.CATEGORY_REPEATED_TEXT)
    if is_grouped:
        group_count = len(items_or_groups)
        item_count = sum(g.count for g in items_or_groups)
        count_text = f"{group_count} group(s) · {item_count} item(s)"
    else:
        count_text = f"{len(items_or_groups)} item(s)"

    stats_row = ctk.CTkFrame(card, fg_color="transparent")
    stats_row.pack(fill="x", padx=12, pady=(0, 8))
    ctk.CTkLabel(stats_row, text=count_text, anchor="w", font=theme.body_font(12)).pack(side="left")

    if category == cs.CATEGORY_DUPLICATE_SCREENSHOT:
        redundant = sum(g.redundant_bytes for g in items_or_groups)
        if redundant:
            ctk.CTkLabel(
                stats_row, text=f"{_format_bytes(redundant)} of redundant assets identified",
                anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
            ).pack(side="left", padx=(10, 0))

    review_btn = ctk.CTkButton(
        stats_row, text="Review", height=26, width=90,
        state="normal" if items_or_groups else "disabled",
        command=lambda: _open_review_dialog(card, callbacks, category, items_or_groups),
        **theme.secondary_button(),
    )
    review_btn.pack(side="right")


_format_bytes = cs.format_bytes


def _open_review_dialog(parent, callbacks, category, items_or_groups) -> None:
    CleanupReviewDialog(parent, callbacks=callbacks, category=category, items_or_groups=items_or_groups)


class CleanupReviewDialog(ctk.CTkToplevel):
    """Per-category detail review: explicit checkboxes, protected labeling,
    recommended-keeper highlight, selection helpers, and the Keep/Keep
    forever/Ignore/Move actions.
    """

    def __init__(self, master, *, callbacks: dict, category: str, items_or_groups: list):
        super().__init__(master)
        self.title(_CATEGORY_LABELS[category])
        self.geometry("620x520")
        self._callbacks = callbacks
        self._category = category
        self._is_grouped = category in (cs.CATEGORY_DUPLICATE_SCREENSHOT, cs.CATEGORY_REPEATED_TEXT)
        self._groups: list[cs.SuggestionGroup] = items_or_groups if self._is_grouped else []
        self._items: list[cs.SuggestionItem] = [] if self._is_grouped else items_or_groups
        self._vars: dict[str, ctk.BooleanVar] = {}  # clip_id -> selection var
        self._protected: set[str] = set()
        self._keepers: set[str] = set()

        self._build()
        _bring_to_front(self, master, modal=True)

    # --- construction --------------------------------------------------

    def _all_items(self) -> list[cs.SuggestionItem]:
        if self._is_grouped:
            out = []
            for g in self._groups:
                out.extend(g.items)
            return out
        return self._items

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(14, 6))
        self._selected_count_label = ctk.CTkLabel(header, text="", font=theme.body_font(12))
        self._selected_count_label.pack(side="left")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkButton(controls, text="Select suggested safe items", height=26,
                       command=self._select_suggested_safe, **theme.secondary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(controls, text="Select unprotected items", height=26,
                       command=self._select_unprotected, **theme.secondary_button()).pack(side="left", padx=(0, 6))
        ctk.CTkButton(controls, text="Deselect all", height=26,
                       command=self._deselect_all, **theme.secondary_button()).pack(side="left")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        if self._is_grouped:
            for group in self._groups:
                self._render_group(group)
        else:
            for item in self._items:
                self._render_item_row(self._scroll, item, indent=0)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 14))
        can_select = self._category != cs.CATEGORY_LARGEST_ASSET  # visibility-only, no actions
        if can_select:
            ctk.CTkButton(actions, text="Keep", height=30, command=lambda: self._decide_selected(DECISION_KEEP),
                          **theme.secondary_button()).pack(side="left", padx=(0, 6))
            ctk.CTkButton(actions, text="Keep forever", height=30,
                          command=lambda: self._decide_selected(DECISION_KEEP_FOREVER),
                          **theme.secondary_button()).pack(side="left", padx=(0, 6))
            ctk.CTkButton(actions, text="Ignore suggestion", height=30,
                          command=lambda: self._decide_selected(DECISION_IGNORED),
                          **theme.secondary_button()).pack(side="left", padx=(0, 6))
            self._move_btn = ctk.CTkButton(
                actions, text="Move selected to Recently Removed", height=30,
                command=self._open_confirm, **theme.primary_button(),
            )
            self._move_btn.pack(side="right")

        self._refresh_selected_count()

    def _render_group(self, group: cs.SuggestionGroup) -> None:
        header = ctk.CTkFrame(self._scroll, fg_color=brand.SURFACE_BG, corner_radius=6)
        header.pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(
            header, text=f"{group.count} copies — hash {group.evidence.get('sha256', group.evidence.get('normalized_hash', ''))[:12]}…",
            anchor="w", font=theme.body_font(12),
        ).pack(fill="x", padx=8, pady=4)
        if group.recommended_keeper_id:
            self._keepers.add(group.recommended_keeper_id)
        for item in group.items:
            self._render_item_row(self._scroll, item, indent=1, group=group)

    def _render_item_row(self, parent, item: cs.SuggestionItem, *, indent: int, group=None) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=(indent * 16, 0), pady=2)

        clip_id = item.clip.id
        is_keeper = clip_id in self._keepers
        is_protected = item.protection.protected
        if is_protected:
            self._protected.add(clip_id)

        var = ctk.BooleanVar(value=False)
        self._vars[clip_id] = var
        checkbox_state = "disabled" if (is_protected or is_keeper) else "normal"
        cb = ctk.CTkCheckBox(
            row, text="", width=20, variable=var, state=checkbox_state,
            command=self._refresh_selected_count,
        )
        cb.pack(side="left", padx=(0, 6))

        label_bits = [item.clip.preview or item.clip.content[:60] or "(no preview)"]
        if is_keeper:
            label_bits.append("— RECOMMENDED KEEPER")
        if is_protected:
            label_bits.append(f"— PROTECTED ({', '.join(item.protection.reasons)})")
        if item.asset_missing:
            label_bits.append("— missing file")
        if item.asset_zero_byte:
            label_bits.append("— zero-byte file")
        if item.asset_undecodable:
            label_bits.append("— unreadable/corrupt")
        if item.asset_width and item.asset_height:
            label_bits.append(f"({item.asset_width}×{item.asset_height})")

        color = brand.MUTED_FG if (is_protected or is_keeper) else None
        ctk.CTkLabel(row, text="  ".join(label_bits), anchor="w", font=theme.body_font(11),
                     text_color=color).pack(side="left", fill="x", expand=True)

    # --- selection helpers -----------------------------------------------

    def _select_suggested_safe(self) -> None:
        """Only the non-keeper, non-protected items -- exactly the
        preselectable set the scan engine already computed. Never selects
        a keeper or a protected item.
        """
        preselect_ids: set[str] = set()
        if self._is_grouped:
            for g in self._groups:
                preselect_ids.update(g.preselectable_ids)
        else:
            preselect_ids.update(
                it.clip.id for it in self._items if not it.protection.protected
            )
        for clip_id, var in self._vars.items():
            var.set(clip_id in preselect_ids)
        self._refresh_selected_count()

    def _select_unprotected(self) -> None:
        for it in self._all_items():
            var = self._vars.get(it.clip.id)
            if var is not None and it.clip.id not in self._keepers:
                var.set(not it.protection.protected)
        self._refresh_selected_count()

    def _deselect_all(self) -> None:
        for var in self._vars.values():
            var.set(False)
        self._refresh_selected_count()

    def _selected_ids(self) -> list[str]:
        return [cid for cid, var in self._vars.items() if var.get()]

    def _refresh_selected_count(self) -> None:
        n = len(self._selected_ids())
        self._selected_count_label.configure(text=f"{n} selected")
        if hasattr(self, "_move_btn"):
            self._move_btn.configure(state="normal" if n else "disabled")

    # --- actions -----------------------------------------------------------

    def _fingerprint_for(self, clip_id: str) -> tuple[str, str]:
        """Returns (scope, fingerprint) for a given selected clip id.

        Always item-scoped, deliberately: the checkboxes in this dialog
        select individual clips, not "the group" as a whole, so Keep /
        Keep forever / Ignore / Move all record a per-item decision keyed
        to that clip's own id -- not the group's fingerprint. (The scan
        engine's group-level fingerprints, which do encode full membership,
        remain available in cleanup_store.SCOPE_GROUP for a possible future
        "dismiss this whole group" action; nothing in this dialog uses that
        scope today.)
        """
        return SCOPE_ITEM, clip_id

    def _decide_selected(self, decision: str) -> None:
        storage = self._callbacks["storage"]()
        selected = self._selected_ids()
        for clip_id in selected:
            scope, fingerprint = self._fingerprint_for(clip_id)
            record_decision(
                storage, category=self._category, scope=scope, fingerprint=fingerprint,
                clip_id=clip_id, decision=decision, rule_version=cs.RULE_VERSION,
            )
        self.destroy()
        rescan = self._callbacks.get("rescan_after_decision")
        if rescan:
            rescan()

    def _open_confirm(self) -> None:
        selected = self._selected_ids()
        if not selected:
            return
        by_id = {it.clip.id: it for it in self._all_items()}
        bytes_selected = sum(by_id[cid].asset_size_bytes for cid in selected if cid in by_id)
        selected_set = set(selected)
        if self._is_grouped:
            group_count = sum(
                1 for g in self._groups if any(it.clip.id in selected_set for it in g.items)
            )
        else:
            group_count = len(selected)
        protected_excluded = len(self._protected)
        CleanupConfirmDialog(
            self, selected_count=len(selected), group_count=group_count,
            protected_excluded=protected_excluded, bytes_selected=bytes_selected,
            on_confirm=lambda: self._do_move(selected),
        )

    def _do_move(self, selected_clip_ids: list[str]) -> None:
        storage = self._callbacks["storage"]()
        events = self._callbacks["events"]()
        by_fingerprint: dict[tuple[str, str], list[str]] = {}
        for clip_id in selected_clip_ids:
            scope, fingerprint = self._fingerprint_for(clip_id)
            by_fingerprint.setdefault((scope, fingerprint), []).append(clip_id)
        selections = [
            CleanupSelection(category=self._category, scope=scope, fingerprint=fp, clip_ids=ids)
            for (scope, fp), ids in by_fingerprint.items()
        ]
        apply_cleanup_selection(
            storage, events, selections=selections, rule_version=cs.RULE_VERSION,
        )
        self.destroy()
        rescan = self._callbacks.get("rescan_after_decision")
        if rescan:
            rescan()
        open_receipts = self._callbacks.get("open_receipts")
        if open_receipts:
            open_receipts()


class CleanupConfirmDialog(ctk.CTkToplevel):
    """Shown before any mutation. States the exact effect, that items move
    to Recently Removed (not permanently deleted), and how many protected
    items were excluded.
    """

    def __init__(
        self, master, *, selected_count: int, group_count: int,
        protected_excluded: int, bytes_selected: int, on_confirm: Callable[[], None],
    ):
        super().__init__(master)
        self.title("Move to Recently Removed")
        self.geometry("420x300")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            body, text=f"Move {selected_count} selected item(s) to Recently Removed",
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w", wraplength=380, justify="left",
        ).pack(fill="x", pady=(0, 10))

        lines = [
            f"Groups affected: {group_count}",
            f"Bytes represented by selected items: {_format_bytes(bytes_selected)}",
            f"Protected items excluded: {protected_excluded}",
            "",
            "Items move to Recently Removed and can be restored.",
            "Disk space is retained until permanent removal.",
            "Permanent deletion is not occurring.",
        ]
        for line in lines:
            ctk.CTkLabel(body, text=line, anchor="w", font=theme.body_font(12),
                         text_color=brand.MUTED_FG if line else None, wraplength=380, justify="left").pack(
                fill="x", pady=1,
            )

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(btns, text="Cancel", height=30, command=self.destroy,
                      **theme.secondary_button()).pack(side="left")

        def _confirm():
            self.destroy()
            on_confirm()

        ctk.CTkButton(btns, text=f"Move {selected_count} item(s)", height=30,
                      command=_confirm, **theme.primary_button()).pack(side="right")

        _bring_to_front(self, master, modal=True)
