"""Screenshot/image asset storage and mobile bridge delivery."""

import json
import os
from io import BytesIO

import pytest
from PIL import Image

from cache_vault.core import image_assets, models
from cache_vault.core.mobile.api import BinaryResponse
from cache_vault.core.mobile.bridge import MobileBridge
from cache_vault.core.mobile.receipts import MobileReceiptLog


def _make_png(width: int = 8, height: int = 6, color: str = "red") -> bytes:
    img = Image.new("RGB", (width, height), color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def assets_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def test_image_asset_metadata_and_sha256(vault, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6, source_app="SnippingTool.exe")
    assert clip is not None
    assert clip.content_type == models.CONTENT_IMAGE
    assert vault.storage.has_clip_asset(clip.id)
    rec = vault.storage.get_asset_record(clip.id)
    assert rec is not None
    assert rec.sha256 == models.bytes_hash(png)
    assert rec.mime_type == "image/png"
    assert rec.size_bytes == len(png)
    assert rec.width == 8
    assert rec.height == 6
    assert (assets_home / "CacheVault" / "assets" / f"{clip.id}.png").is_file()


def test_load_clip_asset_bytes_round_trip(vault, assets_home):
    png = _make_png(4, 4, "blue")
    clip = vault.capture_image(png, width=4, height=4)
    loaded = vault.storage.load_clip_asset_bytes(clip.id)
    assert loaded is not None
    data, mime = loaded
    assert data == png
    assert mime == "image/png"


def test_duplicate_image_not_re_captured(vault, assets_home):
    png = _make_png()
    first = vault.capture_image(png, width=8, height=6)
    second = vault.capture_image(png, width=8, height=6)
    assert first is not None
    assert second is None


def test_asset_persisted_event(vault, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6)
    kinds = {
        e["event_type"]
        for e in vault.events.recent()
        if e["clip_id"] == clip.id
    }
    assert models.EVENT_CAPTURED in kinds
    assert models.EVENT_ASSET_PERSISTED in kinds


def test_hard_delete_removes_asset_file(vault, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6)
    path = assets_home / "CacheVault" / "assets" / f"{clip.id}.png"
    assert path.is_file()
    vault.storage.hard_delete(clip.id)
    assert not path.is_file()
    assert not vault.storage.has_clip_asset(clip.id)


@pytest.fixture
def mobile_bridge(vault, tmp_path):
    log = MobileReceiptLog(tmp_path / "mobile_receipts.json")
    return MobileBridge(vault, receipt_log=log)


def _enable(vault):
    vault.settings.mobile_access_enabled = True


def _pair(bridge, vault, device_id="phone-1", name="Test Pixel"):
    _enable(vault)
    return bridge.pair_device(device_id, name)


def _auth(device_id, token):
    return {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }


def test_paired_device_can_fetch_image_asset(vault, mobile_bridge, assets_home):
    png = _make_png(10, 10)
    clip = vault.capture_image(png, width=10, height=10)
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}/asset", _auth(device.device_id, token))
    assert code == 200
    assert isinstance(body, BinaryResponse)
    assert body.data == png
    assert body.content_type == "image/png"
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["action"] == "get_asset"
    assert rec["result"] == "ok"
    assert rec["clip_id"] == clip.id
    assert "png" not in json.dumps(rec).lower() or rec.get("reason") is None


def test_text_clip_asset_request_returns_asset_not_available(vault, mobile_bridge):
    clip = vault.capture("plain text only")
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}/asset", _auth(device.device_id, token))
    assert code == 404
    assert body["error"] == "asset_not_available"


def test_wrong_clip_id_asset_returns_not_found(vault, mobile_bridge):
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/clips/deadbeef/asset", _auth(device.device_id, token))
    assert code == 404
    assert body["error"] == "not_found"


def test_revoked_device_cannot_fetch_asset(vault, mobile_bridge, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6)
    device, token = _pair(mobile_bridge, vault)
    mobile_bridge.revoke_device(device.device_id)
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}/asset", _auth(device.device_id, token))
    assert code == 401
    rec = mobile_bridge.receipts.recent()[-1]
    assert rec["result"] == "denied"


def test_disabled_bridge_cannot_fetch_asset(vault, mobile_bridge, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6)
    device, token = _pair(mobile_bridge, vault)
    vault.settings.mobile_access_enabled = False
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}/asset", _auth(device.device_id, token))
    assert code == 503
    assert body["error"] == "mobile_access_disabled"


def test_list_marks_image_clip_has_asset(vault, mobile_bridge, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6)
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", "/mobile/v1/clips", _auth(device.device_id, token))
    assert code == 200
    listed = next(c for c in body["clips"] if c["id"] == clip.id)
    assert listed["has_asset"] is True
    assert listed["content_type"] == models.CONTENT_IMAGE


def test_png_dimensions_helper(assets_home):
    png = _make_png(12, 10, "green")
    assert image_assets.png_dimensions(png) == (12, 10)


def test_png_to_dib_roundtrip(assets_home):
    png = _make_png(37, 29, "teal")
    dib = image_assets.png_to_dib(png)
    back, w, h = image_assets.dib_to_png(dib)
    assert (w, h) == (37, 29)
    with Image.open(BytesIO(png)) as a, Image.open(BytesIO(back)) as b:
        assert list(a.convert("RGBA").getdata()) == list(b.getdata())


def test_copied_again_image_returns_bytes(vault, assets_home):
    png = _make_png(6, 6)
    clip = vault.capture_image(png, width=6, height=6)
    again = vault.copied_again_image(clip.id)
    assert again == png
    text = vault.copied_again(clip.id)
    assert text is None


def test_screenshot_filter_count_real(vault, assets_home):
    from cache_vault.core.storage import FILTER_SCREENSHOTS
    assert vault.counts()[FILTER_SCREENSHOTS] == 0
    vault.capture_image(_make_png(), width=4, height=4)
    assert vault.counts()[FILTER_SCREENSHOTS] == 1


def test_asset_storage_ready_on_fresh_db(storage):
    assert storage.asset_storage_ready() is True


def test_missing_asset_file_returns_not_available(vault, mobile_bridge, assets_home):
    png = _make_png()
    clip = vault.capture_image(png, width=8, height=6)
    path = assets_home / "CacheVault" / "assets" / f"{clip.id}.png"
    path.unlink()
    device, token = _pair(mobile_bridge, vault)
    code, body = mobile_bridge.handle(
        "GET", f"/mobile/v1/clips/{clip.id}/asset", _auth(device.device_id, token))
    assert code == 404
    assert body["error"] == "asset_not_available"


def test_export_zip_includes_png_assets(vault, assets_home, tmp_path):
    from cache_vault.core import export
    png = _make_png(5, 5)
    clip = vault.capture_image(png, width=5, height=5)
    zpath = tmp_path / "out.zip"
    export.export_zip(
        [clip], zpath,
        load_asset_bytes=lambda cid: vault.storage.load_clip_asset_bytes(cid)[0],
    )
    import zipfile
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
        assert any(n.startswith("assets/") and n.endswith(".png") for n in names)
        asset_name = next(n for n in names if n.startswith("assets/"))
        assert zf.read(asset_name) == png
