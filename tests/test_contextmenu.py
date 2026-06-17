from cache_vault.core import models
import inspect

from cache_vault.core.contextmenu import clip_menu_items
from cache_vault.core.models import Clip


def _clip(content, **kw):
    return Clip(content=content, preview=content, **kw)


def _keys(items):
    return [i.key for i in items]


def _children(items, key):
    return next(i.children for i in items if i.key == key)


def test_text_clip_has_no_file_actions():
    items = clip_menu_items(_clip("just some text", classification=models.CLASS_PLAIN))
    keys = _keys(items)
    by_key = {i.key: i for i in items}
    assert keys == ["copy_again", "copy_clean", "toggle_favorite",
                    "move_safe", "create_editable_copy", "proof", "remove"]
    assert "open" not in keys and "reveal" not in keys
    assert by_key["create_editable_copy"].enabled is False


def test_removed_clip_menu_offers_restore():
    items = clip_menu_items(_clip("gone", deleted_at="2026-01-01T00:00:00+00:00"))
    keys = _keys(items)
    assert keys == ["copy_again", "restore", "permanently_remove"]


def test_favorite_label_toggles():
    normal = clip_menu_items(_clip("x"))
    assert normal[2].label == "Add to Favorites"
    fav = clip_menu_items(_clip("x", is_pinned=True))
    assert fav[2].label == "Remove from Favorites"


def test_path_clip_exposes_open_and_reveal(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x", encoding="utf-8")
    items = clip_menu_items(_clip(str(f), classification=models.CLASS_PATH))
    by_key = {i.key: i for i in items}
    assert "open" in by_key and "reveal" in by_key
    assert by_key["open"].enabled is True
    assert by_key["reveal"].enabled is True
    assert by_key["open"].label == "Open Editable Copy"


def test_missing_path_disables_open_but_reveal_if_parent_exists(tmp_path):
    missing = tmp_path / "gone.txt"  # parent (tmp_path) exists, file does not
    items = clip_menu_items(_clip(str(missing), classification=models.CLASS_PATH))
    by_key = {i.key: i for i in items}
    assert by_key["open"].enabled is False        # cannot open a missing file
    assert by_key["reveal"].enabled is True        # parent folder still there


def test_missing_path_and_parent_disables_both(tmp_path):
    missing = tmp_path / "nope" / "gone.txt"  # parent also missing
    items = clip_menu_items(_clip(str(missing), classification=models.CLASS_PATH))
    by_key = {i.key: i for i in items}
    assert by_key["open"].enabled is False
    assert by_key["reveal"].enabled is False


def test_url_clip_is_not_treated_as_path():
    items = clip_menu_items(_clip("https://example.com/file.txt",
                                  classification=models.CLASS_LINK))
    assert "open" not in _keys(items)  # never offer file actions for a URL


def test_copy_clean_submenu_marks_unavailable_actions_disabled():
    items = clip_menu_items(_clip("just text", classification=models.CLASS_PLAIN))
    clean = {i.key: i for i in _children(items, "copy_clean")}

    assert clean["copy_clean:copy_plain_text"].enabled is True
    assert clean["copy_clean:copy_markdown"].enabled is False
    assert clean["copy_clean:copy_address"].enabled is False


def test_link_clip_gets_link_actions_and_proof_submenu():
    items = clip_menu_items(_clip(
        "https://example.com",
        classification=models.CLASS_LINK,
        title="Example",
    ))
    keys = _keys(items)
    clean = {i.key: i for i in _children(items, "copy_clean")}
    proof = _children(items, "proof")

    assert "open_link" in keys
    assert clean["copy_clean:copy_title_link"].enabled is True
    assert clean["copy_clean:copy_markdown"].enabled is True
    assert _keys(proof) == ["export_proof_zip", "view_receipts"]


def test_mobile_inbox_clip_gets_mobile_receipt_and_source_summary():
    items = clip_menu_items(_clip(
        "sent from phone",
        capture_mode=models.CAPTURE_MOBILE_SHARE,
    ))
    clean = {i.key: i for i in _children(items, "copy_clean")}

    assert "view_mobile_receipt" in _keys(items)
    assert clean["copy_clean:copy_source_summary"].enabled is True


def test_image_clip_gets_image_and_asset_actions():
    items = clip_menu_items(_clip(
        "asset placeholder",
        content_type=models.CONTENT_IMAGE,
        classification=models.CLASS_IMAGE,
    ))

    assert items[0].label == "Copy Image"
    assert "open_asset_folder" in _keys(items)


def test_shell_context_menus_guard_locked_state():
    from cache_vault.ui.shell import CacheVaultApp

    src = inspect.getsource(CacheVaultApp._open_clip_menu)
    assert "_locked()" in src
    assert "_open_locked_menu" in src


def test_shell_has_receipt_context_menu():
    from cache_vault.ui.shell import CacheVaultApp

    src = inspect.getsource(CacheVaultApp)
    assert "_open_receipt_menu" in src
    assert "Copy Receipt Summary" in src
    assert "EVENT_RECEIPT_SUMMARY_COPIED" in src


def test_shell_has_safe_context_menu():
    from cache_vault.ui.shell import CacheVaultApp

    src = inspect.getsource(CacheVaultApp)
    assert "_open_safe_menu" in src
    assert "Set as Default Safe" in src
    assert "Copy Safe Summary" in src
    assert "Export Safe Proof Zip" in src
