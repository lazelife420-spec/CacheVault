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

        self._title_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._title_frame.pack(fill="x", padx=10, pady=(8, 2))

        self._title = ctk.CTkLabel(self._title_frame, text=brand.TERM_VAULT_ITEM, anchor="w",
                                   font=ctk.CTkFont(size=16, weight="bold"))
        self._title.pack(side="left", fill="x", expand=True)
        
        self._close_btn = ctk.CTkButton(
            self._title_frame, text="✕", width=24, height=24, fg_color="transparent",
            hover_color=brand.MUTED_FG,
            command=self._on_close_clicked
        )
        self._close_btn.pack(side="right")

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

        self._meta_title = ctk.CTkLabel(self._scroll, text="Details", anchor="w",
                                        **theme.section_heading())
        self._meta_title.pack(fill="x", padx=10, pady=(4, 2))
        self._meta = ctk.CTkLabel(self._scroll, text="", anchor="w", justify="left",
                                  text_color=brand.MUTED_FG,
                                  font=theme.body_font(11))
        self._meta.pack(fill="x", padx=10, pady=2)

        self._meta_adv_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._meta_adv_frame.pack(fill="x", padx=8, pady=0)

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
        self._close_btn.pack_forget()

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
        self._title.configure(text="CacheVault")
        self._subtitle.configure(text="")
        self._hide_tabs()
        self._seal_frame.pack_forget()
        self._set_body("")
        self._body.pack_forget()
        self._close_btn.pack_forget()

        self._vault_frame.pack(fill="both", expand=True, padx=10, pady=6)
        for w in self._vault_frame.winfo_children():
            w.destroy()
        
        # Premium Identity Empty State
        center_frame = ctk.CTkFrame(self._vault_frame, fg_color="transparent")
        center_frame.pack(expand=True, fill="both", pady=40)

        ctk.CTkLabel(
            center_frame,
            text="Save it. Prove it. Find it again.",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            center_frame,
            text="CacheVault automatically captures your clipboard and proves its origin.\n\nSelect a clip to view its details, or use the Command Center to process your inbox.",
            font=theme.body_font(12),
            text_color=brand.MUTED_FG,
            wraplength=220,
            justify="center",
        ).pack()

    def _on_close_clicked(self) -> None:
        if "close_inspector" in self._actions:
            self._actions["close_inspector"]()

    def _hide_clip_sections(self) -> None:
        self._hide_tabs()
        self._seal_frame.pack_forget()
        self._body.pack_forget()
        self._image_frame.pack_forget()
        self._meta_title.pack_forget()
        self._meta.pack_forget()
        self._meta_adv_frame.pack_forget()

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
            self._meta_adv_frame,
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
        self._meta_adv_frame.pack(fill="x", padx=8, pady=0)

    def _show_clip_sections(self, *, image: bool = False) -> None:
        self._vault_frame.pack_forget()
        self._hide_tabs()
        if image:
            self._body.pack_forget()
            self._image_frame.pack(fill="x", padx=10, pady=6)
        else:
            self._image_frame.pack_forget()
            self._body.pack(fill="x", padx=10, pady=6)
        self._buttons.pack(fill="x", padx=8, pady=8)
        self._meta_title.pack(fill="x", padx=10, pady=(12, 2))
        self._meta.pack(fill="x", padx=10, pady=2)
        self._meta_adv_frame.pack(fill="x", padx=8, pady=0)

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
        self._close_btn.pack(side="right")

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
        self._render_meta_adv(clip)
        self._render_buttons(clip)
        self._apply_tab_visibility()

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

    def _set_body(self, text: str) -> None:
        self._body.configure(state="normal")
        self._body.delete("1.0", "end")
        self._body.insert("1.0", text)
        self._body.configure(state="disabled")

    def _meta_text(self, clip: Clip) -> str:
        ctx_fn = self._actions.get("clip_inspector_context")
        ctx = ctx_fn(clip.id) if ctx_fn else None
        lines = [
            f"Source:   {clip_metadata.display(clip.source_app)}",
            f"Captured: {clip_metadata.format_captured_at(clip.created_at)}",
            f"Safe:     {clip_metadata.display(clip.safe_name)}",
            f"Type:     {clip_metadata.format_label(clip.classification, clip.content_type)}",
        ]
        if ctx and ctx.get("receipt_count", 0):
            lines.append(f"Receipts: {ctx.get('receipt_count')} stamped")
        return "\n".join(lines)

    def _render_meta_adv(self, clip: Clip) -> None:
        if not hasattr(self, "_meta_adv_expanded"):
            self._meta_adv_expanded = False

        for w in self._meta_adv_frame.winfo_children():
            w.destroy()

        def toggle_meta_adv():
            self._meta_adv_expanded = not self._meta_adv_expanded
            self._render_meta_adv(clip)

        adv_header = ctk.CTkFrame(self._meta_adv_frame, fg_color="transparent")
        adv_header.pack(fill="x", pady=2)

        toggle_char = "▼" if self._meta_adv_expanded else "▶"
        lbl_adv = ctk.CTkLabel(adv_header, text="Proof & Custody Metadata", font=ctk.CTkFont(size=11, weight="bold"), text_color=brand.MUTED_FG)
        lbl_adv.pack(side="left", padx=2)

        btn_toggle = ctk.CTkButton(
            adv_header, text=toggle_char, width=20, height=20,
            fg_color="transparent", hover_color=brand.ROW_BG,
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=10),
            command=toggle_meta_adv
        )
        btn_toggle.pack(side="right")

        if self._meta_adv_expanded:
            adv_body = ctk.CTkFrame(self._meta_adv_frame, fg_color="transparent")
            adv_body.pack(fill="x", pady=2)
            
            lines = [
                f"Item ID:      {clip.id}",
                f"Age:          {clip_metadata.relative_age(clip.created_at)}",
                f"First Saved:  {clip_metadata.human_timestamp(clip.created_at)}",
                f"Last Used:    {clip_metadata.human_timestamp(clip.date_used or clip.updated_at)}",
                f"Use Count:    {clip.use_count}",
                f"Window:       {clip_metadata.display(clip.source_window)}",
                f"Source URL:   {clip_metadata.display(clip.source_url)}",
                f"Favorite:     {'yes' if clip.is_pinned else 'no'}",
                f"Collection:   {clip_metadata.display(clip.collection)}",
                f"Capture Mode: {clip.capture_mode or models.CAPTURE_AUTO}",
                f"Proof Hash:   {clip_metadata.shorten_hash(clip.content_hash)}",
            ]
            
            ctx_fn = self._actions.get("clip_inspector_context")
            ctx = ctx_fn(clip.id) if ctx_fn else None
            if ctx:
                if ctx.get("last_pasted"):
                    lines.append(f"Last Pasted:  {clip_metadata.human_timestamp(ctx['last_pasted'])}")
                if ctx.get("last_exported"):
                    lines.append(f"Last Exported:{clip_metadata.human_timestamp(ctx['last_exported'])}")
                rec = ctx.get("editable_copy")
                if rec:
                    lines.append(f"Editable:     rev {rec.revision} — {rec.copy_path}")
            
            if clip.deleted_at:
                lines.append(f"Removed:      {clip.deleted_at.replace('T', ' ')[:19]}")
            if clip.expires_at:
                lines.append(f"Expires:      {clip.expires_at.replace('T', ' ')[:19]}")
                
            copied = [
                e for e in getattr(self, "_usage_events", [])
                if e.get("event_type") in (models.EVENT_COPIED_AGAIN, models.EVENT_CAPTURED)
            ]
            if len(copied) > 1:
                lines.append("")
                lines.append("Copied on:")
                for ev in copied[:5]:
                    ts = clip_metadata.human_timestamp(ev.get("created_at") or "")
                    lines.append(f"  {ts}")
                    
            text = "\n".join(lines)
            lbl = ctk.CTkLabel(adv_body, text=text, anchor="w", justify="left",
                               text_color=brand.MUTED_FG, font=theme.body_font(10))
            lbl.pack(fill="x", padx=2, pady=2)

    def _render_buttons(self, clip: Clip) -> None:
        if not hasattr(self, "_advanced_expanded"):
            self._advanced_expanded = False
        if not hasattr(self, "_danger_expanded"):
            self._danger_expanded = False

        for w in self._buttons.winfo_children():
            w.destroy()

        def toggle_advanced():
            self._advanced_expanded = not self._advanced_expanded
            self._render_buttons(clip)

        def toggle_danger():
            self._danger_expanded = not self._danger_expanded
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
            add_sec("Save PNG", "save_asset_as", 0, 1, **theme.secondary_button())
            add_sec("Move Safe", "move_safe", 1, 0, **theme.secondary_button())
            add_sec("Receipt", "create_receipt", 1, 1, **theme.secondary_button())
        elif is_link:
            add_sec("Edit", "edit_clip_text", 0, 0, **theme.secondary_button())
            add_sec("Duplicate", "duplicate_editable_clip", 0, 1, **theme.secondary_button())
            add_sec("Move Safe", "move_safe", 1, 0, **theme.secondary_button())
            add_sec("Receipt", "create_receipt", 1, 1, **theme.secondary_button())
        else:
            add_sec("Edit", "edit_clip_text", 0, 0, **theme.secondary_button())
            add_sec("Duplicate", "duplicate_editable_clip", 0, 1, **theme.secondary_button())
            add_sec("Move Safe", "move_safe", 1, 0, **theme.secondary_button())
            add_sec("Receipt", "create_receipt", 1, 1, **theme.secondary_button())

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

            # Non-destructive retention option remains available here.
            add_adv("Mark Keep", "mark_keep", **theme.secondary_button())

        # 4. Destructive actions never compete with the primary workflow.
        danger_header = ctk.CTkFrame(self._buttons, fg_color="transparent")
        danger_header.pack(fill="x", pady=(8, 2))
        danger_char = "▼" if self._danger_expanded else "▶"
        ctk.CTkLabel(
            danger_header, text="Danger Zone", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=brand.WARNING_RED,
        ).pack(side="left")
        ctk.CTkButton(
            danger_header, text=danger_char, width=20, height=20,
            fg_color="transparent", hover_color=brand.ROW_BG,
            text_color=brand.WARNING_RED, font=ctk.CTkFont(size=10),
            command=toggle_danger,
        ).pack(side="right")

        if self._danger_expanded:
            danger_body = ctk.CTkFrame(self._buttons, fg_color="transparent")
            danger_body.pack(fill="x", pady=2)
            if not is_deleted:
                ctk.CTkButton(
                    danger_body, text="Expire Now", height=24,
                    command=lambda: self._fire("expire_now", clip),
                    **theme.destructive_button(),
                ).pack(fill="x", pady=2)
                ctk.CTkButton(
                    danger_body, text="Remove from History", height=24,
                    command=lambda: self._fire("remove_from_history", clip),
                    **theme.destructive_button(),
                ).pack(fill="x", pady=2)
            else:
                ctk.CTkButton(
                    danger_body, text="Permanently Remove", height=24,
                    command=lambda: self._fire("permanently_remove", clip),
                    **theme.destructive_button(),
                ).pack(fill="x", pady=2)

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
