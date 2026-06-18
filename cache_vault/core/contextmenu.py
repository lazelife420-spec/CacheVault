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


def clip_menu_items(clip: Clip) -> list[MenuItem]:
    """Build the context-menu items for ``clip``.

    A clip in Recently Removed (``deleted_at`` set) gets Restore / Permanently
    Remove. Otherwise the normal menu is shown. File actions (Open / Reveal)
    appear only for clearly-local Windows path clips; Open is disabled when the
    target is gone, Reveal stays available while the parent folder exists.
    """
    if clip.deleted_at is not None:
        return [
            MenuItem("copy_again", "Copy Again"),
            MenuItem("restore", "Restore", separator_before=True),
            MenuItem("permanently_remove", "Permanently Remove"),
        ]

    primary_children = [
        MenuItem(
            "copy_again",
            "Copy Image" if clip.content_type == models.CONTENT_IMAGE else "Paste / Copy",
        ),
    ]

    if clip.classification == models.CLASS_LINK:
        primary_children.insert(0, MenuItem("open_link", "Open Link"))
    if clip.content_type == models.CONTENT_IMAGE:
        primary_children.append(MenuItem("drag_out", "Drag PNG"))
        primary_children.append(MenuItem("open_asset_folder", "Open Asset Folder"))

    organize_children = [
        MenuItem("move_safe", "Move to Safe…"),
        MenuItem(
            "toggle_favorite",
            "Remove from Favorites" if clip.is_pinned else "Add to Favorites",
        ),
        MenuItem(
            "toggle_favorite",
            "Mark Keep",
            enabled=not clip.is_pinned,
        ),
    ]

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
