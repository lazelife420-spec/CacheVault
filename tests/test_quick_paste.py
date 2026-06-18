from __future__ import annotations

import inspect
from types import SimpleNamespace

from cache_vault.core import models
from cache_vault.ui.quick_paste import primary_action_label


def _clip(**overrides):
    data = {
        "content_type": models.CONTENT_TEXT,
        "classification": models.CLASS_PLAIN,
        "is_sensitive": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_quick_paste_primary_labels_are_type_aware():
    assert primary_action_label(_clip()) == "Paste Text"
    assert primary_action_label(_clip(classification=models.CLASS_LINK)) == "Paste Link"
    assert primary_action_label(_clip(classification=models.CLASS_PATH)) == "Copy Path"
    assert primary_action_label(_clip(content_type=models.CONTENT_IMAGE)) == "Copy Image"


def test_quick_paste_keyboard_bindings_are_wired():
    from cache_vault.ui.quick_paste import QuickPaste

    source = inspect.getsource(QuickPaste.__init__)

    assert "placeholder_text=\"Search clips...\"" in source
    assert "_query_var.trace_add" in source
    assert "<Up>" in source
    assert "<Down>" in source
    assert "<Home>" in source
    assert "<End>" in source
    assert "<Return>" in source
    assert "<Control-Return>" in source
    assert "<Shift-Return>" in source
    assert "<Escape>" in source


def test_quick_paste_search_filter_uses_metadata_not_body_access():
    from cache_vault.ui import quick_paste

    clip = _clip(
        title="",
        preview="Quarterly report screenshot",
        safe_name="Work",
        source_app="SnippingTool.exe",
        date_used="",
        created_at="2026-01-01",
    )

    assert quick_paste._matches_query(clip, "report")
    assert quick_paste._matches_query(clip, "work")
    assert quick_paste._matches_query(clip, "snipping")
    assert not quick_paste._matches_query(clip, "missing")


def test_quick_paste_image_action_does_not_fake_paste():
    from cache_vault.ui.shell import CacheVaultApp

    image_source = inspect.getsource(CacheVaultApp._quick_paste_image_action)
    finish_source = inspect.getsource(CacheVaultApp._finish_paste)

    assert "write_clipboard_png" in image_source
    assert "deliver_ctrl_v" not in image_source
    assert any(s in image_source for s in ("Copied image to clipboard", "Image copied to clipboard"))
    assert "ACTION_OPEN" in image_source
    assert "ACTION_SAVE_AS" in image_source
    assert "Pasted ✓" not in finish_source
    assert "Paste attempted" in finish_source


def test_quick_paste_open_image_uses_asset_file_helper():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._open_image_asset)

    assert "pathutil.open_file" in source
    assert "quick_paste_opened_asset" in source
    assert "Opened image." in source


def test_quick_paste_path_action_copies_path_only():
    from cache_vault.ui.shell import CacheVaultApp

    do_paste_source = inspect.getsource(CacheVaultApp._do_paste)
    path_source = inspect.getsource(CacheVaultApp._quick_paste_copy_path)

    assert "_quick_paste_copy_path(clip)" in do_paste_source
    assert "Copied path to clipboard" in path_source
    assert "deliver_ctrl_v" not in path_source


def test_quick_paste_copy_only_does_not_deliver_paste():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._do_paste)
    copy_block = source[source.index("if action == ACTION_COPY_ONLY:"):source.index("else:")]

    assert "quick_paste_copy_only" in copy_block
    assert "deliver_ctrl_v" not in copy_block
    assert "Copied to clipboard" in copy_block


def test_quick_paste_locked_path_records_block_and_shows_no_list():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._open_quick_paste)
    locked_block = source[source.index("if self._locked():"):source.index("try:")]

    assert "quick_paste_blocked_locked" in locked_block
    assert "_guard_unlocked" in locked_block
    assert "QuickPaste(" not in locked_block


def test_quick_paste_receipts_are_metadata_only():
    from cache_vault.ui.shell import CacheVaultApp

    source = inspect.getsource(CacheVaultApp._quick_paste_receipt_details)

    assert "safe_id" in source
    assert "safe_name" in source
    assert "target_title" in source
    assert "action_type" in source
    assert "clip.content or" not in source
    assert "clip.content," not in source
    assert "clip.content}" not in source
    assert ".preview" not in source


def test_quick_paste_copy_avoids_forbidden_claims():
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.quick_paste import QuickPaste

    source = "\n".join(
        [
            inspect.getsource(QuickPaste),
            inspect.getsource(CacheVaultApp._do_paste),
            inspect.getsource(CacheVaultApp._quick_paste_image_action),
            inspect.getsource(CacheVaultApp._open_image_asset),
            inspect.getsource(CacheVaultApp._finish_paste),
        ],
    ).lower()

    for claim in ("cloud sync", "encrypted safes", "final release", "bank-grade", "military-grade"):
        assert claim not in source
