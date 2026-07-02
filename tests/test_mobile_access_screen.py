"""Coverage for issue #7: reachable Mobile Access per-device status labels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import customtkinter as ctk


class _Callbacks(dict):
    def __missing__(self, key):  # any unspecified callback is a no-op
        return lambda *a, **k: None


def _button_texts(widget):
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            texts.append(child.cget("text"))
        texts.extend(_button_texts(child))
    return texts


def _find_button(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = _find_button(child, text)
        if found is not None:
            return found
    return None


def _labels_in(widget):
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            texts.append(child.cget("text"))
        texts.extend(_labels_in(child))
    return texts


def _mobile_report(paired_count=1):
    return {
        "summary": {
            "mobile_enabled": True,
            "mobile_port": 8742,
            "paired_count": paired_count,
        },
        "routes": {},
        "local_ip": "192.168.0.11",
        "mdns_advertising": True,
        "pairing_status": "Ready",
        "last_connection": "2026-07-02 12:00",
    }


def _device_dict(device_id="phone-1", name="Test Pixel", last_seen_at=None, revoked_at=None):
    return {
        "device_id": device_id,
        "device_name": name,
        "created_at": "2026-07-01T00:00:00Z",
        "token_hash": "hash-not-a-real-token",
        "last_seen_at": last_seen_at,
        "revoked_at": revoked_at,
        "app_version": None,
        "platform": None,
    }


class TestMobileAccessScreen:
    """The reachable sidebar Mobile Access screen (vault_screens.py)."""

    def test_paired_devices_button_reachable_alongside_pair_android(self, tk_root):
        from cache_vault.ui.vault_screens import VaultScreenHost

        host = VaultScreenHost(tk_root, callbacks=_Callbacks({
            "mobile_report": lambda: _mobile_report(paired_count=1),
        }))
        host.show("nav_mobile_access")
        tk_root.update_idletasks()

        texts = _button_texts(host)
        assert "Pair Android Device" in texts, (
            "existing Pair Android Device action must not regress"
        )
        assert "Paired Devices" in texts, (
            "Mobile Access must expose a way to see per-device status, "
            "not just the aggregate paired count"
        )

        host.destroy()

    def test_paired_devices_button_shown_even_with_zero_paired(self, tk_root):
        from cache_vault.ui.vault_screens import VaultScreenHost

        host = VaultScreenHost(tk_root, callbacks=_Callbacks({
            "mobile_report": lambda: _mobile_report(paired_count=0),
        }))
        host.show("nav_mobile_access")
        tk_root.update_idletasks()

        assert "Paired Devices" in _button_texts(host)

        host.destroy()

    def test_paired_devices_button_invokes_callback(self, tk_root):
        from cache_vault.ui.vault_screens import VaultScreenHost

        calls = []
        host = VaultScreenHost(tk_root, callbacks=_Callbacks({
            "mobile_report": lambda: _mobile_report(paired_count=1),
            "paired_devices": lambda: calls.append("paired_devices"),
        }))
        host.show("nav_mobile_access")
        tk_root.update_idletasks()

        btn = _find_button(host, "Paired Devices")
        assert btn is not None
        btn.invoke()
        assert calls == ["paired_devices"]

        host.destroy()


class TestPairedDevicesDialog:
    """docs/CACHE_VAULT_ANDROID_RECONNECT_RELEASE_GATE_2026-07-02.md follow-up:
    the dialog already computed correct per-device states; this exercises the
    rendering directly now that it's reachable from the live app."""

    def test_online_device_labeled_and_revocable(self, tk_root):
        from cache_vault.ui.mobile_dialogs import PairedDevicesDialog

        now = datetime.now(timezone.utc).isoformat()
        dlg = PairedDevicesDialog(
            tk_root,
            [_device_dict(device_id="phone-online", name="Pixel Online", last_seen_at=now)],
            on_revoke=lambda i: None,
        )
        dlg.update_idletasks()

        labels = _labels_in(dlg)
        assert any("Pixel Online" in t and "phone-on" in t for t in labels)
        assert any(t.startswith("Status: Online") for t in labels)
        assert "Revoke" in _button_texts(dlg)

        dlg.destroy()

    def test_offline_device_when_last_seen_stale(self, tk_root):
        from cache_vault.ui.mobile_dialogs import PairedDevicesDialog

        stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        dlg = PairedDevicesDialog(
            tk_root,
            [_device_dict(device_id="phone-idle", name="Idle Phone", last_seen_at=stale)],
            on_revoke=lambda i: None,
        )
        dlg.update_idletasks()

        labels = _labels_in(dlg)
        assert any(t.startswith("Status: Offline") for t in labels)

        dlg.destroy()

    def test_never_connected_device_waits_for_approval(self, tk_root):
        from cache_vault.ui.mobile_dialogs import PairedDevicesDialog

        dlg = PairedDevicesDialog(
            tk_root,
            [_device_dict(device_id="phone-new", name="New Phone", last_seen_at=None)],
            on_revoke=lambda i: None,
        )
        dlg.update_idletasks()

        labels = _labels_in(dlg)
        assert any("Last seen: Never" in t for t in labels)
        assert any(t.startswith("Status: Waiting for phone approval") for t in labels)

        dlg.destroy()

    def test_revoked_device_is_visibly_distinct_and_not_re_revocable(self, tk_root):
        from cache_vault.ui.mobile_dialogs import PairedDevicesDialog
        from cache_vault import brand

        dlg = PairedDevicesDialog(
            tk_root,
            [_device_dict(
                device_id="phone-revoked", name="Old Phone",
                revoked_at="2026-07-01T00:00:00Z",
            )],
            on_revoke=lambda i: None,
        )
        dlg.update_idletasks()

        status_labels = [
            child for child in _all_labels(dlg)
            if child.cget("text").startswith("Status: Revoked")
        ]
        assert status_labels, "Revoked status must be shown"
        assert status_labels[0].cget("text_color") == brand.WARNING_RED, (
            "Revoked must render in a visibly distinct color, not the default text color"
        )
        assert "Revoke" not in _button_texts(dlg), (
            "an already-revoked device should not offer Revoke again"
        )

        dlg.destroy()

    def test_missing_device_name_falls_back(self, tk_root):
        from cache_vault.ui.mobile_dialogs import PairedDevicesDialog

        dlg = PairedDevicesDialog(
            tk_root,
            [_device_dict(device_id="phone-noname", name=None)],
            on_revoke=lambda i: None,
        )
        dlg.update_idletasks()

        labels = _labels_in(dlg)
        assert any("Android device" in t for t in labels)

        dlg.destroy()

    def test_empty_state_when_no_devices(self, tk_root):
        from cache_vault.ui.mobile_dialogs import PairedDevicesDialog

        dlg = PairedDevicesDialog(tk_root, [], on_revoke=lambda i: None)
        dlg.update_idletasks()

        labels = _labels_in(dlg)
        assert any("No paired devices yet" in t for t in labels)

        dlg.destroy()


def _all_labels(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            found.append(child)
        found.extend(_all_labels(child))
    return found
