"""Pure logic for the left-sidebar context-menu state and command matrix.

This module is deliberately UI-free: it describes which commands appear,
what their labels/enabled state are, and what the invocation context
contains, so it can be unit-tested without Tk. The actual Tk menu
construction and dispatch live in ``cache_vault.ui.sidebar_context``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import storage as S
from .menu_context import MenuCommand
from .search import SearchQuery

# --- Row type constants ------------------------------------------------------

SIDEBAR_HOME = "home"
SIDEBAR_ALL_CLIPS = "all_clips"
SIDEBAR_IMAGES = "images"
SIDEBAR_FAVORITES = "favorites"
SIDEBAR_COLLECTION = "collection"
SIDEBAR_RECENTLY_REMOVED = "recently_removed"
SIDEBAR_CLEANUP_SUGGESTIONS = "cleanup_suggestions"
SIDEBAR_OTHER = "other"

# --- Command keys ------------------------------------------------------------

CMD_OPEN = "open"
CMD_REFRESH = "refresh"
CMD_SCAN_CLEANUP_SUGGESTIONS = "scan_cleanup_suggestions"
CMD_SELECT_ALL_VISIBLE = "select_all_visible"
CMD_SELECT_ALL_MATCHING = "select_all_matching"
CMD_DESELECT_ALL = "deselect_all"
CMD_EXPORT_CURRENT_VIEW = "export_current_view"
CMD_EXPORT_SELECTED = "export_selected"
CMD_SCAN_IMAGE_DUPLICATES = "scan_image_duplicates"
CMD_REVIEW_TINY_IMAGES = "review_tiny_images"
CMD_REVIEW_LARGEST_IMAGES = "review_largest_images"
CMD_PROPERTIES = "properties"
CMD_REMOVE_FAVORITE_MARKS = "remove_favorite_marks"
CMD_RENAME_COLLECTION = "rename_collection"
CMD_EXPORT_COLLECTION = "export_collection"
CMD_EMPTY_COLLECTION = "empty_collection"
CMD_RESTORE_SELECTED = "restore_selected"
CMD_RESTORE_ALL = "restore_all"
CMD_PERMANENTLY_DELETE_SELECTED = "permanently_delete_selected"
CMD_PERMANENTLY_DELETE_ALL = "permanently_delete_all"
CMD_SCAN_AGAIN = "scan_again"
CMD_REVIEW_SUGGESTIONS = "review_suggestions"
CMD_SHOW_IGNORED = "show_ignored"


@dataclass(frozen=True)
class SidebarInvocationContext:
    """Everything a sidebar context-menu command needs, computed once at
    right-click time. Commands that mutate or depend on live selection
    state must re-resolve against the current app state at dispatch
    time rather than trusting this snapshot.

    The ``matching_descriptor`` is only present when the app's current
    matching selection genuinely belongs to the *target* row's query --
    never when it belongs to a different sidebar row or search view.
    """

    target_key: str
    active_key: str
    row_type: str
    collection_name: str | None
    target_query: SearchQuery | None
    visible_selected_ids: tuple[str, ...]
    matching_descriptor: Any | None  # MatchingSelection | None
    item_count: int

    @property
    def is_target_active(self) -> bool:
        return self.target_key == self.active_key

    @property
    def is_matching(self) -> bool:
        return self.matching_descriptor is not None

    @property
    def selection_count(self) -> int:
        if self.is_matching:
            return getattr(self.matching_descriptor, "resolved_count", 0) or 0
        return len(self.visible_selected_ids)

    @property
    def has_selection(self) -> bool:
        return self.selection_count > 0


def classify_sidebar_row(target_key: str) -> str:
    """Classify a sidebar row into one of the supported menu types."""
    if target_key == S.FILTER_HOME:
        return SIDEBAR_HOME
    if target_key == S.FILTER_ALL:
        return SIDEBAR_ALL_CLIPS
    if target_key == S.FILTER_SCREENSHOTS:
        return SIDEBAR_IMAGES
    if target_key in (S.FILTER_FAVORITES, S.FILTER_PINNED):
        return SIDEBAR_FAVORITES
    if target_key == S.FILTER_RECENTLY_REMOVED:
        return SIDEBAR_RECENTLY_REMOVED
    if target_key == "nav_cleanup_suggestions":
        return SIDEBAR_CLEANUP_SUGGESTIONS
    if target_key.startswith(S.COLLECTION_PREFIX):
        return SIDEBAR_COLLECTION
    return SIDEBAR_OTHER


def build_sidebar_query(target_key: str, collection_name: str | None = None) -> SearchQuery | None:
    """Return the natural query for a sidebar row, independent of any
    active search text or other transient filters."""
    if target_key == S.FILTER_HOME or target_key == "nav_cleanup_suggestions":
        return None
    if collection_name is not None:
        key = f"{S.COLLECTION_PREFIX}{collection_name}"
        return SearchQuery(filter_name=key, collection=collection_name)
    if target_key.startswith(S.COLLECTION_PREFIX):
        name = target_key[len(S.COLLECTION_PREFIX):]
        return SearchQuery(filter_name=target_key, collection=name)
    return SearchQuery(filter_name=target_key)


def _matching_belongs_to_target(
    matching: Any | None,
    target_query: SearchQuery | None,
) -> bool:
    """A matching selection belongs to the target row only when it was
    activated against the same natural query -- not against a different
    sidebar row, not against a search result view.
    """
    if matching is None or target_query is None:
        return False
    q = getattr(matching, "query", None)
    if q is None:
        return False
    return (
        getattr(matching, "nav_key", None) == target_query.filter_name
        and q.filter_name == target_query.filter_name
        and not getattr(q, "text", "")
        and getattr(q, "collection", None) == target_query.collection
    )


def build_sidebar_invocation_context(
    target_key: str,
    active_key: str,
    collection_name: str | None,
    visible_selected_ids: tuple[str, ...],
    matching: Any | None,
    item_count: int,
) -> SidebarInvocationContext:
    """Build the authoritative context for a sidebar row right-click."""
    target_query = build_sidebar_query(target_key, collection_name)
    row_type = classify_sidebar_row(target_key)
    matching_descriptor = matching if _matching_belongs_to_target(matching, target_query) else None
    return SidebarInvocationContext(
        target_key=target_key,
        active_key=active_key,
        row_type=row_type,
        collection_name=collection_name,
        target_query=target_query,
        visible_selected_ids=visible_selected_ids,
        matching_descriptor=matching_descriptor,
        item_count=item_count,
    )


def _label_count(label: str, count: int, suffix: str = "") -> str:
    if count == 1:
        return f"{label} 1{suffix}"
    return f"{label} {count}{suffix}"


def _disabled(reason: str, key: str, label: str) -> MenuCommand:
    return MenuCommand(key=key, label=label, enabled=False, reason=reason)


def _enabled(key: str, label: str) -> MenuCommand:
    return MenuCommand(key=key, label=label, enabled=True)


def _active_only(ctx: SidebarInvocationContext) -> bool:
    """Commands that operate on the visible widgets of a view require the
    target row to be active so they don't accidentally act on the
    previously-active view.
    """
    if not ctx.is_target_active:
        return False
    return True


def _properties_label(ctx: SidebarInvocationContext) -> str:
    base = {
        SIDEBAR_ALL_CLIPS: "Properties / item count",
        SIDEBAR_IMAGES: "Properties / image count",
        SIDEBAR_FAVORITES: "Properties / favorite count",
        SIDEBAR_COLLECTION: "Properties / member count",
        SIDEBAR_RECENTLY_REMOVED: "Properties / removed-item count",
        SIDEBAR_CLEANUP_SUGGESTIONS: "Properties / current suggestion counts",
    }.get(ctx.row_type, "Properties")
    if ctx.item_count:
        return f"{base} ({ctx.item_count})"
    return base


def sidebar_command_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    """Return the complete, ordered list of commands for a sidebar row.

    The matrix is deliberately explicit: every supported command is
    decided here with an honest label and, when disabled, a short reason.
    """
    if ctx.row_type == SIDEBAR_HOME:
        return _home_matrix(ctx)
    if ctx.row_type == SIDEBAR_ALL_CLIPS:
        return _all_clips_matrix(ctx)
    if ctx.row_type == SIDEBAR_IMAGES:
        return _images_matrix(ctx)
    if ctx.row_type == SIDEBAR_FAVORITES:
        return _favorites_matrix(ctx)
    if ctx.row_type == SIDEBAR_COLLECTION:
        return _collection_matrix(ctx)
    if ctx.row_type == SIDEBAR_RECENTLY_REMOVED:
        return _recently_removed_matrix(ctx)
    if ctx.row_type == SIDEBAR_CLEANUP_SUGGESTIONS:
        return _cleanup_suggestions_matrix(ctx)
    return _other_matrix(ctx)


def _home_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    return [
        _enabled(CMD_OPEN, "Open"),
        _enabled(CMD_REFRESH, "Refresh dashboard"),
        _enabled(CMD_SCAN_CLEANUP_SUGGESTIONS, "Scan for cleanup suggestions"),
    ]


def _all_clips_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    out: list[MenuCommand] = [_enabled(CMD_OPEN, "Open")]
    if ctx.is_target_active:
        out.append(_enabled(CMD_REFRESH, "Refresh"))
    else:
        out.append(_disabled("target row is not active", CMD_REFRESH, "Refresh"))
    if ctx.is_target_active and ctx.item_count:
        out.append(_enabled(CMD_SELECT_ALL_VISIBLE, f"Select all visible ({ctx.item_count})"))
        out.append(_enabled(CMD_SELECT_ALL_MATCHING, f"Select all matching ({ctx.item_count})"))
    else:
        reason = "target row is not active" if not ctx.is_target_active else "no items"
        out.append(_disabled(reason, CMD_SELECT_ALL_VISIBLE, "Select all visible"))
        out.append(_disabled(reason, CMD_SELECT_ALL_MATCHING, "Select all matching"))

    if ctx.has_selection:
        out.append(_enabled(CMD_DESELECT_ALL, "Deselect all"))
    else:
        out.append(_disabled("nothing selected", CMD_DESELECT_ALL, "Deselect all"))

    if ctx.is_target_active and ctx.item_count:
        out.append(_enabled(CMD_EXPORT_CURRENT_VIEW, _label_count("Export", ctx.item_count, " matching clips")))
    else:
        reason = "target row is not active" if not ctx.is_target_active else "no items"
        out.append(_disabled(reason, CMD_EXPORT_CURRENT_VIEW, "Export current view"))

    out.append(_enabled(CMD_SCAN_CLEANUP_SUGGESTIONS, "Scan for cleanup suggestions"))
    out.append(_enabled(CMD_PROPERTIES, _properties_label(ctx)))
    return out


def _images_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    out: list[MenuCommand] = [_enabled(CMD_OPEN, "Open")]
    if ctx.is_target_active:
        out.append(_enabled(CMD_REFRESH, "Refresh"))
    else:
        out.append(_disabled("target row is not active", CMD_REFRESH, "Refresh"))
    active = ctx.is_target_active
    if active and ctx.item_count:
        out.append(_enabled(CMD_SELECT_ALL_VISIBLE, f"Select all visible ({ctx.item_count})"))
        out.append(_enabled(CMD_SELECT_ALL_MATCHING, f"Select all matching ({ctx.item_count})"))
    else:
        reason = "target row is not active" if not active else "no images"
        out.append(_disabled(reason, CMD_SELECT_ALL_VISIBLE, "Select all visible"))
        out.append(_disabled(reason, CMD_SELECT_ALL_MATCHING, "Select all matching"))

    if active and ctx.has_selection:
        out.append(_enabled(CMD_EXPORT_SELECTED, _label_count("Export selected", ctx.selection_count, " images")))
    else:
        out.append(_disabled("no selection", CMD_EXPORT_SELECTED, "Export selected images"))

    if active and ctx.item_count:
        out.append(_enabled(CMD_SCAN_IMAGE_DUPLICATES, "Scan images for duplicates"))
        out.append(_enabled(CMD_REVIEW_TINY_IMAGES, "Review tiny images"))
        out.append(_enabled(CMD_REVIEW_LARGEST_IMAGES, "Review largest images"))
    else:
        reason = "target row is not active" if not active else "no images"
        out.append(_disabled(reason, CMD_SCAN_IMAGE_DUPLICATES, "Scan images for duplicates"))
        out.append(_disabled(reason, CMD_REVIEW_TINY_IMAGES, "Review tiny images"))
        out.append(_disabled(reason, CMD_REVIEW_LARGEST_IMAGES, "Review largest images"))

    out.append(_enabled(CMD_PROPERTIES, _properties_label(ctx)))
    return out


def _favorites_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    out: list[MenuCommand] = [
        _enabled(CMD_OPEN, "Open"),
    ]
    active = ctx.is_target_active
    if active and ctx.item_count:
        out.append(_enabled(CMD_SELECT_ALL_VISIBLE, f"Select all visible ({ctx.item_count})"))
        out.append(_enabled(CMD_SELECT_ALL_MATCHING, f"Select all matching ({ctx.item_count})"))
    else:
        reason = "target row is not active" if not active else "no favorites"
        out.append(_disabled(reason, CMD_SELECT_ALL_VISIBLE, "Select all visible"))
        out.append(_disabled(reason, CMD_SELECT_ALL_MATCHING, "Select all matching"))

    if active and ctx.item_count:
        export_count = ctx.selection_count if ctx.has_selection else ctx.item_count
        out.append(_enabled(CMD_EXPORT_SELECTED, _label_count("Export", export_count, " favorites/selection")))
    else:
        out.append(_disabled("no favorites", CMD_EXPORT_SELECTED, "Export favorites/selection"))

    if active and ctx.item_count:
        remove_count = ctx.selection_count if ctx.has_selection else ctx.item_count
        out.append(_enabled(CMD_REMOVE_FAVORITE_MARKS, _label_count("Remove favorite marks from", remove_count, " clips")))
    else:
        reason = "target row is not active" if not active else "no favorites"
        out.append(_disabled(reason, CMD_REMOVE_FAVORITE_MARKS, "Remove favorite marks"))

    out.append(_enabled(CMD_PROPERTIES, _properties_label(ctx)))
    return out


def _collection_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    out: list[MenuCommand] = [
        _enabled(CMD_OPEN, "Open collection"),
        _enabled(CMD_RENAME_COLLECTION, "Rename collection"),
        _enabled(CMD_EMPTY_COLLECTION, "Empty collection"),
    ]
    active = ctx.is_target_active
    label = f"'{ctx.collection_name}'" if ctx.collection_name else "collection"
    if active and ctx.item_count:
        out.append(_enabled(CMD_SELECT_ALL_VISIBLE, f"Select all visible ({ctx.item_count})"))
        out.append(_enabled(CMD_SELECT_ALL_MATCHING, f"Select all matching ({ctx.item_count})"))
    else:
        reason = "target row is not active" if not active else "no members"
        out.append(_disabled(reason, CMD_SELECT_ALL_VISIBLE, "Select all visible"))
        out.append(_disabled(reason, CMD_SELECT_ALL_MATCHING, "Select all matching"))

    if active and ctx.item_count:
        export_count = ctx.selection_count if ctx.has_selection else ctx.item_count
        out.append(_enabled(CMD_EXPORT_COLLECTION, _label_count("Export", export_count, f" from {label}")))
    else:
        out.append(_disabled("no members", CMD_EXPORT_COLLECTION, f"Export selected/current {label}"))

    out.append(_enabled(CMD_PROPERTIES, _properties_label(ctx)))
    return out


def _recently_removed_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    out: list[MenuCommand] = [_enabled(CMD_OPEN, "Open")]
    if ctx.is_target_active:
        out.append(_enabled(CMD_REFRESH, "Refresh"))
    else:
        out.append(_disabled("target row is not active", CMD_REFRESH, "Refresh"))
    active = ctx.is_target_active
    if active and ctx.item_count:
        out.append(_enabled(CMD_SELECT_ALL_VISIBLE, f"Select all visible ({ctx.item_count})"))
        out.append(_enabled(CMD_SELECT_ALL_MATCHING, f"Select all matching ({ctx.item_count})"))
    else:
        reason = "target row is not active" if not active else "no removed items"
        out.append(_disabled(reason, CMD_SELECT_ALL_VISIBLE, "Select all visible"))
        out.append(_disabled(reason, CMD_SELECT_ALL_MATCHING, "Select all matching"))

    if ctx.has_selection:
        out.append(_enabled(CMD_DESELECT_ALL, "Deselect all"))
    else:
        out.append(_disabled("nothing selected", CMD_DESELECT_ALL, "Deselect all"))

    if active and ctx.has_selection:
        out.append(_enabled(CMD_RESTORE_SELECTED, _label_count("Restore", ctx.selection_count, " selected items")))
    else:
        out.append(_disabled("no selection", CMD_RESTORE_SELECTED, "Restore selected"))

    if ctx.item_count:
        out.append(_enabled(CMD_RESTORE_ALL, _label_count("Restore all", ctx.item_count, " items")))
    else:
        out.append(_disabled("no removed items", CMD_RESTORE_ALL, "Restore all"))

    if active and ctx.has_selection:
        out.append(_enabled(
            CMD_PERMANENTLY_DELETE_SELECTED,
            f"Permanently delete selected ({ctx.selection_count})",
        ))
    else:
        out.append(_disabled(
            "no selection", CMD_PERMANENTLY_DELETE_SELECTED, "Permanently delete selected",
        ))

    if ctx.item_count:
        out.append(_enabled(
            CMD_PERMANENTLY_DELETE_ALL, "Permanently delete all items in Recently Removed",
        ))
    else:
        out.append(_disabled(
            "no removed items", CMD_PERMANENTLY_DELETE_ALL,
            "Permanently delete all items in Recently Removed",
        ))

    out.append(_enabled(CMD_PROPERTIES, _properties_label(ctx)))
    return out


def _cleanup_suggestions_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    return [
        _enabled(CMD_OPEN, "Open"),
        _enabled(CMD_SCAN_AGAIN, "Scan again"),
        _enabled(CMD_REVIEW_SUGGESTIONS, "Review suggestions"),
        _enabled(CMD_SHOW_IGNORED, "Show ignored suggestions"),
        _enabled(CMD_PROPERTIES, _properties_label(ctx)),
    ]


def _other_matrix(ctx: SidebarInvocationContext) -> list[MenuCommand]:
    """Fallback for rows not explicitly supported in this commit."""
    if ctx.target_key == S.FILTER_HOME or ctx.target_key.startswith("nav_"):
        return [
            _enabled(CMD_OPEN, "Open"),
            _enabled(CMD_PROPERTIES, _properties_label(ctx)),
        ]
    return [
        _enabled(CMD_OPEN, "Open"),
        _enabled(CMD_PROPERTIES, _properties_label(ctx)),
    ]
