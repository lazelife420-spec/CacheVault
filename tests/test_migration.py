import sqlite3

from cache_vault.core.storage import VaultStorage, FILTER_ALL


def test_old_db_missing_columns_loads_after_migration(tmp_path):
    db = tmp_path / "old.db"
    # Simulate a pre-favorites database: a clips table with only the original
    # core columns and none of the later additions (is_pinned, tags, etc.).
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE clips (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            content_hash TEXT,
            content TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO clips (id, created_at, updated_at, content_hash, content) "
        "VALUES (?,?,?,?,?)",
        ("old1", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
         "hash", "legacy clip text"),
    )
    conn.commit()
    conn.close()

    # Opening through VaultStorage must migrate in place (add missing columns
    # with safe defaults) without wiping the existing row.
    storage = VaultStorage(db)
    clip = storage.get_clip("old1")
    assert clip is not None
    assert clip.content == "legacy clip text"
    assert clip.is_pinned is False        # new column defaulted safely
    assert clip.is_sensitive is False
    # And it still shows up in a normal listing.
    assert "old1" in {c.id for c in storage.list_clips(FILTER_ALL)}
    storage.close()


def test_existing_database_is_not_reset(tmp_path):
    db = tmp_path / "keep.db"
    s1 = VaultStorage(db)
    from cache_vault.core.models import Clip, content_hash
    s1.add_clip(Clip(content="row one", content_hash=content_hash("row one")))
    s1.close()

    # Re-opening (which runs migration) must preserve existing rows.
    s2 = VaultStorage(db)
    assert len(s2.list_clips(FILTER_ALL)) == 1
    s2.close()
