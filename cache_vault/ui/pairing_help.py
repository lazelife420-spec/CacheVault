"""Pair Android dialog text builders — testable without Tk."""

from __future__ import annotations

from ..core.lan_ip import best_lan_ipv4, list_lan_ipv4
from ..core.mobile.models import DEFAULT_MOBILE_PORT

DEFAULT_DEVICE_NAME = "Android Phone"

PAIRING_PLACEHOLDER = (
    "Generate pairing credentials, then enter them in "
    "Cache Vault Mobile on your phone."
)

PAIRING_ERROR = (
    "Pairing credentials could not be generated.\n"
    "Check Mobile Access settings and try again."
)

MOBILE_ACCESS_SAVE_HINT = (
    "Save settings to enable Mobile Access before pairing."
)

MOBILE_ACCESS_OFF_HINT = (
    "Turn on Enable Mobile Access and save settings before pairing."
)


def normalize_device_name(name: str) -> str:
    return (name or "").strip() or DEFAULT_DEVICE_NAME


def pairing_host_for_copy(ips: list[str] | None = None) -> str:
    ips = ips if ips is not None else list_lan_ipv4()
    if not ips:
        return "(run ipconfig on your PC)"
    return ips[0]


def pairing_success_text(
    *,
    device_id: str,
    token: str,
    port: int = DEFAULT_MOBILE_PORT,
    ips: list[str] | None = None,
) -> str:
    host = pairing_host_for_copy(ips)
    host_lines = (
        f"Host: {host}"
        if host != "(run ipconfig on your PC)"
        else "Host: (run ipconfig on your PC for your Wi-Fi IPv4)"
    )
    if ips and len(ips) > 1:
        host_lines += "\n" + "\n".join(f"  also: {ip}" for ip in ips[1:])
    return (
        "Cache Vault Mobile pairing\n\n"
        f"{host_lines}\n"
        f"Port: {port}\n"
        f"Device ID: {device_id}\n"
        f"Token: {token}\n\n"
        "Use the same Wi-Fi as your PC.\n"
        "Do not use localhost or 127.0.0.1 from your phone."
    )


def pairing_copy_all_text(
    *,
    device_id: str,
    token: str,
    port: int = DEFAULT_MOBILE_PORT,
    ips: list[str] | None = None,
) -> str:
    host = pairing_host_for_copy(ips)
    return (
        "Cache Vault Mobile pairing\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Device ID: {device_id}\n"
        f"Token: {token}\n\n"
        "Use your PC LAN IP from your phone.\n"
        "Do not use localhost or 127.0.0.1.\n"
        "Keep this token private."
    )
