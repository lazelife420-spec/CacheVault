from cache_vault.core import models
from cache_vault.core.contextmenu import clip_menu_items
from cache_vault.core.models import Clip


def _clip(content, **kw):
    return Clip(content=content, preview=content, **kw)


def _keys(items):
    return [i.key for i in items]


def test_text_clip_has_no_file_actions():
    items = clip_menu_items(_clip("just some text", classification=models.CLASS_PLAIN))
    keys = _keys(items)
    assert keys == ["copy_again", "toggle_favorite", "move_collection",
                    "export", "remove"]
    assert "open" not in keys and "reveal" not in keys


def test_removed_clip_menu_offers_restore():
    items = clip_menu_items(_clip("gone", deleted_at="2026-01-01T00:00:00+00:00"))
    keys = _keys(items)
    assert keys == ["copy_again", "restore", "permanently_remove"]


def test_favorite_label_toggles():
    normal = clip_menu_items(_clip("x"))
    assert normal[1].label == "Add to Favorites"
    fav = clip_menu_items(_clip("x", is_pinned=True))
    assert fav[1].label == "Remove from Favorites"


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
