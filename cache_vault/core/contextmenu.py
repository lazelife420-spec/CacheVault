"""Pure logic for the clip-row right-click menu.

Kept UI-free so it can be unit-tested without Tk. The shell turns this spec
into a native ``tkinter.Menu``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from . import copy_clean, pathutil
from . import models
from .models import Clip


@dataclass
class MenuItem:
    key: str           # action id the UI dispatches on
    label: str         # menu text
    enabled: bool = True
    separator_before: bool = False
    children: list["MenuItem"] = field(default_factory=list)


_COPY_LABELS = {
    copy_clean.COPY_TEXT: "Copy Text",
    copy_clean.COPY_PLAIN_TEXT: "Copy Plain Text",
    copy_clean.COPY_TITLE_LINK: "Copy Title + Link",
    copy_clean.COPY_LINK_ONLY: "Copy Link Only",
    copy_clean.COPY_MARKDOWN: "Copy as Markdown",
    copy_clean.COPY_SMS: "Copy for Text Message",
    copy_clean.COPY_EMAIL: "Copy for Email",
    copy_clean.COPY_PHONE: "Copy Phone Number",
    copy_clean.COPY_EMAIL_ADDRESS: "Copy Email Address",
    copy_clean.COPY_ADDRESS: "Copy Address",
    copy_clean.COPY_FILE_PATH: "Copy File Path",
    copy_clean.COPY_HASH: "Copy Hash",
    copy_clean.COPY_METADATA_SUMMARY: "Copy Metadata Summary",
    copy_clean.COPY_SOURCE_SUMMARY: "Copy Source Summary",
}


def copy_clean_menu_items(clip: Clip) -> list[MenuItem]:
    available = set(copy_clean.available_clip_actions(clip))
    ordered = [
        copy_clean.COPY_PLAIN_TEXT,
        copy_clean.COPY_TITLE_LINK,
        copy_clean.COPY_MARKDOWN,
        copy_clean.COPY_SMS,
        copy_clean.COPY_EMAIL,
        copy_clean.COPY_METADATA_SUMMARY,
        copy_clean.COPY_HASH,
        copy_clean.COPY_LINK_ONLY,
        copy_clean.COPY_TEXT,
        copy_clean.COPY_PHONE,
        copy_clean.COPY_EMAIL_ADDRESS,
        copy_clean.COPY_ADDRESS,
        copy_clean.COPY_FILE_PATH,
        copy_clean.COPY_SOURCE_SUMMARY,
    ]
    return [
        MenuItem(f"copy_clean:{key}", _COPY_LABELS[key], enabled=key in available)
        for key in ordered
    ]


def clip_menu_items(clip_or_clips: Clip | list[Clip], last_safe_name: str | None = None) -> list[MenuItem]:
    """Build the context-menu items for clip or multiple clips.

    If a list of clips is passed and contains more than one item, returns a flat
    list of selection-aware MenuItems. Otherwise, returns the nested single-clip spec.
    """
    if isinstance(clip_or_clips, list) and len(clip_or_clips) > 1:
        clips = clip_or_clips
        from .selection import analyze_selection
        summary = analyze_selection(clips)

        if summary.selection_class == "link_only":
            return [
                MenuItem("copy_plain", "Copy as Plain List"),
                MenuItem("copy_markdown", "Copy as Markdown"),
                MenuItem("copy_numbered", "Copy as Numbered List"),
                MenuItem("move_safe", "Save to Safe…", separator_before=True),
                MenuItem("receipt", "Create Receipt"),
                MenuItem("export", "Export"),
                MenuItem("remove", "Delete Selected", separator_before=True),
            ]
        elif summary.selection_class == "image_only":
            return [
                MenuItem("save_pngs", "Save All As PNG"),
                MenuItem("export_zip", "Export ZIP"),
                MenuItem("copy_paths", "Copy File Paths"),
                MenuItem("view_proof", "View Proof"),
                MenuItem("remove", "Delete Selected", separator_before=True),
            ]
        elif summary.selection_class == "mixed":
            return [
                MenuItem("export_bundle", "Export Bundle"),
                MenuItem("copy_text_links", "Copy Text + Links"),
                MenuItem("save_screenshots", "Save Screenshots"),
                MenuItem("receipt", "Create Receipt"),
                MenuItem("remove", "Delete Selected", separator_before=True),
            ]
        else:  # text_only / other
            return [
                MenuItem("copy_plain", "Copy as Plain List"),
                MenuItem("move_safe", "Save to Safe…", separator_before=True),
                MenuItem("receipt", "Create Receipt"),
                MenuItem("remove", "Delete Selected", separator_before=True),
            ]

    # Single clip path
    clip = clip_or_clips[0] if isinstance(clip_or_clips, list) else clip_or_clips

    if clip.deleted_at is not None:
        return [
            MenuItem("copy_again", "Copy Again"),
            MenuItem("restore", "Restore", separator_before=True),
            MenuItem("permanently_remove", "Permanently Remove"),
        ]

    primary_children = [
        MenuItem(
            "copy_again",
            "Copy Image" if clip.content_type == models.CONTENT_IMAGE else "Copy Selected Item",
        ),
        MenuItem("paste_selected", "Paste Selected Item"),
    ]

    if clip.classification == models.CLASS_LINK:
        primary_children.insert(0, MenuItem("open_link", "Open Link"))
    if clip.content_type == models.CONTENT_IMAGE:
        primary_children.append(MenuItem("drag_out", "Drag PNG"))
        primary_children.append(MenuItem("open_asset_folder", "Open Asset Folder"))

    organize_children = []
    if last_safe_name:
        organize_children.append(MenuItem("copy_to_last_safe", f"Copy to Last Safe ({last_safe_name})"))
    organize_children.append(MenuItem("copy_to_safe", "Copy to Safe…"))
    organize_children.append(MenuItem("move_safe", "Move to Safe…"))
    organize_children.extend([
        MenuItem(
            "toggle_favorite",
            "Remove from Favorites" if clip.is_pinned else "Add to Favorites",
        ),
        MenuItem(
            "mark_keep",
            "Mark Keep",
            enabled=not clip.is_pinned,
        ),
        MenuItem("send_to_macro_safe", "Send to Snippet Macros", separator_before=True),
    ])

    proof_children = [
        MenuItem("view_receipts", "View Receipts"),
        MenuItem("export_proof_zip", "Export Proof Zip"),
    ]
    if clip.capture_mode == models.CAPTURE_MOBILE_SHARE:
        proof_children.insert(0, MenuItem("view_mobile_receipt", "View Mobile Receipt"))

    advanced_children = [
        MenuItem(
            "create_editable_copy",
            "Create Editable Copy",
            enabled=pathutil.is_local_path(clip.content),
        ),
        MenuItem("copy_metadata", "Copy Metadata"),
        MenuItem("copy_item_id", "Copy Item ID"),
    ]
    if clip.capture_mode == models.CAPTURE_MOBILE_SHARE:
        advanced_children.append(MenuItem("copy_source_summary", "Copy Source Summary"))

    if pathutil.is_local_path(clip.content):
        exists = pathutil.target_exists(clip.content)
        parent = pathutil.parent_exists(clip.content)
        is_file = pathutil.is_local_file(clip.content)
        open_label = "Open Asset Folder" if clip.content_type == models.CONTENT_IMAGE else (
            "Open Editable Copy" if is_file else "Open Folder"
        )
        if is_file:
            primary_children.append(MenuItem("drag_out", "Drag File Out", enabled=exists))
        primary_children.append(MenuItem("open", open_label, enabled=exists))
        advanced_children.append(MenuItem("reveal", "Reveal in Explorer",
                                          enabled=exists or parent))

    return [
        MenuItem("primary", "Primary", children=primary_children),
        MenuItem("copy_clean", "Copy Clean", children=copy_clean_menu_items(clip)),
        MenuItem("organize", "Organize", children=organize_children),
        MenuItem("proof", "Proof", children=proof_children),
        MenuItem("advanced", "Advanced", children=advanced_children),
        MenuItem("danger", "Danger", children=[
            MenuItem("remove", "Remove from History"),
        ]),
    ]
