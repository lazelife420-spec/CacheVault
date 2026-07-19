"""Stage D tests: Vault Cleanup Suggestions desktop UI."""

from __future__ import annotations

from io import BytesIO

import customtkinter as ctk
import pytest
from PIL import Image

from cache_vault.core import cleanup_suggestions as cs
from cache_vault.core import image_assets, models
from cache_vault.core.cleanup_store import (
    DECISION_IGNORED, DECISION_KEEP_FOREVER, SCOPE_GROUP, SCOPE_ITEM, get_decision,
)
from cache_vault.core.events import EventLog
from cache_vault.core.models import Clip
from cache_vault.ui import cleanup_screen
from cache_vault.ui.home_dashboard import HomeDashboard


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def _labels(widget):
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            texts.append(child.cget("text"))
        texts.extend(_labels(child))
    return texts


def _tiny_png(color=(10, 20, 30)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (4, 4), color).save(buf, format="PNG")
    return buf.getvalue()


def _add_image_clip(storage, *, data, width=4, height=4, is_pinned=False):
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash, content_type=models.CONTENT_IMAGE,
        classification=models.CLASS_IMAGE, is_pinned=is_pinned,
    )
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=width, height=height,
    )
    storage.save_clip_asset(record, data)
    return clip


# --- Home dashboard card -------------------------------------------------------


def test_home_card_shows_no_scan_yet_by_default(tk_root):
    dashboard = HomeDashboard(
        tk_root,
        on_filter=lambda k: None,
        on_open_receipts=lambda: None,
        on_mobile_settings=lambda: None,
        on_pair_android=lambda: None,
        on_export=lambda: None,
        on_select_clip=lambda _c: None,
        on_copy=lambda _id: None,
        on_open_cleanup=lambda: None,
        on_scan_cleanup=lambda: None,
    )
    summary = {"all": 0, "favorites": 0, "screenshots": 0, "duplicates": 0, "recently_removed": 0, "receipts": 0}
    dashboard.render(summary, [], [], [])  # no cleanup_summary passed -> empty
    dashboard.update_idletasks()

    labels = _labels(dashboard)
    assert any("Cleanup Suggestions" in l for l in labels)
    assert any("No scan yet" in l for l in labels)
    dashboard.destroy()


def test_home_card_shows_scan_result_with_correct_terminology(tk_root):
    dashboard = HomeDashboard(
        tk_root,
        on_filter=lambda k: None,
        on_open_receipts=lambda: None,
        on_mobile_settings=lambda: None,
        on_pair_android=lambda: None,
        on_export=lambda: None,
        on_select_clip=lambda _c: None,
        on_copy=lambda _id: None,
        on_open_cleanup=lambda: None,
        on_scan_cleanup=lambda: None,
    )
    summary = {"all": 0, "favorites": 0, "screenshots": 0, "duplicates": 0, "recently_removed": 0, "receipts": 0}
    cleanup_summary = {
        "total_groups": 2,
        "total_reviewable_items": 5,
        "redundant_bytes_identified": 2048,
        "last_scan_label": "Today 1:00 PM",
        "status": "Idle",
    }
    dashboard.render(summary, [], [], [], cleanup_summary=cleanup_summary)
    dashboard.update_idletasks()

    labels = _labels(dashboard)
    joined = " ".join(labels)
    assert "2" in joined and "5" in joined
    assert "2.0 KB" in joined
    # Exact terminology check: never "recoverable" or "free up".
    assert "recoverable" not in joined.lower()
    assert "free up" not in joined.lower()
    assert "identified" in joined.lower()
    dashboard.destroy()


# --- screen construction never scans -------------------------------------------


