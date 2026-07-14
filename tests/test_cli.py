"""Unit and integration tests for the Cache Vault Developer CLI."""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cache_vault import cli
from cache_vault.core import models
from cache_vault.core.mobile import inbox
from cache_vault.core.mobile.models import PairedDevice
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


class MockResponse:
    def __init__(self, status: int, body: dict) -> None:
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> MockResponse:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def test_cli_push_text(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "test-token"))

    payloads_sent = []

    def mock_urlopen(req, timeout=None):
        assert req.get_header("X-device-id") == models.CLI_DEVICE_ID
        assert req.get_header("Authorization") == "Bearer test-token"
        payloads_sent.append(json.loads(req.data.decode("utf-8")))
        return MockResponse(200, {"success": True, "clip_id": "clip-123"})

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(
            sys,
            "argv",
            ["cv", "push", "hello world", "--title", "CLI Title", "--safe", "Dev"],
        )
        with patch("sys.stdout.write"):
            cli.main()

    assert len(payloads_sent) == 1
    assert payloads_sent[0]["content"] == "hello world"
    assert payloads_sent[0]["item_type"] == "text"
    assert payloads_sent[0]["title"] == "CLI Title"
    assert payloads_sent[0]["safe_id"] == "Dev"


def test_cli_push_stdin(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "test-token"))

    payloads_sent = []

    def mock_urlopen(req, timeout=None):
        payloads_sent.append(json.loads(req.data.decode("utf-8")))
        return MockResponse(200, {"success": True, "clip_id": "clip-123"})

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(sys, "argv", ["cv", "push"])
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "piped content"
        monkeypatch.setattr(sys, "stdin", mock_stdin)
        with patch("sys.stdout.write"):
            cli.main()

    assert len(payloads_sent) == 1
    assert payloads_sent[0]["content"] == "piped content"


def test_cli_push_url(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "test-token"))

    payloads_sent = []

    def mock_urlopen(req, timeout=None):
        payloads_sent.append(json.loads(req.data.decode("utf-8")))
        return MockResponse(200, {"success": True, "clip_id": "clip-123"})

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(
            sys,
            "argv",
            ["cv", "push-url", "https://example.com", "--safe", "Research"],
        )
        with patch("sys.stdout.write"):
            cli.main()

    assert len(payloads_sent) == 1
    assert payloads_sent[0]["content"] == "https://example.com"
    assert payloads_sent[0]["item_type"] == "url"
    assert payloads_sent[0]["safe_id"] == "Research"


def test_cli_push_file_text(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "test-token"))

    test_file = tmp_path / "hello.txt"
    test_file.write_text("file text content", encoding="utf-8")

    payloads_sent = []

    def mock_urlopen(req, timeout=None):
        payloads_sent.append(json.loads(req.data.decode("utf-8")))
        return MockResponse(200, {"success": True, "clip_id": "clip-123"})

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(sys, "argv", ["cv", "push-file", str(test_file)])
        with patch("sys.stdout.write"):
            cli.main()

    assert len(payloads_sent) == 1
    assert payloads_sent[0]["content"] == "file text content"
    assert payloads_sent[0]["item_type"] == "text"


def test_cli_push_file_image(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "test-token"))

    test_file = tmp_path / "screenshot.png"
    test_file.write_bytes(b"dummy-png-bytes")

    payloads_sent = []

    def mock_urlopen(req, timeout=None):
        payloads_sent.append(json.loads(req.data.decode("utf-8")))
        return MockResponse(200, {"success": True, "clip_id": "clip-123"})

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(sys, "argv", ["cv", "push-file", str(test_file)])
        with patch("sys.stdout.write"):
            cli.main()

    assert len(payloads_sent) == 1
    assert payloads_sent[0]["item_type"] == "image"
    assert payloads_sent[0]["mime_type"] == "image/png"
    assert payloads_sent[0]["filename"] == "screenshot.png"
    assert payloads_sent[0]["content_b64"] == base64.b64encode(b"dummy-png-bytes").decode("utf-8")


def test_cli_unreachable_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "test-token"))

    def mock_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(sys, "argv", ["cv", "push", "hello"])
        with pytest.raises(SystemExit):
            cli.main()


