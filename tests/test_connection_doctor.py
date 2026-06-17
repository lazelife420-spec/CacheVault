"""Connection Doctor and pairing failsafe diagnostics."""

from cache_vault.core.lan_ip import advanced_lan_ipv4, recommended_lan_ipv4
from cache_vault.core.mobile.connection_doctor import (
    connection_doctor_report,
    connection_doctor_text,
    format_last_request,
    suggested_fix_for_reason,
)
from cache_vault.ui.pairing_help import mask_token, pairing_copy_all_text, pairing_success_text


def test_recommended_ip_prefers_192_168():
    ips = ["172.29.64.1", "192.168.0.11", "10.0.0.5"]
    assert recommended_lan_ipv4(ips) == "192.168.0.11"


def test_advanced_ips_hide_recommended():
    ips = ["192.168.0.11", "172.29.64.1", "172.28.128.1"]
    assert recommended_lan_ipv4(ips) == "192.168.0.11"
    assert "172.29.64.1" in advanced_lan_ipv4(ips)
    assert "192.168.0.11" not in advanced_lan_ipv4(ips)


def test_token_masked_by_default():
    text = pairing_success_text(
        device_id="dev-1", token="secret-token-value", ips=["192.168.0.11"],
    )
    assert "secret-token-value" not in text
    assert "•" in text
    shown = pairing_success_text(
        device_id="dev-1", token="secret-token-value",
        ips=["192.168.0.11"], show_token=True,
    )
    assert "secret-token-value" in shown


def test_mask_token_helper():
    assert mask_token("abc", visible=False) == "•••"
    assert mask_token("abc", visible=True) == "abc"


def test_copy_all_includes_host_port_device_token():
    text = pairing_copy_all_text(
        device_id="dev-xyz",
        token="plain-token-value",
        port=8742,
        ips=["192.168.0.11"],
    )
    assert "Host: 192.168.0.11" in text
    assert "Port: 8742" in text
    assert "Device ID: dev-xyz" in text
    assert "Token: plain-token-value" in text


def test_suggested_fix_for_invalid_token():
    fix = suggested_fix_for_reason("Invalid device token.")
    assert fix is not None
    assert "Re-pair" in fix


def test_connection_doctor_detects_invalid_token_receipt():
    report = connection_doctor_report(
        mobile_access_enabled=True,
        bridge_listening=True,
        port=8742,
        receipts=[{
            "route": "/mobile/v1/status",
            "result": "denied",
            "reason": "Invalid device token.",
            "device_id": "phone-1",
        }],
    )
    assert report["recommended_ip"] is None or "." in str(report["recommended_ip"])
    assert "invalid device token" in report["last_request"]
    assert report["suggested_fix"] is not None
    assert "pair" in report["suggested_fix"].lower()


def test_connection_doctor_text_includes_bridge_state():
    report = connection_doctor_report(
        mobile_access_enabled=True,
        bridge_listening=True,
        port=8742,
        receipts=[],
    )
    text = connection_doctor_text(report)
    assert "Connection Doctor" in text
    assert "Mobile Access: On" in text
    assert "Bridge: Listening" in text


def test_format_last_request_ok_and_denied():
    assert "ok" in format_last_request({"result": "ok", "action": "status"})
    assert "invalid device token" in format_last_request({
        "result": "denied", "reason": "Invalid device token.",
    })
