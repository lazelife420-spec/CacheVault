"""Center-panel vault screens — receipts, exports, editable copies, HTML bundles, mobile."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models
from ..core.editable_copies import load_bundle_meta
from . import theme
from .clipboard_write import write_text_via_app
from .guide_copy import (
    EMPTY_EXPORTS,
    EMPTY_MOBILE_INBOX,
    EMPTY_STAMPED_RECEIPTS,
    TOOLTIP_EXPORT_PROOF,
    TOOLTIP_MOBILE_INBOX,
    TOOLTIP_STAMPED_RECEIPTS,
    TOOLTIP_VAULT_MACROS,
)
from .textbox import CacheVaultTextbox
from .tooltip import bind_tooltip
from .receipt_ledger import (
    FILTER_ALL,
    FILTERS,
    filter_rows,
    format_detail_text,
    format_list_line,
    rows_from_events,
    shorten_hash,
)


_COMPATIBILITY_LABELS = {
    "compatible": "Compatible",
    "update_recommended": "Update recommended",
    "update_required": "Update required",
    "unknown_client_version": "Unknown client version",
    "unsupported_protocol": "Unsupported protocol",
}


def _section(parent, title: str) -> None:
    ctk.CTkLabel(parent, text=title, anchor="w", **theme.section_heading()).pack(
        fill="x", pady=(12, 6),
    )


def _empty(parent, text: str, title: str = "Empty", icon: str = "📭", actions: list | None = None) -> None:
    from .page_scaffold import EmptyState
    from ..core import storage as S
    for w in parent.winfo_children():
        w.destroy()

    if "editable copies" in text.lower():
        title = "No Editable Copies"
        icon = "⎘"
        host = parent
        while host and not hasattr(host, "_callbacks"):
            host = host.master
        if host and hasattr(host, "_callbacks") and "navigate_filter" in host._callbacks:
            actions = [
                ("Open All Clips", lambda: host._callbacks["navigate_filter"](S.FILTER_ALL), True)
            ]
    elif "receipts" in text.lower():
        title = "No Receipts"
        icon = "⬢"
    elif "mobile inbox" in text.lower():
        title = "Inbox Empty"
        icon = "📥"
    elif "hotkey" in text.lower():
        title = "No Hotkeys Configured"
        icon = "⚡"
    elif "macro" in text.lower():
        title = "No Macros"
        icon = "⚙"
    elif "exports" in text.lower():
        title = "No Exports"
        icon = "↗"
    elif "duplicates" in text.lower():
        title = "No Duplicates"
        icon = "≡"

    est = EmptyState(parent, title=title, description=text, icon=icon, actions=actions)
    est.pack(fill="both", expand=True, pady=40)


class VaultScreenHost(ctk.CTkFrame):
    """Swaps center-panel vault screens."""

    def __init__(self, master, callbacks: dict[str, Callable], **kw):
        super().__init__(master, fg_color=brand.PANEL_BG, **kw)
        self._callbacks = callbacks
        self._screens: dict[str, ctk.CTkScrollableFrame] = {}
        self._active: str | None = None
        self._receipts_filter_hint: str | None = None
        builders = {
            "nav_stamped_receipts": self._build_receipts,
            "nav_exports": self._build_exports,
            "nav_editable_copies": self._build_editable_copies,
            "nav_html_bundles": self._build_html_bundles,
            "nav_mobile_access": self._build_mobile_access,
            "nav_mobile_inbox": self._build_mobile_inbox,
            "nav_vault_macros": self._build_vault_macros,
            "nav_hotkey_actions": self._build_hotkey_actions,
            "nav_cleanup_suggestions": self._build_cleanup_suggestions,
        }
        for key, builder in builders.items():
            frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
            builder(frame)
            self._screens[key] = frame

    def show(self, key: str) -> None:
        if key not in self._screens:
            return
        if self._active and self._active in self._screens:
            self._screens[self._active].pack_forget()
        self._active = key
        self._screens[key].pack(fill="both", expand=True)
        refresh = getattr(self._screens[key], "_refresh", None)
        if callable(refresh):
            refresh()

    def set_receipts_filter_hint(self, filter_name: str | None) -> None:
        self._receipts_filter_hint = filter_name

    def hide(self) -> None:
        if self._active and self._active in self._screens:
            self._screens[self._active].pack_forget()
        self._active = None

    def _build_receipts(self, parent: ctk.CTkScrollableFrame) -> None:
        tools = ctk.CTkFrame(parent, fg_color="transparent")

        tools = ctk.CTkFrame(parent, fg_color="transparent")
        tools.pack(fill="x", pady=(0, 8))
        search = ctk.CTkEntry(tools, placeholder_text="Search receipts…")
        search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        filt = ctk.CTkOptionMenu(tools, values=list(FILTERS))
        filt.set(FILTER_ALL)
        filt.pack(side="right")

        list_frame = ctk.CTkFrame(parent, fg_color=brand.SURFACE_BG, corner_radius=8)
        list_frame.pack(fill="both", expand=True, pady=4)
        detail = CacheVaultTextbox(parent, height=140, wrap="word", font=theme.body_font(11))
        detail.pack(fill="x", pady=(8, 4))
        detail.configure(state="disabled")

        def reload() -> None:
            self._callbacks["set_header_subtitle"]("Local proof ledger — actions, hashes, and outcomes.")
            hint = getattr(self, "_receipts_filter_hint", None)
            if hint:
                from .receipt_ledger import FILTERS
                if hint in FILTERS:
                    filt.set(hint)
                else:
                    search.delete(0, "end")
                    search.insert(0, hint)
                self._receipts_filter_hint = None

            for w in list_frame.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            get_clip = self._callbacks["get_clip"]
            events = vault.events.recent(500)
            rows = rows_from_events(events, get_clip=get_clip)
            rows = filter_rows(rows, flt=filt.get(), query=search.get())
            if not rows:
                if not events:
                    _empty(list_frame, EMPTY_STAMPED_RECEIPTS)
                else:
                    _empty(list_frame, "No receipts match this filter yet.")
                return
            selected = {"row": None}

            def pick(row) -> None:
                selected["row"] = row
                detail.configure(state="normal")
                detail.delete("1.0", "end")
                detail.insert("1.0", format_detail_text(row))
                detail.configure(state="disabled")

            for row in rows[:80]:
                line = format_list_line(row)
                btn = ctk.CTkButton(
                    list_frame, text=line, anchor="w", height=32,
                    fg_color="transparent", hover_color=theme.nav_hover_bg(),
                    command=lambda r=row: pick(r),
                )
                btn.pack(fill="x", padx=4, pady=1)
                if self._callbacks.get("open_receipt_menu"):
                    btn.bind(
                        "<Button-3>",
                        lambda e, r=row: self._callbacks["open_receipt_menu"](
                            r, e.x_root, e.y_root,
                        ),
                    )
            if rows:
                pick(rows[0])

        filt.configure(command=lambda _v: reload())
        search.bind("<KeyRelease>", lambda _e: reload())
        parent._refresh = reload  # type: ignore[attr-defined]
        ctk.CTkButton(
            parent, text=f"Open full {brand.TERM_STAMPED_RECEIPTS} window",
            command=self._callbacks["open_receipts_dialog"],
            **theme.secondary_button(),
        ).pack(anchor="w", pady=(8, 0))

    def _build_exports(self, parent: ctk.CTkScrollableFrame) -> None:
        cap = ctk.CTkFrame(parent, fg_color=brand.SURFACE_BG, corner_radius=8)
        cap.pack(fill="x", pady=(0, 12))
        for label, value in (
            ("Basic export / Save As", "Available now"),
            ("Proof export zip", "Available — manifest + SHA256SUMS + README"),
            ("HTML bundle export", "Uses copied HTML bundle, not originals"),
            ("Proof manifest in export", "Yes — included"),
            ("SHA256SUMS in export", "Yes — included"),
            ("Receipts in export", "Yes — event + file receipts when available"),
            ("Safe metadata in manifest", "Yes — safe_id, safe_name, capture_mode"),
            ("Export by Safe (whole Safe)", "Deferred — manifest schema ready"),
        ):
            row = ctk.CTkFrame(cap, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(11)).pack(
                side="left", fill="x", expand=True,
            )
            ctk.CTkLabel(
                row, text=value, anchor="e", text_color=brand.MUTED_FG,
                font=theme.body_font(10),
            ).pack(side="right")

        _section(parent, "Recent exports")
        self._exports_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._exports_list.pack(fill="x")

        def reload() -> None:
            self._callbacks["set_header_subtitle"]("Export saved clips with honest capability labels.")
            self._callbacks["set_header_actions"](
                primary_text=brand.TERM_EXPORT,
                primary_cmd=self._callbacks["export_view"]
            )
            for w in self._exports_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            exports = vault.list_export_events(30)
            if not exports:
                _empty(self._exports_list, EMPTY_EXPORTS)
                return
            for ev in exports:
                path = ev.get("details", {}).get("path", "")
                eid = ev.get("details", {}).get("export_id", "")
                ts = (ev.get("created_at") or "")[:19].replace("T", " ")
                cid = ev.get("clip_id") or "—"
                card = ctk.CTkFrame(
                    self._exports_list, fg_color=brand.SURFACE_BG, corner_radius=8,
                )
                card.pack(fill="x", pady=4)
                ctk.CTkLabel(
                    card,
                    text=f"{ts} · {ev.get('event_type', 'export')} · "
                         f"clip {shorten_hash(str(cid))} · {path or eid or '(path not recorded)'}",
                    anchor="w", font=theme.body_font(11), wraplength=600,
                ).pack(fill="x", padx=12, pady=8)
                if path:
                    ctk.CTkButton(
                        card, text="Reveal export folder", height=26,
                        command=lambda p=path: self._callbacks["reveal_export"](p),
                        **theme.secondary_button(),
                    ).pack(anchor="w", padx=12, pady=(0, 8))

        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_mobile_inbox(self, parent: ctk.CTkScrollableFrame) -> None:
        self._inbox_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._inbox_list.pack(fill="x")

        def reload() -> None:
            self._callbacks["set_header_subtitle"](f"{brand.TERM_INCOMING_FROM_PHONE} · paired Send-to-PC · {brand.LABEL_LOCAL_ONLY}")
            for w in self._inbox_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            items = vault.list_mobile_inbox()
            if not items:
                _empty(self._inbox_list, EMPTY_MOBILE_INBOX)
                return
            for clip in items[:50]:
                card = ctk.CTkFrame(self._inbox_list, **theme.vault_card())
                card.pack(fill="x", pady=6)
                if self._callbacks.get("open_clip_menu"):
                    card.bind(
                        "<Button-3>",
                        lambda e, c=clip: self._callbacks["open_clip_menu"](
                            c, e.x_root, e.y_root,
                        ),
                    )
                title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
                ctk.CTkLabel(
                    card, text=title, anchor="w",
                    font=ctk.CTkFont(size=13, weight="bold"),
                ).pack(fill="x", padx=12, pady=(10, 2))
                preview = (clip.preview or "")[:160]
                ctk.CTkLabel(
                    card, text=preview or "(empty)", anchor="w", justify="left",
                    text_color=brand.MUTED_FG, font=theme.body_font(11),
                    wraplength=620,
                ).pack(fill="x", padx=12)
                meta_lines = [
                    f"Sent from phone · Source: {clip_metadata.display(clip.source_app)}",
                    f"Safe: {clip_metadata.display(clip.safe_name)} · {brand.LABEL_RECEIPT_STAMPED}",
                ]
                if clip.source_url:
                    meta_lines.append(f"URL: {clip_metadata.display(clip.source_url)}")
                meta_lines.append(
                    f"Received: {(clip.created_at or '')[:19].replace('T', ' ')}"
                )
                for line in meta_lines:
                    ctk.CTkLabel(
                        card, text=line, anchor="w", text_color=brand.MUTED_FG,
                        font=theme.body_font(10),
                    ).pack(fill="x", padx=12)
                btns = ctk.CTkFrame(card, fg_color="transparent")
                btns.pack(fill="x", padx=10, pady=(6, 10))
                cid = clip.id
                ctk.CTkButton(
                    btns, text="Open on PC", width=100, height=28,
                    command=lambda c=cid: self._callbacks["select_clip"](c),
                    **theme.primary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Copy to PC Clipboard", width=150, height=28,
                    command=lambda c=cid: self._callbacks["copy_clip"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                if clip.classification == models.CLASS_LINK:
                    ctk.CTkButton(
                        btns, text="Open Link", width=90, height=28,
                        command=lambda c=cid: self._callbacks["open_link"](c),
                        **theme.secondary_button(),
                    ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Export Proof Zip", width=120, height=28,
                    command=lambda c=cid: self._callbacks["export_proof"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="View Receipt", width=100, height=28,
                    command=self._callbacks["open_receipts_dialog"],
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Remove from History", width=140, height=28,
                    command=lambda c=cid: self._callbacks["remove_clip"](c),
                    **theme.destructive_button(),
                ).pack(side="left", padx=2)

        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_vault_macros(self, parent: ctk.CTkScrollableFrame) -> None:
        from ..core.vault_macros import (
            CORE_MACRO_FILTERS,
            CONTENT_MACRO_FILTERS,
            MACRO_FILTER_ALL,
            SAFETY_MACRO_FILTERS,
            SMART_TYPE_LABELS,
        )

        tools = ctk.CTkFrame(parent, fg_color="transparent")
        tools.pack(fill="x", pady=(0, 8))
        search = ctk.CTkEntry(tools, placeholder_text="Search macros…", width=220)
        search.pack(side="left", padx=(0, 8))
        filt = ctk.CTkOptionMenu(
            tools,
            values=[label for _k, label in CORE_MACRO_FILTERS],
            width=200,
        )
        filt.set("All Macros")
        filt.pack(side="left", padx=(0, 8))

        self._macro_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._macro_list.pack(fill="both", expand=True)
        self._macro_inspector = CacheVaultTextbox(parent, height=120, wrap="word", font=theme.body_font(11))
        self._macro_inspector.pack(fill="x", pady=(8, 0))
        self._macro_inspector.configure(state="disabled")

        filter_map = {label: key for key, label in (
            CORE_MACRO_FILTERS + CONTENT_MACRO_FILTERS + SAFETY_MACRO_FILTERS
        )}

        def reload() -> None:
            self._callbacks["set_header_subtitle"]("Saved macros with Macro Safes and smart filters — not encrypted.")
            self._callbacks["set_header_actions"](
                primary_text="New from template",
                primary_cmd=self._callbacks.get("macro_new_template"),
                secondary_text="Setup wizard",
                secondary_cmd=self._callbacks.get("macro_setup")
            )
            for w in self._macro_list.winfo_children():
                w.destroy()
            macros_cb = self._callbacks.get("macro_list")
            if not callable(macros_cb):
                _empty(self._macro_list, "Snippet Macros not wired.")
                return
            fk = filter_map.get(filt.get(), MACRO_FILTER_ALL)
            rows = macros_cb(fk, search.get())
            if not rows:
                first_use = fk == MACRO_FILTER_ALL and not search.get().strip()
                if first_use:
                    _empty(
                        self._macro_list,
                        "No macros yet.\n\n"
                        "Snippet Macros are reusable snippets — signatures, replies, "
                        "addresses, code, commands — that you paste by hotkey, text "
                        "shortcut, or the macro menu.\n\n"
                        "Click “New from template” to create your first one, then set "
                        "a hotkey combo in the editor to paste it anywhere.",
                    )
                else:
                    _empty(self._macro_list, "No macros match this filter or search.")
                return
            for row in rows[:60]:
                m = row["macro"]
                warns = row.get("warnings") or []
                warn = f" ⚠ {len(warns)}" if warns else ""
                card = ctk.CTkFrame(
                    self._macro_list, fg_color=brand.SURFACE_BG, corner_radius=8,
                )
                card.pack(fill="x", pady=4)
                title = f"{m.name}{warn} · {SMART_TYPE_LABELS.get(m.smart_type, m.smart_type)}"
                ctk.CTkLabel(
                    card, text=title, anchor="w", font=theme.body_font(11),
                ).pack(fill="x", padx=12, pady=(8, 2))
                ctk.CTkLabel(
                    card,
                    text=row.get("subtitle", ""),
                    anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(10),
                ).pack(fill="x", padx=12, pady=(0, 8))
                btns = ctk.CTkFrame(card, fg_color="transparent")
                btns.pack(fill="x", padx=10, pady=(0, 8))
                mid = m.id
                ctk.CTkButton(
                    btns, text="Run", width=70, height=26,
                    command=lambda x=mid: self._callbacks.get("macro_run", lambda _: None)(x),
                    **theme.primary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Inspect", width=80, height=26,
                    command=lambda i=row: _show_inspector(i),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Edit", width=70, height=26,
                    command=lambda x=mid: self._callbacks.get("macro_edit", lambda _: None)(x),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)

        def _show_inspector(row: dict) -> None:
            self._macro_inspector.configure(state="normal")
            self._macro_inspector.delete("1.0", "end")
            self._macro_inspector.insert("1.0", row.get("inspector", ""))
            self._macro_inspector.configure(state="disabled")

        filt.configure(command=lambda _v: reload())
        search.bind("<KeyRelease>", lambda _e: reload())
        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_cleanup_suggestions(self, parent: ctk.CTkScrollableFrame) -> None:
        from . import cleanup_screen
        cleanup_screen.build_cleanup_suggestions_screen(parent, self._callbacks)

    def _build_hotkey_actions(self, parent: ctk.CTkScrollableFrame) -> None:
        from ..core.command_center import (
            REG_ACTIVE,
            REG_CONFLICT,
            REG_DISABLED,
            REG_RESERVED,
            STATUS_LABELS,
            action_label,
        )

        self._hotkey_unavailable = ctk.CTkLabel(
            parent, text="", anchor="w", justify="left",
            text_color=brand.STAMP_GOLD, font=theme.body_font(11), wraplength=640,
        )
        self._hotkey_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._hotkey_list.pack(fill="both", expand=True)

        status_colors = {
            REG_ACTIVE: brand.PROOF_TEAL,
            REG_DISABLED: brand.MUTED_FG,
            REG_CONFLICT: brand.WARNING_RED,
            REG_RESERVED: brand.STAMP_GOLD,
        }

        def reload() -> None:
            self._callbacks["set_header_subtitle"]("Clipboard-powered automation with proof. Trigger → Action → Target → Options → Receipt.")
            self._callbacks["set_header_actions"](
                primary_text="＋ New Hotkey",
                primary_cmd=self._callbacks.get("hotkey_action_new")
            )
            for w in self._hotkey_list.winfo_children():
                w.destroy()
            rows_cb = self._callbacks.get("hotkey_action_list")
            if not callable(rows_cb):
                _empty(self._hotkey_list, "Hotkey Actions not wired.")
                return
            data = rows_cb()
            if not data.get("win32_available", True):
                self._hotkey_unavailable.configure(
                    text="Global shortcuts need Windows (pywin32). Actions are "
                         "saved but will not register on this system.",
                )
                self._hotkey_unavailable.pack(fill="x", pady=(0, 8))
            else:
                self._hotkey_unavailable.pack_forget()
            rows = data.get("rows", [])
            if not rows:
                _empty(
                    self._hotkey_list,
                    "No hotkey actions yet.\n\n"
                    "Hotkey Actions bind a global keyboard shortcut to a safe "
                    "vault action — for example, press Ctrl+Alt+V to paste a "
                    "saved macro, or a combo to copy the latest clip.\n\n"
                    "Click “＋ New Hotkey” to record a shortcut, pick an action "
                    "and target, then save. Every run is stamped to your "
                    "receipts.",
                )
                return
            for row in rows:
                a = row["action"]
                status = row["status"]
                card = ctk.CTkFrame(
                    self._hotkey_list, fg_color=brand.SURFACE_BG, corner_radius=8,
                )
                card.pack(fill="x", pady=4)
                head = ctk.CTkFrame(card, fg_color="transparent")
                head.pack(fill="x", padx=12, pady=(8, 2))
                ctk.CTkLabel(
                    head, text=a.name, anchor="w",
                    font=ctk.CTkFont(size=13, weight="bold"),
                ).pack(side="left")
                ctk.CTkLabel(
                    head, text=STATUS_LABELS.get(status, status), anchor="e",
                    text_color=status_colors.get(status, brand.STAMP_GOLD),
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).pack(side="right")
                detail = (
                    f"{a.hotkey_display or '(no shortcut)'} · "
                    f"{action_label(a.action_type)}"
                    + (f" → {a.target_label}" if a.target_label else "")
                    + f" · {a.scope.capitalize()}"
                )
                ctk.CTkLabel(
                    card, text=detail, anchor="w", text_color=brand.MUTED_FG,
                    font=theme.body_font(10), wraplength=620, justify="left",
                ).pack(fill="x", padx=12)
                meta = (
                    f"Last run: {(a.last_run_at or 'never')[:19].replace('T', ' ')}"
                    f" · Runs: {a.run_count}"
                )
                ctk.CTkLabel(
                    card, text=meta, anchor="w", text_color=brand.MUTED_FG,
                    font=theme.body_font(10),
                ).pack(fill="x", padx=12)
                if row.get("status_message"):
                    ctk.CTkLabel(
                        card, text=row["status_message"], anchor="w",
                        text_color=status_colors.get(status, brand.STAMP_GOLD),
                        font=theme.body_font(10), wraplength=620, justify="left",
                    ).pack(fill="x", padx=12)
                btns = ctk.CTkFrame(card, fg_color="transparent")
                btns.pack(fill="x", padx=10, pady=(4, 8))
                aid = a.id
                ctk.CTkButton(
                    btns, text="Run", width=64, height=26,
                    command=lambda x=aid: self._callbacks.get(
                        "hotkey_action_run", lambda _: None)(x),
                    **theme.primary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Edit", width=64, height=26,
                    command=lambda x=aid: self._callbacks.get(
                        "hotkey_action_edit", lambda _: None)(x),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Disable" if a.enabled else "Enable",
                    width=72, height=26,
                    command=lambda x=aid: self._callbacks.get(
                        "hotkey_action_toggle", lambda _: None)(x),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Delete", width=64, height=26,
                    command=lambda x=aid: self._callbacks.get(
                        "hotkey_action_delete", lambda _: None)(x),
                    **theme.destructive_button(),
                ).pack(side="left", padx=2)

        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_editable_copies(self, parent: ctk.CTkScrollableFrame) -> None:
        self._copies_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._copies_list.pack(fill="x")

        def reload() -> None:
            self._callbacks["set_header_subtitle"](f"{brand.LABEL_ORIGINAL_PROTECTED} · {brand.LABEL_EDITABLE_COPY} · {brand.LABEL_LOCAL_ONLY}")
            for w in self._copies_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            records = vault.list_editable_copies()
            if not records:
                _empty(
                    self._copies_list,
                    "No editable copies yet.\n\n"
                    "An editable copy is a safe, separate working file made from a "
                    "saved file clip — your original stays untouched and "
                    "hash-verified.\n\n"
                    "Select a file clip, then choose “Make Editable Copy” to start "
                    "one. Each saved revision is stamped to your receipts.",
                )
                return
            for rec in records:
                card = ctk.CTkFrame(
                    self._copies_list, fg_color=brand.SURFACE_BG, corner_radius=8,
                )
                card.pack(fill="x", pady=6)
                ctk.CTkLabel(
                    card, text=f"Revision {rec.revision} · {brand.LABEL_HASH_VERIFIED}",
                    anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(fill="x", padx=12, pady=(8, 2))
                for line in (
                    f"Original: {rec.original_path}",
                    f"Editable copy: {rec.copy_path}",
                    f"Created: {(rec.created_at or '')[:19].replace('T', ' ')}",
                    f"Last saved: {(rec.updated_at or '')[:19].replace('T', ' ')}",
                ):
                    ctk.CTkLabel(
                        card, text=line, anchor="w", text_color=brand.MUTED_FG,
                        font=theme.body_font(10), wraplength=620,
                    ).pack(fill="x", padx=12)
                btns = ctk.CTkFrame(card, fg_color="transparent")
                btns.pack(fill="x", padx=10, pady=(4, 10))
                cid = rec.clip_id
                ctk.CTkButton(
                    btns, text="Open Editable Copy", width=130, height=28,
                    command=lambda c=cid: self._callbacks["open_editable_copy"](c),
                    **theme.primary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Save Revision", width=110, height=28,
                    command=lambda c=cid: self._callbacks["save_revision"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Reveal Copy Folder", width=130, height=28,
                    command=lambda c=cid: self._callbacks["reveal_copy"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Show Original", width=110, height=28,
                    command=lambda c=cid: self._callbacks["select_clip_in_place"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)

        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_html_bundles(self, parent: ctk.CTkScrollableFrame) -> None:
        self._html_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._html_list.pack(fill="x")

        def reload() -> None:
            self._callbacks["set_header_subtitle"](f"{brand.LABEL_HTML_BUNDLE_COPY} · copied assets stay local · remote assets skipped")
            for w in self._html_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            records = vault.list_html_bundles()
            if not records:
                _empty(
                    self._html_list,
                    "No HTML bundles yet.\n\n"
                    "An HTML bundle copies a local .html or .htm page plus its local "
                    "assets (images, CSS, scripts) into one editable package. Remote "
                    "assets are skipped and listed so you know what was left out.\n\n"
                    "Select a local HTML file clip, then choose “Make HTML Bundle” to "
                    "create one.",
                )
                return
            for rec in records:
                meta = load_bundle_meta(rec.bundle_dir) if rec.bundle_dir else None
                card = ctk.CTkFrame(
                    self._html_list, fg_color=brand.SURFACE_BG, corner_radius=8,
                )
                card.pack(fill="x", pady=6)
                ctk.CTkLabel(
                    card, text=f"Revision {rec.revision} · {brand.LABEL_HTML_BUNDLE_COPY}",
                    anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(fill="x", padx=12, pady=(8, 2))
                copied = len(meta.copied_assets) if meta else 0
                missing = len(meta.missing_assets) if meta else 0
                remote = len(meta.remote_assets) if meta else 0
                for line in (
                    f"Original HTML: {rec.original_path}",
                    f"Editable HTML copy: {rec.copy_path}",
                    f"Copied asset bundle: {copied} file(s)",
                    f"Missing assets: {missing}",
                    f"Remote assets skipped: {remote}",
                ):
                    ctk.CTkLabel(
                        card, text=line, anchor="w", text_color=brand.MUTED_FG,
                        font=theme.body_font(10), wraplength=620,
                    ).pack(fill="x", padx=12)
                if meta and meta.missing_assets:
                    ctk.CTkLabel(
                        card,
                        text="Missing: " + ", ".join(meta.missing_assets[:6]),
                        anchor="w", text_color=brand.STAMP_GOLD, font=theme.body_font(10),
                    ).pack(fill="x", padx=12)
                btns = ctk.CTkFrame(card, fg_color="transparent")
                btns.pack(fill="x", padx=10, pady=(4, 10))
                cid = rec.clip_id
                ctk.CTkButton(
                    btns, text="Preview Copy", width=110, height=28,
                    command=lambda c=cid: self._callbacks["preview_html"](c),
                    **theme.primary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Edit Source", width=100, height=28,
                    command=lambda c=cid: self._callbacks["edit_html"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Reveal Copied Bundle", width=150, height=28,
                    command=lambda c=cid: self._callbacks["reveal_copy"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)
                ctk.CTkButton(
                    btns, text="Export HTML Bundle", width=140, height=28,
                    command=lambda c=cid: self._callbacks["export_html"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)

        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_mobile_access(self, parent: ctk.CTkScrollableFrame) -> None:
        self._mobile_body = ctk.CTkFrame(parent, fg_color="transparent")
        self._mobile_body.pack(fill="x")
        self._tech_details_visible = False

        def reload() -> None:
            self._callbacks["set_header_subtitle"](brand.MOBILE_ACCESS_HONEST)
            self._callbacks["set_header_actions"]()
            for w in self._mobile_body.winfo_children():
                w.destroy()
            report = self._callbacks["mobile_report"]()
            summary = report.get("summary", {})
            routes = report.get("routes", {})
            devices = report.get("devices", [])
            ctrl_enabled = report.get("controller_enabled", False)
            ctrl_listening = report.get("controller_listening", False)
            ctrl_status = report.get("controller_status", "Off")

            # ── Status Card ──────────────────────────────────────────────
            _section(self._mobile_body, "Status")
            card_status = ctk.CTkFrame(
                self._mobile_body, fg_color=brand.SURFACE_BG, corner_radius=8,
            )
            card_status.pack(fill="x", pady=(0, 12))

            def _status_row(parent_card, label: str, value: str,
                            *, ok_values=("On", "Running", "Active"),
                              muted=False, tooltip_text: str | None = None):
                row = ctk.CTkFrame(parent_card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=5)
                ctk.CTkLabel(
                    row, text=label, anchor="w",
                    font=ctk.CTkFont(size=13),
                ).pack(side="left", fill="x", expand=True)
                if muted or value.startswith("Not running"):
                    color = brand.MUTED_FG
                elif any(v in value for v in ok_values):
                    color = brand.PROOF_TEAL
                elif "Error" in value or "error" in value:
                    color = "#E6A23C"
                else:
                    color = brand.MUTED_FG
                val_label = ctk.CTkLabel(
                    row, text=value, anchor="e",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=color,
                )
                val_label.pack(side="right")
                if tooltip_text:
                    bind_tooltip(val_label, tooltip_text)

            # User-facing status lines
            _status_row(card_status, "Mobile Access", ctrl_status)

            if ctrl_enabled:
                sync_label = "Running" if ctrl_listening else "Not running"
            else:
                sync_label = "Not running \u2014 Mobile Access is off"
            _status_row(card_status, "Phone Sync", sync_label)

            mdns_on = report.get("mdns_advertising", False)
            if ctrl_enabled:
                disc_label = "Active" if mdns_on else "Not running"
            else:
                disc_label = "Not running \u2014 Mobile Access is off"
            _status_row(card_status, "LAN Discovery", disc_label)

            last_conn = report.get("last_connection", "\u2014")
            last_conn_raw = report.get("last_connection_raw", "")
            _status_row(
                card_status, "Last connection", last_conn,
                ok_values=(),
                tooltip_text=last_conn_raw if last_conn_raw and last_conn_raw != "\u2014" else None,
            )

            paired_count = summary.get("paired_count", 0)
            _status_row(
                card_status, "Paired devices",
                f"{paired_count} device{'s' if paired_count != 1 else ''}"
                if paired_count else "No devices paired",
            )

            # Error display
            ctrl_error = report.get("controller_error")
            if ctrl_error:
                err_frame = ctk.CTkFrame(card_status, fg_color="transparent")
                err_frame.pack(fill="x", padx=16, pady=(4, 8))
                ctk.CTkLabel(
                    err_frame, text=f"\u26A0 {ctrl_error}",
                    text_color="#E6A23C", anchor="w",
                    font=ctk.CTkFont(size=12), wraplength=550, justify="left",
                ).pack(fill="x")

            # ── Paired Devices ────────────────────────────────────────────
            active_devices = [d for d in devices if d.get("is_active")]
            if active_devices:
                _section(self._mobile_body, "Paired devices")
                for dev in active_devices:
                    dev_card = ctk.CTkFrame(
                        self._mobile_body, fg_color=brand.SURFACE_BG, corner_radius=8,
                    )
                    dev_card.pack(fill="x", pady=(0, 8))
                    ctk.CTkLabel(
                        dev_card,
                        text=dev.get("device_name", "Unknown device"),
                        anchor="w",
                        font=ctk.CTkFont(size=14, weight="bold"),
                    ).pack(fill="x", padx=16, pady=(10, 2))
                    app_ver = dev.get("app_version", "Unknown")
                    ctk.CTkLabel(
                        dev_card,
                        text=f"CacheVault Mobile {app_ver}",
                        anchor="w", text_color=brand.MUTED_FG,
                        font=ctk.CTkFont(size=12),
                    ).pack(fill="x", padx=16)
                    if "compatibility_state" in dev:
                        protocol = dev.get("protocol")
                        protocol_text = str(protocol) if protocol is not None else "Unknown"
                        state_label = _COMPATIBILITY_LABELS.get(
                            dev["compatibility_state"], "Unknown")
                        if dev.get("update_required"):
                            compat_color = brand.WARNING_RED
                        elif not dev.get("compatible"):
                            compat_color = brand.WARNING_RED
                        elif dev["compatibility_state"] == "compatible":
                            compat_color = brand.PROOF_TEAL
                        else:
                            compat_color = "#E6A23C"
                        ctk.CTkLabel(
                            dev_card,
                            text=f"Protocol {protocol_text} — {state_label}",
                            anchor="w", text_color=compat_color,
                            font=ctk.CTkFont(size=11, weight="bold"),
                        ).pack(fill="x", padx=16, pady=(2, 0))
                    last_seen = dev.get("last_seen", "Never")
                    last_seen_raw = dev.get("last_seen_raw", "")
                    seen_label = ctk.CTkLabel(
                        dev_card,
                        text=f"Last seen {last_seen}",
                        anchor="w", text_color=brand.MUTED_FG,
                        font=ctk.CTkFont(size=11),
                    )
                    seen_label.pack(fill="x", padx=16, pady=(0, 10))
                    if last_seen_raw:
                        bind_tooltip(seen_label, last_seen_raw)

            # ── Actions ──────────────────────────────────────────────────
            btns = ctk.CTkFrame(self._mobile_body, fg_color="transparent")
            btns.pack(fill="x", pady=(12, 0))
            ctk.CTkButton(
                btns, text="Pair Android Device",
                command=self._callbacks["pair_android"],
                **theme.primary_button(),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                btns, text="Paired Devices",
                command=self._callbacks["paired_devices"],
                **theme.secondary_button(),
            ).pack(side="left", padx=(0, 6))
            if paired_count:
                ctk.CTkButton(
                    btns, text="Revoke All Devices",
                    command=self._callbacks["revoke_all_mobile"],
                    **theme.destructive_button(),
                ).pack(side="left", padx=(0, 6))

            btns2 = ctk.CTkFrame(self._mobile_body, fg_color="transparent")
            btns2.pack(fill="x", pady=(6, 0))
            if report.get("local_ip") and report["local_ip"] != "\u2014":
                port = summary.get("mobile_port", 8742)
                address = f"{report['local_ip']}:{port}"

                def _copy_addr(addr=address):
                    try:
                        write_text_via_app(self._mobile_body, addr, operation="copy_pairing_address")
                    except Exception:  # noqa: BLE001
                        pass

                ctk.CTkButton(
                    btns2, text=f"Copy Address ({address})", width=220, height=30,
                    command=_copy_addr,
                    **theme.secondary_button(),
                ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btns2, text="Mobile Settings",
                command=self._callbacks["mobile_settings"],
                **theme.secondary_button(),
            ).pack(side="left")

            # ── Technical Details (collapsed by default) ─────────────────
            tech_frame = ctk.CTkFrame(self._mobile_body, fg_color="transparent")
            tech_frame.pack(fill="x", pady=(16, 0))

            tech_content = ctk.CTkFrame(
                self._mobile_body, fg_color=brand.SURFACE_BG, corner_radius=8,
            )

            def _toggle_tech():
                if tech_content.winfo_manager():
                    tech_content.pack_forget()
                    tech_toggle.configure(text="\u25B6 Technical Details")
                else:
                    tech_content.pack(fill="x", pady=(4, 0))
                    tech_toggle.configure(text="\u25BC Technical Details")

            tech_toggle = ctk.CTkButton(
                tech_frame, text="\u25B6 Technical Details",
                anchor="w", fg_color="transparent",
                hover_color=brand.ROW_SELECTED_BG,
                text_color=brand.MUTED_FG,
                font=ctk.CTkFont(size=12),
                command=_toggle_tech,
            )
            tech_toggle.pack(anchor="w")

            # Populate tech content (hidden until toggled)
            for label_text, value_text in (
                ("LAN IP", report.get("local_ip", "\u2014")),
                ("Port", str(summary.get("mobile_port", 8742))),
                ("Bind host", (summary.get("mobile_bind_host") or "0.0.0.0")),
            ):
                r = ctk.CTkFrame(tech_content, fg_color="transparent")
                r.pack(fill="x", padx=16, pady=3)
                ctk.CTkLabel(r, text=label_text, anchor="w",
                             font=theme.body_font(11)).pack(side="left")
                ctk.CTkLabel(r, text=value_text, anchor="e",
                             text_color=brand.MUTED_FG,
                             font=theme.body_font(11)).pack(side="right")

            # Route health
            if routes:
                ctk.CTkLabel(
                    tech_content, text="ROUTE HEALTH",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=brand.MUTED_FG,
                ).pack(anchor="w", padx=16, pady=(10, 4))
                for route, ok in routes.items():
                    r = ctk.CTkFrame(tech_content, fg_color="transparent")
                    r.pack(fill="x", padx=16, pady=2)
                    ctk.CTkLabel(r, text=route, anchor="w",
                                 font=theme.body_font(11)).pack(side="left")
                    if not ctrl_enabled:
                        status_text = "Not running"
                        status_color = brand.MUTED_FG
                    elif ok:
                        status_text = "200 OK"
                        status_color = brand.PROOF_TEAL
                    else:
                        status_text = "unavailable"
                        status_color = "#E6A23C"
                    ctk.CTkLabel(
                        r, text=status_text, anchor="e",
                        text_color=status_color,
                        font=theme.body_font(11),
                    ).pack(side="right")

            # Pad bottom of tech content
            ctk.CTkFrame(tech_content, height=8, fg_color="transparent").pack()

        parent._refresh = reload  # type: ignore[attr-defined]