def test_cli_bad_token(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(cli, "load_bridge_config", lambda: ("127.0.0.1", 8742, True))
    monkeypatch.setattr(cli, "get_auth_token_or_pair", lambda: (models.CLI_DEVICE_ID, "bad-token"))

    def mock_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        monkeypatch.setattr(sys, "argv", ["cv", "push", "hello"])
        with pytest.raises(SystemExit):
            cli.main()


def test_cli_receipt_metadata():
    settings = Settings()
    settings.user_safes.append({"id": "Dev", "name": "Dev", "icon": "💼", "accent": "#008080"})
    storage = VaultStorage(":memory:")
    vault = Vault(storage, settings)

    device = PairedDevice(
        device_id=models.CLI_DEVICE_ID,
        device_name=models.CLI_DEVICE_NAME,
        created_at=models.now_iso(),
        token_hash="dummy-hash",
    )

    payload = {
        "item_type": "text",
        "content": "pushed text",
        "source_app": "CLI",
        "source_device_name": models.CLI_DEVICE_NAME,
        "safe_id": "Dev",
    }

    res = inbox.receive_mobile_send(vault, device, payload)
    assert res.ok is True

    # Check recorded events
    events = vault.events.recent(limit=10)
    assert len(events) == 1
    evt = events[0]
    assert evt["event_type"] == "cli_push"
    assert evt["details"]["source"] == "cli"
    assert evt["details"]["action"] == "cli_push"
    assert evt["details"]["safe_name"] == "Dev"
    assert evt["details"]["transfer_status"] == "completed"


def test_cli_first_time_auto_pairing(tmp_path, monkeypatch):
    settings_dir = tmp_path / "appdata"
    settings_dir.mkdir()
    settings_path = settings_dir / "settings.json"
    
    settings = Settings()
    settings.save(settings_path)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("cache_vault.core.settings.default_settings_path", lambda: settings_path)
    
    # Prove get_auth_token_or_pair creates config file and prints a message
    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(map(str, args))))
    
    device_id, token = cli.get_auth_token_or_pair()
    assert device_id == models.CLI_DEVICE_ID
    assert token != ""
    assert (tmp_path / ".cache_vault_cli.json").exists()
    assert any("First-time auto-pairing completed" in line for line in printed)


def test_cli_reset_auth(tmp_path, monkeypatch):
    settings_dir = tmp_path / "appdata"
    settings_dir.mkdir()
    settings_path = settings_dir / "settings.json"
    
    settings = Settings()
    # Add dummy CLI device
    settings.paired_devices.append({
        "device_id": models.CLI_DEVICE_ID,
        "device_name": models.CLI_DEVICE_NAME,
        "created_at": models.now_iso(),
        "token_hash": "dummy",
    })
    settings.save(settings_path)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("cache_vault.core.settings.default_settings_path", lambda: settings_path)
    
    config_file = tmp_path / ".cache_vault_cli.json"
    config_file.write_text("{}", encoding="utf-8")
    
    # Run reset-auth
    monkeypatch.setattr(sys, "argv", ["cv", "reset-auth"])
    cli.main()
    
    # Prove config is deleted and settings saved
    assert not config_file.exists()
    fresh = Settings.load(settings_path)
    assert not any(d["device_id"] == models.CLI_DEVICE_ID for d in fresh.paired_devices)


def test_cli_bind_host_0_0_0_0_forces_localhost(tmp_path, monkeypatch):
    settings_dir = tmp_path / "appdata"
    settings_dir.mkdir()
    settings_path = settings_dir / "settings.json"
    
    settings = Settings()
    settings.mobile_access_bind_host = "0.0.0.0"
    settings.mobile_access_port = 9000
    settings.mobile_access_enabled = True
    settings.save(settings_path)

    monkeypatch.setattr("cache_vault.core.settings.default_settings_path", lambda: settings_path)
    
    host, port, enabled = cli.load_bridge_config()
    assert host == "127.0.0.1"
    assert port == 9000
    assert enabled is True


def test_cli_receipt_latest_privacy(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    
    receipts_dir = tmp_path / "CacheVault" / "Receipts" / "2026-06-29"
    receipts_dir.mkdir(parents=True)
    
    # Write unrelated private receipt
    unrelated_file = receipts_dir / "clipboard_auto_saved-1.json"
    unrelated_file.write_text(json.dumps({
        "action": "clipboard_auto_saved",
        "clip_id": "clip-unrelated",
        "content": "super secret code",
    }), encoding="utf-8")
    # Change timestamp of unrelated to be very new
    unrelated_file.stat()
    
    # Write CLI receipt (older modified time)
    cli_file = receipts_dir / "cli_push-2.json"
    cli_file.write_text(json.dumps({
        "action": "cli_push",
        "source": "cli",
        "clip_id": "clip-cli",
        "content": "hello world",
    }), encoding="utf-8")
    
    # get_latest_receipt should check and skip unrelated and only return cli receipt
    latest = cli.get_latest_receipt()
    assert latest is not None
    assert latest["clip_id"] == "clip-cli"
    assert latest["action"] == "cli_push"
