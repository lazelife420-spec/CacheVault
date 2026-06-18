"""Prepare and start honest file drag-out for asset-backed clips on Windows."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

from . import image_assets, models, pathutil

FORBIDDEN_DRAG_CLAIMS = (
    "cloud sync",
    "encrypted safes",
    "final release",
    "bank-grade",
    "military-grade",
)

EVENT_ASSET_DRAG_STARTED = "asset_drag_started"
EVENT_ASSET_DRAG_EXPORT_PREPARED = "asset_drag_export_prepared"
EVENT_ASSET_DRAG_BLOCKED_LOCKED = "asset_drag_blocked_locked"
EVENT_ASSET_DRAG_MISSING_FILE = "asset_drag_missing_file"
EVENT_ASSET_DRAG_FALLBACK_USED = "asset_drag_fallback_used"


@dataclass(frozen=True)
class DragExport:
    clip_id: str
    drag_kind: str
    file_path: str
    display_name: str
    source: str
    reused_existing: bool = False


def drag_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / "CacheVault" / "drag_out"
    path.mkdir(parents=True, exist_ok=True)
    return path


def no_forbidden_drag_claims(text: str) -> bool:
    low = (text or "").lower()
    return not any(claim in low for claim in FORBIDDEN_DRAG_CLAIMS)


def prepare_drag_export(clip, storage) -> DragExport | None:
    """Return a real file suitable for drag-out, or ``None`` when not honest."""

    if getattr(clip, "content_type", None) == models.CONTENT_IMAGE:
        return _prepare_image_export(clip, storage)
    if getattr(clip, "classification", None) == models.CLASS_PATH:
        return _prepare_path_export(clip)
    return None


def drag_fallback_reason(clip) -> str:
    if getattr(clip, "content_type", None) == models.CONTENT_IMAGE:
        return "Image asset unavailable."
    if getattr(clip, "classification", None) == models.CLASS_PATH:
        if not pathutil.is_local_path(getattr(clip, "content", "") or ""):
            return "This item is not a real local file path."
        return "File not found."
    return "This item does not represent a real file."


def start_file_drag(file_path: str) -> int:
    """Start a native Windows file drag using CF_HDROP."""

    import pythoncom
    import win32con
    import winerror
    from win32com.server.exception import COMException
    from win32com.server.util import NewEnum, wrap

    class _FileDataObject:
        _com_interfaces_ = [pythoncom.IID_IDataObject]
        _public_methods_ = (
            "GetData GetDataHere QueryGetData GetCanonicalFormatEtc SetData "
            "EnumFormatEtc DAdvise DUnadvise EnumDAdvise"
        ).split()

        def __init__(self, payload: bytes):
            self._payload = payload
            self._supported = [
                (win32con.CF_HDROP, None, pythoncom.DVASPECT_CONTENT, -1, pythoncom.TYMED_HGLOBAL),
            ]

        def _query_interface_(self, iid):
            if iid == pythoncom.IID_IEnumFORMATETC:
                return NewEnum(self._supported, iid=iid)
            return None

        def GetData(self, fe):
            cf, _target, aspect, _index, tymed = fe
            if (
                cf == win32con.CF_HDROP
                and aspect & pythoncom.DVASPECT_CONTENT
                and tymed == pythoncom.TYMED_HGLOBAL
            ):
                stg = pythoncom.STGMEDIUM()
                stg.set(pythoncom.TYMED_HGLOBAL, self._payload)
                return stg
            raise COMException(hresult=winerror.E_NOTIMPL)

        def GetDataHere(self, fe):
            raise COMException(hresult=winerror.E_NOTIMPL)

        def QueryGetData(self, fe):
            cf, _target, aspect, _index, tymed = fe
            if cf != win32con.CF_HDROP:
                raise COMException(hresult=winerror.DV_E_FORMATETC)
            if aspect & pythoncom.DVASPECT_CONTENT == 0:
                raise COMException(hresult=winerror.DV_E_DVASPECT)
            if tymed != pythoncom.TYMED_HGLOBAL:
                raise COMException(hresult=winerror.DV_E_TYMED)
            return None

        def GetCanonicalFormatEtc(self, fe):
            raise COMException(hresult=winerror.DATA_S_SAMEFORMATETC)

        def SetData(self, fe, medium):
            raise COMException(hresult=winerror.E_NOTIMPL)

        def EnumFormatEtc(self, direction):
            if direction != pythoncom.DATADIR_GET:
                raise COMException(hresult=winerror.E_NOTIMPL)
            return NewEnum(self._supported, iid=pythoncom.IID_IEnumFORMATETC)

        def DAdvise(self, fe, flags, sink):
            raise COMException(hresult=winerror.E_NOTIMPL)

        def DUnadvise(self, connection):
            raise COMException(hresult=winerror.E_NOTIMPL)

        def EnumDAdvise(self):
            raise COMException(hresult=winerror.E_NOTIMPL)

    class _DropSource:
        _com_interfaces_ = [pythoncom.IID_IDropSource]
        _public_methods_ = ["QueryContinueDrag", "GiveFeedback"]

        def QueryContinueDrag(self, escape_pressed, key_state):
            if escape_pressed:
                return winerror.DRAGDROP_S_CANCEL
            if not (key_state & win32con.MK_LBUTTON):
                return winerror.DRAGDROP_S_DROP
            return pythoncom.S_OK

        def GiveFeedback(self, effect):
            return winerror.DRAGDROP_S_USEDEFAULTCURSORS

    path = str(Path(file_path))
    payload = _hdrop_bytes([path])
    pythoncom.OleInitialize()
    try:
        data_obj = wrap(_FileDataObject(payload), iid=pythoncom.IID_IDataObject, useDispatcher=0)
        drop_source = wrap(_DropSource(), iid=pythoncom.IID_IDropSource, useDispatcher=0)
        return pythoncom.DoDragDrop(data_obj, drop_source, 1)
    finally:
        pythoncom.OleUninitialize()


def _prepare_image_export(clip, storage) -> DragExport | None:
    loaded = storage.load_clip_asset_bytes(getattr(clip, "id", ""))
    if not loaded:
        return None
    png_bytes, _mime = loaded
    target = _preferred_drag_path(clip)
    reused = False
    if target.exists():
        try:
            if target.read_bytes() == png_bytes:
                reused = True
            else:
                target = image_assets.next_available_path(target)
        except Exception:  # noqa: BLE001
            target = image_assets.next_available_path(target)
    if not reused:
        target.write_bytes(png_bytes)
    return DragExport(
        clip_id=getattr(clip, "id", ""),
        drag_kind="image",
        file_path=str(target),
        display_name=target.name,
        source="temp_export",
        reused_existing=reused,
    )


def _prepare_path_export(clip) -> DragExport | None:
    raw = getattr(clip, "content", "") or ""
    if not pathutil.is_local_file(raw):
        return None
    path = str(Path(pathutil.clean_path(raw)))
    return DragExport(
        clip_id=getattr(clip, "id", ""),
        drag_kind="file",
        file_path=path,
        display_name=Path(path).name,
        source="original_file",
        reused_existing=True,
    )


def _preferred_drag_path(clip) -> Path:
    target = drag_dir() / image_assets.make_smart_filename(clip)
    if not target.suffix:
        target = target.with_suffix(".png")
    return target


def _hdrop_bytes(paths: list[str]) -> bytes:
    joined = "\0".join(str(Path(p)) for p in paths) + "\0\0"
    return struct.pack("<IiiII", 20, 0, 0, 0, 1) + joined.encode("utf-16le")
