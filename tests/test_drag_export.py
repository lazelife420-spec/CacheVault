from __future__ import annotations

from types import SimpleNamespace

import pytest

from cache_vault.core import drag_export, models
from cache_vault.core.models import Clip
from cache_vault.core.contextmenu import clip_menu_items
from cache_vault.ui.shell import CacheVaultApp


def _clip(**overrides):
    data = {
        "id": "clip-1",
        "content": "plain text",
        "preview": "plain text",
        "classification": models.CLASS_PLAIN,
        "content_type": models.CONTENT_TEXT,
        "created_at": models.now_iso(),
        "updated_at": models.now_iso(),
        "last_used_at": models.now_iso(),
        "content_hash": models.content_hash("plain text"),
        "safe_id": "default",
        "safe_name": "Default Safe",
        "capture_mode": models.CAPTURE_AUTO,
    }
    data.update(overrides)
    return Clip(**data)


def test_prepare_drag_export_creates_temp_png_and_preserves_original(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    clip = vault.capture_image(_png_bytes(), width=8, height=6, source_app="SnippingTool.exe")
    rec = vault.storage.get_asset_record(clip.id)
    original = tmp_path / "CacheVault" / "assets" / rec.storage_name

    prepared = drag_export.prepare_drag_export(clip, vault.storage)

    assert prepared is not None
    assert prepared.drag_kind == "image"
    assert prepared.file_path != str(original)
    assert prepared.file_path.endswith(".png")
    assert prepared.display_name.startswith("CacheVault_screenshot_")
    assert original.is_file()
    assert (tmp_path / "CacheVault" / "drag_out").is_dir()


def test_prepare_drag_export_reuses_same_smart_filename(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    clip = vault.capture_image(_png_bytes(color="blue"), width=4, height=4, source_app="SnippingTool.exe")

    first = drag_export.prepare_drag_export(clip, vault.storage)
    second = drag_export.prepare_drag_export(clip, vault.storage)

    assert first is not None and second is not None
    assert first.file_path == second.file_path
    assert second.reused_existing is True


def test_prepare_drag_export_for_real_file_path(tmp_path):
    real = tmp_path / "report.txt"
    real.write_text("hello", encoding="utf-8")
    clip = _clip(content=str(real), preview=str(real), classification=models.CLASS_PATH)

    prepared = drag_export.prepare_drag_export(clip, storage=None)

    assert prepared is not None
    assert prepared.drag_kind == "file"
    assert prepared.file_path == str(real)
    assert prepared.source == "original_file"


def test_missing_file_path_returns_none_and_no_fake_drag(tmp_path):
    missing = tmp_path / "gone.txt"
    clip = _clip(content=str(missing), preview=str(missing), classification=models.CLASS_PATH)

    prepared = drag_export.prepare_drag_export(clip, storage=None)

    assert prepared is None
    assert drag_export.drag_fallback_reason(clip) == "File not found."


def test_text_and_link_items_do_not_expose_fake_file_drag():
    text_items = clip_menu_items(_clip())
    link_items = clip_menu_items(_clip(content="https://example.com", preview="https://example.com", classification=models.CLASS_LINK))

    assert "drag_out" not in _all_keys(text_items)
    assert "drag_out" not in _all_keys(link_items)


def test_drag_out_records_metadata_only_receipts_for_image(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    clip = vault.capture_image(_png_bytes(), width=8, height=6, source_app="SnippingTool.exe")
    fake = _fake_shell(vault)
    called: list[str] = []
    monkeypatch.setattr(drag_export, "start_file_drag", lambda path: called.append(path) or 1)

    CacheVaultApp._drag_out_clip(fake, clip.id)

    assert called
    events = [e for e in vault.events.recent(10) if e["clip_id"] == clip.id]
    kinds = [e["event_type"] for e in events]
    assert models.EVENT_ASSET_DRAG_STARTED in kinds
    assert models.EVENT_ASSET_DRAG_EXPORT_PREPARED in kinds
    prepared = next(e for e in events if e["event_type"] == models.EVENT_ASSET_DRAG_EXPORT_PREPARED)
    assert "file_name" in prepared["details"]
    assert "source" in prepared["details"]
    assert "content" not in prepared["details"]
    assert "path" not in prepared["details"]


def test_drag_out_locked_is_blocked_and_does_not_start_drag(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    clip = vault.capture_image(_png_bytes(), width=8, height=6, source_app="SnippingTool.exe")
    events_before = len(vault.events.recent(20))
    guarded: list[str] = []
    fake = _fake_shell(vault, locked=True, guard_calls=guarded)
    monkeypatch.setattr(drag_export, "start_file_drag", lambda path: pytest.fail("drag should not start while locked"))

    CacheVaultApp._drag_out_clip(fake, clip.id)

    assert guarded == ["guarded"]
    events = vault.events.recent(20)
    assert len(events) == events_before + 1
    assert events[0]["event_type"] == models.EVENT_ASSET_DRAG_BLOCKED_LOCKED


def test_drag_out_missing_file_uses_honest_fallback(vault, tmp_path, monkeypatch):
    missing = tmp_path / "missing.txt"
    clip = _clip(content=str(missing), preview=str(missing), classification=models.CLASS_PATH)
    vault.storage.add_clip(clip)
    notices: list[str] = []
    fake = _fake_shell(vault, notices=notices)
    monkeypatch.setattr(drag_export, "start_file_drag", lambda path: pytest.fail("missing file should not drag"))

    CacheVaultApp._drag_out_clip(fake, clip.id)

    assert notices
    assert notices[-1].startswith("File not found.")
    event = next(e for e in vault.events.recent(10) if e["clip_id"] == clip.id)
    assert event["event_type"] == models.EVENT_ASSET_DRAG_MISSING_FILE
    assert "content" not in event["details"]


def test_drag_copy_avoids_forbidden_claims():
    source = "\n".join(
        [
            drag_export.__doc__ or "",
            drag_export.EVENT_ASSET_DRAG_STARTED,
            drag_export.EVENT_ASSET_DRAG_EXPORT_PREPARED,
            drag_export.EVENT_ASSET_DRAG_BLOCKED_LOCKED,
            drag_export.EVENT_ASSET_DRAG_MISSING_FILE,
            drag_export.EVENT_ASSET_DRAG_FALLBACK_USED,
        ],
    )
    assert drag_export.no_forbidden_drag_claims(source)


def _fake_shell(vault, *, locked: bool = False, notices: list[str] | None = None, guard_calls: list[str] | None = None):
    notices = notices if notices is not None else []
    guard_calls = guard_calls if guard_calls is not None else []
    return SimpleNamespace(
        vault=vault,
        _locked=lambda: locked,
        _guard_unlocked=lambda: guard_calls.append("guarded") or False,
        _show_toast=lambda text: notices.append(text),
        _copy_text=lambda text, notice="Copied.": notices.append(notice),
    )


def _all_keys(items):
    out = []
    for item in items:
        out.append(item.key)
        out.extend(_all_keys(item.children))
    return out


def _png_bytes(color: str = "red") -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (8, 6), color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