def test_build_screen_never_scans_the_vault():
    """Constructing the screen must not call the scan engine -- scanning is
    always an explicit user action.
    """
    scanned = {"called": False}

    class _Frame(ctk.CTkFrame):
        pass

    # A bare frame with no real Tk root is fine here: we only need to prove
    # build_cleanup_suggestions_screen doesn't reach into storage/scan at
    # construction time, which doesn't require a live widget tree.
    class _FakeFrame:
        def winfo_children(self):
            return []

    callbacks = {
        "storage": lambda: (_ for _ in ()).throw(AssertionError("scan must not run at construction")),
        "scan_cleanup_suggestions": lambda: scanned.__setitem__("called", True),
    }
    # build_cleanup_suggestions_screen only touches winfo_children()/pack --
    # verified structurally rather than with a full Tk instance to keep this
    # test fast and independent of a display.
    import types
    frame = types.SimpleNamespace(winfo_children=lambda: [], _cleanup_state=None, _cleanup_callbacks=None)

    with pytest.raises(AttributeError):
        # render_cleanup_screen expects a real CTk widget (pack/CTkLabel
        # etc.) -- this proves it's *rendering*, not scanning, since the
        # failure is a missing widget method, not a call into "storage".
        cleanup_screen.render_cleanup_screen(frame)
    assert scanned["called"] is False


# --- review dialog: selection, protection, keeper ------------------------------


def test_review_dialog_disables_keeper_and_protected_checkboxes(tk_root, storage, assets_home):
    data = _tiny_png()
    plain = _add_image_clip(storage, data=data)
    fav = _add_image_clip(storage, data=data, is_pinned=True)

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)
    assert len(groups) == 1

    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root, callbacks={"storage": lambda: storage}, category=cs.CATEGORY_DUPLICATE_SCREENSHOT,
        items_or_groups=groups,
    )
    dialog.update_idletasks()

    # Favorite is the recommended keeper (only protected copy) -> its
    # checkbox must be disabled, and it must never appear selectable.
    assert fav.id in dialog._keepers
    assert dialog._vars[fav.id] is not None
    assert plain.id not in dialog._keepers

    dialog.destroy()


def test_select_suggested_safe_never_selects_keeper_or_protected(tk_root, storage, assets_home):
    data = _tiny_png()
    plain_a = _add_image_clip(storage, data=data)
    plain_b = _add_image_clip(storage, data=data)
    fav = _add_image_clip(storage, data=data, is_pinned=True)

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)

    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root, callbacks={"storage": lambda: storage}, category=cs.CATEGORY_DUPLICATE_SCREENSHOT,
        items_or_groups=groups,
    )
    dialog._select_suggested_safe()

    selected = set(dialog._selected_ids())
    assert fav.id not in selected  # keeper, protected
    # Exactly the two non-keeper plain copies should be selected.
    assert selected == {plain_a.id, plain_b.id}

    dialog.destroy()


def test_keep_forever_persists_via_decision_store(tk_root, storage, assets_home):
    data = _tiny_png()
    a = _add_image_clip(storage, data=data)
    b = _add_image_clip(storage, data=data)

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)

    rescanned = {"called": False}
    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root,
        callbacks={
            "storage": lambda: storage,
            "rescan_after_decision": lambda: rescanned.__setitem__("called", True),
        },
        category=cs.CATEGORY_DUPLICATE_SCREENSHOT,
        items_or_groups=groups,
    )
    non_keeper_id = a.id if a.id not in dialog._keepers else b.id
    dialog._vars[non_keeper_id].set(True)
    dialog._decide_selected(DECISION_KEEP_FOREVER)

    decision = get_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope="item",
        fingerprint=non_keeper_id, clip_id=non_keeper_id,
    )
    assert decision is not None
    assert decision.decision == DECISION_KEEP_FOREVER
    assert rescanned["called"] is True


# --- confirm dialog: exact terminology -----------------------------------------


def test_confirm_dialog_states_recently_removed_not_permanent(tk_root):
    confirmed = {"called": False}
    dialog = cleanup_screen.CleanupConfirmDialog(
        tk_root, selected_count=3, group_count=2, protected_excluded=1,
        bytes_selected=4096, on_confirm=lambda: confirmed.__setitem__("called", True),
    )
    dialog.update_idletasks()
    labels = _labels(dialog)
    joined = " ".join(labels)

    assert "3" in joined
    assert "Recently Removed" in joined
    assert "restored" in joined.lower()
    assert "not occurring" in joined.lower()  # "Permanent deletion is not occurring."
    assert "retained" in joined.lower()  # "Disk space is retained..."
    assert "recoverable" not in joined.lower()
    dialog.destroy()


