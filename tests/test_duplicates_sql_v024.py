"""DEF-009 qualification test suite for SQL duplicate aggregation semantic equivalence and negative control."""

from pathlib import Path
import pytest
from cache_vault.core.storage import VaultStorage
from cache_vault.core.models import Clip, CONTENT_TEXT, CONTENT_IMAGE
from cache_vault.core import duplicates


def test_def009_sql_duplicate_semantic_equivalence(tmp_path: Path) -> None:
    db_file = tmp_path / "test_dup.db"
    storage = VaultStorage(db_file)

    # 1. Group 1: 3 identical text clips (hashA)
    storage.add_clip(Clip(id="c1", content="Text A", content_hash="hashA", content_type=CONTENT_TEXT))
    storage.add_clip(Clip(id="c2", content="Text A", content_hash="hashA", content_type=CONTENT_TEXT))
    storage.add_clip(Clip(id="c3", content="Text A", content_hash="hashA", content_type=CONTENT_TEXT))

    # 2. Group 2: 2 identical image clips (hashB)
    storage.add_clip(Clip(id="c4", content="Img B", content_hash="hashB", content_type=CONTENT_IMAGE))
    storage.add_clip(Clip(id="c5", content="Img B", content_hash="hashB", content_type=CONTENT_IMAGE))

    # 3. Singletons (hashC, hashD)
    storage.add_clip(Clip(id="c6", content="Text C", content_hash="hashC", content_type=CONTENT_TEXT))
    storage.add_clip(Clip(id="c7", content="Img D", content_hash="hashD", content_type=CONTENT_IMAGE))

    # 4. Null / empty hashes
    storage.add_clip(Clip(id="c8", content="No Hash 1", content_hash="", content_type=CONTENT_TEXT))
    storage.add_clip(Clip(id="c9", content="No Hash 2", content_hash=None, content_type=CONTENT_TEXT))

    # 5. Soft-deleted clip (hashA duplicate, but soft-deleted)
    storage.add_clip(Clip(id="c10", content="Text A", content_hash="hashA", content_type=CONTENT_TEXT))
    storage.soft_delete("c10")

    # Baseline comparison
    legacy_python_count = len(duplicates.find_exact_duplicate_groups(storage))
    sql_count = duplicates.count_duplicate_groups(storage)
    assert legacy_python_count == 2
    assert sql_count == legacy_python_count


def test_def009_negative_control_detects_flawed_sql(tmp_path: Path) -> None:
    """Mandatory Negative Control: Verify that a flawed SQL query fails the equivalence check."""
    db_file = tmp_path / "test_neg.db"
    storage = VaultStorage(db_file)

    storage.add_clip(Clip(id="c1", content="Text A", content_hash="hashA"))
    storage.add_clip(Clip(id="c2", content="Text A", content_hash="hashA"))
    storage.add_clip(Clip(id="c3", content="Text B", content_hash="hashB"))
    storage.add_clip(Clip(id="c4", content="Text B", content_hash="hashB"))
    storage.soft_delete("c4")  # c4 soft-deleted -> Group B only has 1 live clip left!

    legacy_count = len(duplicates.find_exact_duplicate_groups(storage))
    assert legacy_count == 1  # Only hashA is a duplicate group

    # Deliberately flawed SQL query (omits deleted_at IS NULL)
    flawed_sql = storage.conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT content_hash FROM clips "
        "  WHERE content_hash IS NOT NULL AND content_hash != '' "
        "  GROUP BY content_hash HAVING COUNT(*) > 1"
        ")"
    ).fetchone()[0]

    # Flawed SQL includes soft-deleted c4 -> returns 2 instead of 1
    assert flawed_sql == 2
    assert flawed_sql != legacy_count  # Negative control successfully caught the discrepancy!
