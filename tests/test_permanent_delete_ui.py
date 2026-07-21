"""Commit 5: Tk-level integration tests for permanent deletion from
Recently Removed -- sidebar dispatch, the bulk item/context menu,
keyboard-Delete safety, and the two confirmation dialogs' click-only /
typed-phrase safeguards.

Headless storage/vault-layer proofs (staging, rollback, filesystem
boundary, receipts) live in tests/test_permanent_delete.py; this file
only covers behavior that genuinely requires a live Tk window.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from cache_vault.core import storage as S
from cache_vault.core.models import Clip
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui import dialogs, sidebar_context
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import _tcl_unavailable, probe_tk_ui, wait_for_refresh

OK, REASON = probe_tk_ui()


def _isolated_settings() -> Settings:
    return Settings(capture_paused=True)


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _vault_with_clips(tmp_path, n, prefix="clip"):
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=_isolated_settings())
    for i in range(n):
        vault.capture(f"{prefix} {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app):
    app._do_refresh_sync()
    wait_for_refresh(app)


def _auto_confirm(dialog_cls_path):
    """Patch a dialog class so construction immediately fires its
    on_confirm callback -- simulates a deliberate user click without
    needing a real interactive Tk event loop."""
    def _factory(*args, **kwargs):
        kwargs["on_confirm"]()
        return mock.MagicMock()
    return mock.patch(dialog_cls_path, side_effect=_factory)


# --- Sidebar dispatch: exact ids, execution-time refresh, staleness safety ----


@pytest.mark.skipif(not OK, reason=REASON)
def test_sidebar_permanently_delete_selected_deletes_exact_unique_ids(tmp_path):
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.soft_delete(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)
        app._selected_clip_ids = [clips[0].id, clips[1].id, clips[0].id]  # dup on purpose

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        with _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog"):
            app._dispatch_sidebar_command("permanently_delete_selected", ctx)
        _settle(app)

        assert vault.storage.get_clip(clips[0].id) is None
        assert vault.storage.get_clip(clips[1].id) is None
        assert vault.storage.get_clip(clips[2].id) is not None  # untouched
        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 1  # still soft-deleted, never targeted
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_sidebar_permanently_delete_all_refreshes_membership_at_execution_time(tmp_path):
    vault = _vault_with_clips(tmp_path, 2)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.soft_delete(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )

        # A third clip is removed after the menu context was captured --
        # Delete All must not trust the count frozen in ctx.
        extra = vault.capture("captured after menu opened", force=True)
        vault.storage.soft_delete(extra.id)

        with _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteAllDialog"):
            app._dispatch_sidebar_command("permanently_delete_all", ctx)
        _settle(app)

        assert vault.count_clips(S.FILTER_RECENTLY_REMOVED) == 0
        assert vault.storage.get_clip(extra.id) is None  # included, not missed
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_sidebar_permanently_delete_selected_restored_item_is_skipped(tmp_path):
    vault = _vault_with_clips(tmp_path, 2)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.soft_delete(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)
        app._selected_clip_ids = [clips[0].id, clips[1].id]

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )

        # clips[0] is restored by "something else" between menu-open and
        # the confirmed delete -- it must survive, not be deleted.
        vault.storage.restore(clips[0].id)

        with _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog"):
            app._dispatch_sidebar_command("permanently_delete_selected", ctx)
        _settle(app)

        restored = vault.storage.get_clip(clips[0].id)
        assert restored is not None
        assert restored.deleted_at is None
        assert vault.storage.get_clip(clips[1].id) is None
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_sidebar_permanently_delete_selected_aborts_on_stale_context(tmp_path):
    """A captured ctx for a since-navigated-away row must abort with a
    toast, never silently act -- same contract as every other selection-
    dependent sidebar command (see _dispatch_sidebar_command's allowlist:
    CMD_PERMANENTLY_DELETE_SELECTED is deliberately not exempted).
    """
    vault = _vault_with_clips(tmp_path, 2)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.soft_delete(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)
        app._selected_clip_ids = [clips[0].id]

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )

        # Navigate away before the command actually dispatches.
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)

        with mock.patch.object(app, "_show_toast") as toast, \
             _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog") as dlg:
            app._dispatch_sidebar_command("permanently_delete_selected", ctx)

        dlg.assert_not_called()
        toast.assert_called_once()
        assert vault.storage.get_clip(clips[0].id) is not None  # untouched
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_matching_selection_from_all_clips_cannot_be_reused_for_recently_removed(tmp_path):
    """A matching-wide selection activated against All Clips must never
    be reinterpreted as a Recently Removed selection just because the
    user then right-clicks the Recently Removed row -- ctx's own
    matching_descriptor only ever binds to the row it was built for
    (sidebar_menu_context._matching_belongs_to_target), so this proves
    the wiring holds end-to-end for the new commands too.
    """
    vault = _vault_with_clips(tmp_path, 3)
    clips = vault.storage.list_clips(None)
    for c in clips:
        vault.storage.soft_delete(c.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_ALL)
        _settle(app)
        app._selection_scope.activate_matching(S.FILTER_ALL, None)

        ctx = sidebar_context.build_sidebar_invocation_context_for_window(
            app, S.FILTER_RECENTLY_REMOVED,
        )
        assert ctx.matching_descriptor is None  # never inherited from the All Clips activation
    finally:
        app.destroy()


# --- Single-item path: corrective commit unified it into the same pipeline ----


@pytest.mark.skipif(not OK, reason=REASON)
def test_single_item_menu_invokes_staged_pipeline(tmp_path):
    """window._permanently_remove (wired from both the single-item
    context menu and the preview-pane danger-zone button) must go
    through the shared confirmation dialog and Vault.permanently_delete_many
    -- not a direct, unstaged hard_delete call.
    """
    vault = _vault_with_clips(tmp_path, 1)
    clip = vault.storage.list_clips(None)[0]
    vault.storage.soft_delete(clip.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        with mock.patch.object(vault.storage, "hard_delete") as legacy_hard_delete, \
             _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog"):
            app._permanently_remove(clip.id)
        _settle(app)

        legacy_hard_delete.assert_not_called()  # never the old unstaged path
        assert vault.storage.get_clip(clip.id) is None

        events = [
            e for e in vault.events.recent()
            if e.get("event_type") == "permanently_deleted_batch"
        ]
        assert len(events) == 1
        assert events[0]["details"]["confirmation_mode"] == "selected"
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_single_item_cancellation_changes_nothing(tmp_path):
    vault = _vault_with_clips(tmp_path, 1)
    clip = vault.storage.list_clips(None)[0]
    vault.storage.soft_delete(clip.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        def _factory(*args, **kwargs):
            return mock.MagicMock()  # constructs the dialog but never calls on_confirm

        with mock.patch("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog", side_effect=_factory):
            app._permanently_remove(clip.id)
        _settle(app)

        reloaded = vault.storage.get_clip(clip.id)
        assert reloaded is not None
        assert reloaded.deleted_at is not None  # still soft-deleted, nothing changed
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_single_item_managed_file_staged_and_purged_safely(tmp_path):
    from cache_vault.core import image_assets, models as core_models

    vault = _vault_with_clips(tmp_path, 1)
    clip = vault.storage.list_clips(None)[0]
    data = b"\x89PNG single-item-managed-asset-bytes"
    chash = core_models.bytes_hash(data)
    record = image_assets.ClipAssetRecord(
        asset_id=core_models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=1, height=1,
    )
    vault.storage.save_clip_asset(record, data)
    vault.storage.soft_delete(clip.id)
    asset_path = image_assets.assets_dir() / record.storage_name
    assert asset_path.is_file()

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        with _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog"):
            app._permanently_remove(clip.id)
        _settle(app)

        assert vault.storage.get_clip(clip.id) is None
        assert not asset_path.exists()
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_single_item_external_path_only_file_stays_byte_identical(tmp_path):
    from cache_vault.core.models import Clip as _Clip, CLASS_PATH, bytes_hash

    vault = _vault_with_clips(tmp_path, 0)
    external_dir = tmp_path / "outside_vault"
    external_dir.mkdir()
    external = external_dir / "doc.txt"
    external.write_text("must never change", encoding="utf-8")
    sha_before = bytes_hash(external.read_bytes())

    clip = _Clip(content=str(external), classification=CLASS_PATH)
    vault.storage.add_clip(clip)
    vault.storage.soft_delete(clip.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        with _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog"):
            app._permanently_remove(clip.id)
        _settle(app)

        assert vault.storage.get_clip(clip.id) is None
        assert external.is_file()
        assert bytes_hash(external.read_bytes()) == sha_before
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_single_item_partial_purge_reports_partial_not_success(tmp_path):
    from cache_vault.core import image_assets, models as core_models

    vault = _vault_with_clips(tmp_path, 1)
    clip = vault.storage.list_clips(None)[0]
    data = b"partial-purge-single-item-bytes"
    chash = core_models.bytes_hash(data)
    record = image_assets.ClipAssetRecord(
        asset_id=core_models.new_id(), clip_id=clip.id, mime_type="image/png", file_ext="png",
        size_bytes=len(data), sha256=chash, created_at=clip.created_at, original_name=None,
        storage_name=image_assets.make_storage_name(clip.id, "png"), width=1, height=1,
    )
    vault.storage.save_clip_asset(record, data)
    vault.storage.soft_delete(clip.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)

        with mock.patch("pathlib.Path.unlink", side_effect=OSError("simulated")), \
             _auto_confirm("cache_vault.ui.dialogs.PermanentDeleteSelectedDialog"):
            app._permanently_remove(clip.id)
        _settle(app)

        events = [
            e for e in vault.events.recent()
            if e.get("event_type") == "permanently_deleted_batch"
        ]
        assert len(events) == 1
        assert events[0]["details"]["result"] == "partial"

        from cache_vault.ui.receipt_ledger import _infer_result
        assert _infer_result(events[0]["details"]["action"], events[0]["details"]) == "Partial"
    finally:
        app.destroy()


# --- Keyboard Delete stays soft-remove only ------------------------------------


@pytest.mark.skipif(not OK, reason=REASON)
def test_keyboard_delete_in_recently_removed_never_permanently_deletes(tmp_path):
    vault = _vault_with_clips(tmp_path, 1)
    clip = vault.storage.list_clips(None)[0]
    vault.storage.soft_delete(clip.id)

    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
        _settle(app)
        app._selected_clip_ids = [clip.id]
        app._selected_clip_id = clip.id

        with mock.patch.object(app.vault, "permanently_delete_many") as perm_delete:
            app._keyboard_remove_selected()

        perm_delete.assert_not_called()
        # The clip is already soft-deleted; Delete on an already-removed
        # item must stay a harmless no-op-ish soft path, never escalate.
        reloaded = vault.storage.get_clip(clip.id)
        assert reloaded is not None
        assert reloaded.deleted_at is not None
    finally:
        app.destroy()


# --- Bulk item/context menu scoping --------------------------------------------


def test_bulk_item_menu_permanently_delete_only_when_all_targets_removed():
    from cache_vault.core.contextmenu import clip_menu_items

    active = Clip(content="active one")
    removed_a = Clip(content="removed a")
    removed_b = Clip(content="removed b")
    from cache_vault.core.models import now_iso
    removed_a.deleted_at = now_iso()
    removed_b.deleted_at = now_iso()

    all_removed_items = clip_menu_items([removed_a, removed_b])
    keys = {i.key for i in all_removed_items}
    assert "permanently_remove_selected" in keys

    mixed_items = clip_menu_items([active, removed_a])
    mixed_keys = {i.key for i in mixed_items}
    assert "permanently_remove_selected" not in mixed_keys

    all_active_items = clip_menu_items([active, Clip(content="also active")])
    active_keys = {i.key for i in all_active_items}
    assert "permanently_remove_selected" not in active_keys


# --- Dialog structural safety: click-only, typed-phrase gating ----------------


def _dialog_class_source(class_name: str) -> str:
    src = (Path(__file__).parents[1] / "cache_vault" / "ui" / "dialogs.py").read_text(encoding="utf-8")
    start = src.index(f"class {class_name}")
    # Up to the next top-level "class " after this one (or EOF).
    next_class = src.find("\nclass ", start + 1)
    return src[start:] if next_class == -1 else src[start:next_class]


def test_permanent_delete_dialogs_never_bind_return_or_space():
    for cls in ("PermanentDeleteSelectedDialog", "PermanentDeleteAllDialog"):
        body = _dialog_class_source(cls)
        assert "<Return>" not in body
        assert "<space>" not in body.lower()
        assert "command=self._cancel" in body or "command=self._confirm" in body or "command=self._finish" in body \
            or "command=self._render_stage2" in body


def test_permanent_delete_all_dialog_confirm_button_starts_disabled():
    body = _dialog_class_source("PermanentDeleteAllDialog")
    assert 'state="disabled"' in body
    assert "CONFIRM_PHRASE" in body


@pytest.mark.skipif(not OK, reason=REASON)
def test_permanent_delete_all_dialog_requires_exact_phrase_before_enabling(tmp_path):
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    try:
        confirmed = {"called": False}
        dlg = dialogs.PermanentDeleteAllDialog(
            root, total_count=5, eligible_count=5, skipped_count=0,
            asset_count=0, bytes_scheduled=0,
            on_confirm=lambda: confirmed.__setitem__("called", True),
        )
        dlg._render_stage2()
        assert dlg._confirm_btn.cget("state") == "disabled"

        dlg._finish()  # clicking while disabled must not confirm
        assert confirmed["called"] is False

        # Typing the exact phrase enables the button; the belt-and-
        # suspenders re-check in _finish then allows it through.
        dlg._confirm_entry_var.set(dialogs.PermanentDeleteAllDialog.CONFIRM_PHRASE)
        dlg.update_idletasks()
        assert str(dlg._confirm_btn.cget("state")) == "normal"

        dlg._finish()
        assert confirmed["called"] is True
    finally:
        try:
            dlg.destroy()
        except Exception:
            pass
        root.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_permanent_delete_selected_dialog_cancel_does_not_confirm(tmp_path):
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    try:
        confirmed = {"called": False}
        dlg = dialogs.PermanentDeleteSelectedDialog(
            root, eligible_count=2, skipped_count=0, asset_count=0, bytes_scheduled=0,
            on_confirm=lambda: confirmed.__setitem__("called", True),
        )
        dlg._cancel()
        assert confirmed["called"] is False
    finally:
        root.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_permanent_delete_selected_dialog_escape_cancels_safely(tmp_path):
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    try:
        confirmed = {"called": False}
        dlg = dialogs.PermanentDeleteSelectedDialog(
            root, eligible_count=1, skipped_count=0, asset_count=0, bytes_scheduled=0,
            on_confirm=lambda: confirmed.__setitem__("called", True),
        )
        dlg.event_generate("<Escape>")
        dlg.update_idletasks()
        assert confirmed["called"] is False
    finally:
        try:
            dlg.destroy()
        except Exception:
            pass
        root.destroy()