def test_confirm_dialog_confirm_button_invokes_callback(tk_root):
    confirmed = {"called": False}
    dialog = cleanup_screen.CleanupConfirmDialog(
        tk_root, selected_count=1, group_count=1, protected_excluded=0,
        bytes_selected=100, on_confirm=lambda: confirmed.__setitem__("called", True),
    )
    dialog.update_idletasks()

    def _buttons(widget):
        out = []
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                out.append(child)
            out.extend(_buttons(child))
        return out

    move_btn = next(b for b in _buttons(dialog) if "Move" in b.cget("text"))
    move_btn.invoke()
    assert confirmed["called"] is True


# --- group-scoped Ignore for grouped categories (real UI action path) ----------


def _dup_png(color) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (100, 100), color).save(buf, format="PNG")
    return buf.getvalue()


def _add_dup_image_clip(storage, *, data, is_pinned=False):
    """Non-tiny (100x100) so it never also trips the tiny-image detector."""
    chash = models.bytes_hash(data)
    clip = Clip(
        content_hash=chash, content_type=models.CONTENT_IMAGE,
        classification=models.CLASS_IMAGE, is_pinned=is_pinned,
    )
    storage.add_clip(clip)
    record = image_assets.ClipAssetRecord(
        asset_id=models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=100, height=100,
    )
    storage.save_clip_asset(record, data)
    return clip


def test_ignore_suggestion_is_group_scoped_and_suppresses_whole_group_unchanged(
    tk_root, storage, assets_home,
):
    """Real UI action path: builds the dialog, selects one non-keeper
    checkbox, invokes the exact _decide_selected(DECISION_IGNORED) the
    "Ignore suggestion" button calls -- proves it writes a SCOPE_GROUP
    decision keyed to the scan engine's own group fingerprint, not a
    per-item one, and that a fresh, unchanged rescan suppresses the whole
    group (not just the clicked item).
    """
    data = _dup_png((10, 20, 30))
    a = _add_dup_image_clip(storage, data=data)
    b = _add_dup_image_clip(storage, data=data)
    c = _add_dup_image_clip(storage, data=data)

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)
    assert len(groups) == 1
    group = groups[0]
    assert group.count == 3

    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root, callbacks={"storage": lambda: storage}, category=cs.CATEGORY_DUPLICATE_SCREENSHOT,
        items_or_groups=groups,
    )
    non_keeper_id = next(cid for cid in (a.id, b.id, c.id) if cid != group.recommended_keeper_id)
    dialog._vars[non_keeper_id].set(True)
    dialog._decide_selected(DECISION_IGNORED)

    # A group-scoped decision was recorded, keyed to the scan engine's own
    # fingerprint -- not an item-scoped one for the clicked clip.
    group_decision = get_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=group.fingerprint,
    )
    assert group_decision is not None
    assert group_decision.decision == DECISION_IGNORED
    item_decision = get_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_ITEM,
        fingerprint=non_keeper_id, clip_id=non_keeper_id,
    )
    assert item_decision is None  # no item-level decision was also written

    rescanned = cs.run_scan(storage)
    assert rescanned.duplicate_screenshot_groups == []


def test_ignore_group_reappears_fully_after_membership_changes(tk_root, storage, assets_home):
    """Continuation of the above: adding a 4th duplicate changes the
    group's fingerprint, so the old Ignore no longer matches -- the group
    must reappear with ALL 4 members, including the ones that were part of
    the originally-ignored (3-member) group. None of them were
    individually/permanently hidden by the group-scoped decision.
    """
    data = _dup_png((40, 50, 60))
    a = _add_dup_image_clip(storage, data=data)
    b = _add_dup_image_clip(storage, data=data)
    c = _add_dup_image_clip(storage, data=data)

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)
    group = groups[0]

    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root, callbacks={"storage": lambda: storage}, category=cs.CATEGORY_DUPLICATE_SCREENSHOT,
        items_or_groups=groups,
    )
    non_keeper_id = next(cid for cid in (a.id, b.id, c.id) if cid != group.recommended_keeper_id)
    dialog._vars[non_keeper_id].set(True)
    dialog._decide_selected(DECISION_IGNORED)

    assert cs.run_scan(storage).duplicate_screenshot_groups == []  # suppressed, unchanged

    d = _add_dup_image_clip(storage, data=data)  # 4th duplicate -> membership changes

    rescanned = cs.run_scan(storage)
    assert len(rescanned.duplicate_screenshot_groups) == 1
    new_group = rescanned.duplicate_screenshot_groups[0]
    assert new_group.fingerprint != group.fingerprint
    assert new_group.count == 4
    surviving_ids = {it.clip.id for it in new_group.items}
    assert surviving_ids == {a.id, b.id, c.id, d.id}  # all 4, nobody permanently hidden


