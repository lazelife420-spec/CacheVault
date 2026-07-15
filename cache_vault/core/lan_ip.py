"""Best-effort LAN IPv4 helpers for mobile pairing instructions."""

from __future__ import annotations

import socket
import threading
import time


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


PENDING_TEXT = "Detecting…"
UNAVAILABLE_TEXT = "Could not detect"


class LanIpResolver:
    """Deadline-bounded, cached, background LAN IPv4 lookup.

    ``socket.getaddrinfo`` has no timeout of its own and can block for far
    longer than any UI should wait on a misbehaving resolver/VPN/DNS setup,
    so resolution always runs on a worker thread — never on the caller's
    thread. ``status_text()`` never blocks: it returns a cached result
    immediately if one exists, "Detecting…" while a lookup is in flight and
    under the deadline, or a fallback string once the deadline has elapsed
    without a result. A finished lookup updates the cache regardless of how
    long it took, so a slow-but-eventually-successful resolution still
    self-corrects the next time the value is read.
    """

    def __init__(self, deadline: float = 1.0) -> None:
        self._deadline = deadline
        self._lock = threading.Lock()
        self._cached_ips: list[str] | None = None
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None
        self._generation = 0

    def status_text(self) -> str:
        ips, resolving, elapsed = self._snapshot()
        if ips is not None:
            rec = recommended_lan_ipv4(ips)
            return rec or "Not detected"
        if resolving and elapsed is not None and elapsed < self._deadline:
            return PENDING_TEXT
        return UNAVAILABLE_TEXT

    def is_pending(self) -> bool:
        ips, resolving, elapsed = self._snapshot()
        if ips is not None:
            return False
        return resolving and elapsed is not None and elapsed < self._deadline

    def reset(self) -> None:
        """Drop the cache and invalidate any in-flight lookup's result."""
        with self._lock:
            self._cached_ips = None
            self._generation += 1

    def _snapshot(self) -> tuple[list[str] | None, bool, float | None]:
        """Returns (cached_ips_or_None, still_resolving, seconds_elapsed).

        Starts a background lookup if no cache exists and none is already
        running — never more than one concurrent lookup per resolver.
        """
        with self._lock:
            if self._cached_ips is not None:
                return self._cached_ips, False, None
            if self._thread is None or not self._thread.is_alive():
                self._generation += 1
                gen = self._generation
                self._started_at = time.monotonic()
                t = threading.Thread(target=self._resolve, args=(gen,), daemon=True)
                self._thread = t
                t.start()
            elapsed = time.monotonic() - self._started_at if self._started_at else None
            return None, True, elapsed

    def _resolve(self, gen: int) -> None:
        try:
            ips = list_lan_ipv4()
        except Exception:
            ips = []
        with self._lock:
            if gen != self._generation:
                return  # superseded by a reset() — discard this late result
            self._cached_ips = ips


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
