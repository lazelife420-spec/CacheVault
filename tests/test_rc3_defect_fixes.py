"""Unit tests for CacheVault RC3 UI defect fixes."""

from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace
import pytest
import customtkinter as ctk
import tkinter as tk

from cache_vault.core import models
from cache_vault.ui import batch_actions, clip_context
from cache_vault.ui.shell import CacheVaultApp
from cache_vault.ui.vault_screens import VaultScreenHost
from cache_vault import brand


class FakeVault:
    def __init__(self):
        self.storage = FakeStorage()
        self.events = FakeEvents()
        self._exported_zip = None

    def copied_again_image(self, clip_id: str) -> bytes | None:
        return b"fake-png-bytes" if clip_id in self.storage.clips else None

    def export_proof_zip(self, ids: list[str], dest_zip: str):
        self._exported_zip = (ids, dest_zip)
        return SimpleNamespace(success=True)


class FakeStorage:
    def __init__(self):
        self.clips = {}
        self.records = {}
        self.asset_bytes = {}

    def get_clip(self, clip_id: str):
        return self.clips.get(clip_id)

    def load_clip_asset_bytes(self, clip_id: str):
        return self.asset_bytes.get(clip_id)

    def get_asset_record(self, clip_id: str):
        return self.records.get(clip_id)


class FakeEvents:
    def __init__(self):
        self.records = []

    def record(self, event_type: str, clip_id: str | None, payload: dict) -> None:
        self.records.append((event_type, clip_id, payload))


def _app_stub(vault):
    app = object.__new__(CacheVaultApp)
    app.vault = vault
    app._selected_clip_ids = []
    app._clipboard = []
    app._toasts = []
    app._copied_content = []
    app._copied_images = []

    app._guard_unlocked = lambda: True
    app.clipboard_clear = lambda: app._clipboard.clear()
    app.clipboard_append = lambda s: app._clipboard.append(s)
    app._show_toast = lambda msg: app._toasts.append(msg)
    app._monitor = SimpleNamespace(
        note_local_copy=lambda s: app._copied_content.append(s),
        note_local_copy_image=lambda img: app._copied_images.append(img),
    )
    return app


def _clip(clip_id: str, classification: str, content_type: str, title: str | None = None):
    return SimpleNamespace(
        id=clip_id,
        classification=classification,
        content_type=content_type,
        title=title,
        created_at="2026-07-01T12:00:00Z",
    )


# --- 1. Settings Hub Transient/Pulse Tests ---

def test_settings_hub_transient_pulse(monkeypatch):
    """Verify that SettingsHub sets transient and pulses topmost on init."""
    from tk_support import probe_tk_ui
    tk_ok, tk_reason = probe_tk_ui()
    if not tk_ok:
        pytest.skip(tk_reason)

    transient_called_with = []
    attributes_calls = []

    # Monkeypatch both ctk.CTkToplevel and standard tk.Toplevel attributes to cover all wraps
    monkeypatch.setattr(ctk.CTkToplevel, "transient", lambda self, master: transient_called_with.append(master))
    monkeypatch.setattr(ctk.CTkToplevel, "attributes", lambda self, *args: attributes_calls.append(args))
    monkeypatch.setattr(tk.Toplevel, "attributes", lambda self, *args: attributes_calls.append(args))

    from cache_vault.ui.settings_hub import SettingsHub
    from cache_vault.core.settings import Settings
    from cache_vault.modules.registry import build_default_registry

    try:
        root = ctk.CTk()
    except Exception as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")
    root.withdraw()

    try:
        settings = Settings()
        registry = build_default_registry()
        hub = SettingsHub(root, settings, registry, lambda s: None)
        hub.destroy()
    finally:
        root.destroy()

    assert root in transient_called_with
    assert ("-topmost", True) in attributes_calls


