"""DEF-007 qualification test suite for VaultStorage hard_delete transaction ordering and failure states."""

from pathlib import Path
import pytest
from unittest.mock import patch
from cache_vault.core.storage import VaultStorage
from cache_vault.core.models import Clip
from cache_vault.core import image_assets
from cache_vault.core.image_assets import ClipAssetRecord


def test_def007_normal_hard_delete(tmp_path: Path) -> None:
    db_file = tmp_path / "test_hd.db"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(image_assets, "assets_dir", return_value=assets_dir):
        storage = VaultStorage(db_file)
        storage.add_clip(Clip(id="clip1", content="Image Clip"))

        rec = ClipAssetRecord(
            asset_id="asset1",
            clip_id="clip1",
            mime_type="image/png",
            file_ext=".png",
            size_bytes=24,
            sha256="dummy_hash",
            created_at="2026-01-01T00:00:00Z",
            original_name="test.png",
            storage_name="img1.png",
            width=100,
            height=100,
        )
        storage.save_clip_asset(rec, b"\x89PNG\r\n\x1a\nfake_image_bytes")

        assert storage.has_clip_asset("clip1")
        asset_file = assets_dir / "img1.png"
        assert asset_file.is_file()

        # Execute hard_delete
        storage.hard_delete("clip1")

        assert not storage.has_clip_asset("clip1")
        assert storage.get_clip("clip1") is None
        assert not asset_file.exists()


def test_def007_db_commit_failure_preserves_disk_asset(tmp_path: Path) -> None:
    db_file = tmp_path / "test_hd_fail.db"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(image_assets, "assets_dir", return_value=assets_dir):
        storage = VaultStorage(db_file)
        storage.add_clip(Clip(id="clip2", content="Image Clip 2"))

        rec = ClipAssetRecord(
            asset_id="asset2",
            clip_id="clip2",
            mime_type="image/png",
            file_ext=".png",
            size_bytes=24,
            sha256="dummy_hash2",
            created_at="2026-01-01T00:00:00Z",
            original_name="test2.png",
            storage_name="img2.png",
            width=100,
            height=100,
        )
        storage.save_clip_asset(rec, b"\x89PNG\r\n\x1a\nfake_bytes_2")

        asset_file = assets_dir / "img2.png"
        assert asset_file.is_file()

        # Proxy connection to inject execution failure on DELETE FROM clips
        real_conn = storage.conn

        class FailingConnProxy:
            def execute(self, sql, *args, **kwargs):
                if "DELETE FROM clips" in sql:
                    raise RuntimeError("DB Execution Failure!")
                return real_conn.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(real_conn, name)

        storage.conn = FailingConnProxy()

        with pytest.raises(RuntimeError, match="DB Execution Failure!"):
            storage.hard_delete("clip2")

        # Restore real conn to check state
        storage.conn = real_conn

        # Invariant: DB record and disk file MUST STILL EXIST intact
        assert storage.get_clip("clip2") is not None
        assert storage.has_clip_asset("clip2")
        assert asset_file.is_file()


def test_def007_fs_unlink_failure_leaves_no_broken_db_reference(tmp_path: Path) -> None:
    db_file = tmp_path / "test_hd_fs_fail.db"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(image_assets, "assets_dir", return_value=assets_dir):
        storage = VaultStorage(db_file)
        storage.add_clip(Clip(id="clip3", content="Image Clip 3"))

        rec = ClipAssetRecord(
            asset_id="asset3",
            clip_id="clip3",
            mime_type="image/png",
            file_ext=".png",
            size_bytes=24,
            sha256="dummy_hash3",
            created_at="2026-01-01T00:00:00Z",
            original_name="test3.png",
            storage_name="img3.png",
            width=100,
            height=100,
        )
        storage.save_clip_asset(rec, b"\x89PNG\r\n\x1a\nfake_bytes_3")

        # Mock image_assets.delete_asset_file to fail
        with patch.object(image_assets, "delete_asset_file", side_effect=OSError("File Locked")):
            storage.hard_delete("clip3")  # DB deletes succeed first!

        # Invariant: DB records are deleted (no live DB record pointing to missing/orphaned asset)
        assert storage.get_clip("clip3") is None
        assert not storage.has_clip_asset("clip3")


def test_def007_nonexistent_and_idempotent_delete(tmp_path: Path) -> None:
    db_file = tmp_path / "test_hd_idempotent.db"
    storage = VaultStorage(db_file)

    # Deleting non-existent clip should succeed gracefully
    storage.hard_delete("nonexistent_id")

    # Add and delete a clip twice
    storage.add_clip(Clip(id="clip4", content="Text Clip"))
    storage.hard_delete("clip4")
    storage.hard_delete("clip4")  # Idempotent second call
    assert storage.get_clip("clip4") is None
