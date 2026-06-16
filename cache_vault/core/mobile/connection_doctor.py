"""Mobile Access connection diagnostics — pairing failsafe helpers."""

from __future__ import annotations

from ..lan_ip import advanced_lan_ipv4, recommended_lan_ipv4
from .models import DEFAULT_BIND_HOST, DEFAULT_MOBILE_PORT


def suggested_fix_for_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    low = reason.lower()
    if "invalid device token" in low:
        return "Re-pair this phone with a fresh token."
    if "revoked" in low:
        return "Pair again from your PC — this device was revoked."
    if "mobile_access_disabled" in low or "mobile access is disabled" in low:
        return "Enable Mobile Access in Cache Vault Settings and Save."
    if "unpaired" in low:
        return "Generate a fresh pairing code on your PC."
    if "pairing required" in low:
        return "Enter Device ID and token from your PC pairing dialog."
    return None


def format_last_request(receipt: dict | None) -> str:
    if receipt is None:
        return "No phone requests yet"
    result = receipt.get("result") or "?"
    reason = receipt.get("reason") or ""
    route = receipt.get("route") or ""
    if result == "ok":
        action = receipt.get("action") or "request"
        return f"ok — {action}"
    if result == "denied" and reason:
        short = reason.replace("Invalid device token.", "invalid device token")
        short = short.replace("Device revoked.", "revoked device")
        return f"denied — {short}"
    if reason:
        return f"{result} — {reason}"
    return str(result)


def connection_doctor_report(
    *,
    mobile_access_enabled: bool,
    bridge_listening: bool,
    port: int = DEFAULT_MOBILE_PORT,
    bind_host: str = DEFAULT_BIND_HOST,
    receipts: list[dict] | None = None,
) -> dict:
    """Structured Connection Doctor state for Settings / Pair dialogs."""
    receipts = receipts or []
    latest = receipts[-1] if receipts else None
    recommended = recommended_lan_ipv4()
    advanced = advanced_lan_ipv4()
    last_line = format_last_request(latest)
    suggested = None
    if latest:
        suggested = latest.get("suggested_fix") or suggested_fix_for_reason(
            latest.get("reason")
        )
    if latest and latest.get("result") == "denied":
        reason = (latest.get("reason") or "").lower()
        if "invalid device token" in reason:
            suggested = (
                "Your phone reached this PC, but the pairing token did not match.\n"
                "Disconnect on the phone, then generate a fresh pairing code."
            )

    return {
        "mobile_access": "On" if mobile_access_enabled else "Off",
        "bridge": "Listening" if bridge_listening else "Not listening",
        "port": port,
        "bind_host": bind_host or DEFAULT_BIND_HOST,
        "recommended_ip": recommended,
        "advanced_ips": advanced,
        "last_request": last_line,
        "suggested_fix": suggested,
        "latest_receipt": latest,
    }


def connection_doctor_text(report: dict) -> str:
    """Plain-text Connection Doctor block for dialogs."""
    lines = [
        "Connection Doctor",
        "",
        f"Mobile Access: {report['mobile_access']}",
        f"Bridge: {report['bridge']}",
        f"Port: {report['port']}",
    ]
    if report.get("recommended_ip"):
        lines.append(f"Recommended IP: {report['recommended_ip']}")
    lines.append(f"Last phone request: {report['last_request']}")
    if report.get("suggested_fix"):
        lines.append(f"Suggested fix: {report['suggested_fix']}")
    return "\n".join(lines)