def test_settings_hub_single_instance(monkeypatch):
    """Verify that opening SettingsHub multiple times focuses/lifts the existing instance."""
    app = _app_stub(FakeVault())
    
    # Mocking attributes and window existence
    class FakeWindow:
        def __init__(self):
            self._lifted = False
            self._topmost_calls = []
            self._focused = False

        def winfo_exists(self):
            return True

        def lift(self):
            self._lifted = True

        def attributes(self, name, val):
            self._topmost_calls.append((name, val))

        def after(self, ms, callback):
            callback()

        def focus_force(self):
            self._focused = True

    existing = FakeWindow()
    app._settings_hub_instance = existing

    # Trigger open_settings
    app._open_settings()

    assert existing._lifted is True
    assert existing._focused is True
    assert ("-topmost", True) in existing._topmost_calls
    assert ("-topmost", False) in existing._topmost_calls


# --- 2. Screenshot multi-select export actions tests ---

def test_export_screenshots_success(monkeypatch, tmp_path):
    """Verify selected image assets export to folder successfully."""
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE, "Screenshot A")
    vault.storage.clips = {"c1": c1}
    vault.storage.asset_bytes = {"c1": (b"png-bytes-1", "image/png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    dest_dir = tmp_path / "export_dest"
    dest_dir.mkdir()

    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(dest_dir))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    batch_actions.bulk_save_images(app)

    files = list(dest_dir.glob("*.png"))
    assert len(files) == 1
    assert files[0].name.startswith("CacheVault_")
    assert files[0].read_bytes() == b"png-bytes-1"
    assert "Saved 1 screenshots" in app._toasts[0]


def test_export_zip_success(monkeypatch, tmp_path):
    """Verify selected image assets export to a ZIP archive successfully."""
    vault = FakeVault()
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE, "Screenshot A")
    vault.storage.clips = {"c1": c1}
    vault.storage.asset_bytes = {"c1": (b"png-bytes-1", "image/png")}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    dest_zip = tmp_path / "export.zip"
    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    batch_actions.bulk_export_zip(app)

    assert dest_zip.exists()
    with zipfile.ZipFile(dest_zip, "r") as zf:
        names = zf.namelist()
        assert len(names) == 1
        assert zf.read(names[0]) == b"png-bytes-1"
    assert "Exported 1 items to ZIP" in app._toasts[0]


def test_export_actions_empty_selection(monkeypatch):
    """Verify empty selection toasts and doesn't trigger file dialogues or crashes."""
    app = _app_stub(FakeVault())
    app._selected_clip_ids = []

    dialog_opened = False
    
    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: setattr(filedialog, "_opened", True))
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: setattr(filedialog, "_opened", True))

    # Test folder export
    batch_actions.bulk_save_images(app)
    assert not getattr(filedialog, "_opened", False)
    assert "No screenshots to export." in app._toasts[0]
    app._toasts.clear()

    # Test ZIP export
    batch_actions.bulk_export_zip(app)
    assert not getattr(filedialog, "_opened", False)
    assert "No items selected to export to ZIP." in app._toasts[0]
    app._toasts.clear()

    # Test Copy Paths
    batch_actions.bulk_copy_paths(app)
    assert "No screenshots selected to copy paths." in app._toasts[0]


def test_export_actions_missing_assets(monkeypatch, tmp_path):
    """Verify that operations skip missing asset files gracefully and log failures."""
    vault = FakeVault()
    # c1 has missing asset bytes
    c1 = _clip("c1", models.CLASS_IMAGE, models.CONTENT_IMAGE, "Screenshot A")
    vault.storage.clips = {"c1": c1}
    vault.storage.asset_bytes = {"c1": None}

    app = _app_stub(vault)
    app._selected_clip_ids = ["c1"]

    dest_dir = tmp_path / "export_dest"
    dest_dir.mkdir()
    dest_zip = tmp_path / "export.zip"

    from tkinter import filedialog
    monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(dest_dir))
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(dest_zip))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    # Test folder export with missing asset
    batch_actions.bulk_save_images(app)
    assert "Failed to save screenshots. 1 files missing or corrupted." in app._toasts[0]
    assert len(list(dest_dir.glob("*.png"))) == 0
    app._toasts.clear()

    # Test ZIP export with missing asset
    batch_actions.bulk_export_zip(app)
    assert "Failed to export items to ZIP. Missing or corrupted assets." in app._toasts[0]
    assert not dest_zip.exists() # Should delete empty ZIP file


# --- 3. GUI Dispatch mappings verification ---

