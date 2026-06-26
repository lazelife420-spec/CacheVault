"""Tests for destructive-action confirmations (Phase C.5 Chunk 2)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --- Expire Now / Remove from History confirmation (source-level) ----------

def test_expire_now_has_confirmation_code():
    """_expire_now in shell.py must call askyesno (read from source)."""
    src = (Path(__file__).parents[1] / "cache_vault" / "ui" / "shell.py"
           ).read_text(encoding="utf-8")
    assert 'messagebox.askyesno' in _expire_now_body(src)


def test_remove_from_history_always_confirms():
    """_remove_from_history must call askyesno unconditionally."""
    src = (Path(__file__).parents[1] / "cache_vault" / "ui" / "shell.py"
           ).read_text(encoding="utf-8")
    body = _remove_body(src)
    assert 'messagebox.askyesno' in body, "must contain askyesno call"

    # askyesno must NOT be inside an 'if clip.is_pinned' guard anymore
    # (the old code only asked for pinned; new code asks for all)
    lines = body.split("\n")
    # Find askyesno line
    ask_idx = None
    for i, ln in enumerate(lines):
        if "askyesno" in ln:
            ask_idx = i
            break
    assert ask_idx is not None
    # Check lines before askyesno for is_pinned guard
    for i in range(ask_idx):
        if "is_pinned" in lines[i] and "def " not in lines[i]:
            # The old pattern: if clip.is_pinned: → confirm. New: no guard.
            # Allow is_pinned in comments or the suffix construction
            if lines[i].strip().startswith("#"):
                continue
            if "suffix" in lines[i]:
                continue  # allowed: building "It is a favorite." suffix
            pytest.fail(
                f"askyesno appears conditionally guarded by is_pinned "
                f"at line: {lines[i].strip()}"
            )


def test_expire_now_returns_early_when_cancelled():
    """_expire_now must NOT mutate vault when user cancels."""
    import tkinter.messagebox as mb

    called_vault = False

    class FakeVault:
        def expire_now(self, _id):
            nonlocal called_vault
            called_vault = True

    original = mb.askyesno
    try:
        mb.askyesno = lambda *a, **kw: False

        from cache_vault.ui import shell as shell_mod

        app = shell_mod.CacheVaultApp.__new__(shell_mod.CacheVaultApp)
        app.vault = FakeVault()
        app._preview = MagicMock()
        app.refresh = MagicMock()

        app._expire_now("clip1")
        assert not called_vault
    finally:
        mb.askyesno = original


def test_remove_from_history_returns_early_when_cancelled():
    """_remove_from_history must NOT call vault.remove when user cancels."""
    import tkinter.messagebox as mb

    called_vault = False

    class FakeStorage:
        def get_clip(self, cid):
            return type("C", (), {"id": cid, "is_pinned": False})()

    class FakeVault:
        storage = FakeStorage()

        def remove_from_history(self, _id):
            nonlocal called_vault
            called_vault = True

    original = mb.askyesno
    try:
        mb.askyesno = lambda *a, **kw: False

        from cache_vault.ui import shell as shell_mod

        app = shell_mod.CacheVaultApp.__new__(shell_mod.CacheVaultApp)
        app.vault = FakeVault()
        app._preview = MagicMock()
        app.refresh = MagicMock()

        app._remove_from_history("clip1")
        assert not called_vault
    finally:
        mb.askyesno = original


# --- Mobile Bridge fail-closed ----------------------------------------------

def test_mobile_setting_is_off_by_default():
    """Mobile access defaults to False."""
    from cache_vault.core.settings import Settings
    s = Settings()
    assert s.mobile_access_enabled is False


def test_mobile_bridge_stop_clears_internals():
    """stop() must clear _server, _thread, _listen_host, _listen_port."""
    from cache_vault.core.mobile.bridge import MobileBridge

    vault = MagicMock()
    vault.settings = MagicMock()
    bridge = MobileBridge(vault)
    bridge.stop()
    assert bridge._server is None
    assert bridge._thread is None
    assert bridge._listen_host is None
    assert bridge._listen_port is None


def test_mobile_bridge_not_running_by_default():
    """is_running must be False before any sync/start."""
    from cache_vault.core.mobile.bridge import MobileBridge

    vault = MagicMock()
    vault.settings = MagicMock()
    bridge = MobileBridge(vault)
    assert bridge.is_running is False


def test_mobile_bridge_sync_noop_when_disabled_and_stopped():
    """sync() is a no-op when mobile_access_enabled is False and not running."""
    from cache_vault.core.mobile.bridge import MobileBridge
    from cache_vault.core.settings import Settings

    settings = Settings()
    settings.mobile_access_enabled = False

    vault = MagicMock()
    vault.settings = settings
    bridge = MobileBridge(vault)
    bridge.sync(settings)
    assert bridge.is_running is False


def test_mobile_disable_confirmation_code_present():
    """SettingsDialog._save must confirm when disabling with paired devices."""
    src = (Path(__file__).parents[1] / "cache_vault" / "ui" / "dialogs.py"
           ).read_text(encoding="utf-8")
    assert "paired_devices" in src
    assert "Disable Mobile Access" in src
    assert "askyesno" in src


def test_mobile_promise_is_honest():
    """Brand MOBILE_PROMISE must not claim cloud sync or internet."""
    from cache_vault import brand
    low = brand.MOBILE_PROMISE.lower()
    assert "cloud" not in low
    assert "sync" not in low
    assert "internet" not in low


# --- Export/receipt failure path tests -------------------------------------

def test_create_proof_zip_failure_writes_fail_receipt():
    """On OSError, create_proof_zip must write a failure receipt."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from cache_vault.core import exports

    clips = []
    dest = Path(tempfile.mkdtemp()) / "export.zip"

    with patch("cache_vault.core.exports.tempfile.TemporaryDirectory",
               side_effect=OSError("disk full")):
        with patch("cache_vault.core.exports.write_export_receipt") as mock_wf:
            result = exports.create_proof_zip(clips, dest)

    assert result.success is False
    assert "disk full" in (result.error or "")
    assert mock_wf.called
    payload = mock_wf.call_args[0][0]
    assert payload.get("success") is False
    assert payload.get("action") == "export_zip_created"