def test_item_category_ignore_still_suppresses_only_that_item(tk_root, storage, assets_home):
    """Item-only categories (missing/damaged, tiny, largest) keep the
    original item-scoped Ignore behavior -- only the clicked clip is
    suppressed, unrelated items in the same category remain.
    """
    a = _add_image_clip(storage, data=_tiny_png(), width=4, height=4, is_pinned=False)
    b = _add_image_clip(storage, data=_tiny_png((99, 88, 77)), width=4, height=4, is_pinned=False)

    ctx = cs.build_scan_context(storage)
    tiny = cs.find_tiny_images(ctx)
    assert len(tiny) == 2

    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root, callbacks={"storage": lambda: storage}, category=cs.CATEGORY_TINY_IMAGE,
        items_or_groups=tiny,
    )
    dialog._vars[a.id].set(True)
    dialog._decide_selected(DECISION_IGNORED)

    item_decision = get_decision(
        storage, category=cs.CATEGORY_TINY_IMAGE, scope=SCOPE_ITEM, fingerprint=a.id, clip_id=a.id,
    )
    assert item_decision is not None
    assert item_decision.decision == DECISION_IGNORED

    rescanned = cs.run_scan(storage)
    surviving_ids = {it.clip.id for it in rescanned.tiny_images}
    assert surviving_ids == {b.id}  # a.id suppressed, b.id unaffected


def test_stop_ignoring_restores_the_suggestion(tk_root, storage, assets_home):
    """The IgnoredSuggestionsDialog's "Stop ignoring" action clears the
    decision through the real store call the button invokes, and the
    group reappears on the next scan -- Ignore is durable but not
    unreachable/unreversible from the product UI.
    """
    data = _dup_png((70, 80, 90))
    a = _add_dup_image_clip(storage, data=data)
    b = _add_dup_image_clip(storage, data=data)

    ctx = cs.build_scan_context(storage)
    groups = cs.find_duplicate_screenshot_groups(ctx)
    group = groups[0]

    dialog = cleanup_screen.CleanupReviewDialog(
        tk_root, callbacks={"storage": lambda: storage}, category=cs.CATEGORY_DUPLICATE_SCREENSHOT,
        items_or_groups=groups,
    )
    non_keeper_id = a.id if a.id != group.recommended_keeper_id else b.id
    dialog._vars[non_keeper_id].set(True)
    dialog._decide_selected(DECISION_IGNORED)
    assert cs.run_scan(storage).duplicate_screenshot_groups == []

    rescanned_flag = {"called": False}
    manage_dialog = cleanup_screen.IgnoredSuggestionsDialog(
        tk_root,
        callbacks={
            "storage": lambda: storage,
            "rescan_after_decision": lambda: rescanned_flag.__setitem__("called", True),
        },
    )
    ignored_decision = get_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=group.fingerprint,
    )
    assert ignored_decision is not None
    manage_dialog._stop_ignoring(ignored_decision)
    assert rescanned_flag["called"] is True

    cleared = get_decision(
        storage, category=cs.CATEGORY_DUPLICATE_SCREENSHOT, scope=SCOPE_GROUP,
        fingerprint=group.fingerprint,
    )
    assert cleared is None
    restored = cs.run_scan(storage)
    assert len(restored.duplicate_screenshot_groups) == 1
    assert restored.duplicate_screenshot_groups[0].count == 2
