"""Pure logic for the item context-menu's invocation state and per-view
command availability. Kept UI-free (no tkinter import) so it can be unit-
tested without Tk, mirroring core/contextmenu.py's split.

The whole point of this module: no individual menu command should ever
have to re-derive "what's selected right now, in which mode, in which
view" for itself -- that invites exactly the kind of mismatch this
commit exists to prevent (a matching-mode menu quietly operating on only
the rendered subset). Everything below is built once, by
build_invocation_context, and every command reads from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# View-kind constants. Deliberately plain strings (not an enum) to match
# the rest of this codebase's style (see core/storage.py's FILTER_* names).
VIEW_ACTIVE = "active"
VIEW_RECENTLY_REMOVED = "recently_removed"
VIEW_SEARCH = "search"
VIEW_COLLECTION = "collection"
VIEW_FAVORITES = "favorites"
VIEW_IMAGES = "images"
VIEW_OTHER = "other"


def classify_view_kind(nav_key: str, query: Any | None) -> str:
    """Classifies the current view for menu-matrix purposes. Order
    matters: a search with text active (FILTER_SEARCH_ALL, or any query
    with free text) takes priority over the underlying nav filter, since
    the search-results matrix applies regardless of which tab the search
    was typed from.
    """
    from . import storage as S

    if query is not None and getattr(query, "text", ""):
        return VIEW_SEARCH
    filter_name = nav_key
    if query is not None:
        filter_name = query.filter_name or nav_key
    if filter_name == S.FILTER_RECENTLY_REMOVED:
        return VIEW_RECENTLY_REMOVED
    if filter_name == S.FILTER_SEARCH_ALL:
        return VIEW_SEARCH
    if filter_name in (S.FILTER_FAVORITES, S.FILTER_PINNED):
        return VIEW_FAVORITES
    if filter_name == S.FILTER_SCREENSHOTS:
        return VIEW_IMAGES
    if isinstance(filter_name, str) and filter_name.startswith(S.COLLECTION_PREFIX):
        return VIEW_COLLECTION
    if filter_name == S.FILTER_ALL:
        return VIEW_ACTIVE
    # Everything else (links/files/code/commands/today/week/older/
    # duplicates/safe:/smart:/sensitive) behaves like the active-clips
    # matrix -- a plain, non-deleted, non-collection, non-favorites view.
    return VIEW_ACTIVE


@dataclass(frozen=True)
class MenuInvocationContext:
    """Everything a context-menu command needs, computed once at
    right-click time. Immutable -- a command must re-resolve (via the
    Commit 1 resolver) at execution time rather than trusting any count/
    id list cached here past the moment the menu opened.
    """

    clicked_clip_id: str
    nav_key: str
    view_kind: str
    was_selected_before_click: bool
    selection_mode: str  # "visible" | "matching" | "none"
    visible_selected_ids: tuple[str, ...]
    matching_signature: tuple | None
    matching_count: int | None

    @property
    def is_matching(self) -> bool:
        return self.selection_mode == "matching"

    @property
    def is_bulk_visible(self) -> bool:
        return self.selection_mode == "visible" and len(self.visible_selected_ids) > 1

    @property
    def selection_count(self) -> int:
        if self.selection_mode == "matching":
            return self.matching_count or 0
        return len(self.visible_selected_ids)


@dataclass(frozen=True)
class MenuCommand:
    """One selection-wide (or view-level) command's availability, decided
    once by command_matrix so no dispatch code has to re-derive it."""

    key: str
    label: str
    enabled: bool
    reason: str = ""  # shown (as a disabled-item tooltip/label suffix) when not enabled


def command_matrix(ctx: MenuInvocationContext, *, matching_wide_supported: frozenset[str]) -> list[MenuCommand]:
    """The selection-wide command list for ctx.view_kind, with per-command
    enabled/disabled state already resolved.

    ``matching_wide_supported`` names which command keys have a real
    matching-wide (snapshot + revalidate) implementation wired up in this
    commit -- see clip_context.py's _MATCHING_WIDE_HANDLERS. Anything not
    in that set is disabled (not omitted -- so the user can see the
    action exists and why it's unavailable) whenever selection_mode is
    "matching", per this commit's explicit instruction: never silently
    fall back to operating on just the visible subset.
    """
    n = ctx.selection_count
    matching = ctx.is_matching
    has_selection = ctx.selection_mode != "none"

    def cmd(key: str, label: str, *, view_kinds: set[str] | None = None,
            requires_selection: bool = True, matching_capable: bool = True) -> MenuCommand:
        if view_kinds is not None and ctx.view_kind not in view_kinds:
            return MenuCommand(key, label, enabled=False, reason="not available in this view")
        if requires_selection and not has_selection:
            return MenuCommand(key, label, enabled=False, reason="nothing selected")
        if matching and (not matching_capable or key not in matching_wide_supported):
            return MenuCommand(
                key, label, enabled=False,
                reason="requires a visible selection (not yet supported for \"select all matching\")",
            )
        return MenuCommand(key, label, enabled=True)

    out = [
        MenuCommand("select_all_visible", "Select All Visible", enabled=True, reason=""),
        MenuCommand("select_all_matching", "Select All Matching", enabled=True, reason=""),
        MenuCommand("deselect_all", "Deselect All", enabled=has_selection),
        MenuCommand("invert_visible", "Invert Visible Selection", enabled=True),
    ]

    if ctx.view_kind == VIEW_RECENTLY_REMOVED:
        out.append(cmd("restore", f"Restore {n} item(s)" if n else "Restore"))
        # No permanent-delete commands in this commit -- deliberately
        # absent, not just disabled, per this commit's explicit scope
        # boundary (see checkpoint instructions: permanent delete is a
        # separate, dedicated destructive-confirmation commit).
        return out

    out.append(cmd("copy_selected", f"Copy {n} Selected" if n else "Copy Selected"))
    out.append(cmd("export_selected", f"Export {n} Selected" if n else "Export Selected"))

    if ctx.view_kind == VIEW_FAVORITES:
        out.append(cmd("remove_favorite_marks", f"Remove Favorite Marks ({n})" if n else "Remove Favorite Marks"))
    else:
        out.append(cmd("favorite_selected", f"Favorite {n} Selected" if n else "Favorite Selected"))
        out.append(cmd("unfavorite_selected", f"Remove {n} from Favorites" if n else "Remove from Favorites"))

    if ctx.view_kind == VIEW_COLLECTION:
        out.append(cmd(
            "remove_from_collection", f"Remove {n} from This Collection" if n else "Remove from This Collection",
            matching_capable=False,  # single-assignment label clear -- kept visible-only, see checkpoint note
        ))
    else:
        out.append(cmd("add_to_collection", f"Add {n} to Collection…" if n else "Add to Collection…", matching_capable=False))

    out.append(cmd(
        "move_to_recently_removed",
        f"Move {n} to Recently Removed" if n else "Move to Recently Removed",
    ))

    return out