def test_export_receipt_no_false_security_claims():
    """write_export_receipt output must not claim notarization/tamper-proof."""
    from cache_vault.core.exports import write_export_receipt
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as d:
        receipts = Path(d) / "receipts"
        receipts.mkdir()
        with patch("cache_vault.core.exports.receipts_dir", return_value=receipts):
            path = write_export_receipt({
                "action": "export_zip_created",
                "success": True,
                "export_id": "abc",
                "timestamp": "2025-01-01T00:00:00",
                "item_count": 3,
                "receipts_included": True,
                "receipt_count": 2,
            })
            if path and path.exists():
                text = path.read_text(encoding="utf-8")
                low = text.lower()
                assert "notariz" not in low
                assert "tamper" not in low
                assert "blockchain" not in low
                assert "immutable" not in low
                assert "military" not in low
                assert "bank-grade" not in low


def test_validate_manifest_catches_missing_document_type():
    """validate_manifest returns errors for invalid manifest."""
    from cache_vault.core.exports import validate_manifest

    errors = validate_manifest({"items": []})
    assert len(errors) > 0
    assert any("document_type" in e for e in errors)


def test_validate_manifest_passes_valid_manifest():
    """validate_manifest returns empty list for valid manifest."""
    from cache_vault.core.exports import validate_manifest

    errors = validate_manifest({
        "document_type": "cache_vault_proof_export",
        "export_id": "abc-123",
        "export_timestamp": "2025-01-01T00:00:00",
        "app_version": "0.1.4",
        "manifest_included": True,
        "sha256sums_included": True,
        "items": [{
            "clip_id": "x",
            "type": "text",
            "safe_id": "default",
            "safe_name": "Default",
            "capture_mode": "manual",
            "auto_saved": False,
            "files": [],
        }],
    })
    assert errors == []


# --- Helpers ---------------------------------------------------------------

def _expire_now_body(src: str) -> str:
    lines = src.split("\n")
    in_method = False
    body: list[str] = []
    for ln in lines:
        if "def _expire_now" in ln:
            in_method = True
            continue
        if in_method:
            if ln.startswith("    def ") or ln.startswith("    # ---"):
                break
            body.append(ln)
    return "\n".join(body)


def _remove_body(src: str) -> str:
    lines = src.split("\n")
    in_method = False
    body: list[str] = []
    for ln in lines:
        if "def _remove_from_history" in ln:
            in_method = True
            continue
        if in_method:
            if ln.startswith("    def ") or ln.startswith("    # ---"):
                break
            body.append(ln)
    return "\n".join(body)