def test_gui_dispatch_mappings():
    """Verify that visible selected-actions map to real handlers in clip_context."""
    # Create fake app/window and verify dispatch bindings
    app = _app_stub(FakeVault())
    
    # We inspect context menu items mappings in clip_context.py
    # Expected key mappings:
    # "save_pngs" -> bulk_save_images
    # "export_zip" -> bulk_export_zip
    # "copy_paths" -> bulk_copy_paths
    # "save_screenshots" -> bulk_save_images
    
    # Verify clip_context.py has correct mappings
    # (Since we cannot construct tk.Menu without displaying it easily, we check clip_context dispatch dictionary keys)
    # We mock out open_bulk_clip_menu to see what dispatch dictionary it uses.
    import inspect
    import cache_vault.ui.clip_context as cc
    
    # Get local dispatch mappings defined in open_bulk_clip_menu
    source = inspect.getsource(cc.open_bulk_clip_menu)
    assert '"save_pngs": window._bulk_save_images' in source
    assert '"export_zip": window._bulk_export_zip' in source
    assert '"copy_paths": window._bulk_copy_paths' in source
    assert '"save_screenshots": window._bulk_save_images' in source


# --- 4. Command Center selection highlighting ---

def test_command_center_selection_styling(monkeypatch):
    """Verify that Hotkey action card styling correctly applies border and background changes on selection."""
    # Mocking self._callbacks and hotkey structures
    callbacks = {
        "hotkey_action_list": lambda: {
            "rows": [
                {
                    "action": SimpleNamespace(
                        id="h1", name="hk1", hotkey_display="Ctrl+Alt+S",
                        action_type="save_clip", target_label="", scope="global",
                        last_run_at=None, run_count=0, enabled=True,
                    ),
                    "status": "active",
                },
                {
                    "action": SimpleNamespace(
                        id="h2", name="hk2", hotkey_display="Ctrl+Alt+D",
                        action_type="save_clip", target_label="", scope="global",
                        last_run_at=None, run_count=0, enabled=True,
                    ),
                    "status": "active",
                }
            ],
            "win32_available": True,
        },
        "vault": lambda: SimpleNamespace(events=SimpleNamespace(recent=lambda n: [])),
        "get_clip": lambda cid: None,
    }

    # Instantiate VaultScreenHost
    host = object.__new__(VaultScreenHost)
    host._callbacks = callbacks
    host._screens = {}
    host._active = None
    host._receipts_filter_hint = None
    host._selected_hotkey_id = "h1" # Select h1 first

    # Create dummy scrollable frames
    parent = ctk.CTkScrollableFrame(None)
    host._screens["nav_hotkey_actions"] = parent

    # Call _build_hotkey_actions
    host._build_hotkey_actions(parent)

    # Trigger first load/reload
    parent._refresh()

    # Find created cards (CTkFrame children of host._hotkey_list)
    cards = [w for w in host._hotkey_list.winfo_children() if isinstance(w, ctk.CTkFrame)]
    assert len(cards) == 2

    # Card 0 (h1) is selected
    c0 = cards[0]
    assert c0.cget("fg_color") == brand.ROW_SELECTED_BG
    assert c0.cget("border_width") == 1
    assert c0.cget("border_color") == brand.PROOF_TEAL

    # Card 1 (h2) is not selected
    c1 = cards[1]
    assert c1.cget("fg_color") == brand.ROW_BG
    assert c1.cget("border_width") == 0

    # Select h2 now
    host._select_hotkey("h2")
    assert host._selected_hotkey_id == "h2"

    # Find new cards after refresh
    cards2 = [w for w in host._hotkey_list.winfo_children() if isinstance(w, ctk.CTkFrame)]
    assert len(cards2) == 2
    c0_new = cards2[0]
    c1_new = cards2[1]

    # Verify style colors flipped on refresh
    assert c0_new.cget("fg_color") == brand.ROW_BG
    assert c0_new.cget("border_width") == 0

    assert c1_new.cget("fg_color") == brand.ROW_SELECTED_BG
    assert c1_new.cget("border_width") == 1
    assert c1_new.cget("border_color") == brand.PROOF_TEAL
