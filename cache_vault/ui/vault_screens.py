"""Center-panel vault screens — receipts, exports, editable copies, HTML bundles, mobile."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clip_metadata, models
from ..core.editable_copies import KIND_HTML_BUNDLE, load_bundle_meta
from . import theme
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
        ctk.CTkLabel(
            parent, text=brand.TERM_STAMPED_RECEIPTS,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(4, 2))
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
                ctk.CTkButton(
                    list_frame, text=line, anchor="w", height=32,
                    fg_color="transparent", hover_color=theme.nav_hover_bg(),
                    command=lambda r=row: pick(r),
                ).pack(fill="x", padx=4, pady=1)
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
        ctk.CTkLabel(
            parent, text=brand.TERM_EXPORTS,
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        ).pack(fill="x", pady=(4, 2))
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

        ctk.CTkButton(
            parent, text=brand.TERM_EXPORT,
            command=self._callbacks["export_view"],
            **theme.primary_button(),
        ).pack(anchor="w", pady=(0, 12))

        _section(parent, "Recent exports")
        self._exports_list = ctk.CTkFrame(parent, fg_color="transparent")
        self._exports_list.pack(fill="x")

        def reload() -> None:
            for w in self._exports_list.winfo_children():
                w.destroy()
            vault = self._callbacks["vault"]()
            exports = vault.list_export_events(30)
            if not exports:
                _empty(
                    self._exports_list,
                    "No exports recorded yet.\nUse Export / Save As from the top bar or Home.",
                )
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
