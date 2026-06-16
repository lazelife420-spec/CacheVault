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

SERVICE_TYPE = "_cachevault-mobile._tcp.local."
SERVICE_NAME = "Cache Vault Desktop._cachevault-mobile._tcp.local."


class MobileDiscovery:
    """Advertise the mobile bridge on the local network when enabled."""

    def __init__(self) -> None:
        self._zc: Zeroconf | None = None
        self._info = None
        self._lock = threading.Lock()

    @property
    def is_advertising(self) -> bool:
        return self._info is not None

    def start(self, port: int, *, pc_name: str | None = None) -> bool:
        """Register ``_cachevault-mobile._tcp``; return False if unavailable."""
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
    from .lan_ip import best_lan_ipv4
    return best_lan_ipv4()


def _lan_addresses() -> list[bytes]:
    """Best-effort IPv4 addresses for mDNS advertisement."""
    out: list[bytes] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if addr.startswith("127."):
                continue
            out.append(socket.inet_aton(addr))
    except OSError:
        pass
    return out
