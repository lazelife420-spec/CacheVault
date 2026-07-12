"""LAN service discovery for Cache Vault Mobile (mDNS / Bonjour)."""

from __future__ import annotations

import logging
import socket
import threading
from typing import TYPE_CHECKING

from .models import DEFAULT_MOBILE_PORT

if TYPE_CHECKING:
    from zeroconf import Zeroconf

log = logging.getLogger(__name__)

# mDNS service-type label must be <= 15 bytes (RFC 6763); "cachevault-mobile"
# (17) is rejected by zeroconf, so discovery uses the compliant "cachevault".
SERVICE_TYPE = "_cachevault._tcp.local."
SERVICE_NAME = "Cache Vault Desktop._cachevault._tcp.local."


class MobileDiscovery:
    """Advertise the mobile bridge on the local network when enabled."""

    def __init__(self) -> None:
        self._zc: Zeroconf | None = None
        self._info = None
        self._lock = threading.RLock()

    @property
    def is_advertising(self) -> bool:
        return self._info is not None

    def verify_advertising(self) -> bool:
        """Confirm the mDNS service is registered (best-effort check)."""
        with self._lock:
            return self._info is not None and self._zc is not None

    def start(self, port: int, *, pc_name: str | None = None) -> bool:
        """Register ``_cachevault._tcp``; return False if unavailable."""
        with self._lock:
            self.stop()
            try:
                from zeroconf import ServiceInfo, Zeroconf
            except ImportError:
                log.debug("zeroconf not installed; LAN discovery disabled")
                return False

            label = (pc_name or socket.gethostname() or "PC").strip()
            props = {
                b"product": b"Cache Vault Desktop",
                b"pc_name": label.encode("utf-8", errors="replace"),
            }
            try:
                addrs = _lan_addresses()
                if not addrs:
                    addrs = [socket.inet_aton("127.0.0.1")]
                self._zc = Zeroconf()
                self._info = ServiceInfo(
                    SERVICE_TYPE,
                    SERVICE_NAME,
                    addresses=addrs,
                    port=int(port or DEFAULT_MOBILE_PORT),
                    properties=props,
                )
                self._zc.register_service(self._info)
                return True
            except Exception:
                log.exception("Failed to register mobile discovery service")
                self.stop()
                return False

    def stop(self) -> None:
        with self._lock:
            if self._zc is not None and self._info is not None:
                try:
                    self._zc.unregister_service(self._info)
                except Exception:
                    pass
            if self._zc is not None:
                try:
                    self._zc.close()
                except Exception:
                    pass
            self._zc = None
            self._info = None


def guess_lan_ip() -> str | None:
    """Best-effort LAN IPv4 for pairing instructions (not logged)."""
    from ..lan_ip import best_lan_ipv4
    return best_lan_ipv4()


def _lan_addresses() -> list[bytes]:
    """IPv4 address(es) for mDNS advertisement — the reachable Wi-Fi LAN IP only.

    Advertise just the recommended Wi-Fi LAN IP (192.168.x / 10.x) when one
    exists. mDNS does not preserve A-record order and Android's ``NsdManager``
    resolves a single host, so advertising every adapter lets the phone resolve
    the desktop to an unreachable Hyper-V / WSL virtual adapter (e.g. 172.x) and
    silently fail — surfacing as "No Cache Vault PC found". A single reachable
    address is unambiguous. Only when no home-LAN IP exists do we fall back to
    advertising all detected addresses.
    """
    from ..lan_ip import list_lan_ipv4, recommended_lan_ipv4

    ips = list_lan_ipv4()
    if not ips:
        return []
    recommended = recommended_lan_ipv4(ips)
    if recommended and (recommended.startswith("192.168.") or recommended.startswith("10.")):
        chosen = [recommended]
    else:
        chosen = ips
    out: list[bytes] = []
    for addr in chosen:
        try:
            out.append(socket.inet_aton(addr))
        except OSError:
            continue
    return out
