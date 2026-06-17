"""Pair Android dialog text builders — testable without Tk."""

from __future__ import annotations

from ..core.lan_ip import advanced_lan_ipv4, recommended_lan_ipv4, list_lan_ipv4
from ..core.mobile.models import DEFAULT_MOBILE_PORT

DEFAULT_DEVICE_NAME = "Android Phone"

PAIRING_PLACEHOLDER = (
    "Tap Generate Fresh Pairing Code, then enter the code in "
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

TOKEN_MASK_CHAR = "•"


def normalize_device_name(name: str) -> str:
    return (name or "").strip() or DEFAULT_DEVICE_NAME


def mask_token(token: str, *, visible: bool = False) -> str:
    if visible or not token:
        return token
    return TOKEN_MASK_CHAR * min(len(token), 32)


def pairing_host_for_copy(ips: list[str] | None = None) -> str:
    host = recommended_lan_ipv4(ips)
    if not host:
        return "(run ipconfig on your PC)"
    return host


def pairing_vault_display_text(
    *,
    device_id: str,
    token: str,
    port: int = DEFAULT_MOBILE_PORT,
    ips: list[str] | None = None,
    show_token: bool = False,
) -> str:
    """Secure-vault style pairing code block (token masked by default)."""
    ips = ips if ips is not None else list_lan_ipv4()
    host = pairing_host_for_copy(ips)
    adv = advanced_lan_ipv4(ips)
    lines = [
        "Pairing Code",
        "",
        f"Device ID: {device_id}",
        f"Token: {mask_token(token, visible=show_token)}",
        "",
        f"Host: {host}",
        f"Port: {port}",
        "",
        "Secure local connection — same Wi-Fi only.",
        "Do not use localhost or 127.0.0.1 from your phone.",
    ]
    if adv:
        lines.extend([
            "",
            "Advanced — other adapters:",
            *[f"  {ip}" for ip in adv],
        ])
    return "\n".join(lines)


def pairing_success_text(
    *,
    device_id: str,
    token: str,
    port: int = DEFAULT_MOBILE_PORT,
    ips: list[str] | None = None,
    show_token: bool = False,
) -> str:
    return pairing_vault_display_text(
        device_id=device_id,
        token=token,
        port=port,
        ips=ips,
        show_token=show_token,
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
        "Cache Vault Mobile — secure local pairing\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Device ID: {device_id}\n"
        f"Token: {token}\n\n"
        "Use your PC Wi-Fi LAN IP from your phone.\n"
        "Do not use localhost or 127.0.0.1.\n"
        "Keep this token private."
    )
