"""Smart selection classification, summaries, and action mappings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from cache_vault.core import models


@dataclass(frozen=True)
class SelectionSummary:
    """Headless summary of a selection of clips."""
    selected_count: int
    link_count: int
    image_count: int
    text_count: int
    selection_class: str  # "empty", "link_only", "image_only", "text_only", "mixed"
    summary_label: str
    available_actions: list[str] = field(default_factory=list)

    def get_toast_message(self, action: str, format_name: str | None = None) -> str:
        """Build a smart toast message for the selection action."""
        if self.selection_class == "empty":
            return "No items selected."

        if action == "copy":
            if self.selection_class == "link_only":
                fmt = f" as {format_name}" if format_name else ""
                return f"Copied {self.link_count} links{fmt}"
            elif self.selection_class == "image_only":
                return f"Copied {self.image_count} screenshots as PNG"
            elif self.selection_class == "text_only":
                fmt = f" as {format_name}" if format_name else ""
                return f"Copied {self.text_count} text clips{fmt}"
            else:
                return f"Copied {self.selected_count} selected items\n{self.summary_label}"

        elif action == "save_png":
            return f"Saved {self.image_count} screenshots as PNG"

        elif action == "export":
            if self.selection_class == "image_only":
                return f"Exported {self.image_count} screenshots as ZIP"
            elif self.selection_class == "link_only":
                return f"Exported {self.link_count} links"
            elif self.selection_class == "text_only":
                return f"Exported {self.text_count} text clips"
            else:
                return f"Exported mixed bundle\n{self.summary_label}"

        return f"Processed {self.selected_count} items"

    def get_receipt_metadata(self, action_name: str) -> dict[str, Any]:
        """Return metadata for stamped receipts."""
        return {
            "action": action_name,
            "selected_count": self.selected_count,
            "link_count": self.link_count,
            "image_count": self.image_count,
            "text_count": self.text_count,
            "selection_class": self.selection_class,
            "summary": self.summary_label,
        }


def is_image_clip(clip: Any) -> bool:
    """Check if a clip is an image/screenshot."""
    cls = getattr(clip, "classification", None)
    ct = getattr(clip, "content_type", None)
    if ct == models.CONTENT_IMAGE or cls == models.CLASS_IMAGE:
        return True
    if isinstance(cls, str) and ("screen" in cls.lower() or "screenshot" in cls.lower()):
        return True
    return False


def is_link_clip(clip: Any) -> bool:
    """Check if a clip is a link."""
    return getattr(clip, "classification", None) == models.CLASS_LINK


def analyze_selection(clips: list[Any]) -> SelectionSummary:
    """Analyze a list of selected clips and return a SelectionSummary."""
    total = len(clips)
    if total == 0:
        return SelectionSummary(
            selected_count=0,
            link_count=0,
            image_count=0,
            text_count=0,
            selection_class="empty",
            summary_label="No items selected",
            available_actions=[],
        )

    links = 0
    images = 0
    texts = 0

    for clip in clips:
        if is_link_clip(clip):
            links += 1
        elif is_image_clip(clip):
            images += 1
        else:
            texts += 1

    # Classify selection
    if links == total:
        sel_class = "link_only"
        actions = [
            "Copy as Plain List",
            "Copy as Markdown",
            "Copy as Numbered List",
            "Save to Safe",
            "Create Receipt",
        ]
    elif images == total:
        sel_class = "image_only"
        actions = [
            "Copy PNG Files",
            "Save All As PNG",
            "Export ZIP",
            "Copy File Paths",
            "View Proof",
        ]
    elif texts == total:
        sel_class = "text_only"
        # Expose list/receipt options for text-only similar to links
        actions = [
            "Copy as Plain List",
            "Copy as Markdown",
            "Copy as Numbered List",
            "Save to Safe",
            "Create Receipt",
        ]
    else:
        sel_class = "mixed"
        actions = [
            "Export Bundle",
            "Copy Text + Links",
            "Save Screenshots",
            "Create Receipt",
            "Delete Selected",
        ]

    # Build summary label
    parts = []
    if links > 0:
        parts.append(f"{links} link" + ("s" if links != 1 else ""))
    if images > 0:
        parts.append(f"{images} screenshot" + ("s" if images != 1 else ""))
    if texts > 0:
        parts.append(f"{texts} text clip" + ("s" if texts != 1 else ""))

    summary_label = " · ".join(parts)

    return SelectionSummary(
        selected_count=total,
        link_count=links,
        image_count=images,
        text_count=texts,
        selection_class=sel_class,
        summary_label=summary_label,
        available_actions=actions,
    )
