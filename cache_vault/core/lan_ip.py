"""Best-effort LAN IPv4 helpers for mobile pairing instructions."""

from __future__ import annotations

import socket


def _private_sort_key(ip: str) -> tuple[int, str]:
  """Prefer typical home LAN ranges (192.168, then 10., then 172.16-31)."""
  parts = ip.split(".")
  if len(parts) != 4:
    return (9, ip)
  first, second = int(parts[0]), int(parts[1])
  if first == 192 and second == 168:
    return (0, ip)
  if first == 10:
    return (1, ip)
  if first == 172 and 16 <= second <= 31:
    return (2, ip)
  return (3, ip)


def list_lan_ipv4() -> list[str]:
    """Return unique private-ish IPv4 addresses for this PC."""
    found: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            found.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if addr.startswith("127."):
                continue
            found.add(addr)
    except OSError:
        pass
    return sorted(found, key=_private_sort_key)


def best_lan_ipv4() -> str | None:
    return recommended_lan_ipv4()


def recommended_lan_ipv4(ips: list[str] | None = None) -> str | None:
    """Best Wi-Fi LAN IP for phone pairing (192.168.x / 10.x preferred)."""
    ips = ips if ips is not None else list_lan_ipv4()
    for ip in ips:
        if ip.startswith("192.168.") or ip.startswith("10."):
            return ip
    return ips[0] if ips else None


def advanced_lan_ipv4(ips: list[str] | None = None) -> list[str]:
    """Non-recommended adapters (Hyper-V / 172.x) for Advanced section."""
    ips = ips if ips is not None else list_lan_ipv4()
    rec = recommended_lan_ipv4(ips)
    return [ip for ip in ips if ip != rec]


def lan_ip_guidance(ips: list[str] | None, *, port: int) -> str:
    """Human pairing guidance for the Pair Android dialog."""
    ips = ips if ips is not None else list_lan_ipv4()
    rec = recommended_lan_ipv4(ips)
    if not rec:
        return (
            "Could not detect LAN IP.\n"
            "Use Manual Setup and run ipconfig on your PC.\n"
            f"Port: {port}\n"
            "Do not use localhost or 127.0.0.1 from the phone."
        )
    adv = advanced_lan_ipv4(ips)
    lines = [
        "Recommended connection",
        f"PC found on this Wi-Fi:\n{rec}",
        f"Port: {port}",
        "Same Wi-Fi required.",
        "Do not use localhost or 127.0.0.1 from the phone.",
    ]
    if adv:
        lines.append("Other adapters (Advanced):\n" + "\n".join(f"  • {ip}" for ip in adv))
    return "\n".join(lines)
