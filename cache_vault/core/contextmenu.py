"""Pure logic for the clip-row right-click menu.

Kept UI-free so it can be unit-tested without Tk. The shell turns this spec
into a native ``tkinter.Menu``.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import pathutil
from .models import Clip


@dataclass
class MenuItem:
    key: str           # action id the UI dispatches on
    label: str         # menu text
    enabled: bool = True
    separator_before: bool = False


def clip_menu_items(clip: Clip) -> list[MenuItem]:
    """Build the context-menu items for ``clip``.

    File actions (Open / Reveal in Explorer) appear only for clips that are
    clearly local Windows paths; for text/link/other clips they are omitted
    entirely. Open is disabled when the target is gone; Reveal is allowed while
    the parent folder still exists.
    """
    items = [
        MenuItem("copy_again", "Copy Again"),
        MenuItem(
            "toggle_favorite",
            "Remove from Favorites" if clip.is_pinned else "Add to Favorites",
        ),
    ]

    if pathutil.is_local_path(clip.content):
        exists = pathutil.target_exists(clip.content)
        parent = pathutil.parent_exists(clip.content)
        items.append(MenuItem("open", "Open", enabled=exists,
                              separator_before=True))
        items.append(MenuItem("reveal", "Reveal in Explorer",
                              enabled=exists or parent))

    items.append(MenuItem("remove", "Remove from History",
                          separator_before=True))
    return items
