"""Home dashboard, grid, filters, duplicates, and metadata tests."""

from __future__ import annotations

from cache_vault.core import clip_metadata, models, search
from cache_vault.core.duplicates import (
    DuplicateGroup,
    apply_duplicate_review,
    find_exact_duplicate_groups,
    find_possible_duplicate_groups,
)
from cache_vault.core.models import Clip
from cache_vault.core.storage import (
    FILTER_DUPLICATES,
    FILTER_HOME,
    FILTER_OLDER,
    FILTER_SCREENSHOTS,
    VaultStorage,
)
from cache_vault.core.vault import Vault
from cache_vault.ui import filters as filters_ui
from cache_vault.ui.home_dashboard import HomeDashboard


def _clip(content: str, **kw) -> Clip:
    title = kw.pop("title", clip_metadata.clip_title(content, content))
    use_count = kw.pop("use_count", 1)
    c = Clip(
        content=content,
        content_hash=models.content_hash(content),
        preview=models.make_preview(content),
        normalized_hash=clip_metadata.normalized_hash(content),
        title=title,
        size_bytes=clip_metadata.size_bytes_for(content),
        use_count=use_count,
        **kw,
    )
    c.last_used_at = c.created_at
    return c


def test_home_filter_constant_exists():
    assert FILTER_HOME == "home"
    assert any(k == FILTER_HOME for _h, items in filters_ui.FILTER_GROUPS for k, _l in items)


def test_sidebar_group_headings():
    headings = [h for h, _ in filters_ui.FILTER_GROUPS if h]
    assert "Saved Clips" in headings
    assert "Types" in headings
    assert "Review" in headings
    assert "Time" in headings


def test_dashboard_summary_real_counts(storage):
    storage.add_clip(_clip("one"))
    storage.add_clip(_clip("two"))
    v = Vault(storage=storage)
    summary = v.dashboard_summary()
    assert summary["all"] == 2
    assert summary["receipts"] >= 0


def test_date_added_filter_today(storage):
    c = storage.add_clip(_clip("today clip"))
    q = search.SearchQuery(date_added_preset="today")
    ids = {x.id for x in storage.list_clips(q)}
    assert c.id in ids


def test_date_used_sort(storage):
    a = storage.add_clip(_clip("aaa"))
    b = storage.add_clip(_clip("bbb"))
    storage.touch_clip(a.id)
    q = search.SearchQuery(sort=models.SORT_RECENTLY_USED)
    listed = storage.list_clips(q)
    assert listed[0].id == a.id
    assert listed[1].id == b.id


def test_most_used_sort(storage):
    a = storage.add_clip(_clip("aaa"))
    b = storage.add_clip(_clip("bbb"))
    storage.touch_clip(a.id)
    storage.touch_clip(a.id)
    q = search.SearchQuery(sort=models.SORT_MOST_USED)
    assert storage.list_clips(q)[0].id == a.id


def test_source_app_filter(storage):
    storage.add_clip(_clip("x", source_app="Cursor"))
    storage.add_clip(_clip("y", source_app="Edge"))
    q = search.SearchQuery(source="cursor")
    assert len(storage.list_clips(q)) == 1


def test_source_url_search(storage):
    storage.add_clip(_clip("https://github.com/foo", classification=models.CLASS_LINK,
                           source_url="https://github.com/foo"))
    q = search.SearchQuery(text="github")
    assert len(storage.list_clips(q)) == 1


def test_missing_metadata_safe(storage):
    storage.add_clip(_clip("plain", source_app=None, source_window=None, title=None))
    assert storage.list_clips()  # no crash


def test_old_clip_migration_columns(storage):
    storage.add_clip(_clip("legacy"))
    row = storage.conn.execute("SELECT * FROM clips LIMIT 1").fetchone()
    assert "last_used_at" in row.keys()
    assert "use_count" in row.keys()


