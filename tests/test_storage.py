from cache_vault.core import models
from cache_vault.core import search
from cache_vault.core.models import Clip
from cache_vault.core.storage import (
    VaultStorage, FILTER_PINNED, FILTER_LINKS, FILTER_DUPLICATES, FILTER_ALL,
)


def _clip(content, **kw):
    return Clip(
        content=content,
        content_hash=models.content_hash(content),
        preview=models.make_preview(content),
        **kw,
    )


def test_add_and_get(storage):
    c = storage.add_clip(_clip("hello world"))
    fetched = storage.get_clip(c.id)
    assert fetched is not None
    assert fetched.content == "hello world"


def test_consecutive_duplicate_collapse(storage):
    a = storage.add_clip(_clip("same text"))
    b = storage.add_clip(_clip("same text"))
    # b is linked to a as a duplicate
    assert b.duplicate_of == a.id
    # duplicates filter surfaces clips sharing content_hash
    dups = storage.list_clips(FILTER_DUPLICATES)
    assert {d.id for d in dups} == {a.id, b.id}


def test_non_consecutive_not_duplicate(storage):
    a = storage.add_clip(_clip("alpha"))
    storage.add_clip(_clip("beta"))
    c = storage.add_clip(_clip("alpha"))  # same as a but not consecutive
    assert c.duplicate_of is None


def test_pin_unpin_and_ordering(storage):
    storage.add_clip(_clip("first"))
    second = storage.add_clip(_clip("second"))
    storage.set_pinned(second.id, True)
    pinned = storage.list_clips(FILTER_PINNED)
    assert [c.id for c in pinned] == [second.id]
    fav_first = storage.list_clips(search.SearchQuery(sort=models.SORT_FAVORITES_FIRST))
    assert fav_first[0].id == second.id
    storage.set_pinned(second.id, False)
    assert storage.list_clips(FILTER_PINNED) == []


def test_class_filter(storage):
    storage.add_clip(_clip("https://example.com", classification=models.CLASS_LINK))
    storage.add_clip(_clip("plain note", classification=models.CLASS_PLAIN))
    links = storage.list_clips(FILTER_LINKS)
    assert len(links) == 1
    assert links[0].classification == models.CLASS_LINK


def test_soft_delete_hides_clip(storage):
    c = storage.add_clip(_clip("delete me"))
    storage.soft_delete(c.id)
    assert storage.list_clips(FILTER_ALL) == []


def test_counts(storage):
    storage.add_clip(_clip("https://a.com", classification=models.CLASS_LINK))
    p = storage.add_clip(_clip("note"))
    storage.set_pinned(p.id, True)
    counts = storage.counts()
    assert counts[FILTER_ALL] == 2
    assert counts[FILTER_LINKS] == 1
    assert counts[FILTER_PINNED] == 1


def test_source_metadata_missing_does_not_crash(storage):
    # source_app / source_window are nullable; listing must not blow up.
    c = storage.add_clip(_clip("no source", source_app=None, source_window=None))
    fetched = storage.get_clip(c.id)
    assert fetched.source_app is None
    assert storage.list_clips(FILTER_ALL)  # no exception
