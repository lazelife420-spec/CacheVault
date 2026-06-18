"""Center-panel vault screens — receipts, exports, editable copies, HTML bundles, mobile."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models
from ..core.editable_copies import KIND_HTML_BUNDLE, load_bundle_meta
from . import theme
from .guide_copy import (
    EMPTY_EXPORTS,
    EMPTY_MOBILE_INBOX,
    EMPTY_STAMPED_RECEIPTS,
    TOOLTIP_EXPORT_PROOF,
    TOOLTIP_MOBILE_INBOX,
    TOOLTIP_STAMPED_RECEIPTS,
    TOOLTIP_VAULT_MACROS,
)
from .tooltip import bind_tooltip
from .receipt_ledger import (
    FILTER_ALL,
    FILTERS,
    filter_rows,
    format_detail_text,
    format_list_line,
    humanize_action,
    rows_from_events,
    shorten_hash,
)


def _section(parent, title: str) -> None:
    ctk.CTkLabel(parent, text=title, anchor="w", **theme.section_heading()).pack(
        fill="x", pady=(12, 6),
    )


def _empty(parent, text: str) -> None:
    ctk.CTkLabel(
        parent, text=text, anchor="w", justify="left", wraplength=640,
        text_color=brand.MUTED_FG, font=theme.body_font(12),
    ).pack(fill="x", pady=8)


class VaultScreenHost(ctk.CTkFrame):
    """Swaps center-panel vault screens."""

    def __init__(self, master, callbacks: dict[str, Callable], **kw):
        super().__init__(master, fg_color=brand.PANEL_BG, **kw)
        self._callbacks = callbacks
        self._screens: dict[str, ctk.CTkScrollableFrame] = {}
        self._active: str | None = None
        builders = {
            "nav_stamped_receipts": self._build_receipts,
            "nav_exports": self._build_exports,
            "nav_editable_copies": self._build_editable_copies,
            "nav_html_bundles": self._build_html_bundles,
            "nav_mobile_access": self._build_mobile_access,
            "nav_mobile_inbox": self._build_mobile_inbox,
            "nav_vault_macros": self._build_vault_macros,
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

    def hide(self) -> None:
        if self._active and self._active in self._screens:
            self._screens[self._active].pack_forget()
        self._active = None

    def _build_receipts(self, parent: ctk.CTkScrollableFrame) -> None:
        title_row = ctk.CTkFrame(parent, fg_color="transparent")
        title_row.pack(fill="x", pady=(4, 2))
        title_lbl = ctk.CTkLabel(
            title_row, text=brand.TERM_STAMPED_RECEIPTS,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        )
        title_lbl.pack(side="left")
        bind_tooltip(title_lbl, TOOLTIP_STAMPED_RECEIPTS)
        ctk.CTkLabel(
            parent, text="Local proof ledger — actions, hashes, and outcomes.",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
        ).pack(fill="x", pady=(0, 8))

        tools = ctk.CTkFrame(parent, fg_color="transparent")
        tools.pack(fill="x", pady=(0, 8))
        search = ctk.CTkEntry(tools, placeholder_text="Search receipts…")
        search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        filt = ctk.CTkOptionMenu(tools, values=list(FILTERS))
        filt.set(FILTER_ALL)
        filt.pack(side="right")

        list_frame = ctk.CTkFrame(parent, fg_color=brand.SURFACE_BG, corner_radius=8)
        list_frame.pack(fill="both", expand=True, pady=4)
        detail = ctk.CTkTextbox(parent, height=140, wrap="word", font=theme.body_font(11))
        detail.pack(fill="x", pady=(8, 4))
        detail.configure(state="disabled")

        def reload() -> None:
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
        title_row = ctk.CTkFrame(parent, fg_color="transparent")
        title_row.pack(fill="x", pady=(4, 2))
        exp_title = ctk.CTkLabel(
            title_row, text=brand.TERM_EXPORTS,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        )
        exp_title.pack(side="left")
        bind_tooltip(exp_title, TOOLTIP_EXPORT_PROOF)
        ctk.CTkLabel(
            parent,
            text="Export saved clips with honest capability labels.",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
        ).pack(fill="x", pady=(0, 12))

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

        export_btn = ctk.CTkButton(
            parent, text=brand.TERM_EXPORT,
            command=self._callbacks["export_view"],
            **theme.primary_button(),
        )
        export_btn.pack(anchor="w", pady=(0, 12))
        bind_tooltip(export_btn, TOOLTIP_EXPORT_PROOF)

        _section(parent, "Recent exports")
        self._exports_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._exports_list.pack(fill="x")

        def reload() -> None:
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
        inbox_title_row = ctk.CTkFrame(parent, fg_color="transparent")
        inbox_title_row.pack(fill="x", pady=(4, 2))
        inbox_title = ctk.CTkLabel(
            inbox_title_row, text=brand.TERM_MOBILE_INBOX,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        )
        inbox_title.pack(side="left")
        bind_tooltip(inbox_title, TOOLTIP_MOBILE_INBOX)
        ctk.CTkLabel(
            parent,
            text=f"{brand.TERM_INCOMING_FROM_PHONE} · paired Send-to-PC · {brand.LABEL_LOCAL_ONLY}",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
            wraplength=640, justify="left",
        ).pack(fill="x", pady=(0, 12))
        self._inbox_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._inbox_list.pack(fill="x")

        def reload() -> None:
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

        macro_title_row = ctk.CTkFrame(parent, fg_color="transparent")
        macro_title_row.pack(fill="x", pady=(4, 2))
        macro_title = ctk.CTkLabel(
            macro_title_row, text=brand.TERM_VAULT_MACROS,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        )
        macro_title.pack(side="left")
        bind_tooltip(macro_title, TOOLTIP_VAULT_MACROS)
        ctk.CTkLabel(
            parent,
            text="Saved macros with Macro Safes and smart filters — not encrypted.",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
        ).pack(fill="x", pady=(0, 8))

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
        ctk.CTkButton(
            tools, text="New from template", width=130,
            command=self._callbacks.get("macro_new_template", lambda: None),
            **theme.secondary_button(),
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            tools, text="Setup wizard", width=110,
            command=self._callbacks.get("macro_setup", lambda: None),
            **theme.secondary_button(),
        ).pack(side="right", padx=2)

        self._macro_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._macro_list.pack(fill="both", expand=True)
        self._macro_inspector = ctk.CTkTextbox(parent, height=120, wrap="word", font=theme.body_font(11))
        self._macro_inspector.pack(fill="x", pady=(8, 0))
        self._macro_inspector.configure(state="disabled")

        filter_map = {label: key for key, label in (
            CORE_MACRO_FILTERS + CONTENT_MACRO_FILTERS + SAFETY_MACRO_FILTERS
        )}

        def reload() -> None:
            for w in self._macro_list.winfo_children():
                w.destroy()
            macros_cb = self._callbacks.get("macro_list")
            if not callable(macros_cb):
                _empty(self._macro_list, "Vault Macros not wired.")
                return
            fk = filter_map.get(filt.get(), MACRO_FILTER_ALL)
            rows = macros_cb(fk, search.get())
            if not rows:
                _empty(self._macro_list, "No macros match this filter.")
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

    def _build_editable_copies(self, parent: ctk.CTkScrollableFrame) -> None:
        ctk.CTkLabel(
            parent, text=brand.TERM_EDITABLE_COPIES,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(
            parent,
            text=f"{brand.LABEL_ORIGINAL_PROTECTED} · {brand.LABEL_EDITABLE_COPY} · {brand.LABEL_LOCAL_ONLY}",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
        ).pack(fill="x", pady=(0, 12))
        self._copies_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._copies_list.pack(fill="x")

        def reload() -> None:
            for w in self._copies_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            records = vault.list_editable_copies()
            if not records:
                _empty(
                    self._copies_list,
                    "No editable copies yet. Create one from a file clip to protect the original.",
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
                    command=lambda c=cid: self._callbacks["select_clip"](c),
                    **theme.secondary_button(),
                ).pack(side="left", padx=2)

        parent._refresh = reload  # type: ignore[attr-defined]

    def _build_html_bundles(self, parent: ctk.CTkScrollableFrame) -> None:
        ctk.CTkLabel(
            parent, text=brand.TERM_HTML_BUNDLES,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(
            parent,
            text=f"{brand.LABEL_HTML_BUNDLE_COPY} · copied assets stay local · remote assets skipped",
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
        ).pack(fill="x", pady=(0, 12))
        self._html_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._html_list.pack(fill="x")

        def reload() -> None:
            for w in self._html_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            records = vault.list_html_bundles()
            if not records:
                _empty(
                    self._html_list,
                    "No HTML bundles yet. Create one from a local .html or .htm file.",
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
        ctk.CTkLabel(
            parent, text=brand.TERM_MOBILE_ACCESS,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(
            parent, text=brand.MOBILE_ACCESS_HONEST,
            anchor="w", text_color=brand.MUTED_FG, font=theme.body_font(11),
            wraplength=640, justify="left",
        ).pack(fill="x", pady=(0, 12))
        self._mobile_body = ctk.CTkFrame(parent, fg_color="transparent")
        self._mobile_body.pack(fill="x")

        def reload() -> None:
            for w in self._mobile_body.winfo_children():
                w.destroy()
            report = self._callbacks["mobile_report"]()
            summary = report.get("summary", {})
            routes = report.get("routes", {})
            lines = [
                ("Bridge enabled", "Yes" if summary.get("mobile_enabled") else "No"),
                ("Local IP", report.get("local_ip", "—")),
                ("Port", str(summary.get("mobile_port", 8742))),
                ("Pairing status", report.get("pairing_status", "—")),
                ("Paired devices", str(summary.get("paired_count", 0))),
                ("Android companion", brand.MOBILE_PRODUCT_NAME),
                ("Last phone connection", report.get("last_connection", "—")),
            ]
            card = ctk.CTkFrame(
                self._mobile_body, fg_color=brand.SURFACE_BG, corner_radius=8,
            )
            card.pack(fill="x", pady=(0, 12))
            for label, val in lines:
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=4)
                ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(11)).pack(
                    side="left",
                )
                color = brand.PROOF_TEAL if val not in ("No", "—") else brand.MUTED_FG
                ctk.CTkLabel(
                    row, text=val, anchor="e", text_color=color,
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).pack(side="right")
            _section(self._mobile_body, "Route health")
            for route, ok in routes.items():
                row = ctk.CTkFrame(self._mobile_body, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=route, anchor="w", font=theme.body_font(11)).pack(
                    side="left",
                )
                ctk.CTkLabel(
                    row, text="200 OK" if ok else "unavailable",
                    text_color=brand.PROOF_TEAL if ok else brand.WARNING_RED,
                    font=theme.body_font(11),
                ).pack(side="right")
            btns = ctk.CTkFrame(self._mobile_body, fg_color="transparent")
            btns.pack(fill="x", pady=(12, 0))
            ctk.CTkButton(
                btns, text="Pair Android Device",
                command=self._callbacks["pair_android"],
                **theme.primary_button(),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                btns, text="Mobile Settings",
                command=self._callbacks["mobile_settings"],
                **theme.secondary_button(),
            ).pack(side="left")

        parent._refresh = reload  # type: ignore[attr-defined]
