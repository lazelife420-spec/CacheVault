"""Right-hand preview / details / actions panel."""

from __future__ import annotations

import webbrowser
from io import BytesIO
from typing import Callable

import customtkinter as ctk
from PIL import Image

from .. import brand
from ..core import clip_metadata, models, pathutil
from ..core.clip_accents import LOCKED_ITEMS_MESSAGE
from ..core.models import Clip
from . import theme


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master, actions: dict[str, Callable], **kw):
        super().__init__(master, **kw)
        self._actions = actions
        self._clip: Clip | None = None
        self._revealed = False
        self._usage_events: list[dict] = []
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self._title = ctk.CTkLabel(self._scroll, text=brand.TERM_VAULT_ITEM, anchor="w",
                                   font=ctk.CTkFont(size=16, weight="bold"))
        self._title.pack(fill="x", padx=10, pady=(8, 2))

        self._seal_frame = ctk.CTkFrame(self._scroll, **theme.vault_card())
        self._seal_labels: list[ctk.CTkLabel] = []

        self._subtitle = ctk.CTkLabel(self._scroll, text="", anchor="w",
                                      text_color=brand.MUTED_FG,
                                      font=theme.body_font(11))
        self._subtitle.pack(fill="x", padx=10)

        self._active_tab = "Actions"
        self._tabs = ctk.CTkSegmentedButton(
            self._scroll,
            values=["Actions", "Seal", "Metadata", "History"],
            command=self._set_tab,
        )
        self._tabs.set(self._active_tab)

        self._body = ctk.CTkTextbox(self._scroll, height=140, wrap="word",
                                    font=theme.body_font(12))
        self._body.pack(fill="x", padx=10, pady=6)
        self._body.configure(state="disabled")

        self._image_frame = ctk.CTkFrame(self._scroll, fg_color=brand.SURFACE_BG,
                                         corner_radius=8)
        self._image_label = ctk.CTkLabel(self._image_frame, text="")
        self._image_label.pack(padx=8, pady=8)
        self._image_ref = None
        self._image_hint = ctk.CTkLabel(
            self._image_frame, text="", anchor="w", justify="left",
            text_color=brand.MUTED_FG, font=theme.body_font(10),
        )
        self._image_hint.pack(fill="x", padx=10, pady=(0, 8))

        self._meta_title = ctk.CTkLabel(self._scroll, text="Custody metadata", anchor="w",
                                        **theme.section_heading())
        self._meta_title.pack(fill="x", padx=10, pady=(4, 2))
        self._meta = ctk.CTkLabel(self._scroll, text="", anchor="w", justify="left",
                                  text_color=brand.MUTED_FG,
                                  font=theme.body_font(11))
        self._meta.pack(fill="x", padx=10, pady=2)

        self._usage_title = ctk.CTkLabel(self._scroll, text="Usage History", anchor="w",
                                         **theme.section_heading())
        self._usage_title.pack(fill="x", padx=10, pady=(8, 2))
        self._usage = ctk.CTkTextbox(self._scroll, height=80, wrap="word",
                                     font=theme.body_font(11))
        self._usage.pack(fill="x", padx=10, pady=2)
        self._usage.configure(state="disabled")

        self._buttons = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._buttons.pack(fill="x", padx=8, pady=8)

        self._vault_frame = ctk.CTkFrame(self._scroll, fg_color=brand.SURFACE_BG,
                                         corner_radius=8)
        self.show_empty_tip()

    def set_usage_events(self, events: list[dict]) -> None:
        self._usage_events = events

    def show_empty_tip(self) -> None:
        self._clip = None
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()
        self._hide_clip_sections()
        self._vault_frame.pack_forget()
        self._title.configure(text=brand.TERM_VAULT_ITEM)
        self._subtitle.configure(text="")
        self._hide_tabs()
        self._seal_frame.pack_forget()
        self._set_body(
            "Select a clip to see details.\n\n"
            "Tip:\n"
            "Use Home for recently saved clips, or switch to Grid to sort by "
            "First Saved, Last Used, Source, and Type."
        )

    def show_locked_message(self) -> None:
        self._clip = None
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()
        self._hide_clip_sections()
        self._vault_frame.pack_forget()
        self._title.configure(text=LOCKED_ITEMS_MESSAGE)
        self._subtitle.configure(text="")
        self._hide_tabs()
        self._seal_frame.pack_forget()
        self._set_body(LOCKED_ITEMS_MESSAGE)

    def show_vault_summary(self, summary: dict, callbacks: dict[str, Callable]) -> None:
        """Show Vault Control when Home is active and no clip is selected."""
        self.show_vault_control(summary, callbacks)

    def show_vault_control(self, summary: dict, callbacks: dict[str, Callable]) -> None:
        self._clip = None
        self._revealed = False
        for w in self._buttons.winfo_children():
            w.destroy()
        self._hide_clip_sections()
        self._title.configure(text=brand.TERM_VAULT_STATUS)
        self._subtitle.configure(text=f"{brand.VAULT_TAGLINE} · {brand.LABEL_LOCAL_ONLY}")
        self._hide_tabs()
        self._seal_frame.pack_forget()
        self._set_body("")
        self._body.pack_forget()

        self._vault_frame.pack(fill="both", expand=True, padx=10, pady=6)
        for w in self._vault_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._vault_frame, text=brand.TERM_VAULT_STATUS, anchor="w",
                     **theme.section_heading()).pack(anchor="w", padx=12, pady=(10, 4))

        capture = (
            brand.LABEL_CAPTURE_ACTIVE
            if not summary.get("capture_paused")
            else "Capture paused"
        )
        mobile = (
            "Mobile Access active" if summary.get("mobile_enabled")
            else "Mobile Access off"
        )
        status_lines = [
            (brand.VAULT_STATUS_ACTIVE, brand.STAMP_GOLD),
            (capture, brand.PROOF_TEAL if not summary.get("capture_paused") else brand.MUTED_FG),
            (brand.LABEL_RECEIPTS_AVAILABLE, brand.STAMP_GOLD),
            (mobile, brand.PROOF_TEAL if summary.get("mobile_enabled") else brand.MUTED_FG),
        ]
        for line, color in status_lines:
            row = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text="●", text_color=color,
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=line, anchor="w",
                         font=theme.body_font(11)).pack(side="left")

        ctk.CTkLabel(
            self._vault_frame, text=brand.VAULT_STATUS_NOTE,
            anchor="w", justify="left", wraplength=280,
            text_color=brand.MUTED_FG, font=theme.body_font(10),
        ).pack(anchor="w", padx=12, pady=(6, 4))

        ctk.CTkLabel(self._vault_frame, text=brand.TERM_CUSTODY_SUMMARY, anchor="w",
                     **theme.section_heading()).pack(anchor="w", padx=12, pady=(12, 4))
        lines = [
            ("Saved", summary.get("all", 0)),
            ("Safes", summary.get("safe_count", 0)),
            ("Receipts", summary.get("receipts", 0)),
            ("Exports", summary.get("exports", 0)),
            ("Editable copies", summary.get("editable_copies", 0)),
            ("HTML bundles", summary.get("html_bundles", 0)),
            ("Snippet macros", summary.get("vault_macros", 0)),
            ("Mobile inbox", summary.get("mobile_inbox", 0)),
        ]
        for label, count in lines:
            row = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=label, anchor="w", font=theme.body_font(12)).grid(
                row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=str(count), anchor="e",
                         text_color=brand.STAMP_GOLD,
                         font=ctk.CTkFont(size=13, weight="bold")).grid(
                row=0, column=1, sticky="e")

        ctk.CTkLabel(self._vault_frame, text=brand.TERM_QUICK_ACTIONS, anchor="w",
                     **theme.section_heading()).pack(anchor="w", padx=12, pady=(12, 4))
        actions = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 12))
        if callbacks.get("open_receipts"):
            ctk.CTkButton(actions, text=f"View {brand.TERM_STAMPED_RECEIPTS}",
                          command=callbacks["open_receipts"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("view_editable_copies"):
            ctk.CTkButton(actions, text=brand.TERM_EDITABLE_COPIES,
                          command=callbacks["view_editable_copies"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("view_html_bundles"):
            ctk.CTkButton(actions, text=brand.TERM_HTML_BUNDLES,
                          command=callbacks["view_html_bundles"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("review_duplicates"):
            ctk.CTkButton(actions, text="Review Duplicates",
                          command=callbacks["review_duplicates"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("open_receipts"):
            ctk.CTkButton(actions, text=f"Open {brand.TERM_STAMPED_RECEIPTS}",
                          command=callbacks["open_receipts"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("pair_android"):
            ctk.CTkButton(actions, text="Pair Android Device",
                          command=callbacks["pair_android"],
                          **theme.primary_button()).pack(fill="x", pady=2)
        if callbacks.get("export"):
            ctk.CTkButton(actions, text=brand.TERM_EXPORT,
                          command=callbacks["export"],
                          **theme.secondary_button()).pack(fill="x", pady=2)
        if callbacks.get("mobile_settings"):
            ctk.CTkButton(actions, text=brand.TERM_MOBILE_ACCESS,
                          command=callbacks["mobile_settings"],
                          **theme.secondary_button()).pack(fill="x", pady=2)

    def _hide_clip_sections(self) -> None:
        self._hide_tabs()
        self._seal_frame.pack_forget()
        self._body.pack(fill="x", padx=10, pady=6)
        self._image_frame.pack_forget()
        self._meta_title.pack_forget()
        self._meta.pack_forget()
        self._usage_title.pack_forget()
        self._usage.pack_forget()

    def _show_tabs(self) -> None:
        self._tabs.pack(fill="x", padx=10, pady=(8, 4))

    def _hide_tabs(self) -> None:
        self._tabs.pack_forget()

    def _set_tab(self, tab: str) -> None:
        self._active_tab = tab
        self._apply_tab_visibility()

    def _apply_tab_visibility(self) -> None:
        if self._clip is None:
            return
        for widget in (
            self._seal_frame,
            self._body,
            self._image_frame,
            self._meta_title,
            self._meta,
            self._usage_title,
            self._usage,
            self._buttons,
        ):
            widget.pack_forget()

        # Premium workspace: stack sections vertically
        if self._clip.content_type == models.CONTENT_IMAGE:
            self._image_frame.pack(fill="x", padx=10, pady=6)
        else:
            self._body.pack(fill="x", padx=10, pady=6)

        self._buttons.pack(fill="x", padx=8, pady=8)

        self._meta_title.pack(fill="x", padx=10, pady=(12, 2))
        self._meta.pack(fill="x", padx=10, pady=2)

        self._seal_frame.pack(fill="x", padx=10, pady=(12, 6))

        self._usage_title.pack(fill="x", padx=10, pady=(12, 2))
        self._usage.pack(fill="x", padx=10, pady=2)

    def _show_clip_sections(self, *, image: bool = False) -> None:
        self._vault_frame.pack_forget()
        self._hide_tabs()  # Keep tabs hidden for the premium stacked layout
        if image:
            self._body.pack_forget()
            self._image_frame.pack(fill="x", padx=10, pady=6)
        else:
            self._image_frame.pack_forget()
            self._body.pack(fill="x", padx=10, pady=6)
        self._buttons.pack(fill="x", padx=8, pady=8)
        self._meta_title.pack(fill="x", padx=10, pady=(12, 2))
        self._meta.pack(fill="x", padx=10, pady=2)
        self._seal_frame.pack(fill="x", padx=10, pady=(12, 6))
        self._usage_title.pack(fill="x", padx=10, pady=(12, 2))
        self._usage.pack(fill="x", padx=10, pady=2)

    def show(self, clip: Clip | None) -> None:
        if clip is None:
            self.show_empty_tip()
            return
        self._clip = clip
        self._revealed = False
        self._body.unbind("<ButtonPress-1>")
        self._body.configure(cursor="")
        for w in self._buttons.winfo_children():
            w.destroy()

        title = clip.title or clip_metadata.clip_title(clip.content, clip.preview)
        type_label = clip_metadata.format_label(clip.classification, clip.content_type)
        safety = "Sensitive — masked in lists" if clip.is_sensitive else "Standard"
        self._title.configure(text=title)

        # Collect badges based on metadata and storage status
        badges = []
        storage = self._actions.get("get_storage", lambda: None)()
        badges.extend(clip_metadata.status_badges(clip, storage))

        ctx_fn = self._actions.get("clip_inspector_context")
        ctx = ctx_fn(clip.id) if ctx_fn else None
        if ctx and ctx.get("original_protected"):
            badges.append(brand.LABEL_ORIGINAL_PROTECTED)
        if ctx and ctx.get("editable_copy"):
            if ctx.get("is_html"):
                badges.append(brand.LABEL_HTML_BUNDLE_COPY)
            else:
                badges.append(brand.LABEL_EDITABLE_COPY)
        if ctx and ctx.get("receipt_count", 0):
            badges.append(brand.LABEL_RECEIPT_STAMPED)

        sub = f"{type_label} · {safety}"
        if badges:
            sub += " · " + " · ".join(badges)
        self._subtitle.configure(text=sub)
        self._render_seal(clip, ctx)

        is_image = clip.content_type == models.CONTENT_IMAGE
        self._show_clip_sections(image=is_image)

        if is_image:
            self._render_image_preview(clip)
        elif clip.is_sensitive and not self._revealed:
            self._set_body("Sensitive clip hidden.\nUse Reveal to view its contents.")
        else:
            self._set_body(clip.content or "(empty)")
            if (
                clip.classification == models.CLASS_PATH
                and pathutil.is_local_file(clip.content)
                and self._actions.get("drag_out")
            ):
                self._body.configure(cursor="hand2")
                self._body.bind(
                    "<ButtonPress-1>",
                    lambda _e, c=clip: self._fire("drag_out", c),
                )
        self._meta.configure(text=self._meta_text(clip))
        self._set_usage(self._usage_text(clip))
        self._render_buttons(clip)
        self._apply_tab_visibility()

    def _render_seal(self, clip: Clip, ctx: dict | None) -> None:
        for w in self._seal_frame.winfo_children():
            w.destroy()
        self._seal_frame.pack(fill="x", padx=10, pady=(4, 6))
        ctk.CTkLabel(
            self._seal_frame, text=brand.TERM_INSPECTOR_SEAL, anchor="w",
            **theme.section_heading(),
        ).pack(anchor="w", padx=10, pady=(8, 4))
        badges: list[tuple[str, str]] = [
            (brand.LABEL_LOCAL_ONLY, brand.MUTED_FG),
        ]
        if ctx and ctx.get("original_protected"):
            badges.append((brand.LABEL_ORIGINAL_PROTECTED, brand.STAMP_GOLD))
        if ctx and ctx.get("receipt_count", 0):
            badges.append((brand.LABEL_RECEIPT_STAMPED, brand.STAMP_GOLD))
        if clip.content_hash:
            badges.append((brand.LABEL_HASH_VERIFIED, brand.PROOF_TEAL))
        if clip.safe_name:
            badges.append((f"{brand.LABEL_SAFE_ASSIGNED}: {clip.safe_name}", brand.STAMP_GOLD))
        if clip.capture_mode == models.CAPTURE_MOBILE_SHARE:
            badges.append(("Sent from phone", brand.PROOF_TEAL))
        if ctx and ctx.get("editable_copy"):
            if ctx.get("is_html"):
                badges.append((brand.LABEL_HTML_BUNDLE_COPY, brand.MUTED_FG))
            else:
                badges.append((brand.LABEL_EDITABLE_COPY, brand.MUTED_FG))
        if ctx and ctx.get("export_ready"):
            badges.append((brand.LABEL_READY_EXPORT, brand.PROOF_TEAL))
        for text, color in badges:
            row = ctk.CTkFrame(self._seal_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(row, text="◈", text_color=color,
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=text, anchor="w",
                         font=theme.body_font(11)).pack(side="left")
        ctk.CTkLabel(self._seal_frame, text="").pack(pady=2)

    def _render_image_preview(self, clip: Clip) -> None:
        self._image_label.unbind("<ButtonPress-1>")
        self._image_label.configure(cursor="")
        loader = self._actions.get("load_asset")
        loaded = loader(clip.id) if loader else None
        if not loaded:
            self._image_ref = None
            self._image_label.configure(image=None, text="Image file unavailable.")
            self._image_hint.configure(
                text="The vault record exists but the PNG asset is missing from local storage.")
            return
        png_bytes, mime = loaded
        try:
            with Image.open(BytesIO(png_bytes)) as img:
                w, h = img.size
                max_w, max_h = 300, 220
                scale = min(max_w / w, max_h / h, 1.0)
                thumb = img.convert("RGBA").resize(
                    (max(1, int(w * scale)), max(1, int(h * scale))),
                    Image.Resampling.LANCZOS,
                )
                self._image_ref = ctk.CTkImage(
                    light_image=thumb, dark_image=thumb, size=thumb.size)
                self._image_label.configure(image=self._image_ref, text="")
                self._image_label.configure(cursor="hand2")
                self._image_label.bind(
                    "<Double-Button-1>",
                    lambda _e, c=clip: self._fire("view_larger", c),
                )
                if self._actions.get("drag_out"):
                    self._image_label.bind(
                        "<ButtonPress-1>",
                        lambda _e, c=clip: self._fire("drag_out", c),
                    )
        except Exception:  # noqa: BLE001
            self._image_ref = None
            self._image_label.configure(image=None, text="Could not render preview.")
        size_kb = max(1, len(png_bytes) // 1024)
        hint = f"Local PNG · {mime} · {size_kb} KB · stored on this PC only."
        if self._actions.get("drag_out"):
            hint += " Use Drag PNG or drag the preview out."
        self._image_hint.configure(text=hint)

    def _set_usage(self, text: str) -> None:
        self._usage.configure(state="normal")
        self._usage.delete("1.0", "end")
        self._usage.insert("1.0", text)
        self._usage.configure(state="disabled")

    def _set_body(self, text: str) -> None:
        self._body.configure(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)
        self._body.configure(state="disabled")

    def _meta_text(self, clip: Clip) -> str:
        ctx_fn = self._actions.get("clip_inspector_context")
        ctx = ctx_fn(clip.id) if ctx_fn else None
        lines = [
            f"Item ID:      {clip.id}",
            f"Captured:     {clip_metadata.format_captured_at(clip.created_at)}",
            f"Age:          {clip_metadata.relative_age(clip.created_at)}",
            f"First Saved:  {clip_metadata.human_timestamp(clip.created_at)}",
            f"Last Used:    {clip_metadata.human_timestamp(clip.date_used or clip.updated_at)}",
            f"Type:         {clip_metadata.format_label(clip.classification, clip.content_type)}",
            f"Use Count:    {clip.use_count}",
            f"Source App:   {clip_metadata.display(clip.source_app)}",
            f"Window:       {clip_metadata.display(clip.source_window)}",
            f"Source URL:   {clip_metadata.display(clip.source_url)}",
            f"Favorite:     {'yes' if clip.is_pinned else 'no'}",
            f"Collection:   {clip_metadata.display(clip.collection)}",
            f"Safe:         {clip_metadata.display(clip.safe_name)} ({clip.safe_id})",
            f"Capture Mode: {clip.capture_mode or models.CAPTURE_AUTO}",
            f"Proof Hash:   {clip_metadata.shorten_hash(clip.content_hash)}",
        ]
        if ctx:
            lines.append(f"Receipts:     {ctx.get('receipt_count', 0)}")
            if ctx.get("last_pasted"):
                lines.append(
                    f"Last Pasted:  {clip_metadata.human_timestamp(ctx['last_pasted'])}"
                )
            if ctx.get("last_exported"):
                lines.append(
                    f"Last Exported:{clip_metadata.human_timestamp(ctx['last_exported'])}"
                )
            if ctx.get("original_protected"):
                lines.append(f"Status:       {brand.LABEL_ORIGINAL_PROTECTED}")
            rec = ctx.get("editable_copy")
            if rec:
                lines.append(f"Editable:     rev {rec.revision} — {rec.copy_path}")
        if clip.deleted_at:
            lines.append(f"Removed:      {clip.deleted_at.replace('T', ' ')[:19]}")
        if clip.expires_at:
            lines.append(f"Expires:      {clip.expires_at.replace('T', ' ')[:19]}")
        if clip.content_type == models.CONTENT_IMAGE:
            loader = self._actions.get("asset_meta")
            if loader:
                meta = loader(clip.id)
                if meta:
                    lines.append(f"Asset SHA256: {clip_metadata.shorten_hash(meta.get('sha256', ''))}")
                    if meta.get("width") and meta.get("height"):
                        lines.append(f"Dimensions:   {meta['width']}×{meta['height']}")
                    lines.append(f"Asset size:   {meta.get('size_bytes', 0)} bytes")
        summary = self._actions.get("html_bundle_summary")
        if summary:
            info = summary(clip.id)
            if info:
                lines.extend([
                    "",
                    "Original HTML:        " + info.get("original_html", ""),
                    "Editable HTML Copy:   " + info.get("editable_html_copy", ""),
                    "Copied Asset Bundle:  " + str(info.get("copied_asset_count", 0)) + " file(s)",
                    "Missing Assets:       " + str(info.get("missing_asset_count", 0)),
                    "Remote Assets Skipped:" + str(info.get("remote_asset_count", 0)),
                ])
                if info.get("missing_assets"):
                    lines.append("  missing: " + ", ".join(info["missing_assets"][:5]))
                if info.get("remote_assets"):
                    lines.append("  remote:  " + ", ".join(info["remote_assets"][:5]))
        return "\n".join(lines)

    def _usage_text(self, clip: Clip) -> str:
        lines = [
            f"First Saved:   {clip_metadata.human_timestamp(clip.created_at)}",
            f"Last Used:     {clip_metadata.human_timestamp(clip.date_used or clip.updated_at)}",
            f"Used:          {clip.use_count} times",
            f"Copied Again:  {clip.copied_count}",
        ]
        copied = [
            e for e in self._usage_events
            if e.get("event_type") in (models.EVENT_COPIED_AGAIN, models.EVENT_CAPTURED)
        ]
        if len(copied) > 1:
            lines.append("")
            lines.append("Copied on:")
            for ev in copied[:8]:
                ts = clip_metadata.human_timestamp(ev.get("created_at") or "")
                lines.append(f"  {ts}")
        return "\n".join(lines)

    def _render_buttons(self, clip: Clip) -> None:
        if not hasattr(self, "_advanced_expanded"):
            self._advanced_expanded = False

        for w in self._buttons.winfo_children():
            w.destroy()

        def toggle_advanced():
            self._advanced_expanded = not self._advanced_expanded
            self._render_buttons(clip)

        def add_primary(text, key, **kw):
            ctk.CTkButton(
                self._buttons, text=text, height=32, font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: self._fire(key, clip), **kw
            ).pack(fill="x", pady=(0, 6))

        # 1. Primary Action Button
        is_deleted = clip.deleted_at is not None
        is_image = clip.content_type == models.CONTENT_IMAGE
        is_link = clip.classification == models.CLASS_LINK

        if is_deleted:
            add_primary("Restore Clip", "restore", **theme.primary_button())
        elif is_image:
            add_primary("Copy Image", "copy_again", **theme.primary_button())
        elif is_link:
            add_primary("Open Link", "open_link", **theme.primary_button())
        else:
            from ..core import pathutil
            from ..core.editable_copies import is_html_path
            if clip.classification == models.CLASS_PATH and pathutil.is_local_file(clip.content) and is_html_path(clip.content):
                has_copy = bool(self._actions.get("latest_editable_copy", lambda _cid: None)(clip.id))
                if has_copy:
                    add_primary("Preview Copy", "preview_html_copy", **theme.primary_button())
                else:
                    add_primary("Create HTML Copy", "create_editable_copy", **theme.primary_button())
            elif clip.classification == models.CLASS_PATH and pathutil.is_local_file(clip.content):
                add_primary("Open Editable Copy", "open_editable_copy", **theme.primary_button())
            else:
                add_primary("Copy to Clipboard", "copy_again", **theme.primary_button())

        # 2. Compact Grid of 3-4 obvious secondary actions
        sec_frame = ctk.CTkFrame(self._buttons, fg_color="transparent")
        sec_frame.pack(fill="x", pady=2)
        sec_frame.grid_columnconfigure(0, weight=1)
        sec_frame.grid_columnconfigure(1, weight=1)

        def add_sec(text, key, r, c, **kw):
            btn = ctk.CTkButton(
                sec_frame, text=text, height=26, font=ctk.CTkFont(size=11),
                command=lambda: self._fire(key, clip), **kw
            )
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")

        if is_deleted:
            if is_image:
                add_sec("View Larger", "view_larger", 0, 0, **theme.secondary_button())
                add_sec("Unfavorite" if clip.is_pinned else "Favorite", "toggle_favorite", 0, 1, **theme.secondary_button())
            else:
                add_sec("Unfavorite" if clip.is_pinned else "Favorite", "toggle_favorite", 0, 0, **theme.secondary_button())
        elif is_image:
            add_sec("View Larger", "view_larger", 0, 0, **theme.secondary_button())
            add_sec("Save As", "save_asset_as", 0, 1, **theme.secondary_button())
            add_sec("Unfavorite" if clip.is_pinned else "Favorite", "toggle_favorite", 1, 0, **theme.secondary_button())
            if self._actions.get("open_asset_folder"):
                add_sec("Open Folder", "open_asset_folder", 1, 1, **theme.secondary_button())
        elif is_link:
            add_sec("Copy Link", "copy_clean:copy_link_only", 0, 0, **theme.secondary_button())
            add_sec("Edit", "edit_clip_text", 0, 1, **theme.secondary_button())
            add_sec("Duplicate", "duplicate_editable_clip", 1, 0, **theme.secondary_button())
            add_sec("Unfavorite" if clip.is_pinned else "Favorite", "toggle_favorite", 1, 1, **theme.secondary_button())
        else:
            from ..core import pathutil
            from ..core.editable_copies import is_html_path
            # Check if this is an editable html or file copy
            if clip.classification == models.CLASS_PATH and pathutil.is_local_file(clip.content):
                add_sec("Edit", "edit_clip_text", 0, 0, **theme.secondary_button())
                add_sec("Duplicate", "duplicate_editable_clip", 0, 1, **theme.secondary_button())
                add_sec("Unfavorite" if clip.is_pinned else "Favorite", "toggle_favorite", 1, 0, **theme.secondary_button())
                add_sec("Move Safe", "move_safe", 1, 1, **theme.secondary_button())
            else:
                add_sec("Edit", "edit_clip_text", 0, 0, **theme.secondary_button())
                add_sec("Duplicate", "duplicate_editable_clip", 0, 1, **theme.secondary_button())
                add_sec("Unfavorite" if clip.is_pinned else "Favorite", "toggle_favorite", 1, 0, **theme.secondary_button())
                add_sec("Move Safe", "move_safe", 1, 1, **theme.secondary_button())

        # 3. Collapsible More Options Accordion
        adv_header = ctk.CTkFrame(self._buttons, fg_color="transparent")
        adv_header.pack(fill="x", pady=(10, 2))

        toggle_char = "▼" if self._advanced_expanded else "▶"
        lbl_adv = ctk.CTkLabel(adv_header, text="More Options", font=ctk.CTkFont(size=11, weight="bold"), text_color=brand.MUTED_FG)
        lbl_adv.pack(side="left")

        btn_toggle = ctk.CTkButton(
            adv_header, text=toggle_char, width=20, height=20,
            fg_color="transparent", hover_color=brand.ROW_BG,
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=10),
            command=toggle_advanced
        )
        btn_toggle.pack(side="right")

        if self._advanced_expanded:
            adv_body = ctk.CTkFrame(self._buttons, fg_color="transparent")
            adv_body.pack(fill="x", pady=2)

            def add_adv(text, key, **kw):
                ctk.CTkButton(
                    adv_body, text=text, height=24, font=ctk.CTkFont(size=10),
                    command=lambda: self._fire(key, clip), **kw
                ).pack(fill="x", pady=2)

            add_adv("Copy Metadata", "copy_metadata", **theme.secondary_button())
            add_adv("Export Proof Zip", "export_proof_zip", **theme.secondary_button())

            # Path specific options
            from ..core import pathutil
            from ..core.editable_copies import is_html_path
            if clip.classification == models.CLASS_PATH and pathutil.is_local_file(clip.content):
                if is_html_path(clip.content):
                    add_adv("Edit Source", "edit_html_source", **theme.secondary_button())
                    if self._actions.get("export_html_bundle"):
                        add_adv("Export HTML Bundle", "export_html_bundle", **theme.secondary_button())
                else:
                    if self._actions.get("export_editable_copy"):
                        add_adv("Export Editable Copy", "export_editable_copy", **theme.secondary_button())
                add_adv("Show Original in Explorer", "show_original_path", **theme.secondary_button())

            # Macro options
            if self._actions.get("send_to_macro"):
                if self._actions.get("create_paste_macro"):
                    add_adv("Create Paste Macro…", "create_paste_macro", **theme.secondary_button())
                add_adv("Save to Snippet Macros", "send_to_macro", **theme.secondary_button())

            # Mark Keep / Expire / Remove
            add_adv("Mark Keep", "mark_keep", **theme.secondary_button())
            if not is_deleted:
                add_adv("Expire Now", "expire_now", **theme.secondary_button())
                add_adv("Remove from History", "remove_from_history", **theme.secondary_button())
            else:
                add_adv("Permanently Remove", "permanently_remove", **theme.secondary_button())

    def _fire(self, key: str, clip: Clip) -> None:
        if key == "reveal":
            content = self._actions["reveal"](clip.id)
            if content is not None:
                self._revealed = True
                self._set_body(content)
            return
        if key == "open_link":
            webbrowser.open(clip.content.strip())
            return
        if key == "open_folder":
            from ..core import pathutil
            target = clip.content
            if pathutil.is_local_path(target) and not pathutil.target_exists(target):
                target = pathutil.parent_dir(target)
            pathutil.open_path(target)
            return
        if key == "show_original_path":
            from ..core import pathutil
            pathutil.reveal_in_explorer(clip.content)
            return
        if key == "copy_path":
            handler = self._actions.get("copy_path")
            if handler:
                handler(clip.id)
            return
        handler = self._actions.get(key)
        if handler:
            handler(clip.id)
