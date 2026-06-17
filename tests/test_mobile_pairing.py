"""Pair Android dialog helpers — no GUI required."""

from __future__ import annotations

import io
import sys

import pytest

from cache_vault.core.lan_ip import lan_ip_guidance, list_lan_ipv4
from cache_vault.core.settings import Settings
from cache_vault.ui.pairing_help import (
    DEFAULT_DEVICE_NAME,
    MOBILE_ACCESS_OFF_HINT,
    PAIRING_ERROR,
    pairing_copy_all_text,
    pairing_success_text,
    normalize_device_name,
)


def test_blank_device_name_defaults_to_android_phone():
    assert normalize_device_name("") == DEFAULT_DEVICE_NAME
    assert normalize_device_name("   ") == DEFAULT_DEVICE_NAME
    assert DEFAULT_DEVICE_NAME == "Android Phone"


def test_device_name_trimmed():
    assert normalize_device_name("  Pixel 8  ") == "Pixel 8"


def test_lan_ip_guidance_when_no_ips(monkeypatch):
    monkeypatch.setattr(
        "cache_vault.core.lan_ip.list_lan_ipv4", lambda: []
    )
    text = lan_ip_guidance([], port=8742)
    assert "Could not detect LAN IP" in text
    assert "ipconfig" in text
    assert "127.0.0.1" in text


def test_lan_ip_guidance_single_ip():
    text = lan_ip_guidance(["192.168.0.16"], port=8742)
    assert "Recommended connection" in text
    assert "192.168.0.16" in text
    assert "Port: 8742" in text


def test_lan_ip_guidance_multiple_ips():
    text = lan_ip_guidance(["192.168.0.11", "172.29.64.1"], port=8742)
    assert "192.168.0.11" in text
    assert "172.29.64.1" in text
    assert "Advanced" in text


def test_pairing_success_masks_token_by_default():
    text = pairing_success_text(
        device_id="dev-abc",
        token="tok-secret",
        port=8742,
        ips=["192.168.0.16"],
    )
    assert "dev-abc" in text
    assert "tok-secret" not in text
    assert "8742" in text
    assert "192.168.0.16" in text


def test_copy_all_setup_info_contains_host_port_device_token():
    text = pairing_copy_all_text(
        device_id="dev-xyz",
        token="plain-token-value",
        port=8742,
        ips=["10.0.0.5"],
    )
    assert "Host: 10.0.0.5" in text
    assert "Port: 8742" in text
    assert "Device ID: dev-xyz" in text
    assert "Token: plain-token-value" in text
    assert "localhost" in text


def test_pairing_generate_does_not_write_stdout(monkeypatch):
    """Simulate packaged GUI with stdout/stderr = None."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    # Helpers must not touch stdout/stderr.
    normalize_device_name("")
    pairing_success_text(device_id="a", token="b", ips=["1.2.3.4"])
    assert PAIRING_ERROR
    assert MOBILE_ACCESS_OFF_HINT


def test_mobile_access_default_off():
    s = Settings()
    assert s.mobile_access_enabled is False


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows display")
def test_pair_android_dialog_generate_blank_name(tmp_path, monkeypatch):
    """Integration: dialog generates credentials without lan_hint crash."""
    try:
        import customtkinter as ctk
        ctk.CTk().destroy()
    except Exception:
        pytest.skip("no display")

    import customtkinter as ctk
    from cache_vault.ui.mobile_dialogs import PairAndroidDialog

    root = ctk.CTk()

    def fake_pair(device_id, name):
        assert name == DEFAULT_DEVICE_NAME
        return device_id, "test-token-123"

    dlg = PairAndroidDialog(root, on_pair=fake_pair, port=8742)
    dlg._name.delete(0, "end")
    dlg._generate()
    content = dlg._out.get("1.0", "end")
    assert "Device ID:" in content
    assert "•" in content or "Token:" in content
    assert PAIRING_ERROR not in content
    assert "NameError" not in content
    dlg.destroy()
    root.destroy()


def test_pair_android_dialog_shows_inline_error_on_failure(monkeypatch):
    try:
        import customtkinter as ctk
        ctk.CTk().destroy()
    except Exception:
        pytest.skip("no display")

    import customtkinter as ctk
    from cache_vault.ui.mobile_dialogs import PairAndroidDialog

    root = ctk.CTk()

    def boom(_did, _name):
        raise RuntimeError("pair failed")

    dlg = PairAndroidDialog(root, on_pair=boom, port=8742)
    dlg._generate()
    content = dlg._out.get("1.0", "end")
    assert PAIRING_ERROR.splitlines()[0] in content
    dlg.destroy()
    root.destroy()