def test_exact_duplicate_groups(storage):
    a = storage.add_clip(_clip("dup me"))
    b = storage.add_clip(_clip("dup me"))
    groups = find_exact_duplicate_groups(storage)
    assert len(groups) == 1
    assert {c.id for c in groups[0].clips} == {a.id, b.id}


def test_possible_duplicate_groups(storage):
    storage.add_clip(_clip("Hello"))
    storage.add_clip(_clip("  hello  "))
    groups = find_possible_duplicate_groups(storage)
    assert any(g.kind == "possible" for g in groups)


def test_duplicate_review_moves_extras_not_permanent(storage):
    a = storage.add_clip(_clip("same"))
    b = storage.add_clip(_clip("same"))
    fav = storage.add_clip(_clip("same", is_pinned=True))
    group = DuplicateGroup("h", "exact", a.content_hash, a.normalized_hash, [a, b, fav])
    v = Vault(storage=storage)
    kept = apply_duplicate_review(storage, v.events, group, "keep_favorite")
    assert kept == fav.id
    assert storage.get_clip(fav.id).deleted_at is None
    assert storage.get_clip(a.id).deleted_at is not None
    assert storage.get_clip(b.id).deleted_at is not None


def test_keep_newest_duplicate(storage):
    a = storage.add_clip(_clip("z"))
    b = storage.add_clip(_clip("z"))
    group = find_exact_duplicate_groups(storage)[0]
    v = Vault(storage=storage)
    kept = v.review_duplicates(group, "keep_newest")
    assert kept == b.id
    assert storage.get_clip(a.id).deleted_at is not None


def test_merge_usage_history(storage):
    a = storage.add_clip(_clip("z", use_count=2))
    b = storage.add_clip(_clip("z", use_count=3))
    group = find_exact_duplicate_groups(storage)[0]
    v = Vault(storage=storage)
    v.review_duplicates(group, "keep_newest", merge_history=True)
    kept = storage.get_clip(b.id)
    assert kept.use_count >= 5


def test_duplicate_review_writes_receipt(storage):
    storage.add_clip(_clip("r"))
    storage.add_clip(_clip("r"))
    group = find_exact_duplicate_groups(storage)[0]
    v = Vault(storage=storage)
    v.review_duplicates(group, "keep_all")
    types = {e["event_type"] for e in storage.conn.execute("SELECT event_type FROM events").fetchall()}
    assert models.EVENT_DUPLICATE_REVIEW in types


def test_sensitive_masked_preview():
    from cache_vault.core import sensitive
    c = _clip("password=secret123", is_sensitive=True)
    c.preview = sensitive.masked_preview(c.content)
    assert "secret" not in c.preview.lower()


def test_grid_metadata_fields():
    from cache_vault.ui.clip_grid import COLUMNS, DEFAULT_VISIBLE
    keys = {k for k, _l, _w in COLUMNS}
    for field in ("name", "type", "added", "used", "source", "favorite", "collection"):
        assert field in keys
    assert "added" in DEFAULT_VISIBLE
    assert "used" in DEFAULT_VISIBLE


def test_home_dashboard_module_importable():
    assert HomeDashboard is not None


def test_screenshot_filter_honest_count(storage):
    assert storage.counts()[FILTER_SCREENSHOTS] == 0


def test_older_filter(storage):
    storage.add_clip(_clip("oldish"))
    listed = storage.list_clips(FILTER_OLDER)
    assert isinstance(listed, list)


def test_clip_usage_events(storage):
    c = storage.add_clip(_clip("use"))
    storage.conn.execute(
        "INSERT INTO events (id, created_at, event_type, clip_id, details) "
        "VALUES (?,?,?,?,?)",
        (models.new_id(), models.now_iso(), models.EVENT_COPIED_AGAIN, c.id, "{}"),
    )
    storage.conn.commit()
    assert len(storage.events_for_clip(c.id)) == 1


def test_asset_storage_ready_false_without_table(tmp_path):
    db = tmp_path / "no_assets.db"
    s = VaultStorage(db)
    assert s.asset_storage_ready() is False
    s.close()
